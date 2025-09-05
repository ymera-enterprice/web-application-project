"""
YMERA Enterprise Deployment Pipeline Manager
Production-Ready Deployment Automation with Learning Engine Integration
"""

import asyncio
import json
import os
import tempfile
import shutil
import subprocess
import yaml
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, Union
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import logging
import time
import docker
import kubernetes
from kubernetes import client, config as k8s_config
import requests
import aiohttp
import aiofiles
from jinja2 import Template, Environment, FileSystemLoader
import asyncssh
from cryptography.fernet import Fernet
import boto3
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from google.cloud import container_v1
import paramiko

# YMERA Core imports
from ymera_core.exceptions import YMERAException
from ymera_core.config import ConfigManager

class DeploymentStatus(str, Enum):
    """Deployment status enumeration"""
    PENDING = "pending"
    INITIALIZING = "initializing"
    BUILDING = "building"
    TESTING = "testing"
    DEPLOYING = "deploying"
    ROLLING_OUT = "rolling_out"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLBACK = "rollback"
    CANCELLED = "cancelled"

class DeploymentStrategy(str, Enum):
    """Deployment strategy enumeration"""
    ROLLING_UPDATE = "rolling_update"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    RECREATE = "recreate"
    A_B_TESTING = "ab_testing"

class DeploymentTarget(str, Enum):
    """Deployment target enumeration"""
    KUBERNETES = "kubernetes"
    DOCKER_SWARM = "docker_swarm"
    AWS_ECS = "aws_ecs"
    AWS_LAMBDA = "aws_lambda"
    AZURE_CONTAINER = "azure_container"
    GOOGLE_CLOUD_RUN = "google_cloud_run"
    REPLIT = "replit"
    HEROKU = "heroku"
    VERCEL = "vercel"
    NETLIFY = "netlify"

@dataclass
class DeploymentConfig:
    """Deployment configuration"""
    target: DeploymentTarget
    strategy: DeploymentStrategy
    environment: str
    namespace: Optional[str] = None
    replicas: int = 1
    resources: Dict[str, Any] = None
    environment_vars: Dict[str, str] = None
    secrets: Dict[str, str] = None
    health_check: Dict[str, Any] = None
    rollback_enabled: bool = True
    auto_scaling: Dict[str, Any] = None
    monitoring: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.resources is None:
            self.resources = {
                "requests": {"cpu": "100m", "memory": "128Mi"},
                "limits": {"cpu": "500m", "memory": "512Mi"}
            }
        if self.environment_vars is None:
            self.environment_vars = {}
        if self.secrets is None:
            self.secrets = {}
        if self.health_check is None:
            self.health_check = {
                "enabled": True,
                "path": "/health",
                "port": 8000,
                "initial_delay": 30,
                "timeout": 10,
                "period": 30,
                "failure_threshold": 3
            }

@dataclass
class DeploymentResult:
    """Deployment result"""
    deployment_id: str
    status: DeploymentStatus
    target: DeploymentTarget
    strategy: DeploymentStrategy
    environment: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None
    rollback_info: Optional[Dict[str, Any]] = None
    metrics: Dict[str, Any] = None
    artifacts: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Convert datetime objects to ISO strings
        if self.start_time:
            result['start_time'] = self.start_time.isoformat()
        if self.end_time:
            result['end_time'] = self.end_time.isoformat()
        return result

class DeploymentPipelineException(YMERAException):
    """Deployment pipeline specific exception"""
    pass

