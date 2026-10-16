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
