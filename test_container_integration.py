"""Opt-in real runtime acceptance. Never touches unlabeled application resources."""
import os
import subprocess
import unittest
from nexus_runtime_adapters import create_container,stop_container
@unittest.skipUnless(os.getenv('NEXUS_CERTIFICATION_IMAGE'), 'isolated runtime/image not configured')
class ContainerIntegrationTests(unittest.TestCase):
    def test_create_duplicate_stop_readback(self):
        runtime=os.environ['NEXUS_CONTAINER_RUNTIME']; key='integration-'+str(os.getpid());name='nexus-cert-'+key
        try:
            first=create_container({'image':os.environ['NEXUS_CERTIFICATION_IMAGE'],'request_id':key})
            second=create_container({'image':os.environ['NEXUS_CERTIFICATION_IMAGE'],'request_id':key})
            self.assertTrue(first['verified']);self.assertTrue(second['duplicate'])
            self.assertEqual(first['container']['id'],second['container']['id'])
            self.assertTrue(stop_container(name)['verified'])
        finally:
            subprocess.run([runtime,'rm','--force',name],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)

@unittest.skipUnless(os.getenv('NEXUS_CERTIFICATION_IMAGE'), 'isolated runtime/image not configured')
class ContainerRollbackTests(unittest.TestCase):
    def test_failed_start_removes_real_fixture_and_verifies_absence(self):
        from unittest.mock import patch
        from nexus_runtime_adapters import RuntimeErrorSafe,list_containers
        runtime=os.environ['NEXUS_CONTAINER_RUNTIME'];key='rollback-'+str(os.getpid());name='nexus-cert-'+key
        original=subprocess.run
        def fail_start(args,**kwargs):
            if args[:2]==[runtime,'start']: raise subprocess.CalledProcessError(1,args)
            return original(args,**kwargs)
        try:
            with patch('nexus_runtime_adapters.subprocess.run',side_effect=fail_start):
                with self.assertRaisesRegex(RuntimeErrorSafe,'cleanup_verified'):
                    create_container({'image':os.environ['NEXUS_CERTIFICATION_IMAGE'],'request_id':key})
            self.assertTrue(list_containers()['verified'])
        finally:
            original([runtime,'rm','--force',name],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)

@unittest.skipUnless(os.getenv('NEXUS_CERTIFICATION_IMAGE'), 'isolated runtime/image not configured')
class ContainerFailureAcceptanceTests(unittest.TestCase):
    def setUp(self):
        import secrets
        self.runtime=os.environ['NEXUS_CONTAINER_RUNTIME']
        self.key='matrix-'+secrets.token_hex(6)
        self.name='nexus-cert-'+self.key
        self.config={'image':os.environ['NEXUS_CERTIFICATION_IMAGE'],'request_id':self.key}
        self.original=subprocess.run
        self.addCleanup(lambda:self.original([self.runtime,'rm','--force',self.name],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20))
    def inspect(self,identity):
        import json
        return json.loads(self.original([self.runtime,'inspect',identity],check=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=20).stdout)[0]
    def test_concurrent_duplicate_requests_converge(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:create_container(self.config),range(4)))
        self.assertTrue(all(r['verified'] for r in results))
        self.assertEqual(len({r['container']['id'] for r in results}),1)
        self.assertEqual(sum(not r['duplicate'] for r in results),1)
        self.assertTrue(self.inspect(results[0]['container']['id'])['State']['Running'])
        self.assertTrue(stop_container(self.name)['verified'])
    def test_start_timeout_rolls_back_real_started_container(self):
        from unittest.mock import patch
        from nexus_runtime_adapters import RuntimeErrorSafe,list_containers
        captured=[]
        def lose_ack(args,**kwargs):
            result=self.original(args,**kwargs)
            if args[:2]==[self.runtime,'start']:
                captured.append(args[-1])
                raise subprocess.TimeoutExpired(args,20)
            return result
        with patch('nexus_runtime_adapters.subprocess.run',side_effect=lose_ack):
            with self.assertRaisesRegex(RuntimeErrorSafe,'cleanup_verified'):
                create_container(self.config)
        self.assertEqual(len(captured),1)
        self.assertTrue(all(not captured[0].startswith(x['id']) for x in list_containers()['containers']))
    def test_cleanup_failure_is_unconfirmed_and_resource_remains(self):
        from unittest.mock import patch
        from nexus_runtime_adapters import RuntimeErrorSafe
        def deny(args,**kwargs):
            if args[:2] in ([self.runtime,'start'],[self.runtime,'rm']):
                raise subprocess.CalledProcessError(1,args)
            return self.original(args,**kwargs)
        with patch('nexus_runtime_adapters.subprocess.run',side_effect=deny):
            with self.assertRaisesRegex(RuntimeErrorSafe,'cleanup_unconfirmed'):
                create_container(self.config)
        state=self.inspect(self.name)
        self.assertFalse(state['State']['Running'])
        self.assertEqual(state['Config']['Labels']['nexus.scope'],'certification')
    def test_lost_stop_ack_fails_closed_then_readback_recovers(self):
        from unittest.mock import patch
        from nexus_runtime_adapters import RuntimeErrorSafe
        created=create_container(self.config)
        def lose_ack(args,**kwargs):
            result=self.original(args,**kwargs)
            if args[:2]==[self.runtime,'stop']:
                raise subprocess.TimeoutExpired(args,20)
            return result
        with patch('nexus_runtime_adapters.subprocess.run',side_effect=lose_ack):
            with self.assertRaisesRegex(RuntimeErrorSafe,'stop_outcome_unconfirmed'):
                stop_container(self.name)
        self.assertFalse(self.inspect(created['container']['id'])['State']['Running'])
        self.assertTrue(stop_container(self.name)['verified'])
