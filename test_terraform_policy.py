import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from nexus_terraform import TerraformAdapter,RuntimeErrorSafe
class TerraformPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);(root/'.nexus-certification').touch()
        env=patch.dict(os.environ,{'NEXUS_TERRAFORM_CERTIFICATION_ROOT':str(root),'NEXUS_TERRAFORM_APPLY_ENABLED':'1'});env.start();self.addCleanup(env.stop)
        self.adapter=TerraformAdapter()
    def test_production_is_always_rejected(self):
        with self.assertRaisesRegex(RuntimeErrorSafe,'production_operation_forbidden'): self.adapter.apply('test','production')
    def test_existing_workspace_is_never_applied(self):
        with patch.object(self.adapter,'state',return_value=[{'address':'existing'}]),patch.object(self.adapter,'run') as run:
            with self.assertRaisesRegex(RuntimeErrorSafe,'workspace_not_empty'): self.adapter.apply('test')
            run.assert_not_called()
    def test_pending_timeout_is_not_blindly_retried(self):
        (self.adapter.root/'.nexus-pending.json').write_text('{}')
        with patch.object(self.adapter,'state',return_value=[]),patch.object(self.adapter,'plan',return_value=(Path('fixture'),[{'address':'terraform_data.fixture'}])),patch.object(self.adapter,'run') as run:
            with self.assertRaisesRegex(RuntimeErrorSafe,'previous_outcome_unconfirmed'): self.adapter.apply('test')
            run.assert_not_called()
    def test_mutating_or_unapproved_plan_is_rejected(self):
        import json
        for resource,actions in [('aws_instance',['create']),('terraform_data',['update'])]:
            with self.subTest(resource=resource,actions=actions),patch.object(self.adapter,'run',side_effect=[b'',json.dumps({'resource_changes':[{'type':resource,'change':{'actions':actions}}]}).encode()]):
                with self.assertRaisesRegex(RuntimeErrorSafe,'plan_scope_rejected'): self.adapter.plan()
    def test_parallel_operation_fails_closed(self):
        with self.adapter.lock():
            with self.assertRaisesRegex(RuntimeErrorSafe,'operation_in_progress'):
                with self.adapter.lock(): pass
    def test_destroy_requires_recorded_receipt(self):
        with self.assertRaisesRegex(RuntimeErrorSafe,'receipt_required'): self.adapter.destroy({})
