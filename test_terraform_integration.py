import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from nexus_terraform import TerraformAdapter,RuntimeErrorSafe
@unittest.skipUnless(shutil.which('terraform'),'Terraform executable unavailable')
class RealTerraformTests(unittest.TestCase):
    def test_create_duplicate_destroy_real_state(self):
        with tempfile.TemporaryDirectory(prefix='nexus-cert-') as root,patch.dict(os.environ,{'NEXUS_TERRAFORM_CERTIFICATION_ROOT':root,'NEXUS_TERRAFORM_APPLY_ENABLED':'1'}):
            path=Path(root);(path/'.nexus-certification').touch()
            (path/'main.tf.json').write_text(json.dumps({'resource':{'terraform_data':{'fixture':{'input':'isolated-certification'}}}}))
            adapter=TerraformAdapter();adapter.run('init','-input=false')
            receipt=adapter.apply('fixture')['receipt']
            self.assertTrue(adapter.apply('fixture')['duplicate'])
            with self.assertRaisesRegex(RuntimeErrorSafe,'production_operation_forbidden'): adapter.apply('other','production')
            self.assertTrue(adapter.destroy(receipt)['verified']);self.assertEqual(adapter.state(),[])
