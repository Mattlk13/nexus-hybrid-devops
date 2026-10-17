import asyncio
import unittest
from nexus_hybrid_devops import HybridDevOpsEngine

class FailClosedInfrastructureTests(unittest.TestCase):
    def setUp(self):
        self.engine = HybridDevOpsEngine()

    def run_action(self, operation):
        result = asyncio.run(operation)
        self.assertFalse(result["success"], result)
        self.assertIn("not_configured", result["error"])
        return result

    def test_no_fabricated_infrastructure(self):
        self.run_action(self.engine.create_infrastructure({"provider": "aws", "type": "server"}))
        self.run_action(self.engine.destroy_infrastructure("nonexistent"))
        self.run_action(self.engine.get_infrastructure_state())

    def test_no_fabricated_containers(self):
        self.run_action(self.engine.create_container({"image": "alpine:latest"}))
        self.run_action(self.engine.stop_container("nonexistent"))
        self.run_action(self.engine.list_containers())

    def test_no_fabricated_deployment(self):
        self.run_action(self.engine.deploy_service("example", "prod", "1.0"))
        self.run_action(self.engine.rollback_deployment("example", "prod"))
        self.run_action(self.engine.get_deployment_history())

    def test_no_fabricated_alert(self):
        self.run_action(self.engine.create_alert({"name": "test"}))

if __name__ == "__main__":
    unittest.main()
