from nexus_terraform import TerraformAdapter
from nexus_runtime_adapters import RuntimeErrorSafe, list_containers as runtime_list, infrastructure_state, create_container as runtime_create, stop_container as runtime_stop
"""
NEXUS Hybrid DevOps Engine
Unified DevOps operations combining 20+ industry-leading tools

Combined Capabilities:
1. Infrastructure as Code (Terraform, Puppet, Chef, Salt, Ansible)
2. Container Management (Docker, Vagrant, OpenShift)
3. Monitoring & Observability (Prometheus, Grafana, Logstash, StatsD)
4. Build Tools (Gradle, Maven)
5. Deployment Automation (Capistrano, Fabric)
6. Error Tracking (Sentry)
7. Event-Driven Automation (StackStorm)

Features:
- Multi-cloud infrastructure management
- Container lifecycle management
- Real-time metrics & monitoring
- Automated deployments
- Error tracking & alerting
- Log aggregation
- Event-driven workflows
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import asyncio
import json

logger = logging.getLogger(__name__)

class HybridDevOpsEngine:
    def __init__(self, db=None):
        """Initialize the unified DevOps engine"""
        self.db = db
        self.llm_key = os.environ.get('EMERGENT_LLM_KEY')
        
        # Supported providers
        self.cloud_providers = ['aws', 'gcp', 'azure', 'digitalocean', 'local']
        self.container_runtimes = ['docker', 'containerd', 'podman']
        
        # Infrastructure state
        self.resources = {}
        self.deployments = {}
        self.metrics_buffer = []
        
        logger.info("🔧 Hybrid DevOps Engine initialized")
    
    # ==================== INFRASTRUCTURE AS CODE ====================
    
    async def create_infrastructure(self, config: Dict) -> Dict:
        """Fail closed until a verified IaC provider adapter is configured."""
        try:
            if not isinstance(config, dict):
                return {"success": False, "error": "configuration_required"}
            adapter = TerraformAdapter()
            return await asyncio.to_thread(adapter.apply, config.get("request_id"), config.get("environment", "certification"))
        except RuntimeErrorSafe as exc:
            return {"success": False, "error": str(exc), "state_unconfirmed": True}

    async def destroy_infrastructure(self, resource_id: str) -> Dict:
        """Never claim resource deletion without provider confirmation."""
        try:
            adapter = TerraformAdapter()
            return await asyncio.to_thread(adapter.destroy, resource_id)
        except RuntimeErrorSafe as exc:
            return {"success": False, "error": str(exc), "state_unconfirmed": True}

    async def get_infrastructure_state(self) -> Dict:
        """Real infrastructure inventory requires a provider."""
        try:
            return await asyncio.to_thread(infrastructure_state)
        except RuntimeErrorSafe as exc:
            return {"success": False, "error": str(exc)}

    # ==================== CONTAINER MANAGEMENT ====================
    
    async def create_container(self, config: Dict) -> Dict:
        """Require an actual container runtime before reporting creation."""
        try:
            return await asyncio.to_thread(runtime_create, config)
        except RuntimeErrorSafe as exc:
            return {"success": False, "error": str(exc), "container": None}

    async def list_containers(self, status: Optional[str] = None) -> Dict:
        """Container discovery cannot rely on local simulated state."""
        try:
            return await asyncio.to_thread(runtime_list, status)
        except RuntimeErrorSafe as exc:
            return {"success": False, "error": str(exc), "containers": None}

    async def stop_container(self, container_id: str) -> Dict:
        """Require confirmed stop from a real container runtime."""
        try:
            return await asyncio.to_thread(runtime_stop, container_id)
        except RuntimeErrorSafe as exc:
            return {"success": False, "error": str(exc), "state_unconfirmed": True}

    # ==================== MONITORING & METRICS ====================
    
    async def collect_metrics(self, service: str, metrics: Dict) -> Dict:
        """
        Collect metrics (Prometheus-style)
        """
        try:
            metric_entry = {
                "service": service,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": metrics
            }
            
            # Buffer metrics
            self.metrics_buffer.append(metric_entry)
            
            # Store in database
            if self.db:
                await self.db.metrics.insert_one(metric_entry)
            
            # Keep buffer size manageable
            if len(self.metrics_buffer) > 1000:
                self.metrics_buffer = self.metrics_buffer[-1000:]
            
            return {
                "success": True,
                "message": "Metrics collected"
            }
            
        except Exception as e:
            logger.error(f"Metrics collection failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def query_metrics(
        self, 
        service: Optional[str] = None,
        timeframe: str = "1h",
        metric_type: Optional[str] = None
    ) -> Dict:
        """
        Query metrics (Prometheus-style queries)
        """
        try:
            # Filter metrics
            filtered = self.metrics_buffer
            
            if service:
                filtered = [m for m in filtered if m["service"] == service]
            
            if metric_type:
                filtered = [
                    m for m in filtered 
                    if metric_type in m["metrics"]
                ]
            
            # Calculate aggregates
            if filtered and metric_type:
                values = [m["metrics"].get(metric_type, 0) for m in filtered]
                aggregates = {
                    "avg": sum(values) / len(values) if values else 0,
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                    "current": values[-1] if values else 0
                }
            else:
                aggregates = {}
            
            return {
                "success": True,
                "count": len(filtered),
                "metrics": filtered[-100:],  # Last 100 entries
                "aggregates": aggregates
            }
            
        except Exception as e:
            logger.error(f"Metrics query failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_alert(self, config: Dict) -> Dict:
        """Monitoring alerts require a real notification/alert backend."""
        return {"success": False, "error": "alert_backend_not_configured",
                "executed": False}

    # ==================== DEPLOYMENT AUTOMATION ====================
    
    async def deploy_service(self, service: str, environment: str, version: str,
                             strategy: str = "rolling") -> Dict:
        """Do not simulate tests, deployment, or health checks."""
        return {"success": False, "error": "deployment_runner_not_configured",
                "service": service, "environment": environment, "version": version,
                "executed": False}

    async def rollback_deployment(self, service: str, environment: str) -> Dict:
        """Rollback requires a verified deployment adapter."""
        return {"success": False, "error": "deployment_runner_not_configured",
                "service": service, "environment": environment, "executed": False}

    async def get_deployment_history(self, service: Optional[str] = None, environment: Optional[str] = None) -> Dict:
        """Do not treat in-memory test records as deployment history."""
        return {"success": False, "error": "deployment_runner_not_configured",
                "deployments": None}

    # ==================== LOG MANAGEMENT ====================
    
    async def ingest_logs(self, source: str, logs: List[str]) -> Dict:
        """
        Ingest logs (Logstash-style)
        """
        try:
            log_entries = []
            
            for log in logs:
                entry = {
                    "source": source,
                    "message": log,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": self._detect_log_level(log)
                }
                log_entries.append(entry)
            
            if self.db:
                await self.db.logs.insert_many(log_entries)
            
            return {
                "success": True,
                "ingested": len(log_entries),
                "source": source
            }
            
        except Exception as e:
            logger.error(f"Log ingestion failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_logs(
        self, 
        query: str,
        source: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 100
    ) -> Dict:
        """Search logs"""
        try:
            if not self.db:
                return {"success": False, "error": "Database not available"}
            
            # Build query
            search_filter = {}
            
            if source:
                search_filter["source"] = source
            
            if level:
                search_filter["level"] = level
            
            if query:
                search_filter["message"] = {"$regex": query, "$options": "i"}
            
            logs = await self.db.logs.find(
                search_filter,
                {"_id": 0}
            ).sort("timestamp", -1).limit(limit).to_list(limit)
            
            return {
                "success": True,
                "count": len(logs),
                "logs": logs
            }
            
        except Exception as e:
            logger.error(f"Log search failed: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== ERROR TRACKING ====================
    
    async def track_error(self, error_data: Dict) -> Dict:
        """
        Track application error (Sentry-style)
        """
        try:
            error = {
                "id": f"error_{int(datetime.now(timezone.utc).timestamp())}",
                "message": error_data.get('message'),
                "stack_trace": error_data.get('stack_trace'),
                "service": error_data.get('service'),
                "environment": error_data.get('environment'),
                "user": error_data.get('user'),
                "context": error_data.get('context', {}),
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "count": 1,
                "status": "unresolved"
            }
            
            if self.db:
                await self.db.errors.insert_one(error)
            
            return {
                "success": True,
                "error_id": error["id"],
                "message": "Error tracked"
            }
            
        except Exception as e:
            logger.error(f"Error tracking failed: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== HELPER METHODS ====================
    
    def _detect_log_level(self, message: str) -> str:
        """Detect log level from message"""
        message_lower = message.lower()
        if 'error' in message_lower:
            return 'error'
        elif 'warn' in message_lower:
            return 'warning'
        elif 'info' in message_lower:
            return 'info'
        return 'debug'
    
    def _group_by_key(self, items: Dict, key: str) -> Dict[str, int]:
        """Group items by key and count"""
        groups = {}
        for item in items.values():
            value = item.get(key, "unknown")
            groups[value] = groups.get(value, 0) + 1
        return groups
    
    def get_capabilities(self) -> Dict:
        """Return all DevOps engine capabilities"""
        return {
            "infrastructure": {
                "providers": self.cloud_providers,
                "operations": ["create", "destroy", "state"]
            },
            "containers": {
                "runtimes": self.container_runtimes,
                "operations": ["create", "stop", "list"]
            },
            "monitoring": {
                "features": ["metrics", "alerts", "queries"]
            },
            "deployment": {
                "strategies": ["rolling", "blue-green", "canary"],
                "operations": ["deploy", "rollback", "history"]
            },
            "logging": {
                "operations": ["ingest", "search"]
            },
            "error_tracking": {
                "features": ["track", "group", "resolve"]
            },
            "status": "integration_not_configured"
        }

def create_devops_engine(db=None):
    """Factory function"""
    return HybridDevOpsEngine(db)

# Global instance
hybrid_devops = HybridDevOpsEngine()
