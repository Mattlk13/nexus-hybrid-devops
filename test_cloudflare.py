import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib import error
from nexus_cloudflare import CloudflareStagingAdapter, RuntimeErrorSafe

A='11111111-1111-4111-8111-111111111111'
B='22222222-2222-4222-8222-222222222222'
D='33333333-3333-4333-8333-333333333333'
E='44444444-4444-4444-8444-444444444444'

def deployment(version=A,identifier=D,message='initial'):
    return {'id':identifier,'versions':[{'version_id':version,'percentage':100}], 'annotations':{'workers/message':message}}

class StagingCloudflareTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        (Path(self.temp.name)/'.nexus-cloudflare-staging').touch()
        env={'NEXUS_CLOUDFLARE_TOKEN':'fixture-secret','NEXUS_CLOUDFLARE_ACCOUNT':'a'*32,
             'NEXUS_CLOUDFLARE_WORKER':'nexus-fixture-staging','NEXUS_CLOUDFLARE_RECEIPTS':self.temp.name}
        self.env=patch.dict(os.environ,env);self.env.start();self.addCleanup(self.env.stop)
        self.adapter=CloudflareStagingAdapter();self.current=deployment();self.writes=[]
        def api(method,path,body=None):
            if method=='POST':
                self.writes.append(body)
                self.current=deployment(body['versions'][0]['version_id'],E if len(self.writes)==1 else D,body['annotations']['workers/message'])
                return self.current
            return {'deployments':[self.current]}
        self.api=patch.object(self.adapter,'_api',side_effect=api);self.api.start();self.addCleanup(self.api.stop)

    def test_deploy_duplicate_and_exact_restore(self):
        result=self.adapter.deploy('nexus-fixture-staging','staging',B)
        self.assertTrue(result['verified']);self.assertEqual(len(self.writes),1)
        self.assertTrue(self.adapter.deploy('nexus-fixture-staging','staging',B)['duplicate'])
        self.assertEqual(len(self.writes),1)
        self.assertEqual(self.adapter.rollback('nexus-fixture-staging','staging')['version'],A)
        self.assertTrue(self.adapter.rollback('nexus-fixture-staging','staging')['duplicate'])
        self.assertEqual(len(self.writes),2)

    def test_no_rollback_of_another_actor(self):
        self.adapter.deploy('nexus-fixture-staging','staging',B)
        self.current=deployment(B,D,'another actor')
        with self.assertRaisesRegex(RuntimeErrorSafe,'ownership_unconfirmed'):
            self.adapter.rollback('nexus-fixture-staging','staging')
        self.assertEqual(len(self.writes),1)

    def test_timeout_stays_pending_and_is_not_retried(self):
        def api(method,path,body=None):
            if method=='POST': raise RuntimeErrorSafe('cloudflare_request_state_unconfirmed')
            return {'deployments':[deployment()]}
        with patch.object(self.adapter,'_api',side_effect=api) as calls:
            with self.assertRaisesRegex(RuntimeErrorSafe,'state_unconfirmed'): self.adapter.deploy('nexus-fixture-staging','staging',B)
            with self.assertRaisesRegex(RuntimeErrorSafe,'pending_outcome'): self.adapter.deploy('nexus-fixture-staging','staging',B)
            self.assertEqual(sum(c.args[0]=='POST' for c in calls.call_args_list),1)
        self.assertEqual(json.loads(self.adapter.receipt.read_text())['status'],'pending')

    def test_lost_acknowledgement_reconciles_before_rollback(self):
        original=self.adapter._write_version
        def lost_ack(version,message):
            original(version,message)
            raise RuntimeErrorSafe('cloudflare_request_state_unconfirmed')
        with patch.object(self.adapter,'_write_version',side_effect=lost_ack):
            with self.assertRaisesRegex(RuntimeErrorSafe,'state_unconfirmed'):
                self.adapter.deploy('nexus-fixture-staging','staging',B)
        self.assertEqual(json.loads(self.adapter.receipt.read_text())['status'],'pending')
        self.assertEqual(self.adapter.rollback('nexus-fixture-staging','staging')['version'],A)
        self.assertEqual(len(self.writes),2)

    def test_production_and_other_worker_rejected(self):
        for worker,env in [('nexus-fixture-staging','production'),('other-staging','staging')]:
            with self.assertRaisesRegex(RuntimeErrorSafe,'scope_required'): self.adapter.deploy(worker,env,B)
        self.assertEqual(self.writes,[])

    def test_unowned_rollback_and_active_lock_rejected(self):
        with self.assertRaisesRegex(RuntimeErrorSafe,'owned_receipt'): self.adapter.rollback('nexus-fixture-staging','staging')
        (Path(self.temp.name)/'nexus-fixture-staging.lock').touch()
        with self.assertRaisesRegex(RuntimeErrorSafe,'operation_in_progress'): self.adapter.deploy('nexus-fixture-staging','staging',B)

    def test_gradual_or_malformed_current_state_rejected(self):
        self.current['versions'][0]['percentage']=50
        with self.assertRaisesRegex(RuntimeErrorSafe,'single_version_required'): self.adapter.deploy('nexus-fixture-staging','staging',B)
        self.assertEqual(self.writes,[])

    def test_transport_errors_are_redacted(self):
        # Use the real transport method, not this fixture's deployment simulator.
        for failure,expected in [(error.HTTPError('https://example.invalid',401,'fixture-secret',{},None),'authentication_failed'),
                                 (error.HTTPError('https://example.invalid',403,'fixture-secret',{},None),'permission_denied'),
                                 (TimeoutError('fixture-secret'),'state_unconfirmed')]:
            with patch('nexus_cloudflare.request.build_opener') as opener:
                opener.return_value.open.side_effect=failure
                with self.assertRaisesRegex(RuntimeErrorSafe,expected) as caught:
                    CloudflareStagingAdapter._api(self.adapter,'GET','/deployments')
                self.assertNotIn('fixture-secret',str(caught.exception))
