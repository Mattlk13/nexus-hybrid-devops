"""Explicit staging-only live gate. Deploy old uploaded version, restore baseline."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
from nexus_cloudflare import CloudflareStagingAdapter, RuntimeErrorSafe
from nexus_hybrid_devops import HybridDevOpsEngine

@unittest.skipUnless(os.getenv('NEXUS_CLOUDFLARE_LIVE_TESTS')=='1','isolated Cloudflare staging gate not enabled')
class LiveStagingDeploymentTests(unittest.TestCase):
    def test_existing_version_deploy_duplicate_and_rollback(self):
        self.assertEqual(os.environ.get('NEXUS_CLOUDFLARE_WORKER'),'nexus2-staging')
        evidence={'environment':'staging','worker':'nexus2-staging','production':'HOLD'}
        evidence_path=Path(os.environ['NEXUS_CLOUDFLARE_EVIDENCE'])
        def public_source():
            # Token is never attached to a public application request.
            with tempfile.TemporaryDirectory(prefix='nexus-public-readback-') as temp:
                target=Path(temp)/'app.js'
                env={k:v for k,v in os.environ.items() if k in ('PATH','SystemRoot','HTTPS_PROXY','HTTP_PROXY','NO_PROXY','SSL_CERT_FILE','CURL_CA_BUNDLE')}
                result=subprocess.run(['curl','--disable','--proto','=https','--max-time','15','--fail','--silent','--show-error','--compressed',
                    '--header','Cache-Control: no-cache','--output',str(target),
                    'https://nexus2-staging.hm2krebsmatthewl.workers.dev/app.js'],
                    env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,check=False)
                self.assertEqual(result.returncode,0,'public staging asset HTTP readback failed')
                self.assertLessEqual(target.stat().st_size,1048576)
                return target.read_bytes()
        def await_hash(expected,equal=True):
            for attempt in range(10):
                actual=hashlib.sha256(public_source()).hexdigest()
                if (actual==expected)==equal: return actual
                if attempt<9: time.sleep(1)
            self.fail('public staging asset does not confirm requested deployment')
        with tempfile.TemporaryDirectory(prefix='nexus-cf-staging-') as root:
            (Path(root)/'.nexus-cloudflare-staging').touch()
            with patch.dict(os.environ,{'NEXUS_CLOUDFLARE_RECEIPTS':root}):
                adapter=CloudflareStagingAdapter();engine=HybridDevOpsEngine()
                baseline=adapter.history('nexus2-staging','staging')
                before=hashlib.sha256(public_source()).hexdigest()
                expected=hashlib.sha256(Path(os.environ['NEXUS_STAGING_EXPECTED_APP_JS']).read_bytes()).hexdigest()
                self.assertEqual(before,expected,'baseline must match checked-out staging application')
                deployments=adapter._api('GET','/deployments')['deployments']
                candidates=[d['versions'][0]['version_id'] for d in deployments if len(d.get('versions',[]))==1 and d['versions'][0].get('percentage')==100 and d['versions'][0]['version_id']!=baseline['current_version']]
                target=os.environ['NEXUS_CLOUDFLARE_TEST_VERSION']
                self.assertIn(target,candidates,'explicit test version must exist in this staging Worker history')
                with patch.dict(os.environ,{'NEXUS_CLOUDFLARE_TOKEN':'invalid-nexus-certification-token'}):
                    with self.assertRaises(RuntimeErrorSafe): CloudflareStagingAdapter().history('nexus2-staging','staging')
                evidence['invalidCredentialDenied']=True
                try:
                    result=asyncio.run(engine.deploy_service('nexus2-staging','staging',target))
                    self.assertTrue(result['success'],result)
                    self.assertTrue(result['created'])
                    evidence['deployment']=result
                    evidence['changedAssetSha256']=await_hash(before,equal=False)
                    self.assertEqual(adapter.history('nexus2-staging','staging')['current_version'],target)
                    duplicate=asyncio.run(engine.deploy_service('nexus2-staging','staging',target))
                    self.assertTrue(duplicate['duplicate'],duplicate)
                    self.assertEqual(adapter.history('nexus2-staging','staging')['current_deployment'],result['deployment_id'])
                    evidence['duplicateWithoutMutation']=True
                finally:
                    # The adapter will refuse to overwrite a deployment it does not own.
                    if adapter.receipt.exists():
                        restored=asyncio.run(engine.rollback_deployment('nexus2-staging','staging'))
                        evidence['rollback']=restored
                        evidence_path.write_text(json.dumps(evidence,indent=2))
                        self.assertTrue(restored['success'],restored)
                        self.assertEqual(adapter.history('nexus2-staging','staging')['current_version'],baseline['current_version'])
                        self.assertEqual(await_hash(before),before)
                        self.assertTrue(asyncio.run(engine.rollback_deployment('nexus2-staging','staging'))['duplicate'])
                        evidence['restoredAssetSha256']=before
                        evidence['providerVersionRestored']=True
                        evidence_path.write_text(json.dumps(evidence,indent=2))
