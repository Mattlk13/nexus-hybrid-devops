import os
import subprocess
import unittest
from unittest.mock import patch
from nexus_runtime_adapters import list_containers, infrastructure_state, RuntimeErrorSafe
class RuntimeAdapterTests(unittest.TestCase):
    def test_container_scope_and_redaction(self):
        with patch.dict(os.environ, {'NEXUS_CONTAINER_RUNTIME':'podman'}), patch('nexus_runtime_adapters._run',return_value=[{'Id':'a'*64,'State':'running','Env':'SECRET'}]) as run:
            result=list_containers()
            self.assertTrue(result['verified'])
            self.assertNotIn('SECRET',str(result))
            self.assertIn('label=nexus.scope=certification',run.call_args.args[0])
    def test_invalid_runtime(self):
        with patch.dict(os.environ, {'NEXUS_CONTAINER_RUNTIME':'sh'}):
            with self.assertRaises(RuntimeErrorSafe): list_containers()
    def test_failed_command_does_not_succeed(self):
        with patch.dict(os.environ, {'NEXUS_CONTAINER_RUNTIME':'podman'}), patch('nexus_runtime_adapters.subprocess.run',return_value=subprocess.CompletedProcess([],1,b'',b'secret')):
            with self.assertRaisesRegex(RuntimeErrorSafe,'adapter_operation_failed'): list_containers()
    def test_timeout_redacted(self):
        with patch.dict(os.environ, {'NEXUS_CONTAINER_RUNTIME':'podman'}), patch('nexus_runtime_adapters.subprocess.run',side_effect=subprocess.TimeoutExpired('secret',20)):
            with self.assertRaisesRegex(RuntimeErrorSafe,'adapter_timeout'): list_containers()
    def test_state_never_claims_live_provider_validation(self):
        with patch.dict(os.environ, {'NEXUS_TERRAFORM_CHECKOUT':'.'}), patch('nexus_runtime_adapters._run',return_value={'format_version':'1.0','values':{'root_module':{'resources':[{'values':{'password':'secret'}}]}}}):
            result=infrastructure_state()
            self.assertEqual(result['resource_count'],1)
            self.assertFalse(result['live_provider_verified'])
            self.assertNotIn('secret',str(result).lower().replace('secrets_redacted',''))
