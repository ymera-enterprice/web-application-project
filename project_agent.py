"""
YMERA Enterprise Multi-Agent System v3.0
Project Agent - Enterprise Project Management & Structure
Production-Ready Agent for Project Lifecycle Management
"""

import asyncio
import json
import uuid
import os
import shutil
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from pathlib import Path
import aiofiles
import yaml
import toml
import subprocess
from git import Repo, GitCommandError
from github import Github
import tempfile
import zipfile
import tarfile

from base_agent import BaseAgent, AgentStatus, TaskPriority, ExecutionResult
from sqlalchemy import Column, String, DateTime, JSON, Integer, Text, Boolean, Float
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, validator

logger = structlog.get_logger()

class ProjectType(Enum):
    WEB_APPLICATION = "web_application"
    API_SERVICE = "api_service"
    DESKTOP_APPLICATION = "desktop_application"
    MOBILE_APPLICATION = "mobile_application"
    MICROSERVICE = "microservice"
    LIBRARY = "library"
    DATA_PIPELINE = "data_pipeline"
    AI_MODEL = "ai_model"
    INFRASTRUCTURE = "infrastructure"
    DOCUMENTATION = "documentation"

class ProjectStatus(Enum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    FAILED = "failed"

class TechnologyStack(Enum):
    PYTHON_FASTAPI = "python_fastapi"
    PYTHON_DJANGO = "python_django"
    PYTHON_FLASK = "python_flask"
    NODE_EXPRESS = "node_express"
    NODE_NEXTJS = "node_nextjs"
    REACT = "react"
    VUE = "vue"
    ANGULAR = "angular"
    DOTNET = "dotnet"
    JAVA_SPRING = "java_spring"
    GO = "go"
    RUST = "rust"
    CPP = "cpp"
    FLUTTER = "flutter"
    REACT_NATIVE = "react_native"

@dataclass
class ProjectConfiguration:
    """Complete project configuration"""
    name: str
    description: str
    project_type: ProjectType
    technology_stack: TechnologyStack
    version: str = "1.0.0"
    license: str = "MIT"
    author: str = ""
    repository_url: str = ""
    dependencies: List[str] = None
    dev_dependencies: List[str] = None
    scripts: Dict[str, str] = None
    environment_variables: Dict[str, str] = None
    deployment_config: Dict[str, Any] = None
    testing_framework: str = "pytest"
    ci_cd_enabled: bool = True
    monitoring_enabled: bool = True
    documentation_enabled: bool = True

@dataclass
class ProjectStructure:
    """Project directory structure definition"""
    base_path: str
    directories: List[str]
    files: Dict[str, str]  # filename -> template/content
    templates: Dict[str, str]  # template_name -> template_path

class ProjectAgent(BaseAgent):
    """
    Enterprise Project Management Agent
    Handles project creation, structure management, and lifecycle operations
    """
    
    def __init__(self, agent_id: str = None):
        super().__init__(
            agent_id=agent_id or f"project_{uuid.uuid4().hex[:8]}",
            agent_type="project",
            capabilities=[
                "project_creation",
                "structure_management",
                "dependency_management",
                "version_control",
                "configuration_management",
                "template_management",
                "project_analysis",
                "migration_support",
                "deployment_preparation"
            ]
        )
        
        self.active_projects: Dict[str, ProjectConfiguration] = {}
        self.project_templates: Dict[str, Dict[str, Any]] = {}
        self.github_client: Optional[Github] = None
        self.workspace_path = Path(os.getenv("WORKSPACE_PATH", "./workspace"))
        
        # Project statistics
        self.project_stats = {
            "total_projects_created": 0,
            "active_projects_count": 0,
            "successful_deployments": 0,
            "template_usage": {},
            "technology_usage": {},
            "average_project_size": 0
        }
        
        logger.info("Project Agent initialized", agent_id=self.agent_id)

    async def initialize(self) -> bool:
        """Initialize project agent with enterprise capabilities"""
        try:
            await super().initialize()
            
            # Initialize GitHub client
            github_token = os.getenv("GITHUB_TOKEN")
            if github_token:
                self.github_client = Github(github_token)
                logger.info("GitHub integration initialized")
            
            # Setup workspace
            await self._setup_workspace()
            
            # Load project templates
            await self._load_project_templates()
            
            # Load existing projects
            await self._load_existing_projects()
            
            logger.info("Project Agent fully initialized",
                       workspace_path=str(self.workspace_path),
                       templates_loaded=len(self.project_templates))
            return True
            
        except Exception as e:
            logger.error("Failed to initialize Project Agent", error=str(e))
            return False

    async def _setup_workspace(self):
        """Setup project workspace directory"""
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Create standard workspace directories
        workspace_dirs = [
            "projects",
            "templates", 
            "archives",
            "backups",
            "temp"
        ]
        
        for dir_name in workspace_dirs:
            (self.workspace_path / dir_name).mkdir(exist_ok=True)

    async def _load_project_templates(self):
        """Load predefined project templates"""
        self.project_templates = {
            "python_fastapi_api": {
                "name": "FastAPI REST API",
                "type": ProjectType.API_SERVICE,
                "tech_stack": TechnologyStack.PYTHON_FASTAPI,
                "structure": {
                    "directories": [
                        "app",
                        "app/api",
                        "app/api/v1",
                        "app/core",
                        "app/models",
                        "app/schemas",
                        "app/services",
                        "app/utils",
                        "tests",
                        "tests/api",
                        "tests/unit",
                        "docs",
                        "scripts",
                        "deployment"
                    ],
                    "files": {
                        "main.py": "fastapi_main_template",
                        "requirements.txt": "fastapi_requirements_template",
                        "app/__init__.py": "empty_file",
                        "app/api/__init__.py": "empty_file",
                        "app/api/v1/__init__.py": "empty_file",
                        "app/api/v1/endpoints.py": "fastapi_endpoints_template",
                        "app/core/config.py": "fastapi_config_template",
                        "app/core/security.py": "fastapi_security_template",
                        "app/models/__init__.py": "empty_file",
                        "app/schemas/__init__.py": "empty_file",
                        "app/services/__init__.py": "empty_file",
                        "Dockerfile": "fastapi_dockerfile_template",
                        "docker-compose.yml": "fastapi_docker_compose_template",
                        "README.md": "fastapi_readme_template",
                        ".gitignore": "python_gitignore_template",
                        "pytest.ini": "pytest_config_template",
                        ".github/workflows/ci.yml": "github_actions_python_template"
                    }
                },
                "dependencies": [
                    "fastapi>=0.104.0",
                    "uvicorn[standard]>=0.24.0",
                    "pydantic>=2.4.0",
                    "sqlalchemy>=2.0.0",
                    "alembic>=1.12.0",
                    "redis>=5.0.0",
                    "celery>=5.3.0",
                    "python-jose[cryptography]>=3.3.0",
                    "passlib[bcrypt]>=1.7.4",
                    "python-multipart>=0.0.6",
                    "email-validator>=2.1.0"
                ],
                "dev_dependencies": [
                    "pytest>=7.4.0",
                    "pytest-asyncio>=0.21.0",
                    "httpx>=0.25.0",
                    "black>=23.9.0",
                    "flake8>=6.1.0",
                    "mypy>=1.6.0",
                    "pre-commit>=3.4.0"
                ]
            },
            
            "react_web_app": {
                "name": "React Web Application",
                "type": ProjectType.WEB_APPLICATION,
                "tech_stack": TechnologyStack.REACT,
                "structure": {
                    "directories": [
                        "src",
                        "src/components",
                        "src/pages",
                        "src/hooks",
                        "src/services",
                        "src/utils",
                        "src/styles",
                        "src/assets",
                        "src/context",
                        "public",
                        "tests",
                        "__tests__",
                        "docs"
                    ],
                    "files": {
                        "package.json": "react_package_template",
                        "src/index.js": "react_index_template",
                        "src/App.js": "react_app_template",
                        "src/App.css": "react_app_css_template",
                        "public/index.html": "react_html_template",
                        "README.md": "react_readme_template",
                        ".gitignore": "node_gitignore_template",
                        "Dockerfile": "react_dockerfile_template",
                        ".github/workflows/ci.yml": "github_actions_node_template"
                    }
                }
            },
            
            "microservice_template": {
                "name": "Enterprise Microservice",
                "type": ProjectType.MICROSERVICE,
                "tech_stack": TechnologyStack.PYTHON_FASTAPI,
                "structure": {
                    "directories": [
                        "src",
                        "src/api",
                        "src/core",
                        "src/models",
                        "src/services",
                        "src/utils",
                        "src/middleware",
                        "tests",
                        "tests/integration",
                        "tests/unit",
                        "config",
                        "scripts",
                        "deployment",
                        "monitoring",
                        "docs"
                    ],
                    "files": {
                        "src/main.py": "microservice_main_template",
                        "requirements.txt": "microservice_requirements_template",
                        "Dockerfile": "microservice_dockerfile_template",
                        "docker-compose.yml": "microservice_compose_template",
                        "k8s-deployment.yml": "kubernetes_deployment_template",
                        "config/settings.py": "microservice_config_template",
                        "monitoring/prometheus.yml": "prometheus_config_template",
                        "README.md": "microservice_readme_template"
                    }
                }
            }
        }

    async def create_project(self, 
                           project_name: str,
                           project_config: ProjectConfiguration,
                           template_name: Optional[str] = None,
                           github_repo: bool = True) -> str:
        """Create new project with full enterprise setup"""
        
        try:
            project_id = f"proj_{uuid.uuid4().hex[:12]}"
            project_path = self.workspace_path / "projects" / project_name
            
            logger.info("Creating new project", 
                       project_id=project_id,
                       project_name=project_name,
                       template=template_name)
            
            # Validate project configuration
            await self._validate_project_config(project_config)
            
            # Create project directory structure
            if template_name and template_name in self.project_templates:
                template = self.project_templates[template_name]
                await self._create_from_template(project_path, template, project_config)
            else:
                await self._create_custom_project(project_path, project_config)
            
            # Initialize version control
            await self._initialize_git_repo(project_path)
            
            # Setup project configuration files
            await self._generate_config_files(project_path, project_config)
            
            # Install dependencies
            await self._setup_dependencies(project_path, project_config)
            
            # Setup CI/CD pipeline
            if project_config.ci_cd_enabled:
                await self._setup_ci_cd(project_path, project_config)
            
            # Setup monitoring
            if project_config.monitoring_enabled:
                await self._setup_monitoring(project_path, project_config)
            
            # Create GitHub repository if requested
            if github_repo and self.github_client:
                repo_url = await self._create_github_repo(project_name, project_config)
                project_config.repository_url = repo_url
            
            # Generate documentation
            if project_config.documentation_enabled:
                await self._generate_documentation(project_path, project_config)
            
            # Store project configuration
            self.active_projects[project_id] = project_config
            
            # Update statistics
            self.project_stats["total_projects_created"] += 1
            self.project_stats["active_projects_count"] += 1
            
            template_key = template_name or "custom"
            self.project_stats["template_usage"][template_key] = \
                self.project_stats["template_usage"].get(template_key, 0) + 1
            
            tech_stack = project_config.technology_stack.value
            self.project_stats["technology_usage"][tech_stack] = \
                self.project_stats["technology_usage"].get(tech_stack, 0) + 1
            
            logger.info("Project created successfully", 
                       project_id=project_id,
                       project_path=str(project_path),
                       github_repo=project_config.repository_url is not None)
            
            return project_id
            
        except Exception as e:
            logger.error("Failed to create project", 
                        project_name=project_name,
                        error=str(e))
            raise

    async def _validate_project_config(self, config: ProjectConfiguration):
        """Validate project configuration"""
        
        if not config.name or not config.name.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Invalid project name")
        
        if len(config.name) > 100:
            raise ValueError("Project name too long")
        
        if not config.description:
            raise ValueError("Project description is required")
        
        # Validate dependencies format
        if config.dependencies:
            for dep in config.dependencies:
                if not isinstance(dep, str) or not dep.strip():
                    raise ValueError(f"Invalid dependency: {dep}")

    async def _create_from_template(self, 
                                  project_path: Path, 
                                  template: Dict[str, Any], 
                                  config: ProjectConfiguration):
        """Create project from template"""
        
        # Create directories
        for directory in template["structure"]["directories"]:
            (project_path / directory).mkdir(parents=True, exist_ok=True)
        
        # Create files from templates
        for file_path, template_name in template["structure"]["files"].items():
            file_full_path = project_path / file_path
            file_full_path.parent.mkdir(parents=True, exist_ok=True)
            
            content = await self._generate_file_content(template_name, config)
            
            async with aiofiles.open(file_full_path, 'w') as f:
                await f.write(content)

    async def _generate_file_content(self, template_name: str, config: ProjectConfiguration) -> str:
        """Generate file content from template"""
        
        templates = {
            "empty_file": "",
            
            "fastapi_main_template": f'''"""
{config.name} - FastAPI Application
{config.description}
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.endpoints import router as api_router

app = FastAPI(
    title="{config.name}",
    description="{config.description}",
    version="{config.version}"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {{"message": "Welcome to {config.name}", "version": "{config.version}"}}

@app.get("/health")
async def health_check():
    return {{"status": "healthy", "service": "{config.name}"}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
''',
            
            "fastapi_requirements_template": '\n'.join([
                "fastapi>=0.104.0",
                "uvicorn[standard]>=0.24.0",
                "pydantic>=2.4.0",
                "sqlalchemy>=2.0.0",
                "alembic>=1.12.0",
                "redis>=5.0.0",
                "python-jose[cryptography]>=3.3.0",
                "passlib[bcrypt]>=1.7.4",
                "python-multipart>=0.0.6",
                "email-validator>=2.1.0"
            ] + (config.dependencies or [])),
            
            "fastapi_dockerfile_template": f'''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
''',
            
            "fastapi_readme_template": f'''# {config.name}

{config.description}

## Features

- FastAPI framework
- Async/await support
- Automatic API documentation
- Pydantic data validation
- SQLAlchemy ORM
- JWT authentication
- Redis caching
- Docker support
- CI/CD pipeline

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
uvicorn main:app --reload
```

3. Open your browser to http://localhost:8000

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testing

```bash
pytest
```

## License

{config.license}
''',
            
            "python_gitignore_template": '''# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# PyInstaller
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
.hypothesis/
.pytest_cache/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
target/

# Jupyter Notebook
.ipynb_checkpoints

# pyenv
.python-version

# celery beat schedule file
celerybeat-schedule

# SageMath parsed files
*.sage.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json
''',
            
            "github_actions_python_template": f'''name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        pytest --cov=./ --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3

  build:
    needs: test
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build Docker image
      run: |
        docker build -t {config.name.lower()}:latest .
'''
        }
        
        return templates.get(template_name, f"# Generated file for {template_name}")

    async def _initialize_git_repo(self, project_path: Path):
        """Initialize Git repository"""
        try:
            repo = Repo.init(project_path)
            
            # Create initial commit
            repo.index.add(["."])
            repo.index.commit("Initial project setup")
            
            logger.info("Git repository initialized", project_path=str(project_path))
            
        except Exception as e:
            logger.error("Failed to initialize Git repository", error=str(e))
            raise

    async def _generate_config_files(self, project_path: Path, config: ProjectConfiguration):
        """Generate project configuration files"""
        
        # Create project metadata file
        project_meta = {
            "name": config.name,
            "description": config.description,
            "version": config.version,
            "type": config.project_type.value,
            "technology_stack": config.technology_stack.value,
            "created_at": datetime.utcnow().isoformat(),
            "license": config.license,
            "author": config.author
        }
        
        async with aiofiles.open(project_path / "project.json", 'w') as f:
            await f.write(json.dumps(project_meta, indent=2))
        
        # Create environment configuration
        if config.environment_variables:
            env_content = '\n'.join([
                f"{key}={value}" 
                for key, value in config.environment_variables.items()
            ])
            
            async with aiofiles.open(project_path / ".env.example", 'w') as f:
                await f.write(env_content)

    async def _setup_dependencies(self, project_path: Path, config: ProjectConfiguration):
        """Setup project dependencies"""
        
        try:
            if config.technology_stack in [TechnologyStack.PYTHON_FASTAPI, 
                                         TechnologyStack.PYTHON_DJANGO, 
                                         TechnologyStack.PYTHON_FLASK]:
                # Create virtual environment
                venv_path = project_path / "venv"
                subprocess.run([
                    "python", "-m", "venv", str(venv_path)
                ], check=True)
                
                # Install dependencies
                if (project_path / "requirements.txt").exists():
                    pip_executable = venv_path / "bin" / "pip" if os.name != "nt" else venv_path / "Scripts" / "pip.exe"
                    subprocess.run([
                        str(pip_executable), "install", "-r", "requirements.txt"
                    ], cwd=project_path, check=True)
                
            elif config.technology_stack in [TechnologyStack.NODE_EXPRESS, 
                                           TechnologyStack.NODE_NEXTJS,
                                           TechnologyStack.REACT]:
                # Install npm dependencies
                if (project_path / "package.json").exists():
                    subprocess.run(["npm", "install"], cwd=project_path, check=True)
            
            logger.info("Dependencies setup completed", project_path=str(project_path))
            
        except subprocess.CalledProcessError as e:
            logger.error("Failed to setup dependencies", error=str(e))
            # Don't raise - dependencies can be installed manually

    async def _create_github_repo(self, project_name: str, config: ProjectConfiguration) -> str:
        """Create GitHub repository"""
        
        try:
            if not self.github_client:
                raise Exception("GitHub client not initialized")
            
            user = self.github_client.get_user()
            
            # Create repository
            repo = user.create_repo(
                name=project_name,
                description=config.description,
                private=False,
                auto_init=False
            )
            
            logger.info("GitHub repository created", 
                       repo_name=project_name,
                       repo_url=repo.html_url)
            
            return repo.html_url
            
        except Exception as e:
            logger.error("Failed to create GitHub repository", error=str(e))
            return ""

    async def _setup_ci_cd(self, project_path: Path, config: ProjectConfiguration):
        """Setup CI/CD pipeline"""
        
        github_workflows_path = project_path / ".github" / "workflows"
        github_workflows_path.mkdir(parents=True, exist_ok=True)
        
        # CI/CD pipeline is already created in templates
        logger.info("CI/CD pipeline setup completed", project_path=str(project_path))

    async def _setup_monitoring(self, project_path: Path, config: ProjectConfiguration):
        """Setup monitoring and observability"""
        
        monitoring_path = project_path / "monitoring"
        monitoring_path.mkdir(exist_ok=True)
        
        # Create basic monitoring configuration
        monitoring_config = {
            "prometheus": {
                "enabled": True,
                "port": 9090
            },
            "grafana": {
                "enabled": True,
                "port": 3000
            },
            "logging": {
                "level": "INFO",
                "format": "json"
            }
        }
        
        async with aiofiles.open(monitoring_path / "config.yml", 'w') as f:
            await f.write(yaml.dump(monitoring_config, indent=2))

    async def _generate_documentation(self, project_path: Path, config: ProjectConfiguration):
        """Generate project documentation"""
        
        docs_path = project_path / "docs"
        docs_path.mkdir(exist_ok=True)
        
        # API documentation
        api_docs = f'''# {config.name} API Documentation

## Overview
{config.description}

## Architecture
This project follows enterprise-grade architecture patterns:

- **API Layer**: RESTful API endpoints
- **Business Logic**: Service layer with business rules
- **Data Layer**: Database models and repositories
- **Security**: Authentication and authorization
- **Monitoring**: Logging and metrics collection

## Endpoints

### Health Check
- `GET /health` - Service health status
- `GET /` - Welcome message

## Authentication
JWT-based authentication is implemented for secure API access.

## Error Handling
Standardized error responses with proper HTTP status codes.

## Testing
Comprehensive test suite with unit and integration tests.
'''
        
        async with aiofiles.open(docs_path / "api.md", 'w') as f:
            await f.write(api_docs)
        
        # Deployment documentation
        deploy_docs = f'''# {config.name} Deployment Guide

## Docker Deployment

1. Build the image:
```bash
docker build -t {config.name.lower()} .
```

2. Run the container:
```bash
docker run -p 8000:8000 {config.name.lower()}
```

## Kubernetes Deployment

Apply the Kubernetes manifests:
```bash
kubectl apply -f k8s-deployment.yml
```

## Environment Variables

Configure the following environment variables:
- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection string
- `JWT_SECRET_KEY`: JWT signing key

## Monitoring

The application includes built-in monitoring:
- Prometheus metrics at `/metrics`
- Health checks at `/health`
- Structured logging
'''
        
        async with aiofiles.open(docs_path / "deployment.md", 'w') as f:
            await f.write(deploy_docs)

    async def analyze_project(self, project_id: str) -> Dict[str, Any]:
        """Analyze existing project structure and health"""
        
        if project_id not in self.active_projects:
            raise ValueError(f"Project {project_id} not found")
        
        config = self.active_projects[project_id]
        project_path = self.workspace_path / "projects" / config.name
        
        try:
            analysis = {
                "project_id": project_id,
                "name": config.name,
                "type": config.project_type.value,
                "technology_stack": config.technology_stack.value,
                "structure_analysis": await self._analyze_structure(project_path),
                "code_quality": await self._analyze_code_quality(project_path, config),
                "dependencies": await self._analyze_dependencies(project_path, config),
                "security": await self._analyze_security(project_path, config),
                "performance": await self._analyze_performance(project_path, config),
                "recommendations": []
            }
            
            # Generate recommendations based on analysis
            analysis["recommendations"] = await self._generate_recommendations(analysis)
            
            logger.info("Project analysis completed", 
                       project_id=project_id,
                       recommendations_count=len(analysis["recommendations"]))
            
            return analysis
            
        except Exception as e:
            logger.error("Project analysis failed", 
                        project_id=project_id,
                        error=str(e))
            raise

    async def _analyze_structure(self, project_path: Path) -> Dict[str, Any]:
        """Analyze project structure"""
        
        structure_info = {
            "total_files": 0,
            "total_directories": 0,
            "file_types": {},
            "largest_files": [],
            "empty_directories": [],
            "missing_standard_files": []
        }
        
        if not project_path.exists():
            return structure_info
        
        # Walk through project directory
        for item in project_path.rglob("*"):
            if item.is_file():
                structure_info["total_files"] += 1
                
                # Count file types file_ext = item.suffix.lower()
                structure_info["file_types"][file_ext] = structure_info["file_types"].get(file_ext, 0) + 1
                
                # Track largest files
                file_size = item.stat().st_size
                structure_info["largest_files"].append({
                    "name": str(item.relative_to(project_path)),
                    "size": file_size
                })
            
            elif item.is_dir():
                structure_info["total_directories"] += 1
                
                # Check for empty directories
                if not any(item.iterdir()):
                    structure_info["empty_directories"].append(str(item.relative_to(project_path)))
        
        # Sort largest files
        structure_info["largest_files"] = sorted(
            structure_info["largest_files"], 
            key=lambda x: x["size"], 
            reverse=True
        )[:10]
        
        # Check for standard files
        standard_files = ["README.md", ".gitignore", "LICENSE", "requirements.txt", "package.json"]
        for std_file in standard_files:
            if not (project_path / std_file).exists():
                structure_info["missing_standard_files"].append(std_file)
        
        return structure_info

    async def _analyze_code_quality(self, project_path: Path, config: ProjectConfiguration) -> Dict[str, Any]:
        """Analyze code quality metrics"""
        
        quality_metrics = {
            "lines_of_code": 0,
            "complexity_score": 0,
            "test_coverage": 0,
            "code_duplication": 0,
            "linting_issues": [],
            "documentation_coverage": 0
        }
        
        try:
            # Count lines of code
            code_extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp", ".c"}
            
            for file_path in project_path.rglob("*"):
                if file_path.suffix.lower() in code_extensions:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            # Count non-empty, non-comment lines
                            code_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
                            quality_metrics["lines_of_code"] += len(code_lines)
                    except:
                        continue
            
            # Run linting for Python projects
            if config.technology_stack in [TechnologyStack.PYTHON_FASTAPI, TechnologyStack.PYTHON_DJANGO, TechnologyStack.PYTHON_FLASK]:
                quality_metrics["linting_issues"] = await self._run_python_linting(project_path)
            
            # Calculate basic complexity score (simplified)
            quality_metrics["complexity_score"] = min(100, max(0, 100 - len(quality_metrics["linting_issues"]) * 5))
            
        except Exception as e:
            logger.warning("Code quality analysis incomplete", error=str(e))
        
        return quality_metrics

    async def _run_python_linting(self, project_path: Path) -> List[Dict[str, Any]]:
        """Run Python linting analysis"""
        
        issues = []
        
        try:
            # Simple static analysis - check for common issues
            for py_file in project_path.rglob("*.py"):
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                        for i, line in enumerate(lines, 1):
                            # Check line length
                            if len(line) > 120:
                                issues.append({
                                    "file": str(py_file.relative_to(project_path)),
                                    "line": i,
                                    "type": "line_too_long",
                                    "message": f"Line too long ({len(line)} characters)"
                                })
                            
                            # Check for unused imports (basic check)
                            if line.strip().startswith("import ") and "# noqa" not in line:
                                import_name = line.split()[1].split('.')[0]
                                if import_name not in content.replace(line, ""):
                                    issues.append({
                                        "file": str(py_file.relative_to(project_path)),
                                        "line": i,
                                        "type": "unused_import",
                                        "message": f"Potentially unused import: {import_name}"
                                    })
                
                except Exception:
                    continue
        
        except Exception:
            pass
        
        return issues[:50]  # Limit to 50 issues

    async def _analyze_dependencies(self, project_path: Path, config: ProjectConfiguration) -> Dict[str, Any]:
        """Analyze project dependencies"""
        
        deps_analysis = {
            "total_dependencies": 0,
            "outdated_dependencies": [],
            "security_vulnerabilities": [],
            "license_conflicts": [],
            "dependency_tree_depth": 0,
            "unused_dependencies": []
        }
        
        try:
            # Python dependencies
            if (project_path / "requirements.txt").exists():
                async with aiofiles.open(project_path / "requirements.txt", 'r') as f:
                    requirements = await f.read()
                    deps_analysis["total_dependencies"] = len([
                        line for line in requirements.split('\n') 
                        if line.strip() and not line.startswith('#')
                    ])
            
            # Node.js dependencies
            elif (project_path / "package.json").exists():
                async with aiofiles.open(project_path / "package.json", 'r') as f:
                    package_data = json.loads(await f.read())
                    deps_analysis["total_dependencies"] = len(
                        package_data.get("dependencies", {})
                    ) + len(package_data.get("devDependencies", {}))
        
        except Exception as e:
            logger.warning("Dependencies analysis incomplete", error=str(e))
        
        return deps_analysis

    async def _analyze_security(self, project_path: Path, config: ProjectConfiguration) -> Dict[str, Any]:
        """Analyze security aspects"""
        
        security_analysis = {
            "security_score": 85,  # Default good score
            "vulnerabilities": [],
            "security_headers": False,
            "authentication_implemented": False,
            "secrets_exposed": [],
            "https_enforced": False
        }
        
        try:
            # Check for exposed secrets in files
            secret_patterns = [
                r'password\s*=\s*["\'][^"\']+["\']',
                r'api_key\s*=\s*["\'][^"\']+["\']',
                r'secret_key\s*=\s*["\'][^"\']+["\']',
                r'token\s*=\s*["\'][^"\']+["\']'
            ]
            
            import re
            
            for file_path in project_path.rglob("*"):
                if file_path.suffix in ['.py', '.js', '.ts', '.env', '.config']:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                            for pattern in secret_patterns:
                                matches = re.findall(pattern, content, re.IGNORECASE)
                                if matches:
                                    security_analysis["secrets_exposed"].append({
                                        "file": str(file_path.relative_to(project_path)),
                                        "type": "potential_secret",
                                        "matches": len(matches)
                                    })
                    except:
                        continue
            
            # Check for authentication implementation
            auth_files = list(project_path.rglob("*auth*")) + list(project_path.rglob("*security*"))
            security_analysis["authentication_implemented"] = len(auth_files) > 0
            
            # Calculate security score
            score_deductions = len(security_analysis["secrets_exposed"]) * 10
            security_analysis["security_score"] = max(0, 85 - score_deductions)
        
        except Exception as e:
            logger.warning("Security analysis incomplete", error=str(e))
        
        return security_analysis

    async def _analyze_performance(self, project_path: Path, config: ProjectConfiguration) -> Dict[str, Any]:
        """Analyze performance aspects"""
        
        performance_analysis = {
            "performance_score": 80,
            "bottlenecks": [],
            "optimization_opportunities": [],
            "resource_usage": {
                "estimated_memory": "< 100MB",
                "estimated_cpu": "Low",
                "disk_space": 0
            },
            "caching_implemented": False,
            "database_optimization": False
        }
        
        try:
            # Calculate disk space usage
            total_size = sum(
                f.stat().st_size for f in project_path.rglob("*") if f.is_file()
            )
            performance_analysis["resource_usage"]["disk_space"] = total_size
            
            # Check for caching implementation
            cache_keywords = ["redis", "memcached", "cache", "lru_cache"]
            for file_path in project_path.rglob("*.py"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().lower()
                        if any(keyword in content for keyword in cache_keywords):
                            performance_analysis["caching_implemented"] = True
                            break
                except:
                    continue
            
            # Look for database optimization
            db_optimization_keywords = ["index", "optimize", "explain", "query_plan"]
            for file_path in project_path.rglob("*"):
                if file_path.suffix in ['.py', '.sql', '.js']:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read().lower()
                            if any(keyword in content for keyword in db_optimization_keywords):
                                performance_analysis["database_optimization"] = True
                                break
                    except:
                        continue
        
        except Exception as e:
            logger.warning("Performance analysis incomplete", error=str(e))
        
        return performance_analysis

    async def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate improvement recommendations based on analysis"""
        
        recommendations = []
        
        # Structure recommendations
        if analysis["structure_analysis"]["missing_standard_files"]:
            recommendations.append({
                "category": "structure",
                "priority": "high",
                "title": "Add Standard Project Files",
                "description": f"Missing standard files: {', '.join(analysis['structure_analysis']['missing_standard_files'])}",
                "action": "Create the missing standard files to improve project organization"
            })
        
        # Code quality recommendations
        if analysis["code_quality"]["linting_issues"]:
            recommendations.append({
                "category": "code_quality",
                "priority": "medium",
                "title": "Fix Code Quality Issues",
                "description": f"Found {len(analysis['code_quality']['linting_issues'])} linting issues",
                "action": "Run a linter and fix the identified issues"
            })
        
        # Security recommendations
        if analysis["security"]["secrets_exposed"]:
            recommendations.append({
                "category": "security",
                "priority": "critical",
                "title": "Remove Exposed Secrets",
                "description": "Potential secrets found in code files",
                "action": "Move secrets to environment variables or secure vaults"
            })
        
        if not analysis["security"]["authentication_implemented"]:
            recommendations.append({
                "category": "security",
                "priority": "high",
                "title": "Implement Authentication",
                "description": "No authentication system detected",
                "action": "Add user authentication and authorization"
            })
        
        # Performance recommendations
        if not analysis["performance"]["caching_implemented"]:
            recommendations.append({
                "category": "performance",
                "priority": "medium",
                "title": "Implement Caching",
                "description": "No caching mechanism detected",
                "action": "Add Redis or in-memory caching for better performance"
            })
        
        return recommendations

    async def migrate_project(self, 
                            project_id: str, 
                            target_tech_stack: TechnologyStack,
                            migration_options: Dict[str, Any] = None) -> str:
        """Migrate project to different technology stack"""
        
        if project_id not in self.active_projects:
            raise ValueError(f"Project {project_id} not found")
        
        try:
            source_config = self.active_projects[project_id]
            migration_id = f"migration_{uuid.uuid4().hex[:8]}"
            
            logger.info("Starting project migration",
                       project_id=project_id,
                       source_stack=source_config.technology_stack.value,
                       target_stack=target_tech_stack.value,
                       migration_id=migration_id)
            
            # Create migration plan
            migration_plan = await self._create_migration_plan(
                source_config, target_tech_stack, migration_options or {}
            )
            
            # Execute migration
            new_project_path = await self._execute_migration(
                source_config, target_tech_stack, migration_plan
            )
            
            # Update project configuration
            migrated_config = ProjectConfiguration(
                name=f"{source_config.name}_migrated",
                description=f"Migrated version of {source_config.description}",
                project_type=source_config.project_type,
                technology_stack=target_tech_stack,
                version=source_config.version,
                license=source_config.license,
                author=source_config.author
            )
            
            # Create new project entry
            new_project_id = await self.create_project(
                migrated_config.name,
                migrated_config,
                github_repo=False
            )
            
            logger.info("Project migration completed",
                       migration_id=migration_id,
                       new_project_id=new_project_id)
            
            return new_project_id
            
        except Exception as e:
            logger.error("Project migration failed",
                        project_id=project_id,
                        error=str(e))
            raise

    async def _create_migration_plan(self, 
                                   source_config: ProjectConfiguration,
                                   target_tech_stack: TechnologyStack,
                                   options: Dict[str, Any]) -> Dict[str, Any]:
        """Create detailed migration plan"""
        
        migration_mappings = {
            (TechnologyStack.PYTHON_FASTAPI, TechnologyStack.NODE_EXPRESS): {
                "file_mappings": {
                    "main.py": "app.js",
                    "requirements.txt": "package.json"
                },
                "dependency_mappings": {
                    "fastapi": "express",
                    "uvicorn": "nodemon",
                    "pydantic": "joi"
                }
            },
            (TechnologyStack.REACT, TechnologyStack.VUE): {
                "file_mappings": {
                    "App.js": "App.vue",
                    "index.js": "main.js"
                }
            }
        }
        
        mapping_key = (source_config.technology_stack, target_tech_stack)
        migration_mapping = migration_mappings.get(mapping_key, {})
        
        return {
            "source_stack": source_config.technology_stack.value,
            "target_stack": target_tech_stack.value,
            "file_mappings": migration_mapping.get("file_mappings", {}),
            "dependency_mappings": migration_mapping.get("dependency_mappings", {}),
            "manual_steps": migration_mapping.get("manual_steps", []),
            "estimated_effort": "medium",
            "compatibility_score": 85
        }

    async def _execute_migration(self, 
                               source_config: ProjectConfiguration,
                               target_tech_stack: TechnologyStack,
                               migration_plan: Dict[str, Any]) -> Path:
        """Execute the migration process"""
        
        # This is a simplified migration - in practice, this would involve
        # complex code transformation, dependency conversion, etc.
        
        source_path = self.workspace_path / "projects" / source_config.name
        target_path = self.workspace_path / "projects" / f"{source_config.name}_migrated"
        
        # Copy source to target
        shutil.copytree(source_path, target_path, dirs_exist_ok=True)
        
        # Apply file mappings
        for source_file, target_file in migration_plan["file_mappings"].items():
            source_file_path = target_path / source_file
            target_file_path = target_path / target_file
            
            if source_file_path.exists():
                source_file_path.rename(target_file_path)
        
        return target_path

    async def export_project(self, 
                           project_id: str, 
                           export_format: str = "zip",
                           include_dependencies: bool = False) -> str:
        """Export project as archive"""
        
        if project_id not in self.active_projects:
            raise ValueError(f"Project {project_id} not found")
        
        try:
            config = self.active_projects[project_id]
            project_path = self.workspace_path / "projects" / config.name
            export_path = self.workspace_path / "exports" / f"{config.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Create exports directory
            export_path.parent.mkdir(exist_ok=True)
            
            if export_format.lower() == "zip":
                archive_path = f"{export_path}.zip"
                with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in project_path.rglob("*"):
                        if file_path.is_file():
                            # Skip certain files
                            if any(skip in str(file_path) for skip in ["__pycache__", ".git", "node_modules", "venv"]):
                                continue
                            
                            arcname = file_path.relative_to(project_path)
                            zipf.write(file_path, arcname)
            
            elif export_format.lower() == "tar":
                archive_path = f"{export_path}.tar.gz"
                with tarfile.open(archive_path, "w:gz") as tar:
                    tar.add(project_path, arcname=config.name, 
                           exclude=lambda path: any(skip in path for skip in ["__pycache__", ".git", "node_modules", "venv"]))
            
            logger.info("Project exported successfully",
                       project_id=project_id,
                       archive_path=archive_path,
                       format=export_format)
            
            return archive_path
            
        except Exception as e:
            logger.error("Project export failed",
                        project_id=project_id,
                        error=str(e))
            raise

    async def import_project(self, archive_path: str, project_name: str = None) -> str:
        """Import project from archive"""
        
        try:
            import_id = f"import_{uuid.uuid4().hex[:8]}"
            
            # Extract archive
            temp_dir = tempfile.mkdtemp()
            
            if archive_path.endswith('.zip'):
                with zipfile.ZipFile(archive_path, 'r') as zipf:
                    zipf.extractall(temp_dir)
            elif archive_path.endswith(('.tar', '.tar.gz')):
                with tarfile.open(archive_path, 'r:*') as tar:
                    tar.extractall(temp_dir)
            
            # Find project configuration
            extracted_contents = list(Path(temp_dir).iterdir())
            if len(extracted_contents) == 1 and extracted_contents[0].is_dir():
                project_source = extracted_contents[0]
            else:
                project_source = Path(temp_dir)
            
            # Try to load project configuration
            project_config_path = project_source / "project.json"
            if project_config_path.exists():
                async with aiofiles.open(project_config_path, 'r') as f:
                    project_data = json.loads(await f.read())
                
                config = ProjectConfiguration(
                    name=project_name or project_data["name"],
                    description=project_data["description"],
                    project_type=ProjectType(project_data["type"]),
                    technology_stack=TechnologyStack(project_data["technology_stack"]),
                    version=project_data.get("version", "1.0.0"),
                    license=project_data.get("license", "MIT"),
                    author=project_data.get("author", "")
                )
            else:
                # Create default configuration
                config = ProjectConfiguration(
                    name=project_name or "imported_project",
                    description="Imported project",
                    project_type=ProjectType.WEB_APPLICATION,
                    technology_stack=TechnologyStack.PYTHON_FASTAPI
                )
            
            # Copy to workspace
            target_path = self.workspace_path / "projects" / config.name
            shutil.copytree(project_source, target_path, dirs_exist_ok=True)
            
            # Create project entry
            project_id = f"proj_{uuid.uuid4().hex[:12]}"
            self.active_projects[project_id] = config
            
            # Cleanup
            shutil.rmtree(temp_dir)
            
            logger.info("Project imported successfully",
                       import_id=import_id,
                       project_id=project_id,
                       project_name=config.name)
            
            return project_id
            
        except Exception as e:
            logger.error("Project import failed",
                        archive_path=archive_path,
                        error=str(e))
            raise

    async def get_project_status(self, project_id: str) -> Dict[str, Any]:
        """Get comprehensive project status"""
        
        if project_id not in self.active_projects:
            raise ValueError(f"Project {project_id} not found")
        
        config = self.active_projects[project_id]
        project_path = self.workspace_path / "projects" / config.name
        
        status = {
            "project_id": project_id,
            "name": config.name,
            "type": config.project_type.value,
            "technology_stack": config.technology_stack.value,
            "version": config.version,
            "status": ProjectStatus.ACTIVE.value,
            "created_at": "N/A",
            "last_modified": "N/A",
            "size": 0,
            "files_count": 0,
            "git_status": {},
            "health_score": 85
        }
        
        if project_path.exists():
            # Get project statistics
            all_files = list(project_path.rglob("*"))
            status["files_count"] = len([f for f in all_files if f.is_file()])
            status["size"] = sum(f.stat().st_size for f in all_files if f.is_file())
            
            # Get git status
            try:
                repo = Repo(project_path)
                status["git_status"] = {
                    "branch": repo.active_branch.name,
                    "commits": repo.git.rev_list('--count', 'HEAD'),
                    "modified_files": len(repo.git.diff('HEAD', name_only=True).split('\n')) if repo.git.diff('HEAD', name_only=True) else 0,
                    "untracked_files": len(repo.untracked_files)
                }
            except:
                status["git_status"] = {"error": "Not a git repository"}
            
            # Get modification time
            status["last_modified"] = datetime.fromtimestamp(project_path.stat().st_mtime).isoformat()
        
        return status

    async def list_projects(self, 
                          filter_by_type: Optional[ProjectType] = None,
                          filter_by_tech: Optional[TechnologyStack] = None) -> List[Dict[str, Any]]:
        """List all active projects with optional filtering"""
        
        projects = []
        
        for project_id, config in self.active_projects.items():
            if filter_by_type and config.project_type != filter_by_type:
                continue
            
            if filter_by_tech and config.technology_stack != filter_by_tech:
                continue
            
            project_info = {
                "project_id": project_id,
                "name": config.name,
                "description": config.description,
                "type": config.project_type.value,
                "technology_stack": config.technology_stack.value,
                "version": config.version,
                "status": ProjectStatus.ACTIVE.value
            }
            
            projects.append(project_info)
        
        return projects

    async def get_agent_statistics(self) -> Dict[str, Any]:
        """Get comprehensive agent statistics"""
        
        return {
            "agent_info": {
                "agent_id": self.agent_id,
                "agent_type": self.agent_type,
                "status": self.status.value,
                "uptime": (datetime.utcnow() - self.created_at).total_seconds() if self.created_at else 0
            },
            "project_statistics": self.project_stats,
            "active_projects": len(self.active_projects),
            "available_templates": list(self.project_templates.keys()),
            "supported_tech_stacks": [stack.value for stack in TechnologyStack],
            "workspace_info": {
                "workspace_path": str(self.workspace_path),
                "total_size": self._get_workspace_size(),
                "projects_count": len(list((self.workspace_path / "projects").iterdir())) if (self.workspace_path / "projects").exists() else 0
            }
        }

    def _get_workspace_size(self) -> int:
        """Calculate total workspace size"""
        try:
            return sum(
                f.stat().st_size 
                for f in self.workspace_path.rglob("*") 
                if f.is_file()
            )
        except:
            return 0

    async def cleanup_projects(self, 
                             older_than_days: int = 30,
                             archive_before_delete: bool = True) -> Dict[str, Any]:
        """Cleanup old or inactive projects"""
        
        cleanup_results = {
            "projects_cleaned": 0,
            "projects_archived": 0,
            "space_freed": 0,
            "errors": []
        }
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
            
            for project_id in list(self.active_projects.keys()):
                config = self.active_projects[project_id]
                project_path = self.workspace_path / "projects" / config.name
                
                if not project_path.exists():
                    continue
                
                # Check last modification time
                last_modified = datetime.fromtimestamp(project_path.stat().st_mtime)
                
                if last_modified < cutoff_date:
                    project_size = sum(
                        f.stat().st_size 
                        for f in project_path.rglob("*") 
                        if f.is_file()
                    )
                    
                    if archive_before_delete:
                        try:
                            await self.export_project(project_id, "zip")
                            cleanup_results["projects_archived"] += 1
                        except Exception as e:
                            cleanup_results["errors"].append(f"Failed to archive {config.name}: {str(e)}")
                    
                    # Remove project directory
                    shutil.rmtree(project_path)
                    
                    # Remove from active projects
                    del self.active_projects[project_id]
                    
                    cleanup_results["projects_cleaned"] += 1
                    cleanup_results["space_freed"] += project_size
                    self.project_stats["active_projects_count"] -= 1
            
            logger.info("Project cleanup completed", **cleanup_results)
            
        except Exception as e:
            logger.error("Project cleanup failed", error=str(e))
            cleanup_results["errors"].append(str(e))
        
        return cleanup_results

    async def _load_existing_projects(self):
        """Load existing projects from workspace"""
        
        projects_path = self.workspace_path / "projects"
        if not projects_path.exists():
            return
        
        for project_dir in projects_path.iterdir():
            if not project_dir.is_dir():
                continue
            
            project_config_path = project_dir / "project.json"
            if project_config_path.exists():
                try:
                    async with aiofiles.open(project_config_path, 'r') as f:
                        project_data = json.loads(await f.read())
                    
                    config = ProjectConfiguration(
                        name=project_data["name"],
                        description=project_data["description"],
                        project_type=ProjectType(project_data["type"]),
                        technology_stack=TechnologyStack(project_data["technology_stack"]),
                        version=project_data.get("version", "1.0.0"),
                        license=project_data.get("license", "MIT"),
                        author=project_data.get("author", "")
                    )
                    
                    project_id = f"proj_{uuid.uuid4().hex[:12]}"
                    self.active_projects[project_id] = config
                    self.project_stats["active_projects_count"] += 1
                    
                except Exception as e:
                    logger.warning("Failed to load existing project", 
                                 project_dir=str(project_dir),
                                 error=str(e))

    async def _create_custom_project(self, project_path: Path, config: ProjectConfiguration):
        """Create custom project structure"""
        
        # Create basic directory structure based on project type
        if config.project_type == ProjectType.API_SERVICE:
            directories = ["src", "tests", "docs", "config", "scripts"]
        elif config.project_type == ProjectType.WEB_APPLICATION:
            directories = ["src", "public", "tests", "docs", "build"]
        else:
            directories = ["src", "tests", "docs"]
        
        for directory in directories:
            (project_path / directory).mkdir(parents=True, exist_ok=True)
        
        # Create basic README
        readme_content = f"""# {config.name}

{config.description}

## Getting Started

This project was created using YMERA Project Agent.

## License

{config.license}
"""
        
        async with aiofiles.open(project_path / "README.md", 'w') as f: await f.write(readme_content)
        
        # Create gitignore based on technology stack
        gitignore_content = await self._generate_gitignore(config.technology_stack)
        async with aiofiles.open(project_path / ".gitignore", 'w') as f:
            await f.write(gitignore_content)
        
        # Create package configuration
        package_config = await self._generate_package_config(config)
        if package_config:
            config_file = "package.json" if "node" in config.technology_stack.value else "requirements.txt"
            async with aiofiles.open(project_path / config_file, 'w') as f:
                await f.write(package_config)
        
        # Create docker configuration
        if config.containerized:
            dockerfile_content = await self._generate_dockerfile(config)
            async with aiofiles.open(project_path / "Dockerfile", 'w') as f:
                await f.write(dockerfile_content)
            
            docker_compose_content = await self._generate_docker_compose(config)
            async with aiofiles.open(project_path / "docker-compose.yml", 'w') as f:
                await f.write(docker_compose_content)
        
        # Create CI/CD pipeline
        await self._create_cicd_pipeline(project_path, config)
        
        logger.info("Custom project structure created", project_name=config.name)

    async def _generate_gitignore(self, tech_stack: TechnologyStack) -> str:
        """Generate appropriate .gitignore based on technology stack"""
        
        base_ignores = [
            "# OS generated files",
            ".DS_Store",
            ".DS_Store?",
            "._*",
            ".Spotlight-V100",
            ".Trashes",
            "ehthumbs.db",
            "Thumbs.db",
            "",
            "# IDE files",
            ".vscode/",
            ".idea/",
            "*.swp",
            "*.swo",
            "*~",
            "",
            "# Logs",
            "*.log",
            "logs/",
            "",
            "# Environment files",
            ".env",
            ".env.local",
            ".env.*.local",
            ""
        ]
        
        tech_specific = {
            TechnologyStack.PYTHON_FASTAPI: [
                "# Python",
                "__pycache__/",
                "*.py[cod]",
                "*$py.class",
                "*.so",
                ".Python",
                "build/",
                "develop-eggs/",
                "dist/",
                "downloads/",
                "eggs/",
                ".eggs/",
                "lib/",
                "lib64/",
                "parts/",
                "sdist/",
                "var/",
                "wheels/",
                "*.egg-info/",
                ".installed.cfg",
                "*.egg",
                "",
                "# Virtual environments",
                "venv/",
                "ENV/",
                "env/",
                ".venv/",
                "",
                "# FastAPI specific",
                ".pytest_cache/",
                "htmlcov/",
                ".coverage",
                ".coverage.*"
            ],
            TechnologyStack.NODE_TYPESCRIPT: [
                "# Node.js",
                "node_modules/",
                "npm-debug.log*",
                "yarn-debug.log*",
                "yarn-error.log*",
                "",
                "# TypeScript",
                "*.tsbuildinfo",
                "dist/",
                "build/",
                "",
                "# Dependencies",
                "package-lock.json",
                "yarn.lock"
            ],
            TechnologyStack.REACT_TYPESCRIPT: [
                "# React",
                "node_modules/",
                "build/",
                "dist/",
                ".env",
                "",
                "# Production build",
                "/build",
                "",
                "# TypeScript",
                "*.tsbuildinfo",
                "",
                "# Testing",
                "coverage/"
            ]
        }
        
        ignores = base_ignores.copy()
        if tech_stack in tech_specific:
            ignores.extend(tech_specific[tech_stack])
        
        return "\n".join(ignores)

    async def _generate_package_config(self, config: ProjectConfiguration) -> Optional[str]:
        """Generate package configuration based on technology stack"""
        
        if "node" in config.technology_stack.value:
            package_json = {
                "name": config.name.lower().replace(" ", "-"),
                "version": config.version,
                "description": config.description,
                "main": "src/index.js" if "javascript" in config.technology_stack.value else "src/index.ts",
                "scripts": {
                    "start": "node dist/index.js",
                    "dev": "nodemon src/index.ts",
                    "build": "tsc",
                    "test": "jest",
                    "lint": "eslint src/**/*.ts",
                    "format": "prettier --write src/**/*.ts"
                },
                "keywords": [],
                "author": config.author,
                "license": config.license,
                "dependencies": {},
                "devDependencies": {
                    "@types/node": "^20.0.0",
                    "typescript": "^5.0.0",
                    "ts-node": "^10.9.0",
                    "nodemon": "^3.0.0",
                    "jest": "^29.0.0",
                    "@types/jest": "^29.0.0",
                    "eslint": "^8.0.0",
                    "prettier": "^3.0.0"
                }
            }
            
            # Add specific dependencies based on project type
            if config.project_type == ProjectType.API_SERVICE:
                package_json["dependencies"].update({
                    "express": "^4.18.0",
                    "helmet": "^7.0.0",
                    "cors": "^2.8.5",
                    "morgan": "^1.10.0"
                })
                package_json["devDependencies"]["@types/express"] = "^4.17.0"
            
            return json.dumps(package_json, indent=2)
            
        elif "python" in config.technology_stack.value:
            requirements = [
                "# Core dependencies",
                "fastapi>=0.104.0" if config.technology_stack == TechnologyStack.PYTHON_FASTAPI else "",
                "uvicorn[standard]>=0.24.0" if config.technology_stack == TechnologyStack.PYTHON_FASTAPI else "",
                "pydantic>=2.0.0",
                "python-multipart>=0.0.6",
                "python-jose[cryptography]>=3.3.0",
                "passlib[bcrypt]>=1.7.4",
                "",
                "# Database",
                "sqlalchemy>=2.0.0",
                "alembic>=1.12.0",
                "asyncpg>=0.29.0",
                "",
                "# Redis",
                "redis>=5.0.0",
                "",
                "# HTTP Client",
                "httpx>=0.25.0",
                "aiohttp>=3.9.0",
                "",
                "# Utilities",
                "python-dotenv>=1.0.0",
                "structlog>=23.2.0",
                "rich>=13.7.0",
                "",
                "# Development",
                "pytest>=7.4.0",
                "pytest-asyncio>=0.21.0",
                "pytest-cov>=4.1.0",
                "black>=23.9.0",
                "flake8>=6.1.0",
                "mypy>=1.6.0",
                "pre-commit>=3.5.0"
            ]
            
            return "\n".join(filter(None, requirements))
        
        return None

    async def _generate_dockerfile(self, config: ProjectConfiguration) -> str:
        """Generate Dockerfile based on technology stack"""
        
        if "python" in config.technology_stack.value:
            return f"""# Multi-stage build for Python application
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable:
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
        
        elif "node" in config.technology_stack.value:
            return f"""# Multi-stage build for Node.js application
FROM node:18-alpine as builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build application
RUN npm run build

# Production stage
FROM node:18-alpine

WORKDIR /app

# Copy built application
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./

# Create non-root user
RUN addgroup -g 1001 -S nodejs
RUN adduser -S nextjs -u 1001
USER nextjs

EXPOSE 3000

CMD ["npm", "start"]
"""
        
        return """FROM alpine:latest
RUN apk add --no-cache ca-certificates
WORKDIR /root/
CMD ["./app"]
"""

    async def _generate_docker_compose(self, config: ProjectConfiguration) -> str:
        """Generate docker-compose.yml for development environment"""
        
        compose_config = {
            "version": "3.8",
            "services": {
                config.name.lower().replace(" ", "-"): {
                    "build": ".",
                    "ports": ["8000:8000"] if "python" in config.technology_stack.value else ["3000:3000"],
                    "environment": [
                        "NODE_ENV=development" if "node" in config.technology_stack.value else "ENVIRONMENT=development",
                        "DATABASE_URL=postgresql://user:password@postgres:5432/app"
                    ],
                    "volumes": [
                        "./src:/app/src"
                    ],
                    "depends_on": ["postgres", "redis"]
                },
                "postgres": {
                    "image": "postgres:15-alpine",
                    "environment": [
                        "POSTGRES_DB=app",
                        "POSTGRES_USER=user",
                        "POSTGRES_PASSWORD=password"
                    ],
                    "volumes": [
                        "postgres_data:/var/lib/postgresql/data"
                    ],
                    "ports": ["5432:5432"]
                },
                "redis": {
                    "image": "redis:7-alpine",
                    "ports": ["6379:6379"],
                    "volumes": [
                        "redis_data:/data"
                    ]
                }
            },
            "volumes": {
                "postgres_data": None,
                "redis_data": None
            }
        }
        
        return yaml.dump(compose_config, default_flow_style=False)

    async def _create_cicd_pipeline(self, project_path: Path, config: ProjectConfiguration):
        """Create CI/CD pipeline configuration"""
        
        # Create .github/workflows directory
        workflows_dir = project_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        
        # GitHub Actions workflow
        github_workflow = {
            "name": "CI/CD Pipeline",
            "on": {
                "push": {
                    "branches": ["main", "develop"]
                },
                "pull_request": {
                    "branches": ["main"]
                }
            },
            "jobs": {
                "test": {
                    "runs-on": "ubuntu-latest",
                    "strategy": {
                        "matrix": {
                            "python-version": ["3.9", "3.10", "3.11"] if "python" in config.technology_stack.value else None,
                            "node-version": ["16", "18", "20"] if "node" in config.technology_stack.value else None
                        }
                    },
                    "steps": [
                        {
                            "uses": "actions/checkout@v4"
                        },
                        {
                            "name": "Set up Python" if "python" in config.technology_stack.value else "Set up Node.js",
                            "uses": "actions/setup-python@v4" if "python" in config.technology_stack.value else "actions/setup-node@v4",
                            "with": {
                                "python-version": "${{ matrix.python-version }}" if "python" in config.technology_stack.value else None,
                                "node-version": "${{ matrix.node-version }}" if "node" in config.technology_stack.value else None
                            }
                        },
                        {
                            "name": "Install dependencies",
                            "run": "pip install -r requirements.txt" if "python" in config.technology_stack.value else "npm ci"
                        },
                        {
                            "name": "Run tests",
                            "run": "pytest --cov=src --cov-report=xml" if "python" in config.technology_stack.value else "npm test"
                        },
                        {
                            "name": "Upload coverage",
                            "uses": "codecov/codecov-action@v3",
                            "with": {
                                "file": "./coverage.xml" if "python" in config.technology_stack.value else "./coverage/lcov.info"
                            }
                        }
                    ]
                },
                "deploy": {
                    "needs": "test",
                    "runs-on": "ubuntu-latest",
                    "if": "github.ref == 'refs/heads/main'",
                    "steps": [
                        {
                            "uses": "actions/checkout@v4"
                        },
                        {
                            "name": "Build and push Docker image",
                            "env": {
                                "REGISTRY": "ghcr.io",
                                "IMAGE_NAME": "${{ github.repository }}"
                            },
                            "run": """
                                echo ${{ secrets.GITHUB_TOKEN }} | docker login $REGISTRY -u ${{ github.actor }} --password-stdin
                                docker build -t $REGISTRY/$IMAGE_NAME:latest .
                                docker push $REGISTRY/$IMAGE_NAME:latest
                            """
                        }
                    ]
                }
            }
        }
        
        # Remove None values from matrix
        if github_workflow["jobs"]["test"]["strategy"]["matrix"]["python-version"] is None:
            del github_workflow["jobs"]["test"]["strategy"]["matrix"]["python-version"]
        if github_workflow["jobs"]["test"]["strategy"]["matrix"]["node-version"] is None:
            del github_workflow["jobs"]["test"]["strategy"]["matrix"]["node-version"]
        
        async with aiofiles.open(workflows_dir / "ci-cd.yml", 'w') as f:
            await f.write(yaml.dump(github_workflow, default_flow_style=False))

    async def _create_basic_source_files(self, project_path: Path, config: ProjectConfiguration):
        """Create basic source files based on project type and technology stack"""
        
        src_dir = project_path / "src"
        src_dir.mkdir(exist_ok=True)
        
        if config.technology_stack == TechnologyStack.PYTHON_FASTAPI:
            await self._create_fastapi_files(src_dir, config)
        elif config.technology_stack == TechnologyStack.NODE_TYPESCRIPT:
            await self._create_node_typescript_files(src_dir, config)
        elif config.technology_stack == TechnologyStack.REACT_TYPESCRIPT:
            await self._create_react_typescript_files(src_dir, config)

    async def _create_fastapi_files(self, src_dir: Path, config: ProjectConfiguration):
        """Create FastAPI project structure"""
        
        # Main application file
        main_py_content = f'''"""
{config.name} - FastAPI Application
Generated by YMERA Project Agent
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
from typing import List, Optional
import logging
import os
from datetime import datetime

from .database import database, metadata, engine
from .models import *
from .routers import health, auth, api
from .core.config import settings
from .core.security import get_current_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    await database.connect()
    logger.info("Database connected")
    
    yield
    
    # Shutdown
    await database.disconnect()
    logger.info("Database disconnected")

# Create FastAPI application
app = FastAPI(
    title="{config.name}",
    description="{config.description}",
    version="{config.version}",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(api.router, prefix="/api/v1", tags=["API"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {{
        "message": "Welcome to {config.name}",
        "version": "{config.version}",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "operational"
    }}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )
'''
        
        async with aiofiles.open(src_dir / "main.py", 'w') as f:
            await f.write(main_py_content)
        
        # Create additional FastAPI structure files
        await self._create_fastapi_structure(src_dir, config)

    async def _create_fastapi_structure(self, src_dir: Path, config: ProjectConfiguration):
        """Create complete FastAPI project structure"""
        
        # Create directories
        (src_dir / "core").mkdir(exist_ok=True)
        (src_dir / "routers").mkdir(exist_ok=True)
        (src_dir / "models").mkdir(exist_ok=True)
        (src_dir / "services").mkdir(exist_ok=True)
        (src_dir / "utils").mkdir(exist_ok=True)
        
        # Core configuration
        config_content = '''"""
Application configuration
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    """Application settings"""
    
    # Basic settings
    app_name: str = "FastAPI Application"
    debug: bool = False
    version: str = "1.0.0"
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    
    # Security
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    class Config:
        env_file = ".env"

settings = Settings()
'''
        
        async with aiofiles.open(src_dir / "core" / "config.py", 'w') as f:
            await f.write(config_content)
        
        # Security module
        security_content = '''"""
Security utilities
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional

from .config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token authentication
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Here you would typically fetch the user from the database
    # For now, just return the username
    return {"username": username}
'''
        
        async with aiofiles.open(src_dir / "core" / "security.py", 'w') as f:
            await f.write(security_content)
        
        # Create __init__.py files
        for init_dir in ["core", "routers", "models", "services", "utils"]:
            async with aiofiles.open(src_dir / init_dir / "__init__.py", 'w') as f:
                await f.write("")

    async def backup_project(self, project_id: str, backup_type: str = "full") -> Dict[str, Any]:
        """Create backup of project"""
        
        if project_id not in self.active_projects:
            raise HTTPException(status_code=404, detail="Project not found")
        
        config = self.active_projects[project_id]
        project_path = self.workspace_path / "projects" / config.name
        
        backup_dir = self.workspace_path / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{config.name}_{backup_type}_{timestamp}"
        
        if backup_type == "full":
            # Create full backup with git history
            backup_path = backup_dir / f"{backup_name}.tar.gz"
            
            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(project_path, arcname=config.name)
        
        elif backup_type == "source_only":
            # Backup only source code
            backup_path = backup_dir / f"{backup_name}.zip"
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in project_path.rglob("*"):
                    if file_path.is_file() and not any(exclude in str(file_path) for exclude in [
                        ".git", "node_modules", "__pycache__", ".venv", "dist", "build"
                    ]):
                        arcname = file_path.relative_to(project_path)
                        zipf.write(file_path, arcname)
        
        backup_info = {
            "backup_id": f"backup_{uuid.uuid4().hex[:12]}",
            "project_id": project_id,
            "project_name": config.name,
            "backup_type": backup_type,
            "backup_path": str(backup_path),
            "size_bytes": backup_path.stat().st_size,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Store backup metadata
        metadata_path = backup_dir / f"{backup_name}.json"
        async with aiofiles.open(metadata_path, 'w') as f:
            await f.write(json.dumps(backup_info, indent=2))
        
        self.project_stats["backups_created"] += 1
        
        logger.info("Project backup created", **backup_info)
        return backup_info

    async def restore_project(self, backup_id: str, restore_location: Optional[str] = None) -> Dict[str, Any]:
        """Restore project from backup"""
        
        backup_dir = self.workspace_path / "backups"
        
        # Find backup metadata
        backup_metadata = None
        for metadata_file in backup_dir.glob("*.json"):
            async with aiofiles.open(metadata_file, 'r') as f:
                data = json.loads(await f.read())
                if data.get("backup_id") == backup_id:
                    backup_metadata = data
                    break
        
        if not backup_metadata:
            raise HTTPException(status_code=404, detail="Backup not found")
        
        backup_path = Path(backup_metadata["backup_path"])
        if not backup_path.exists():
            raise HTTPException(status_code=404, detail="Backup file not found")
        
        # Determine restore location
        if restore_location:
            restore_path = Path(restore_location)
        else:
            restore_path = self.workspace_path / "projects" / f"{backup_metadata['project_name']}_restored"
        
        restore_path.mkdir(parents=True, exist_ok=True)
        
        # Extract backup
        if backup_path.suffix == ".gz":
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(restore_path.parent)
        elif backup_path.suffix == ".zip":
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                zipf.extractall(restore_path)
        
        restore_info = {
            "restore_id": f"restore_{uuid.uuid4().hex[:12]}",
            "backup_id": backup_id,
            "original_project": backup_metadata["project_name"],
            "restore_path": str(restore_path),
            "restored_at": datetime.utcnow().isoformat()
        }
        
        logger.info("Project restored from backup", **restore_info)
        return restore_info

    async def analyze_project_health(self, project_id: str) -> Dict[str, Any]:
        """Analyze project health and provide recommendations"""
        
        if project_id not in self.active_projects:
            raise HTTPException(status_code=404, detail="Project not found")
        
        config = self.active_projects[project_id]
        project_path = self.workspace_path / "projects" / config.name
        
        health_report = {
            "project_id": project_id,
            "project_name": config.name,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "overall_score": 0,
            "metrics": {},
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Code quality metrics
            if (project_path / "src").exists():
                code_metrics = await self._analyze_code_quality(project_path / "src")
                health_report["metrics"]["code_quality"] = code_metrics
            
            # Security analysis
            security_metrics = await self._analyze_security(project_path)
            health_report["metrics"]["security"] = security_metrics
            
            # Dependency analysis
            if (project_path / "requirements.txt").exists() or (project_path / "package.json").exists():
                dep_metrics = await self._analyze_dependencies(project_path)
                health_report["metrics"]["dependencies"] = dep_metrics
            
            # Git repository health
            if (project_path / ".git").exists():
                git_metrics = await self._analyze_git_health(project_path)
                health_report["metrics"]["git"] = git_metrics
            
            # Calculate overall score
            scores = [metrics.get("score", 0) for metrics in health_report["metrics"].values()]
            health_report["overall_score"] = sum(scores) / len(scores) if scores else 0
            
            # Generate recommendations
            health_report["recommendations"] = await self._generate_health_recommendations(health_report)
            
        except Exception as e:
            logger.error("Project health analysis failed", project_id=project_id, error=str(e))
            health_report["error"] = str(e)
        
        return health_report

    async def _analyze_code_quality(self, src_path: Path) -> Dict[str, Any]:
        """Analyze code quality metrics"""
        
        metrics = {
            "total_files": 0,
            "total_lines": 0,
            "avg_complexity": 0,
            "test_coverage": 0,
            "score": 0
        }
        
        try:
            python_files = list(src_path.rglob("*.py"))
            js_ts_files = list(src_path.rglob("*.js")) + list(src_path.rglob("*.ts"))
            
            total_files = python_files + js_ts_files
            metrics["total_files"] = len(total_files)
            
            # Count lines of code
            total_lines = 0
            for file_path in total_files:
                try:
                    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                        lines = (await f.read()).count('\n')
                        total_lines += lines
                except:
                    continue
            
            metrics["total_lines"] = total_lines
            
            # Simple scoring based on project structure
            has_tests = any((src_path.parent / "tests").exists() for _ in [1])
            has_docs = any((src_path.parent / "docs").exists() for _ in [1])
            has_config = any((src_path.parent / "config").exists() for _ in [1])
            
            score = 50  # Base score
            if has_tests:
                score += 20
            if has_docs:
                score += 15
            if has_config:
                score += 15
            if total_files > 0:
                score = min(100, score)
            
            metrics["score"] = score
            
        except Exception as e:
            logger.error("Code quality analysis failed", error=str(e))
            metrics["score"] = 0
        
        return metrics

    async def _analyze_security(self, project_path: Path) -> Dict[str, Any]:
        """Analyze security aspects of the project"""
        
        metrics = {
            "has_env_example": False,
            "has_gitignore": False,
            "has_security_headers": False,
            "vulnerable_dependencies": 0,
            "score": 0
        }
        
        try:
            # Check for .env.example
            metrics["has_env_example"] = (project_path / ".env.example").exists()
            
            # Check for .gitignore
            metrics["has_gitignore"] = (project_path / ".gitignore").exists()
            
            # Check for security-related files
            security_files = [
                project_path / "src" / "core" / "security.py",
                project_path / "src" / "middleware" / "security.js",
                project_path / "src" / "utils" / "auth.py"
            ]
            metrics["has_security_headers"] = any(f.exists() for f in security_files)
            
            # Calculate score
            score = 0
            if metrics["has_env_example"]:
                score += 25
            if metrics["has_gitignore"]:
                score += 25
            if metrics["has_security_headers"]:
                score += 50
            
            metrics["score"] = score
            
        except Exception as e:
            logger.error("Security analysis failed", error=str(e))
            metrics["score"] = 0
        
        return metrics

    async def _analyze_dependencies(self, project_path: Path) -> Dict[str, Any]:
        """Analyze project dependencies"""
        
        metrics = {
            "total_dependencies": 0,
            "outdated_dependencies": 0,
            "security_vulnerabilities": 0,
            "score": 0
        }
        
        try:
            # Python dependencies
            if (project_path / "requirements.txt").exists():
                async with aiofiles.open(project_path / "requirements.txt", 'r') as f:
                    content = await f.read()
                    deps = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
                    metrics["total_dependencies"] = len(deps)
            
            # Node.js dependencies
            elif (project_path / "package.json").exists():
                async with aiofiles.open(project_path / "package.json", 'r') as f:
                    content = await f.read()
                    package_data = json.loads(content)
                    deps = len(package_data.get("dependencies", {})) + len(package_data.get("devDependencies", {}))
                    metrics["total_dependencies"] = deps
            
            # Simple scoring based on having dependencies managed
            if metrics["total_dependencies"] > 0:
                metrics["score"] = 80  # Good score for having managed dependencies
            else:
                metrics["score"] = 60  # Neutral score for no dependencies
                
        except Exception as e:
            logger.error("Dependency analysis failed", error=str(e))
            metrics["score"] = 50
        
        return metrics

    async def _analyze_git_health(self, project_path: Path) -> Dict[str, Any]:
        """Analyze Git repository health"""
        
        metrics = {
            "has_git": False,
            "commit_count": 0,
            "branch_count": 0,
            "has_remote": False,
            "last_commit_days": 0,
            "score": 0
        }
        
        try:
            if (project_path / ".git").exists():
                metrics["has_git"] = True
                
                repo = Repo(project_path)
                
                # Count commits
                metrics["commit_count"] = len(list(repo.iter_commits()))
                
                # Count branches
                metrics["branch_count"] = len(list(repo.branches))
                
                # Check for remote
                metrics["has_remote"] = len(repo.remotes) > 0
                
                # Last commit age
                if metrics["commit_count"] > 0:
                    last_commit = repo.head.commit
                    days_since = (datetime.now() - datetime.fromtimestamp(last_commit.committed_date)).days
                    metrics["last_commit_days"] = days_since
                
                # Calculate score
                score = 0
                if metrics["has_git"]:
                    score += 30
                if metrics["commit_count"] > 1:
                    score += 20
                if metrics["has_remote"]:
                    score += 25
                if metrics["last_commit_days"] < 7:
                    score += 25
                
                metrics["score"] = score
            
        except Exception as e:
            logger.error("Git analysis failed", error=str(e))
            metrics["score"] = 0
        
        return metrics

    async def _generate_health_recommendations(self, health_report: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on health analysis"""
        
        recommendations = []
        
        # Code quality recommendations
        code_metrics = health_report["metrics"].get("code_quality", {})
        if code_metrics.get("score", 0) < 70:
            recommendations.append("Consider adding comprehensive tests to improve code quality")
            recommendations.append("Add documentation to improve maintainability")
            recommendations.append("Implement proper project structure with config management")
        
        # Security recommendations
        security_metrics = health_report["metrics"].get("security", {})
        if not security_metrics.get("has_env_example"):
            recommendations.append("Add .env.example file to document required environment variables")
        if not security_metrics.get("has_gitignore"):
            recommendations.append("Add .gitignore file to exclude sensitive and build files")
        if not security_metrics.get("has_security_headers"):
            recommendations.append("Implement security middleware and authentication")
        
        # Git recommendations
        git_metrics = health_report["metrics"].get("git", {})
        if not git_metrics.get("has_remote"):
            recommendations.append("Add remote repository for backup and collaboration")
        if git_metrics.get("last_commit_days", 0) > 30:
            recommendations.append("Project appears inactive - consider archiving or updating")
        
        # Dependency recommendations
        dep_metrics = health_report["metrics"].get("dependencies", {})
        if dep_metrics.get("total_dependencies", 0) == 0:
            recommendations.append("Consider using a package manager to track dependencies")
        
        return recommendations

    async def generate_project_report(self, project_id: str) -> Dict[str, Any]:
        """Generate comprehensive project report"""
        
        if project_id not in self.active_projects:
            raise HTTPException(status_code=404, detail="Project not found")
        
        config = self.active_projects[project_id]
        project_path = self.workspace_path / "projects" / config.name
        
        # Get project status and health
        status = await self.get_project_status(project_id)
        health = await self.analyze_project_health(project_id)
        
        report = {
            "report_id": f"report_{uuid.uuid4().hex[:12]}",
            "generated_at": datetime.utcnow().isoformat(),
            "project_info": {
                "id": project_id,
                "name": config.name,
                "description": config.description,
                "type": config.project_type.value,
                "technology_stack": config.technology_stack.value,
                "version": config.version,
                "author": config.author,
                "license": config.license
            },
            "status": status,
            "health_analysis": health,
            "statistics": {
                "created_at": config.created_at.isoformat() if hasattr(config, 'created_at') else None,
                "file_count": len(list(project_path.rglob("*"))) if project_path.exists() else 0,
                "directory_count": len([p for p in project_path.rglob("*") if p.is_dir()]) if project_path.exists() else 0
            },
            "recommendations": health.get("recommendations", [])
        }
        
        # Save report
        reports_dir = self.workspace_path / "reports"
        reports_dir.mkdir(exist_ok=True)
        
        report_filename = f"project_report_{project_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        async with aiofiles.open(reports_dir / report_filename, 'w') as f:
            await f.write(json.dumps(report, indent=2))
        
        logger.info("Project report generated", 
                   project_id=project_id,
                   report_file=report_filename)
        
        return report

    async def migrate_project(self, project_id: str, target_tech_stack: TechnologyStack) -> Dict[str, Any]:
        """Migrate project to different technology stack"""
        
        if project_id not in self.active_projects:
            raise HTTPException(status_code=404, detail="Project not found")
        
        config = self.active_projects[project_id]
        current_stack = config.technology_stack
        
        if current_stack == target_tech_stack:
            raise HTTPException(status_code=400, detail="Project already uses target technology stack")
        
        migration_id = f"migration_{uuid.uuid4().hex[:12]}"
        project_path = self.workspace_path / "projects" / config.name
        backup_path = self.workspace_path / "migrations" / f"{config.name}_{migration_id}_backup"
        
        # Create migration directory
        backup_path.mkdir(parents=True, exist_ok=True)
        
        migration_result = {
            "migration_id": migration_id,
            "project_id": project_id,
            "from_stack": current_stack.value,
            "to_stack": target_tech_stack.value,
            "started_at": datetime.utcnow().isoformat(),
            "status": "in_progress",
            "steps_completed": [],
            "errors": []
        }
        
        try:
            # Step 1: Create backup
            shutil.copytree(project_path, backup_path)
            migration_result["steps_completed"].append("backup_created")
            
            # Step 2: Analyze current structure
            current_files = await self._analyze_project_structure(project_path)
            migration_result["steps_completed"].append("structure_analyzed")
            
            # Step 3: Generate migration plan
            migration_plan = await self._generate_migration_plan(current_stack, target_tech_stack, current_files)
            migration_result["migration_plan"] = migration_plan
            migration_result["steps_completed"].append("migration_plan_generated")
            
            # Step 4: Execute migration
            await self._execute_migration(project_path, migration_plan)
            migration_result["steps_completed"].append("migration_executed")
            
            # Step 5: Update project configuration
            config.technology_stack = target_tech_stack
            await self._save_project_config(project_path, config)
            migration_result["steps_completed"].append("config_updated")
            
            migration_result["status"] = "completed"
            migration_result["completed_at"] = datetime.utcnow().isoformat()
            
            logger.info("Project migration completed", **migration_result)
            
        except Exception as e:
            migration_result["status"] = "failed"
            migration_result["error"] = str(e)
            migration_result["failed_at"] = datetime.utcnow().isoformat()
            logger.error("Project migration failed", migration_id=migration_id, error=str(e))
        
        # Save migration record
        migrations_dir = self.workspace_path / "migrations"
        migrations_dir.mkdir(exist_ok=True)
        
        async with aiofiles.open(migrations_dir / f"{migration_id}.json", 'w') as f:
            await f.write(json.dumps(migration_result, indent=2))
        
        return migration_result

    async def _analyze_project_structure(self, project_path: Path) -> Dict[str, Any]:
        """Analyze current project structure"""
        
        structure = {
            "source_files": [],
            "config_files": [],
            "dependencies": {},
            "build_system": None
        }
        
        # Find source files
        for ext in [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs"]:
            files = list(project_path.rglob(f"*{ext}"))
            structure["source_files"].extend([str(f.relative_to(project_path)) for f in files])
        
        # Find config files
        config_patterns = ["*.json", "*.yaml", "*.yml", "*.toml", "*.ini", "Dockerfile", "*.config.*"]
        for pattern in config_patterns:
            files = list(project_path.rglob(pattern))
            structure["config_files"].extend([str(f.relative_to(project_path)) for f in files])
        
        # Detect build system
        if (project_path / "package.json").exists():
            structure["build_system"] = "npm"
        elif (project_path / "requirements.txt").exists() or (project_path / "pyproject.toml").exists():
            structure["build_system"] = "python"
        elif (project_path / "go.mod").exists():
            structure["build_system"] = "go"
        elif (project_path / "Cargo.toml").exists():
            structure["build_system"] = "rust"
        
        return structure

    async def _generate_migration_plan(self, from_stack: TechnologyStack, to_stack: TechnologyStack, current_structure: Dict) -> Dict[str, Any]:
        """Generate detailed migration plan"""
        
        plan = {
            "phases": [],
            "file_mappings": {},
            "new_dependencies": {},
            "commands_to_run": []
        }
        
        # Phase 1: Backup and preparation
        plan["phases"].append({
            "name": "preparation",
            "description": "Backup current project and prepare for migration",
            "steps": ["create_backup", "analyze_dependencies", "validate_migration_path"]
        })
        
        # Phase 2: Structure transformation
        plan["phases"].append({
            "name": "structure_transformation",
            "description": "Transform project structure for target technology",
            "steps": ["create_new_structure", "migrate_source_files", "update_configs"]
        })
        
        # Phase 3: Dependency migration
        plan["phases"].append({
            "name": "dependency_migration",
            "description": "Migrate and update dependencies",
            "steps": ["install_new_dependencies", "update_imports", "configure_build_system"]
        })
        
        # Phase 4: Testing and validation
        plan["phases"].append({
            "name": "validation",
            "description": "Test and validate migrated project",
            "steps": ["run_syntax_check", "test_build", "validate_functionality"]
        })
        
        # Generate specific mappings based on migration path
        if from_stack == TechnologyStack.PYTHON_FASTAPI and to_stack == TechnologyStack.NODE_TYPESCRIPT:
            plan["file_mappings"] = {
                "src/main.py": "src/index.ts",
                "requirements.txt": "package.json",
                "src/models/": "src/models/",
                "src/routers/": "src/routes/"
            }
            plan["new_dependencies"] = {
                "express": "^4.18.0",
                "typescript": "^5.0.0",
                "@types/node": "^20.0.0",
                "@types/express": "^4.17.0"
            }
        
        return plan

    async def _execute_migration(self, project_path: Path, migration_plan: Dict[str, Any]):
        """Execute the migration plan"""
        
        for phase in migration_plan["phases"]:
            logger.info(f"Executing migration phase: {phase['name']}")
            
            for step in phase["steps"]:
                if step == "create_new_structure":
                    await self._create_target_structure(project_path, migration_plan)
                elif step == "migrate_source_files":
                    await self._migrate_source_files(project_path, migration_plan)
                elif step == "update_configs":
                    await self._update_config_files(project_path, migration_plan)
                # Add more step implementations as needed

    async def _create_target_structure(self, project_path: Path, migration_plan: Dict[str, Any]):
        """Create new directory structure for target technology"""
        
        # Create standard directories based on target technology
        standard_dirs = ["src", "tests", "docs", "config"]
        for dir_name in standard_dirs:
            (project_path / dir_name).mkdir(exist_ok=True)

    async def _migrate_source_files(self, project_path: Path, migration_plan: Dict[str, Any]):
        """Migrate source files according to the plan"""
        
        for source_path, target_path in migration_plan.get("file_mappings", {}).items():
            source_file = project_path / source_path
            target_file = project_path / target_path
            
            if source_file.exists():
                target_file.parent.mkdir(parents=True, exist_ok=True)
                if source_file.is_file():
                    shutil.copy2(source_file, target_file)

    async def _update_config_files(self, project_path: Path, migration_plan: Dict[str, Any]):
        """Update configuration files for target technology"""
        
        # This would contain specific logic for updating config files
        # Implementation depends on the specific migration path
        pass

    async def _save_project_config(self, project_path: Path, config: ProjectConfiguration):
        """Save updated project configuration"""
        
        config_data = {
            "name": config.name,
            "description": config.description,
            "type": config.project_type.value,
            "technology_stack": config.technology_stack.value,
            "version": config.version,
            "license": config.license,
            "author": config.author,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        async with aiofiles.open(project_path / "project.json", 'w') as f:
            await f.write(json.dumps(config_data, indent=2))

    async def cleanup_workspace(self) -> Dict[str, Any]:
        """Clean up workspace and temporary files"""
        
        cleanup_stats = {
            "files_removed": 0,
            "directories_removed": 0,
            "space_freed_bytes": 0,
            "errors": []
        }
        
        try:
            # Clean temporary files
            temp_patterns = ["*.tmp", "*.temp", "*.cache", "*~", "*.bak"]
            for pattern in temp_patterns:
                for temp_file in self.workspace_path.rglob(pattern):
                    try:
                        size = temp_file.stat().st_size
                        temp_file.unlink()
                        cleanup_stats["files_removed"] += 1
                        cleanup_stats["space_freed_bytes"] += size
                    except Exception as e:
                        cleanup_stats["errors"].append(f"Failed to remove {temp_file}: {str(e)}")
            
            # Clean empty directories
            for project_dir in (self.workspace_path / "projects").iterdir():
                if project_dir.is_dir():
                    try:
                        # Remove empty subdirectories
                        for subdir in project_dir.rglob("*"):
                            if subdir.is_dir() and not any(subdir.iterdir()):
                                subdir.rmdir()
                                cleanup_stats["directories_removed"] += 1
                    except Exception as e:
                        cleanup_stats["errors"].append(f"Failed to clean {project_dir}: {str(e)}")
            
            logger.info("Workspace cleanup completed", **cleanup_stats)
            
        except Exception as e:
            logger.error("Workspace cleanup failed", error=str(e))
            cleanup_stats["errors"].append(str(e))
        
        return cleanup_stats

    async def get_workspace_statistics(self) -> Dict[str, Any]:
        """Get comprehensive workspace statistics"""
        
        stats = {
            "workspace_path": str(self.workspace_path),
            "total_projects": len(self.active_projects),
            "projects_by_type": {},
            "projects_by_tech_stack": {},
            "total_files": 0,
            "total_size_bytes": 0,
            "disk_usage": {},
            "recent_activity": []
        }
        
        try:
            # Count projects by type and tech stack
            for config in self.active_projects.values():
                proj_type = config.project_type.value
                tech_stack = config.technology_stack.value
                
                stats["projects_by_type"][proj_type] = stats["projects_by_type"].get(proj_type, 0) + 1
                stats["projects_by_tech_stack"][tech_stack] = stats["projects_by_tech_stack"].get(tech_stack, 0) + 1
            
            # Calculate total files and size
            if self.workspace_path.exists():
                for file_path in self.workspace_path.rglob("*"):
                    if file_path.is_file():
                        stats["total_files"] += 1
                        stats["total_size_bytes"] += file_path.stat().st_size
            
            # Disk usage by directory
            main_dirs = ["projects", "backups", "reports", "migrations", "templates"]
            for dir_name in main_dirs:
                dir_path = self.workspace_path / dir_name
                if dir_path.exists():
                    size = sum(f.stat().st_size for f in dir_path.rglob("*") if f.is_file())
                    stats["disk_usage"][dir_name] = size
            
            # Recent activity (last 7 days)
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            for project_id, config in self.active_projects.items():
                project_path = self.workspace_path / "projects" / config.name
                if project_path.exists():
                    modified_time = datetime.fromtimestamp(project_path.stat().st_mtime)
                    if modified_time > cutoff_date:
                        stats["recent_activity"].append({
                            "project_id": project_id,
                            "project_name": config.name,
                            "last_modified": modified_time.isoformat()
                        })
            
            # Sort recent activity by modification time
            stats["recent_activity"].sort(key=lambda x: x["last_modified"], reverse=True)
            
        except Exception as e:
            logger.error("Failed to calculate workspace statistics", error=str(e))
            stats["error"] = str(e)
        
        return stats

# Export the agent class
__all__ = ["ProjectAgent"]