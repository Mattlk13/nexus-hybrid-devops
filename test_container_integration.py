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