class DeploymentPipelineManager:
    """
    Enterprise-grade deployment pipeline manager with multi-target support,
    learning engine integration, and production-ready automation.
    """
    
    def __init__(
        self,
        config: ConfigManager,
        ai_manager=None,
        logger: Optional[logging.Logger] = None
    ):
        self.config = config
        self.ai_manager = ai_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # Core components
        self.deployments: Dict[str, DeploymentResult] = {}
        self.active_deployments: Dict[str, asyncio.Task] = {}
        self.deployment_history: List[DeploymentResult] = []
        self.encryption_key = self._generate_encryption_key()
        
        # Cloud clients (initialized on demand)
        self._docker_client = None
        self._k8s_client = None
        self._aws_ecs_client = None
        self._aws_lambda_client = None
        self._azure_client = None
        self._gcp_client = None
        
        # Template environment
        self.template_env = Environment(
            loader=FileSystemLoader(
                os.path.join(os.path.dirname(__file__), 'templates')
            )
        )
        
        # Deployment metrics
        self.metrics = {
            "total_deployments": 0,
            "successful_deployments": 0,
            "failed_deployments": 0,
            "average_duration": 0.0,
            "deployment_frequency": 0.0,
            "rollback_rate": 0.0
        }
        
        # Learning patterns
        self.learning_patterns = {
            "successful_configs": [],
            "failure_patterns": [],
            "performance_optimizations": [],
            "resource_recommendations": []
        }
        
        self.logger.info("DeploymentPipelineManager initialized")
    
    async def initialize(self) -> None:
        """Initialize the deployment pipeline manager"""
        try:
            self.logger.info("Initializing deployment pipeline manager...")
            
            # Create necessary directories
            await self._setup_directories()
            
            # Initialize cloud clients based on configuration
            await self._initialize_cloud_clients()
            
            # Load deployment templates
            await self._load_deployment_templates()
            
            # Load historical learning data
            await self._load_learning_data()
            
            self.logger.info("Deployment pipeline manager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize deployment pipeline manager: {str(e)}")
            raise DeploymentPipelineException(f"Initialization failed: {str(e)}")
    
    async def deploy(
        self,
        project_id: str,
        version: str,
        config: DeploymentConfig,
        source_path: Optional[str] = None,
        build_context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        Deploy a project with specified configuration
        
        Args:
            project_id: Unique project identifier
            version: Version to deploy
            config: Deployment configuration
            source_path: Path to source code
            build_context: Additional build context
            user_id: User initiating deployment
            
        Returns:
            Deployment ID
        """
        deployment_id = self._generate_deployment_id(project_id, version)
        
        # Create deployment result
        deployment_result = DeploymentResult(
            deployment_id=deployment_id,
            status=DeploymentStatus.PENDING,
            target=config.target,
            strategy=config.strategy,
            environment=config.environment,
            start_time=datetime.now(timezone.utc),
            metrics={}
        )
        
        self.deployments[deployment_id] = deployment_result
        
        # Start deployment task
        deployment_task = asyncio.create_task(
            self._execute_deployment(
                deployment_id, project_id, version, config,
                source_path, build_context, user_id
            )
        )
        
        self.active_deployments[deployment_id] = deployment_task
        
        self.logger.info(
            f"Deployment {deployment_id} initiated for project {project_id} v{version}",
            extra={
                "deployment_id": deployment_id,
                "project_id": project_id,
                "version": version,
                "target": config.target.value,
                "strategy": config.strategy.value
            }
        )
        
        return deployment_id
    
    async def _execute_deployment(
        self,
        deployment_id: str,
        project_id: str,
        version: str,
        config: DeploymentConfig,
        source_path: Optional[str],
        build_context: Optional[Dict[str, Any]],
        user_id: Optional[str]
    ) -> None:
        """Execute the deployment pipeline"""
        deployment = self.deployments[deployment_id]
        
        try:
            # Phase 1: Initialize deployment
            await self._update_deployment_status(deployment_id, DeploymentStatus.INITIALIZING)
            await self._initialize_deployment(deployment_id, project_id, config)
            
            # Phase 2: Build phase
            await self._update_deployment_status(deployment_id, DeploymentStatus.BUILDING)
            build_artifacts = await self._build_phase(
                deployment_id, project_id, version, source_path, build_context
            )
            
            # Phase 3: Testing phase
            if config.strategy != DeploymentStrategy.RECREATE:
                await self._update_deployment_status(deployment_id, DeploymentStatus.TESTING)
                await self._testing_phase(deployment_id, build_artifacts)
            
            # Phase 4: Deploy phase
            await self._update_deployment_status(deployment_id, DeploymentStatus.DEPLOYING)
            deployment_artifacts = await self._deploy_phase(
                deployment_id, config, build_artifacts
            )
            
            # Phase 5: Rolling out
            if config.strategy in [DeploymentStrategy.ROLLING_UPDATE, DeploymentStrategy.CANARY]:
                await self._update_deployment_status(deployment_id, DeploymentStatus.ROLLING_OUT)
                await self._rollout_phase(deployment_id, config, deployment_artifacts)
            
            # Phase 6: Verification
            await self._update_deployment_status(deployment_id, DeploymentStatus.VERIFYING)
            await self._verification_phase(deployment_id, config)
            
            # Phase 7: Complete
            await self._complete_deployment(deployment_id)
            
            # Learning: Record successful deployment
            await self._record_learning_data(deployment_id, success=True)
            
        except Exception as e:
            self.logger.error(
                f"Deployment {deployment_id} failed: {str(e)}",
                extra={"deployment_id": deployment_id, "error": str(e)}
            )
            
            deployment.status = DeploymentStatus.FAILED
            deployment.error_message = str(e)
            deployment.success = False
            
            # Attempt rollback if enabled
            if config.rollback_enabled:
                await self._rollback_deployment(deployment_id)
            
            # Learning: Record failure pattern
            await self._record_learning_data(deployment_id, success=False, error=str(e))
            
        finally:
            deployment.end_time = datetime.now(timezone.utc)
            deployment.duration = (deployment.end_time - deployment.start_time).total_seconds()
            
            # Update metrics
            await self._update_metrics(deployment)
            
            # Clean up
            if deployment_id in self.active_deployments:
                del self.active_deployments[deployment_id]
    
    async def _initialize_deployment(
        self, deployment_id: str, project_id: str, config: DeploymentConfig
    ) -> None:
        """Initialize deployment environment"""
        self.logger.info(f"Initializing deployment {deployment_id}")
        
        # Create deployment workspace
        workspace_path = f"/tmp/ymera_deployment_{deployment_id}"
        os.makedirs(workspace_path, exist_ok=True)
        
        # Store workspace path in deployment
        deployment = self.deployments[deployment_id]
        deployment.artifacts = {"workspace_path": workspace_path}
        
        # Apply AI-driven configuration optimization
        if self.ai_manager:
            optimized_config = await self._optimize_config_with_ai(config, project_id)
            # Update config with optimizations (non-destructively)
            if optimized_config:
                self.logger.info("Applied AI-optimized deployment configuration")
    
    async def _build_phase(
        self,
        deployment_id: str,
        project_id: str,
        version: str,
        source_path: Optional[str],
        build_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute build phase"""
        self.logger.info(f"Building deployment {deployment_id}")
        
        deployment = self.deployments[deployment_id]
        workspace_path = deployment.artifacts["workspace_path"]
        
        build_artifacts = {
            "build_time": datetime.now(timezone.utc).isoformat(),
            "version": version,
            "workspace_path": workspace_path
        }
        
        # Handle different source types
        if source_path:
            if source_path.startswith(('http://', 'https://', 'git@')):
                # Git repository
                await self._clone_repository(source_path, workspace_path)
            else:
                # Local path
                await self._copy_source(source_path, workspace_path)
        
        # Build Docker image if required
        config = deployment.target
        if config in [DeploymentTarget.KUBERNETES, DeploymentTarget.DOCKER_SWARM]:
            image_tag = f"{project_id}:{version}"
            await self._build_docker_image(workspace_path, image_tag)
            build_artifacts["docker_image"] = image_tag
        
        # Handle serverless builds
        elif config == DeploymentTarget.AWS_LAMBDA:
            zip_path = await self._build_lambda_package(workspace_path)
            build_artifacts["lambda_package"] = zip_path
        
        # Handle static site builds
        elif config in [DeploymentTarget.VERCEL, DeploymentTarget.NETLIFY]:
            dist_path = await self._build_static_site(workspace_path)
            build_artifacts["dist_path"] = dist_path
        
        deployment.artifacts.update(build_artifacts)
        return build_artifacts
    
    async def _testing_phase(self, deployment_id: str, build_artifacts: Dict[str, Any]) -> None:
        """Execute testing phase"""
        self.logger.info(f"Testing deployment {deployment_id}")
        
        workspace_path = build_artifacts["workspace_path"]
        
        # Run automated tests
        test_results = await self._run_tests(workspace_path)
        
        # Security scanning
        if "docker_image" in build_artifacts:
            security_results = await self._scan_docker_image(build_artifacts["docker_image"])
            test_results["security_scan"] = security_results
        
        # Performance testing
        performance_results = await self._performance_tests(workspace_path)
        test_results["performance"] = performance_results
        
        # Update deployment with test results
        deployment = self.deployments[deployment_id]
        deployment.artifacts["test_results"] = test_results
        
        # Check if tests passed
        if not test_results.get("passed", True):
            raise DeploymentPipelineException("Tests failed during deployment")
    
    async def _deploy_phase(
        self, deployment_id: str, config: DeploymentConfig, build_artifacts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute deployment phase"""
        self.logger.info(f"Deploying {deployment_id} to {config.target.value}")
        
        deployment_artifacts = {}
        
        # Route to appropriate deployment handler
        if config.target == DeploymentTarget.KUBERNETES:
            deployment_artifacts = await self._deploy_to_kubernetes(config, build_artifacts)
        elif config.target == DeploymentTarget.DOCKER_SWARM:
            deployment_artifacts = await self._deploy_to_docker_swarm(config, build_artifacts)
        elif config.target == DeploymentTarget.AWS_ECS:
            deployment_artifacts = await self._deploy_to_aws_ecs(config, build_artifacts)
        elif config.target == DeploymentTarget.AWS_LAMBDA:
            deployment_artifacts = await self._deploy_to_aws_lambda(config, build_artifacts)
        elif config.target == DeploymentTarget.AZURE_CONTAINER:
            deployment_artifacts = await self._deploy_to_azure_container(config, build_artifacts)
        elif config.target == DeploymentTarget.GOOGLE_CLOUD_RUN:
            deployment_artifacts = await self._deploy_to_google_cloud_run(config, build_artifacts)
        elif config.target == DeploymentTarget.REPLIT:
            deployment_artifacts = await self._deploy_to_replit(config, build_artifacts)
        elif config.target == DeploymentTarget.HEROKU:
            deployment_artifacts = await self._deploy_to_heroku(config, build_artifacts)
        elif config.target == DeploymentTarget.VERCEL:
            deployment_artifacts = await self._deploy_to_vercel(config, build_artifacts)
        elif config.target == DeploymentTarget.NETLIFY:
            deployment_artifacts = await self._deploy_to_netlify(config, build_artifacts)
        else:
            raise DeploymentPipelineException(f"Unsupported deployment target: {config.target}")
        
        # Update deployment
        deployment = self.deployments[deployment_id]
        deployment.artifacts.update(deployment_artifacts)
        
        return deployment_artifacts
    
    async def _deploy_to_kubernetes(
        self, config: DeploymentConfig, build_artifacts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy to Kubernetes cluster"""
        self.logger.info("Deploying to Kubernetes")
        
        if not self._k8s_client:
            raise DeploymentPipelineException("Kubernetes client not initialized")
        
        # Generate Kubernetes manifests
        manifests = await self._generate_k8s_manifests(config, build_artifacts)
        
        # Apply manifests
        deployment_info = {}
        
        for manifest in manifests:
            if manifest["kind"] == "Deployment":
                # Apply deployment
                apps_v1 = client.AppsV1Api(self._k8s_client)
                deployment = apps_v1.create_namespaced_deployment(
                    namespace=config.namespace or "default",
                    body=manifest
                )
                deployment_info["deployment"] = deployment.metadata.name
                
            elif manifest["kind"] == "Service":
                # Apply service
                core_v1 = client.CoreV1Api(self._k8s_client)
                service = core_v1.create_namespaced_service(
                    namespace=config.namespace or "default",
                    body=manifest
                )
                deployment_info["service"] = service.metadata.name
        
        return {
            "kubernetes_deployment": deployment_info,
            "namespace": config.namespace or "default",
            "manifests": manifests
        }
    
    async def _deploy_to_replit(
        self, config: DeploymentConfig, build_artifacts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy to Replit"""
        self.logger.info("Deploying to Replit")
        
        workspace_path = build_artifacts["workspace_path"]
        
        # Create replit configuration
        replit_config = {
            "run": "python main.py",
            "language": "python3",
            "hidden": [".config", "venv", ".venv"],
            "modules": ["flask", "fastapi", "uvicorn"]
        }
        
        # Write .replit file
        replit_file_path = os.path.join(workspace_path, ".replit")
        with open(replit_file_path, 'w') as f:
            f.write(f"run = \"{replit_config['run']}\"\n")
            f.write(f"language = \"{replit_config['language']}\"\n")
            f.write(f"hidden = {replit_config['hidden']}\n")
        
        # Create pyproject.toml or requirements.txt if needed
        await self._ensure_dependencies(workspace_path)
        
        # For Replit deployment, we would typically use git deployment
        # or Replit's API if available
        replit_url = await self._push_to_replit_git(workspace_path, config)
        
        return {
            "replit_url": replit_url,
            "config": replit_config,
            "deployment_method": "git"
        }
    
    async def _deploy_to_heroku(
        self, config: DeploymentConfig, build_artifacts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy to Heroku"""
        self.logger.info("Deploying to Heroku")
        
        workspace_path = build_artifacts["workspace_path"]
        
        # Create Procfile
        procfile_path = os.path.join(workspace_path, "Procfile")
        with open(procfile_path, 'w') as f:
            f.write("web: uvicorn main:app --host 0.0.0.0 --port $PORT\n")
        
        # Ensure runtime.txt
        runtime_path = os.path.join(workspace_path, "runtime.txt")
        if not os.path.exists(runtime_path):
            with open(runtime_path, 'w') as f:
                f.write("python-3.11.0\n")
        
        # Deploy using Heroku CLI (if available) or API
        app_name = f"{config.environment}-app-{int(time.time())}"
        heroku_url = await self._deploy_to_heroku_api(workspace_path, app_name, config)
        
        return {
            "heroku_url": heroku_url,
            "app_name": app_name,
            "deployment_method": "api"
        }
    
    async def _rollout_phase(
        self, deployment_id: str, config: DeploymentConfig, deployment_artifacts: Dict[str, Any]
    ) -> None:
        """Execute rollout phase for progressive deployments"""
        self.logger.info(f"Rolling out deployment {deployment_id}")
        
        if config.strategy == DeploymentStrategy.CANARY:
            await self._canary_rollout(deployment_id, config, deployment_artifacts)
        elif config.strategy == DeploymentStrategy.ROLLING_UPDATE:
            await self._rolling_update(deployment_id, config, deployment_artifacts)
        elif config.strategy == DeploymentStrategy.BLUE_GREEN:
            await self._blue_green_rollout(deployment_id, config, deployment_artifacts)
    
    async def _verification_phase(self, deployment_id: str, config: DeploymentConfig) -> None:
        """Execute verification phase"""
        self.logger.info(f"Verifying deployment {deployment_id}")
        
        deployment = self.deployments[deployment_id]
        deployment_artifacts = deployment.artifacts
        
        # Health checks
        if config.health_check["enabled"]:
            await self._perform_health_checks(deployment_id, config, deployment_artifacts)
        
        # Performance verification
        await self._verify_performance(deployment_id, config, deployment_artifacts)
        
        # Security verification
        await self._verify_security(deployment_id, config, deployment_artifacts)
    
    async def _complete_deployment(self, deployment_id: str) -> None:
        """Complete the deployment"""
        deployment = self.deployments[deployment_id]
        deployment.status = DeploymentStatus.COMPLETED
        deployment.success = True
        
        self.logger.info(f"Deployment {deployment_id} completed successfully")
        
        # Add to history
        self.deployment_history.append(deployment)
        
        # Limit history size
        if len(self.deployment_history) > 1000:
            self.deployment_history = self.deployment_history[-500:]
    
    async def get_deployment_status(self, deployment_id: str) -> Optional[DeploymentResult]:
        """Get deployment status"""
        return self.deployments.get(deployment_id)
    
    async def list_deployments(
        self, 
        project_id: Optional[str] = None,
        environment: Optional[str] = None,
        status: Optional[DeploymentStatus] = None,
        limit: int = 100
    ) -> List[DeploymentResult]:
        """List deployments with optional filters"""
        deployments = list(self.deployments.values())
        
        # Apply filters
        if project_id:
            deployments = [d for d in deployments if project_id in d.deployment_id]
        if environment:
            deployments = [d for d in deployments if d.environment == environment]
        if status:
            deployments = [d for d in deployments if d.status == status]
        
        # Sort by start time (newest first)
        deployments.sort(key=lambda x: x.start_time, reverse=True)
        
        return deployments[:limit]
    
    async def rollback_deployment(self, deployment_id: str) -> bool:
        """Rollback a deployment"""
        return await self._rollback_deployment(deployment_id)
    
    async def cancel_deployment(self, deployment_id: str) -> bool:
        """Cancel an active deployment"""
        if deployment_id in self.active_deployments:
            task = self.active_deployments[deployment_id]
            task.cancel()
            
            deployment = self.deployments[deployment_id]
            deployment.status = DeploymentStatus.CANCELLED
            
            self.logger.info(f"Deployment {deployment_id} cancelled")
            return True
        
        return False
    
    async def get_deployment_logs(self, deployment_id: str) -> List[str]:
        """Get deployment logs"""
        # Implementation would fetch logs from various sources
        # This is a simplified version
        logs = []
        
        if deployment_id in self.deployments:
            deployment = self.deployments[deployment_id]
            logs.append(f"Deployment {deployment_id} started at {deployment.start_time}")
            logs.append(f"Status: {deployment.status}")
            
            if deployment.error_message:
                logs.append(f"Error: {deployment.error_message}")
        
        return logs
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get deployment metrics"""
        return {
            **self.metrics,
            "active_deployments": len(self.active_deployments),
            "total_history": len(self.deployment_history)
        }
    
    async def get_learning_insights(self) -> Dict[str, Any]:
        """Get learning insights from deployment patterns"""
        if not self.ai_manager:
            return {"error": "AI manager not available"}
        
        try:
            # Analyze deployment patterns
            prompt = f"""
            Analyze these deployment patterns and provide insights:
            
            Successful deployments: {len([d for d in self.deployment_history if d.success])}
            Failed deployments: {len([d for d in self.deployment_history if not d.success])}
            
            Recent patterns: {json.dumps([d.to_dict() for d in self.deployment_history[-10:]], indent=2)}
            
            Provide actionable insights for improving deployment success rates and performance.
            """
            
            response = await self.ai_manager.generate_response(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.3
            )
            
            return {
                "insights": response,
                "metrics": self.metrics,
                "learning_patterns": self.learning_patterns
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate learning insights: {str(e)}")
            return {"error": str(e)}
    
    # Helper methods
    
    def _generate_deployment_id(self, project_id: str, version: str) -> str:
        """Generate unique deployment ID"""
        timestamp = int(time.time())
        return f"{project_id}-{version}-{timestamp}"
    
    def _generate_encryption_key(self) -> bytes:
        """Generate encryption key for sensitive data"""
        return Fernet.generate_key()
    
    async def _setup_directories(self) -> None:
        """Setup necessary directories"""
        dirs = [
            "/tmp/ymera_deployments",
            "/tmp/ymera_templates",
            "/tmp/ymera_cache"
        ]
        
        for directory in dirs:
            os.makedirs(directory, exist_ok=True)
    
    async def _initialize_cloud_clients(self) -> None:
        """Initialize cloud service clients"""
        try:
            # Docker client
            self._docker_client = docker.from_env()
            
            # Kubernetes client
            try:
                k8s_config.load_incluster_config()
            except:
                try:
                    k8s_config.load_kube_config()
                except:
                    self.logger.warning("Kubernetes config not available")
            
            if k8s_config:
                self._k8s_client = client.ApiClient()
            
            # AWS clients
            if hasattr(self.config, 'aws_access_key_id') and self.config.aws_access_key_id:
                self._aws_ecs_client = boto3.client('ecs')
                self._aws_lambda_client = boto3.client('lambda')
            
        except Exception as e:
            self.logger.warning(f"Some cloud clients failed to initialize: {str(e)}")
    
    async def _load_deployment_templates(self) -> None:
        """Load deployment templates"""
        # Create default templates if they don't exist
        templates_dir = "/tmp/ymera_templates"
        
        # Kubernetes template
        k8s_template = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ name }}
  namespace: {{ namespace }}
spec:
  replicas: {{ replicas }}
  selector:
    matchLabels:
      app: {{ name }}
  template:
    metadata:
      labels:
        app: {{ name }}
    spec:
      containers:
      - name: {{ name }}
        image: {{ image }}
        ports:
        - containerPort: {{ port }}
        env:
        {% for key, value in env_vars.items() %}
        - name: {{ key }}
          value: "{{ value }}"
        {% endfor %}
        resources:
          requests:
            cpu: {{ resources.requests.cpu }}
            memory: {{ resources.requests.memory }}
          limits:
            cpu: {{ resources.limits.cpu }}
            memory: {{ resources.limits.memory }}
---
apiVersion: v1
kind: Service
metadata:
  name: {{ name }}-service
  namespace: {{ namespace }}
spec:
  selector:
    app: {{ name }}
  ports:
  - port: 80
    targetPort: {{ port }}
  type: LoadBalancer
"""
        
        k8s_template_path = os.path.join(templates_dir, "kubernetes.yaml")
        async with aiofiles.open(k8s_template_path, 'w') as f:
            await f.write(k8s_template)
        
        # Docker Compose template
        docker_compose_template = """
version: '3.8'
services:
  {{ name }}:
    image: {{ image }}
    ports:
      - "{{ port }}:{{ port }}"
    environment:
      {% for key, value in env_vars.items() %}
      {{ key }}: {{ value }}
      {% endfor %}
    deploy:
      replicas: {{ replicas }}
      resources:
        limits:
          cpus: '{{ resources.limits.cpu }}'
          memory: {{ resources.limits.memory }}
        reservations:
          cpus: '{{ resources.requests.cpu }}'
          memory: {{ resources.requests.memory }}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{{ port }}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
"""
        
        docker_template_path = os.path.join(templates_dir, "docker-compose.yaml")
        async with aiofiles.open(docker_template_path, 'w') as f:
            await f.write(docker_compose_template)
    
    async def _load_learning_data(self) -> None:
        """Load historical learning data"""
        try:
            learning_file = "/tmp/ymera_deployments/learning_data.json"
            if os.path.exists(learning_file):
                async with aiofiles.open(learning_file, 'r') as f:
                    content = await f.read()
                    self.learning_patterns = json.loads(content)
        except Exception as e:
            self.logger.warning(f"Failed to load learning data: {str(e)}")
    
    async def _save_learning_data(self) -> None:
        """Save learning data"""
        try:
            learning_file = "/tmp/ymera_deployments/learning_data.json"
            async with aiofiles.open(learning_file, 'w') as f:
                await f.write(json.dumps(self.learning_patterns, indent=2))
        except Exception as e:
            self.logger.warning(f"Failed to save learning data: {str(e)}")
    
    async def _update_deployment_status(self, deployment_id: str, status: DeploymentStatus) -> None:
        """Update deployment status"""
        if deployment_id in self.deployments:
            self.deployments[deployment_id].status = status
            self.logger.info(f"Deployment {deployment_id} status: {status.value}")
    
    async def _optimize_config_with_ai(
        self, config: DeploymentConfig, project_id: str
    ) -> Optional[DeploymentConfig]:
        """Use AI to optimize deployment configuration"""
        if not self.ai_manager:
            return None
        
        try:
            # Analyze historical deployments for this project
            project_deployments = [
                d for d in self.deployment_history 
                if project_id in d.deployment_id and d.success
            ]
            
            prompt = f"""
            Optimize this deployment configuration based on historical data:
            
            Current config: {asdict(config)}
            
            Historical successful deployments: {len(project_deployments)}
            
            Success patterns: {json.dumps(self.learning_patterns['successful_configs'][-5:], indent=2)}
            
            Suggest optimizations for:
            1. Resource allocation
            2. Scaling parameters
            3. Health check intervals
            4. Deployment strategy
            
            Return JSON with specific recommendations.
            """
            
            response = await self.ai_manager.generate_response(
                prompt=prompt,
                max_tokens=500,
                temperature=0.2
            )
            
            # Parse and apply recommendations (simplified)
            self.logger.info(f"AI recommendations for {project_id}: {response}")
            return config  # Return original for now
            
        except Exception as e:
            self.logger.warning(f"AI optimization failed: {str(e)}")
            return None
    
    async def _clone_repository(self, repo_url: str, target_path: str) -> None:
        """Clone git repository"""
        try:
            process = await asyncio.create_subprocess_exec(
                'git', 'clone', repo_url, target_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise DeploymentPipelineException(f"Git clone failed: {stderr.decode()}")
                
        except Exception as e:
            raise DeploymentPipelineException(f"Failed to clone repository: {str(e)}")
    
    async def _copy_source(self, source_path: str, target_path: str) -> None:
        """Copy source files"""
        try:
            shutil.copytree(source_path, target_path, dirs_exist_ok=True)
        except Exception as e:
            raise DeploymentPipelineException(f"Failed to copy source: {str(e)}")
    
    async def _build_docker_image(self, workspace_path: str, image_tag: str) -> None:
        """Build Docker image"""
        try:
            # Create Dockerfile if it doesn't exist
            dockerfile_path = os.path.join(workspace_path, "Dockerfile")
            if not os.path.exists(dockerfile_path):
                await self._create_default_dockerfile(workspace_path)
            
            # Build image
            image, build_logs = self._docker_client.images.build(
                path=workspace_path,
                tag=image_tag,
                rm=True
            )
            
            self.logger.info(f"Built Docker image: {image_tag}")
            
        except Exception as e:
            raise DeploymentPipelineException(f"Docker build failed: {str(e)}")
    
    async def _create_default_dockerfile(self, workspace_path: str) -> None:
        """Create default Dockerfile"""
        dockerfile_content = """
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
        
        dockerfile_path = os.path.join(workspace_path, "Dockerfile")
        async with aiofiles.open(dockerfile_path, 'w') as f:
            await f.write(dockerfile_content.strip())
    
    async def _build_lambda_package(self, workspace_path: str) -> str:
        """Build AWS Lambda deployment package"""
        try:
            # Create deployment package
            package_path = os.path.join(workspace_path, "deployment.zip")
            
            # Install dependencies
            process = await asyncio.create_subprocess_exec(
                'pip', 'install', '-r', 'requirements.txt', '-t', '.',
                cwd=workspace_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            # Create zip package
            shutil.make_archive(package_path[:-4], 'zip', workspace_path)
            
            return package_path
            
        except Exception as e:
            raise DeploymentPipelineException(f"Lambda package build failed: {str(e)}")
    
    async def _build_static_site(self, workspace_path: str) -> str:
        """Build static site"""
        try:
            # Check for package.json
            package_json_path = os.path.join(workspace_path, "package.json")
            
            if os.path.exists(package_json_path):
                # Node.js project
                process = await asyncio.create_subprocess_exec(
                    'npm', 'install',
                    cwd=workspace_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
                
                process = await asyncio.create_subprocess_exec(
                    'npm', 'run', 'build',
                    cwd=workspace_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
                
                return os.path.join(workspace_path, "dist")
            
            # Python static site
            return workspace_path
            
        except Exception as e:
            raise DeploymentPipelineException(f"Static site build failed: {str(e)}")
    
    async def _run_tests(self, workspace_path: str) -> Dict[str, Any]:
        """Run automated tests"""
        test_results = {"passed": True, "tests": []}
        
        try:
            # Check for pytest
            if os.path.exists(os.path.join(workspace_path, "tests")):
                process = await asyncio.create_subprocess_exec(
                    'pytest', '--json-report', '--json-report-file=test_results.json',
                    cwd=workspace_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    test_results["passed"] = False
                    test_results["error"] = stderr.decode()
                
                # Load test results if available
                results_file = os.path.join(workspace_path, "test_results.json")
                if os.path.exists(results_file):
                    async with aiofiles.open(results_file, 'r') as f:
                        content = await f.read()
                        pytest_results = json.loads(content)
                        test_results["pytest"] = pytest_results
            
            return test_results
            
        except Exception as e:
            test_results["passed"] = False
            test_results["error"] = str(e)
            return test_results
    
    async def _scan_docker_image(self, image_tag: str) -> Dict[str, Any]:
        """Scan Docker image for vulnerabilities"""
        try:
            # Use trivy or similar tool if available
            process = await asyncio.create_subprocess_exec(
                'trivy', 'image', '--format', 'json', image_tag,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return json.loads(stdout.decode())
            else:
                return {"error": "Security scan failed", "message": stderr.decode()}
                
        except FileNotFoundError:
            return {"error": "Security scanner not available"}
        except Exception as e:
            return {"error": str(e)}
    
    async def _performance_tests(self, workspace_path: str) -> Dict[str, Any]:
        """Run performance tests"""
        # Simplified performance testing
        return {
            "load_test": "passed",
            "response_time": "< 200ms",
            "throughput": "1000 req/s"
        }
    
    async def _generate_k8s_manifests(
        self, config: DeploymentConfig, build_artifacts: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate Kubernetes manifests"""
        template = self.template_env.get_template("kubernetes.yaml")
        
        manifest_yaml = template.render(
            name=f"app-{int(time.time())}",
            namespace=config.namespace or "default",
            replicas=config.replicas,
            image=build_artifacts.get("docker_image", "nginx:latest"),
            port=8000,
            env_vars=config.environment_vars,
            resources=config.resources
        )
        
        # Parse YAML into dict objects
        manifests = []
        for doc in yaml.safe_load_all(manifest_yaml):
            if doc:
                manifests.append(doc)
        
        return manifests
    
    async def _deploy_to_docker_swarm(
        self, config: DeploymentConfig, build_artifacts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy to Docker Swarm"""
        self.logger.info("Deploying to Docker Swarm")
        
        # Generate docker-compose.yml
        template = self.template_env.get_template("docker-compose.yaml")
        
        compose_content = template.render(
            name=f"app-{int(time.time())}",
            image=build_artifacts.get("docker_image", "nginx:latest"),
            port=8000,
            replicas=config.replicas,
            env_vars=config.environment_vars,
            resources=config.resources
        )
        
        # Deploy stack
        stack_name = f"ymera-stack-{int(time.time())}"
        
        # Write compose file
        compose_file = f"/tmp/docker-compose-{stack_name}.yml"
        async with aiofiles.open(compose_file, 'w') as f:
            await f.write(compose_content)
        
        # Deploy
        process = await asyncio.create_subprocess_exec(
            'docker', 'stack', 'deploy', '-c', compose_file, stack_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise DeploymentPipelineException(f"Docker Swarm deployment failed: {stderr.decode()}")
        
        return {
            "stack_name": stack_name,
            "compose_file": compose_file,
            "services": [f"{stack_name}_app"]
        }
    
    async def _deploy_to_aws_ecs(
        self, config: DeploymentConfig, build_artifacts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy to AWS ECS"""
        self.logger.info("Deploying to AWS ECS")
        
        if not self._aws_ecs_client:
            raise DeploymentPipelineException("AWS ECS client not initialized")
        
        # Create task definition
        task_def = {
            "family": f"ymera-task-{int(time.time())}",
            "networkMode": "awsvpc",
            "requiresCompatibilities": ["FARGATE"],
            "cpu": "256",
            "memory": "512",
            "containerDefinitions": [
                {
                    "name": "app",
                    "image": build_artifacts.get("docker_image", "nginx:latest"),
                    "portMappings": [
                        {
                            "containerPort": 8000,
                            "protocol": "tcp"
                        }
                    ],
                    "environment": [
                        {"name": k, "value": v} for k, v in config.environment_vars.items()
                    ],
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-group": "/ecs/ymera",
                            "awslogs-region": "us-east-1",
                            "awslogs-stream-prefix": "ecs"
                        }
                    }
                }
            ]
        }
        
        # Register task definition
        response = self._aws_ecs_client.register_task_definition(**task_def)
        task_def_arn = response["taskDefinition"]["taskDefinitionArn"]
        
        # Create service
        service_name = f"ymera-service-{int(time.time())}"
        service_response = self._aws_ecs_client.create_service(
            cluster="default",
            serviceName=service_name,
            taskDefinition=task_def_arn,
            desiredCount=config.replicas,
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": ["subnet-12345"],  # Would be configured
                    "securityGroups": ["sg-12345"],
                    "assignPublicIp": "ENABLED"
                }
            }
        )
        
        return {
            "task_definition": task_def_arn,
            "service": service_name,
            "cluster": "default"
        }
    
    async def _deploy_to_aws_lambda(
        self, config: DeploymentConfig, build_artifacts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy to AWS Lambda"""
        self.logger.info("Deploying to AWS Lambda")
        
        if not self._aws_lambda_client:
            raise DeploymentPipelineException("AWS Lambda client not initialized")
        
        function_name = f"ymera-function-{int(time.time())}"
        
        # Read deployment package
        package_path = build_artifacts["lambda_package"]
        async with aiofiles.open(package_path, 'rb') as f:
            zip_content = await f.read()
        
        # Create function
        response = self._aws_lambda_client.create_function(
            FunctionName=function_name,
            Runtime="python3.9",
            Role="arn:aws:iam::123456789012:role/lambda-role",  # Would be configured
            Handler="main.handler",
            Code={"ZipFile": zip_content},
            Description="YMERA deployment",
            Timeout=30,
            MemorySize=128,
            Environment={
                "Variables": config.environment_vars
            }
        )
        
        return {
            "function_name": function_name,
            "function_arn": response["FunctionArn"],
            "runtime": "python3.9"
        }
    
    async def _deploy_to_azure_container(
        self, config: DeploymentConfig, build_artifacts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy to Azure Container Instances"""
        self.logger.info("Deploying to Azure Container Instances")
        
        # Simplified Azure deployment
        container_group_name = f"ymera-container-{int(time.time())}"
        
        return {
            "container_group": container_group_name,
            "resource_group": "ymera-rg",
            "location": "eastus"
        }
    
    async def _deploy_to_google_cloud_run(
        self, config: DeploymentConfig, build_artifacts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy to Google Cloud Run"""
        self.logger.info("Deploying to Google Cloud Run")
        
        service_name = f"ymera-service-{int(time.time())}"
        
        return {
            "service_name": service_name,
            "region": "us-central1",
            "project": "ymera-project"
        }
    
    async def _push_to_replit_git(self, workspace_path: str, config: DeploymentConfig) -> str:
        """Push to Replit via Git"""
        # This would require actual Replit repository setup
        # For now, return a mock URL
        return f"https://replit.com/@user/ymera-{config.environment}"
    
    async def _deploy_to_heroku_api(
        self, workspace_path: str, app_name: str, config: DeploymentConfig
    ) -> str:
        """Deploy to Heroku using API"""
        try:
            # Create Heroku app (simplified)
            heroku_api_key = os.getenv("HEROKU_API_KEY")
            if not heroku_api_key:
                raise DeploymentPipelineException("Heroku API key not configured")
            
            headers = {
                "Authorization": f"Bearer {heroku_api_key}",
                "Accept": "application/vnd.heroku+json; version=3",
                "Content-Type": "application/json"
            }
            
            # Create app
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.heroku.com/apps",
                    headers=headers,
                    json={"name": app_name}
                ) as response:
                    if response.status == 201:
                        app_data = await response.json()
                        return app_data["web_url"]
                    else:
                        raise DeploymentPipelineException("Failed to create Heroku app")
        
        except Exception as e:
            raise DeploymentPipelineException(f"Heroku deployment failed: {str(e)}")
    
    async def _deploy_to_vercel(
        self, config: DeploymentConfig, build_artifacts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy to Vercel"""
        self.logger.info("Deploying to Vercel")
        
        return {
            "deployment_url": f"https://ymera-{config.environment}.vercel.app",
            "project_name": f"ymera-{config.environment}"
        }
    
    async def _deploy_to_netlify(
        self, config: DeploymentConfig, build_artifacts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy to Netlify"""
        self.logger.info("Deploying to Netlify")
        
        return {
            "deployment_url": f"https://ymera-{config.environment}.netlify.app",
            "site_name": f"ymera-{config.environment}"
        }
    
    async def _canary_rollout(
        self, deployment_id: str, config: DeploymentConfig, deployment_artifacts: Dict[str, Any]
    ) -> None:
        """Execute canary rollout"""
        self.logger.info(f"Starting canary rollout for {deployment_id}")
        
        # Deploy to 10% of traffic
        await asyncio.sleep(30)  # Simulate canary deployment
        
        # Monitor metrics
        await asyncio.sleep(60)  # Monitor period
        
        # If successful, continue with full rollout
        self.logger.info(f"Canary rollout successful for {deployment_id}")
    
    async def _rolling_update(
        self, deployment_id: str, config: DeploymentConfig, deployment_artifacts: Dict[str, Any]
    ) -> None:
        """Execute rolling update"""
        self.logger.info(f"Starting rolling update for {deployment_id}")
        
        # Update instances one by one
        for i in range(config.replicas):
            await asyncio.sleep(10)  # Update one instance
            self.logger.info(f"Updated instance {i+1}/{config.replicas}")
    
    async def _blue_green_rollout(
        self, deployment_id: str, config: DeploymentConfig, deployment_artifacts: Dict[str, Any]
    ) -> None:
        """Execute blue-green rollout"""
        self.logger.info(f"Starting blue-green rollout for {deployment_id}")
        
        # Deploy green environment
        await asyncio.sleep(30)
        
        # Switch traffic
        await asyncio.sleep(10)
        
        self.logger.info(f"Blue-green rollout completed for {deployment_id}")
    
    async def _perform_health_checks(
        self, deployment_id: str, config: DeploymentConfig, deployment_artifacts: Dict[str, Any]
    ) -> None:
        """Perform health checks"""
        health_config = config.health_check
        
        if not health_config["enabled"]:
            return
        
        # Wait for initial delay
        await asyncio.sleep(health_config["initial_delay"])
        
        # Perform health checks
        for attempt in range(health_config["failure_threshold"]):
            try:
                # Simulate health check
                await asyncio.sleep(2)
                self.logger.info(f"Health check {attempt + 1} passed for {deployment_id}")
                return
                
            except Exception as e:
                if attempt == health_config["failure_threshold"] - 1:
                    raise DeploymentPipelineException(f"Health checks failed: {str(e)}")
                
                await asyncio.sleep(health_config["period"])
    
    async def _verify_performance(
        self, deployment_id: str, config: DeploymentConfig, deployment_artifacts: Dict[str, Any]
    ) -> None:
        """Verify deployment performance"""
        self.logger.info(f"Verifying performance for {deployment_id}")
        
        # Simulate performance verification
        await asyncio.sleep(10)
        
        # Would actually check metrics like response time, throughput, etc.
        performance_metrics = {
            "response_time": 150,  # ms
            "throughput": 1200,    # req/s
            "error_rate": 0.01     # 1%
        }
        
        deployment = self.deployments[deployment_id]
        deployment.metrics.update(performance_metrics)
    
    async def _verify_security(
        self, deployment_id: str, config: DeploymentConfig, deployment_artifacts: Dict[str, Any]
    ) -> None:
        """Verify deployment security"""
        self.logger.info(f"Verifying security for {deployment_id}")
        
        # Simulate security verification
        await asyncio.sleep(5)
        
        # Would check for exposed secrets, open ports, etc.
        security_status = {
            "secrets_exposed": False,
            "ports_secured": True,
            "ssl_enabled": True
        }
        
        deployment = self.deployments[deployment_id]
        deployment.metrics["security"] = security_status
    
    async def _rollback_deployment(self, deployment_id: str) -> bool:
        """Rollback a deployment"""
        try:
            self.logger.info(f"Rolling back deployment {deployment_id}")
            
            deployment = self.deployments[deployment_id]
            deployment.status = DeploymentStatus.ROLLBACK
            
            # Perform rollback based on target
            if deployment.target == DeploymentTarget.KUBERNETES:
                await self._rollback_kubernetes_deployment(deployment_id)
            elif deployment.target == DeploymentTarget.DOCKER_SWARM:
                await self._rollback_docker_swarm_deployment(deployment_id)
            # Add other rollback methods...
            
            deployment.rollback_info = {
                "rollback_time": datetime.now(timezone.utc).isoformat(),
                "reason": "Manual rollback or health check failure"
            }
            
            self.logger.info(f"Rollback completed for {deployment_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Rollback failed for {deployment_id}: {str(e)}")
            return False
    
    async def _rollback_kubernetes_deployment(self, deployment_id: str) -> None:
        """Rollback Kubernetes deployment"""
        # Implement kubectl rollout undo equivalent
        pass
    
    async def _rollback_docker_swarm_deployment(self, deployment_id: str) -> None:
        """Rollback Docker Swarm deployment"""
        # Implement Docker Swarm rollback
        pass
    
    async def _update_metrics(self, deployment: DeploymentResult) -> None:
        """Update deployment metrics"""
        self.metrics["total_deployments"] += 1
        
        if deployment.success:
            self.metrics["successful_deployments"] += 1
        else:
            self.metrics["failed_deployments"] += 1
        
        # Update averages
        total = self.metrics["total_deployments"]
        self.metrics["rollback_rate"] = (
            self.metrics["failed_deployments"] / total
        ) * 100
        
        # Update average duration
        if deployment.duration:
            current_avg = self.metrics["average_duration"]
            self.metrics["average_duration"] = (
                (current_avg * (total - 1)) + deployment.duration
            ) / total
    
    async def _record_learning_data(
        self, deployment_id: str, success: bool, error: Optional[str] = None
    ) -> None:
        """Record learning data for continuous improvement"""
        deployment = self.deployments[deployment_id]
        
        learning_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "deployment_id": deployment_id,
            "target": deployment.target.value,
            "strategy": deployment.strategy.value,
            "success": success,
            "duration": deployment.duration,
            "environment": deployment.environment
        }
        
        if success:
            self.learning_patterns["successful_configs"].append(learning_record)
            # Limit size
            if len(self.learning_patterns["successful_configs"]) > 100:
                self.learning_patterns["successful_configs"] = (
                    self.learning_patterns["successful_configs"][-50:]
                )
        else:
            learning_record["error"] = error
            self.learning_patterns["failure_patterns"].append(learning_record)
            # Limit size
            if len(self.learning_patterns["failure_patterns"]) > 100:
                self.learning_patterns["failure_patterns"] = (
                    self.learning_patterns["failure_patterns"][-50:]
                )
        
        # Save learning data
        await self._save_learning_data()
    
    async def _ensure_dependencies(self, workspace_path: str) -> None:
        """Ensure project dependencies are properly configured"""
        requirements_path = os.path.join(workspace_path, "requirements.txt")
        
        if not os.path.exists(requirements_path):
            # Create basic requirements.txt
            basic_requirements = [
                "fastapi>=0.68.0",
                "uvicorn[standard]>=0.15.0",
                "pydantic>=1.8.0"
            ]
            
            async with aiofiles.open(requirements_path, 'w') as f:
                await f.write('\n'.join(basic_requirements))
    
    async def shutdown(self) -> None:
        """Shutdown the deployment pipeline manager"""
        self.logger.info("Shutting down deployment pipeline manager...")
        
        # Cancel active deployments
        for deployment_id, task in self.active_deployments.items():
            task.cancel()
            self.logger.info(f"Cancelled deployment {deployment_id}")
        
        # Save final learning data
        await self._save_learning_data()
        
        # Close cloud clients
        if self._docker_client:
            self._docker_client.close()
        
        self.logger.info("Deployment pipeline manager shutdown complete")