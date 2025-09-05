"""
YMERA Enterprise Code & Documentation Organizer System
Production-Ready with Multi-LLM Integration and Learning Engine
"""

import os
import asyncio
import json
import hashlib
import mimetypes
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from pathlib import Path
import aiofiles
import aiohttp
import logging
from dataclasses import dataclass, asdict
from enum import Enum
import zipfile
import tarfile
from concurrent.futures import ThreadPoolExecutor
import tiktoken
import anthropic
import openai
from google.generativeai import GenerativeModel
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import markdown
from markdownify import markdownify as md
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from pydantic import BaseModel, Field
import redis.asyncio as redis

# Configuration
@dataclass
class OrganizerConfig:
    # API Keys
    openai_api_key: str = os.getenv("OPENAI_API_KEY")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY") 
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY")
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/ymera_organizer")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Storage
    storage_root: str = os.getenv("STORAGE_ROOT", "./ymera_storage")
    max_file_size: int = int(os.getenv("MAX_FILE_SIZE", "100000000"))  # 100MB
    
    # Processing
    max_workers: int = int(os.getenv("MAX_WORKERS", "10"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "4000"))
    overlap_size: int = int(os.getenv("OVERLAP_SIZE", "200"))
    
    # Browser
    enable_browser: bool = os.getenv("ENABLE_BROWSER", "true").lower() == "true"
    browser_timeout: int = int(os.getenv("BROWSER_TIMEOUT", "30"))

class FileType(Enum):
    CODE = "code"
    DOCUMENTATION = "documentation"
    CONFIG = "config"
    DATA = "data"
    MEDIA = "media"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"

class ProcessingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    OPTIMIZING = "optimizing"

class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"

# Database Models
Base = declarative_base()

class FileRecord(Base):
    __tablename__ = "file_records"
    
    id = sa.Column(sa.String, primary_key=True)
    original_name = sa.Column(sa.String, nullable=False)
    file_type = sa.Column(sa.Enum(FileType), nullable=False)
    size = sa.Column(sa.BigInteger, nullable=False)
    hash_md5 = sa.Column(sa.String, nullable=False)
    storage_path = sa.Column(sa.String, nullable=False)
    mime_type = sa.Column(sa.String)
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow)
    updated_at = sa.Column(sa.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processing_status = sa.Column(sa.Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    metadata = sa.Column(sa.JSON)
    analysis_results = sa.Column(sa.JSON)
    organization_data = sa.Column(sa.JSON)
    learning_insights = sa.Column(sa.JSON)

class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"
    
    id = sa.Column(sa.String, primary_key=True)
    name = sa.Column(sa.String, nullable=False)
    description = sa.Column(sa.Text)
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow)
    updated_at = sa.Column(sa.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = sa.Column(sa.Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    file_count = sa.Column(sa.Integer, default=0)
    configuration = sa.Column(sa.JSON)
    results_summary = sa.Column(sa.JSON)

class LearningData(Base):
    __tablename__ = "learning_data"
    
    id = sa.Column(sa.String, primary_key=True)
    session_id = sa.Column(sa.String, sa.ForeignKey("analysis_sessions.id"))
    file_id = sa.Column(sa.String, sa.ForeignKey("file_records.id"))
    pattern_type = sa.Column(sa.String, nullable=False)
    pattern_data = sa.Column(sa.JSON, nullable=False)
    confidence_score = sa.Column(sa.Float, default=0.0)
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow)
    feedback_score = sa.Column(sa.Float)

# Pydantic Models
class FileAnalysisRequest(BaseModel):
    file_path: str
    analysis_type: str = "comprehensive"
    use_learning: bool = True
    custom_instructions: Optional[str] = None

class OrganizationRequest(BaseModel):
    session_id: str
    organization_strategy: str = "intelligent"
    create_structure: bool = True
    generate_docs: bool = True

class LearningFeedback(BaseModel):
    session_id: str
    file_id: str
    feedback_type: str
    score: float
    comments: Optional[str] = None

# Multi-LLM Manager
class MultiLLMManager:
    def __init__(self, config: OrganizerConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.clients = {}
        
    async def initialize(self):
        """Initialize all available LLM clients"""
        try:
            # OpenAI
            if self.config.openai_api_key:
                self.clients[LLMProvider.OPENAI] = openai.AsyncOpenAI(
                    api_key=self.config.openai_api_key
                )
                self.logger.info("✅ OpenAI client initialized")
            
            # Anthropic
            if self.config.anthropic_api_key:
                self.clients[LLMProvider.ANTHROPIC] = anthropic.AsyncAnthropic(
                    api_key=self.config.anthropic_api_key
                )
                self.logger.info("✅ Anthropic client initialized")
            
            # Gemini
            if self.config.gemini_api_key:
                genai.configure(api_key=self.config.gemini_api_key)
                self.clients[LLMProvider.GEMINI] = GenerativeModel('gemini-pro')
                self.logger.info("✅ Gemini client initialized")
                
            # DeepSeek
            if self.config.deepseek_api_key:
                self.clients[LLMProvider.DEEPSEEK] = openai.AsyncOpenAI(
                    api_key=self.config.deepseek_api_key,
                    base_url="https://api.deepseek.com"
                )
                self.logger.info("✅ DeepSeek client initialized")
                
        except Exception as e:
            self.logger.error(f"Error initializing LLM clients: {e}")
            raise
    
    async def analyze_with_best_model(self, content: str, analysis_type: str) -> Dict[str, Any]:
        """Analyze content using the most appropriate LLM"""
        try:
            # Choose best model based on analysis type
            if analysis_type == "code_analysis":
                providers = [LLMProvider.ANTHROPIC, LLMProvider.OPENAI, LLMProvider.DEEPSEEK]
            elif analysis_type == "documentation":
                providers = [LLMProvider.OPENAI, LLMProvider.GEMINI, LLMProvider.ANTHROPIC]
            else:
                providers = list(self.clients.keys())
            
            # Try providers in order
            for provider in providers:
                if provider in self.clients:
                    try:
                        return await self._analyze_with_provider(content, analysis_type, provider)
                    except Exception as e:
                        self.logger.warning(f"Provider {provider} failed: {e}")
                        continue
            
            raise Exception("All LLM providers failed")
            
        except Exception as e:
            self.logger.error(f"Error in multi-LLM analysis: {e}")
            raise
    
    async def _analyze_with_provider(self, content: str, analysis_type: str, provider: LLMProvider) -> Dict[str, Any]:
        """Analyze content with specific provider"""
        prompt = self._get_analysis_prompt(content, analysis_type)
        
        if provider == LLMProvider.OPENAI:
            response = await self.clients[provider].chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=4000
            )
            return {
                "provider": provider.value,
                "analysis": response.choices[0].message.content,
                "model": "gpt-4-turbo-preview",
                "tokens_used": response.usage.total_tokens
            }
            
        elif provider == LLMProvider.ANTHROPIC:
            response = await self.clients[provider].messages.create(
                model="claude-3-opus-20240229",
                max_tokens=4000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            return {
                "provider": provider.value,
                "analysis": response.content[0].text,
                "model": "claude-3-opus-20240229",
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens
            }
            
        elif provider == LLMProvider.GEMINI:
            response = self.clients[provider].generate_content(prompt)
            return {
                "provider": provider.value,
                "analysis": response.text,
                "model": "gemini-pro",
                "tokens_used": len(prompt) + len(response.text)  # Approximate
            }
            
        elif provider == LLMProvider.DEEPSEEK:
            response = await self.clients[provider].chat.completions.create(
                model="deepseek-coder",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=4000
            )
            return {
                "provider": provider.value,
                "analysis": response.choices[0].message.content,
                "model": "deepseek-coder",
                "tokens_used": response.usage.total_tokens
            }
    
    def _get_analysis_prompt(self, content: str, analysis_type: str) -> str:
        """Generate appropriate prompt based on analysis type"""
        base_prompt = f"""
        Analyze the following content and provide a comprehensive assessment:

        Content:
        {content}

        Please provide your analysis in JSON format with the following structure:
        {{
            "summary": "Brief summary of the content",
            "type": "Identified content type",
            "language": "Programming language or document type",
            "complexity": "Assessment of complexity level",
            "quality_score": "Score from 1-10",
            "key_components": ["List of main components or sections"],
            "recommendations": ["List of improvement recommendations"],
            "organization_suggestions": {{
                "category": "Suggested category for organization",
                "folder_structure": "Recommended folder placement",
                "related_files": "Types of files this should be grouped with"
            }},
            "learning_patterns": {{
                "patterns_identified": ["Technical patterns found"],
                "best_practices": ["Best practices observed"],
                "anti_patterns": ["Issues or anti-patterns found"]
            }}
        }}
        """
        
        if analysis_type == "code_analysis":
            return base_prompt + """
            
            Focus on:
            - Code quality and structure
            - Security vulnerabilities
            - Performance optimization opportunities
            - Design patterns used
            - Dependencies and imports
            - Documentation quality
            """
            
        elif analysis_type == "documentation":
            return base_prompt + """
            
            Focus on:
            - Documentation completeness
            - Clarity and readability
            - Structure and organization
            - Code examples quality
            - Missing sections
            - Accessibility
            """
            
        return base_prompt

# File Processor
class FileProcessor:
    def __init__(self, config: OrganizerConfig, llm_manager: MultiLLMManager):
        self.config = config
        self.llm_manager = llm_manager
        self.logger = logging.getLogger(__name__)
        
    def detect_file_type(self, file_path: str) -> FileType:
        """Detect file type based on extension and content"""
        ext = Path(file_path).suffix.lower()
        
        code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala', '.r', '.sql', '.sh', '.ps1', '.bat'}
        doc_extensions = {'.md', '.txt', '.rst', '.adoc', '.tex', '.pdf', '.doc', '.docx', '.rtf', '.odt'}
        config_extensions = {'.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.xml', '.env'}
        data_extensions = {'.csv', '.xlsx', '.xls', '.sqlite', '.db', '.json', '.parquet', '.avro'}
        media_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.mp4', '.avi', '.mov', '.pdf'}
        archive_extensions = {'.zip', '.tar', '.gz', '.rar', '.7z', '.bz2'}
        
        if ext in code_extensions:
            return FileType.CODE
        elif ext in doc_extensions:
            return FileType.DOCUMENTATION
        elif ext in config_extensions:
            return FileType.CONFIG
        elif ext in data_extensions:
            return FileType.DATA
        elif ext in media_extensions:
            return FileType.MEDIA
        elif ext in archive_extensions:
            return FileType.ARCHIVE
        else:
            return FileType.UNKNOWN
    
    async def process_file(self, file_path: str, session_id: str) -> Dict[str, Any]:
        """Process a single file"""
        try:
            # Basic file info
            file_stats = Path(file_path).stat()
            file_hash = await self._calculate_file_hash(file_path)
            file_type = self.detect_file_type(file_path)
            
            # Read content
            content = await self._read_file_content(file_path)
            if not content:
                return {"error": "Could not read file content"}
            
            # Analyze with LLM
            analysis_result = await self.llm_manager.analyze_with_best_model(
                content, 
                "code_analysis" if file_type == FileType.CODE else "documentation"
            )
            
            # Extract structured data
            try:
                analysis_data = json.loads(analysis_result["analysis"])
            except:
                analysis_data = {"raw_analysis": analysis_result["analysis"]}
            
            return {
                "file_info": {
                    "path": file_path,
                    "name": Path(file_path).name,
                    "size": file_stats.st_size,
                    "type": file_type.value,
                    "hash": file_hash,
                    "mime_type": mimetypes.guess_type(file_path)[0]
                },
                "analysis": analysis_data,
                "llm_metadata": {
                    "provider": analysis_result["provider"],
                    "model": analysis_result["model"],
                    "tokens_used": analysis_result["tokens_used"]
                },
                "session_id": session_id,
                "processed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}")
            return {"error": str(e)}
    
    async def _read_file_content(self, file_path: str) -> Optional[str]:
        """Read file content with proper encoding detection"""
        try:
            # Try UTF-8 first
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                return await f.read()
        except UnicodeDecodeError:
            try:
                # Try latin-1 as fallback
                async with aiofiles.open(file_path, 'r', encoding='latin-1') as f:
                    return await f.read()
            except:
                # Try binary mode for non-text files
                try:
                    async with aiofiles.open(file_path, 'rb') as f:
                        content = await f.read()
                        return content.decode('utf-8', errors='ignore')
                except:
                    return None
    
    async def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of file"""
        hash_md5 = hashlib.md5()
        async with aiofiles.open(file_path, 'rb') as f:
            async for chunk in self._chunked_read(f, 8192):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    async def _chunked_read(self, file_obj, chunk_size: int):
        """Read file in chunks"""
        while True:
            chunk = await file_obj.read(chunk_size)
            if not chunk:
                break
            yield chunk

# Organization Engine
class OrganizationEngine:
    def __init__(self, config: OrganizerConfig, llm_manager: MultiLLMManager):
        self.config = config
        self.llm_manager = llm_manager
        self.logger = logging.getLogger(__name__)
    
    async def organize_files(self, session_id: str, files_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Organize files based on analysis results"""
        try:
            # Analyze overall structure
            structure_analysis = await self._analyze_project_structure(files_data)
            
            # Create organization plan
            organization_plan = await self._create_organization_plan(
                files_data, 
                structure_analysis
            )
            
            # Execute organization
            if organization_plan.get("create_structure", True):
                await self._create_directory_structure(organization_plan)
            
            # Generate documentation
            if organization_plan.get("generate_docs", True):
                documentation = await self._generate_documentation(files_data, organization_plan)
            else:
                documentation = {}
            
            return {
                "session_id": session_id,
                "organization_plan": organization_plan,
                "documentation": documentation,
                "organized_files": len(files_data),
                "created_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error organizing files: {e}")
            raise
    
    async def _analyze_project_structure(self, files_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze overall project structure using LLM"""
        # Prepare summary for LLM
        file_summary = []
        for file_data in files_data:
            if "analysis" in file_data:
                file_summary.append({
                    "name": file_data["file_info"]["name"],
                    "type": file_data["file_info"]["type"],
                    "analysis": file_data["analysis"]
                })
        
        prompt = f"""
        Analyze this project structure and provide organization recommendations:
        
        Files: {json.dumps(file_summary, indent=2)}
        
        Provide response in JSON format:
        {{
            "project_type": "Type of project (web app, library, etc.)",
            "architecture_pattern": "Identified architecture pattern",
            "technology_stack": ["List of technologies identified"],
            "organization_strategy": {{
                "primary_categories": ["Main categories for organization"],
                "folder_structure": {{"folder": "purpose"}},
                "grouping_logic": "How files should be grouped"
            }},
            "recommendations": ["List of organization recommendations"]
        }}
        """
        
        result = await self.llm_manager.analyze_with_best_model(prompt, "documentation")
        
        try:
            return json.loads(result["analysis"])
        except:
            return {"error": "Could not parse structure analysis", "raw": result["analysis"]}
    
    async def _create_organization_plan(self, files_data: List[Dict[str, Any]], structure_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Create detailed organization plan"""
        plan = {
            "base_directory": os.path.join(self.config.storage_root, "organized"),
            "structure": structure_analysis.get("organization_strategy", {}),
            "file_mappings": {},
            "create_structure": True,
            "generate_docs": True
        }
        
        # Map each file to its organized location
        for file_data in files_data:
            file_info = file_data["file_info"]
            analysis = file_data.get("analysis", {})
            
            # Determine target folder based on analysis
            target_folder = self._determine_target_folder(file_info, analysis, structure_analysis)
            target_path = os.path.join(plan["base_directory"], target_folder, file_info["name"])
            
            plan["file_mappings"][file_info["path"]] = {
                "target_path": target_path,
                "folder": target_folder,
                "reason": f"Categorized as {analysis.get('type', 'unknown')} based on analysis"
            }
        
        return plan
    
    def _determine_target_folder(self, file_info: Dict, analysis: Dict, structure_analysis: Dict) -> str:
        """Determine target folder for file based on analysis"""
        file_type = file_info.get("type", "unknown")
        
        # Use LLM suggestions if available
        if "organization_suggestions" in analysis:
            suggested_folder = analysis["organization_suggestions"].get("folder_structure", "")
            if suggested_folder:
                return suggested_folder.strip("/")
        
        # Default categorization
        type_mapping = {
            "code": "src",
            "documentation": "docs", 
            "config": "config",
            "data": "data",
            "media": "assets",
            "archive": "archives"
        }
        
        return type_mapping.get(file_type, "misc")
    
    async def _create_directory_structure(self, plan: Dict[str, Any]):
        """Create the organized directory structure"""
        try:
            base_dir = Path(plan["base_directory"])
            base_dir.mkdir(parents=True, exist_ok=True)
            
            # Create all necessary directories
            folders = set()
            for mapping in plan["file_mappings"].values():
                folders.add(os.path.dirname(mapping["target_path"]))
            
            for folder in folders:
                Path(folder).mkdir(parents=True, exist_ok=True)
            
            # Copy/move files
            for source_path, mapping in plan["file_mappings"].items():
                source = Path(source_path)
                target = Path(mapping["target_path"])
                
                if source.exists():
                    # Copy file (preserve original)
                    import shutil
                    shutil.copy2(source, target)
                    
        except Exception as e:
            self.logger.error(f"Error creating directory structure: {e}")
            raise
    
    async def _generate_documentation(self, files_data: List[Dict[str, Any]], plan: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive documentation"""
        try:
            # Create documentation sections
            docs = {
                "project_overview": await self._generate_project_overview(files_data),
                "file_index": await self._generate_file_index(files_data, plan),
                "api_documentation": await self._generate_api_docs(files_data),
                "setup_guide": await self._generate_setup_guide(files_data),
                "organization_guide": await self._generate_organization_guide(plan)
            }
            
            # Save documentation files
            docs_dir = Path(plan["base_directory"]) / "docs"
            docs_dir.mkdir(exist_ok=True)
            
            for doc_type, content in docs.items():
                if content:
                    doc_path = docs_dir / f"{doc_type}.md"
                    async with aiofiles.open(doc_path, 'w', encoding='utf-8') as f:
                        await f.write(content)
            
            return docs
            
        except Exception as e:
            self.logger.error(f"Error generating documentation: {e}")
            return {}
    
    async def _generate_project_overview(self, files_data: List[Dict[str, Any]]) -> str:
        """Generate project overview documentation"""
        # Prepare data for LLM
        project_summary = {
            "file_count": len(files_data),
            "file_types": {},
            "technologies": set(),
            "key_files": []
        }
        
        for file_data in files_data:
            file_type = file_data["file_info"]["type"]
            project_summary["file_types"][file_type] = project_summary["file_types"].get(file_type, 0) + 1
            
            analysis = file_data.get("analysis", {})
            if "language" in analysis:
                project_summary["technologies"].add(analysis["language"])
            
            # Identify key files
            if analysis.get("quality_score", 0) > 7 or "main" in file_data["file_info"]["name"].lower():
                project_summary["key_files"].append({
                    "name": file_data["file_info"]["name"],
                    "type": file_type,
                    "summary": analysis.get("summary", "")
                })
        
        project_summary["technologies"] = list(project_summary["technologies"])
        
        prompt = f"""
        Generate a comprehensive project overview documentation based on this analysis:
        
        {json.dumps(project_summary, indent=2)}
        
        Create a professional README.md style overview including:
        1. Project title and description
        2. Technology stack
        3. Project structure overview
        4. Key components and files
        5. Getting started section
        6. Features and capabilities
        
        Format as proper Markdown.
        """
        
        result = await self.llm_manager.analyze_with_best_model(prompt, "documentation")
        return result["analysis"]
    
    async def _generate_file_index(self, files_data: List[Dict[str, Any]], plan: Dict[str, Any]) -> str:
        """Generate comprehensive file index"""
        index_content = "# File Index\n\n"
        
        # Group by folder
        folder_groups = {}
        for file_data in files_data:
            source_path = file_data["file_info"]["path"]
            if source_path in plan["file_mappings"]:
                folder = plan["file_mappings"][source_path]["folder"]
                if folder not in folder_groups:
                    folder_groups[folder] = []
                folder_groups[folder].append(file_data)
        
        # Generate index for each folder
        for folder, files in folder_groups.items():
            index_content += f"## {folder.title()}\n\n"
            
            for file_data in files:
                file_info = file_data["file_info"]
                analysis = file_data.get("analysis", {})
                
                index_content += f"### {file_info['name']}\n"
                index_content += f"- **Type**: {file_info['type']}\n"
                index_content += f"- **Size**: {file_info['size']} bytes\n"
                
                if "summary" in analysis:
                    index_content += f"- **Description**: {analysis['summary']}\n"
                
                if "language" in analysis:
                    index_content += f"- **Language**: {analysis['language']}\n"
                
                if "quality_score" in analysis:
                    index_content += f"- **Quality Score**: {analysis['quality_score']}/10\n"
                
                index_content += "\n"
        
        return index_content
    
    async def _generate_api_docs(self, files_data: List[Dict[str, Any]]) -> str:
        """Generate API documentation from code files"""
        api_files = [
            file_data for file_data in files_data
            if file_data["file_info"]["type"] == "code" and 
            any(keyword in file_data.get("analysis", {}).get("summary", "").lower() 
                for keyword in ["api", "endpoint", "route", "controller"])
        ]
        
        if not api_files:
            return ""
        
        prompt = f"""
        Generate API documentation based on these API-related files:
        
        {json.dumps([{
            "name": f["file_info"]["name"],
            "analysis": f.get("analysis", {})
        } for f in api_files], indent=2)}
        
        Create comprehensive API documentation including:
        1. API Overview
        2. Authentication requirements
        3. Available endpoints
        4. Request/response formats
        5. Error codes
        6. Usage examples
        
        Format as proper Markdown.
        """
        
        result = await self.llm_manager.analyze_with_best_model(prompt, "documentation")
        return result["analysis"]
    
    async def _generate_setup_guide(self, files_data: List[Dict[str, Any]]) -> str:
        """Generate setup and installation guide"""
        config_files = [
            file_data for file_data in files_data
            if file_data["file_info"]["type"] in ["config", "code"] and
            any(keyword in file_data["file_info"]["name"].lower()
                for keyword in ["package.json", "requirements.txt", "pom.xml", "cargo.toml", "go.mod"])
        ]
        
        prompt = f"""
        Generate a setup and installation guide based on these configuration files:
        
        {json.dumps([{
            "name": f["file_info"]["name"],
            "analysis": f.get("analysis", {})
        } for f in config_files], indent=2)}
        
        Create a comprehensive setup guide including:
        1. Prerequisites and system requirements
        2. Installation steps
        3. Configuration instructions
        4. Environment setup
        5. Running the application
        6. Troubleshooting common issues
        
        Format as proper Markdown.
        """
        
        if not config_files:
            return "# Setup Guide\n\nNo configuration files detected. Manual setup may be required."
        
        result = await self.llm_manager.analyze_with_best_model(prompt, "documentation")
        return result["analysis"]
    
    async def _generate_organization_guide(self, plan: Dict[str, Any]) -> str:
        """Generate guide explaining the organization structure"""
        guide_content = "# Organization Guide\n\n"
        guide_content += "This document explains how the files have been organized.\n\n"
        
        guide_content += "## Directory Structure\n\n"
        
        # Show folder structure
        folders = set()
        for mapping in plan["file_mappings"].values():
            folders.add(mapping["folder"])
        
        for folder in sorted(folders):
            guide_content += f"### {folder}/\n"
            
            # Count files in folder
            file_count = sum(1 for m in plan["file_mappings"].values() if m["folder"] == folder)
            guide_content += f"Contains {file_count} files\n\n"
            
            # Show some example files
            example_files = [
                os.path.basename(source) for source, mapping in plan["file_mappings"].items() 
                if mapping["folder"] == folder
            ][:5]
            
            if example_files:
                guide_content += "Examples:\n"
                for file in example_files:
                    guide_content += f"- {file}\n"
                guide_content += "\n"
        
        guide_content += "## Organization Logic\n\n"
        guide_content += "Files were organized based on:\n"
        guide_content += "- File type and extension\n"
        guide_content += "- Content analysis using AI\n"
        guide_content += "- Best practices for project structure\n"
        guide_content += "- Related functionality grouping\n\n"
        
        return guide_content

# Learning Engine
class LearningEngine:
    def __init__(self, config: OrganizerConfig, db_engine):
        self.config = config
        self.db_engine = db_engine
        self.logger = logging.getLogger(__name__)
        self.patterns = {}
        self.feedback_data = []
    
    async def learn_from_analysis(self, session_id: str, file_data: Dict[str, Any]):
        """Learn patterns from file analysis"""
        try:
            analysis = file_data.get("analysis", {})
            if not analysis:
                return
            
            # Extract learning patterns
            patterns = self._extract_patterns(file_data)
            
            # Store in database
            async with AsyncSession(self.db_engine) as session:
                for pattern_type, pattern_data in patterns.items():
                    learning_record = LearningData(
                        id=f"{session_id}_{file_data['file_info']['hash']}_{pattern_type}",
                        session_id=session_id,
                        file_id=file_data['file_info']['hash'],
                        pattern_type=pattern_type,
                        pattern_data=pattern_data,
                        confidence_score=self._calculate_confidence(pattern_data)
                    )
                    session.add(learning_record)
                await session.commit()
            
            self.logger.info(f"Learned {len(patterns)} patterns from {file_data['file_info']['name']}")
            
        except Exception as e:
            self.logger.error(f"Error in learning process: {e}")
    
    def _extract_patterns(self, file_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract learnable patterns from analysis"""
        patterns = {}
        analysis = file_data.get("analysis", {})
        file_info = file_data["file_info"]
        
        # File type patterns
        patterns["file_type_indicators"] = {
            "extension": Path(file_info["name"]).suffix,
            "detected_type": file_info["type"],
            "size_range": self._get_size_range(file_info["size"]),
            "language": analysis.get("language", "unknown")
        }
        
        # Quality patterns
        if "quality_score" in analysis:
            patterns["quality_indicators"] = {
                "score": analysis["quality_score"],
                "complexity": analysis.get("complexity", "unknown"),
                "key_components": analysis.get("key_components", []),
                "best_practices": analysis.get("learning_patterns", {}).get("best_practices", [])
            }
        
        # Organization patterns
        if "organization_suggestions" in analysis:
            patterns["organization_preferences"] = analysis["organization_suggestions"]
        
        # Technology patterns
        if analysis.get("learning_patterns"):
            patterns["technology_patterns"] = analysis["learning_patterns"]
        
        return patterns
    
    def _get_size_range(self, size: int) -> str:
        """Categorize file size"""
        if size < 1024:
            return "tiny"
        elif size < 10240:
            return "small"
        elif size < 102400:
            return "medium"
        elif size < 1048576:
            return "large"
        else:
            return "huge"
    
    def _calculate_confidence(self, pattern_data: Any) -> float:
        """Calculate confidence score for pattern"""
        if isinstance(pattern_data, dict):
            return min(1.0, len(pattern_data) / 10.0)
        return 0.5
    
    async def get_recommendations(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI-powered recommendations based on learned patterns"""
        try:
            # Query similar patterns from database
            async with AsyncSession(self.db_engine) as session:
                # Get similar file type patterns
                result = await session.execute(
                    sa.text("""
                    SELECT pattern_data, confidence_score 
                    FROM learning_data 
                    WHERE pattern_type = 'file_type_indicators'
                    AND JSON_EXTRACT(pattern_data, '$.extension') = :ext
                    ORDER BY confidence_score DESC
                    LIMIT 10
                    """),
                    {"ext": Path(file_info["name"]).suffix}
                )
                similar_patterns = result.fetchall()
            
            if not similar_patterns:
                return {"recommendations": [], "confidence": 0.0}
            
            # Aggregate recommendations
            recommendations = self._aggregate_recommendations(similar_patterns)
            
            return {
                "recommendations": recommendations,
                "confidence": sum(p[1] for p in similar_patterns) / len(similar_patterns),
                "based_on_patterns": len(similar_patterns)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting recommendations: {e}")
            return {"recommendations": [], "confidence": 0.0}
    
    def _aggregate_recommendations(self, patterns: List[Tuple]) -> List[str]:
        """Aggregate recommendations from similar patterns"""
        recommendations = []
        
        for pattern_data, confidence in patterns:
            try:
                data = json.loads(pattern_data) if isinstance(pattern_data, str) else pattern_data
                
                # Extract organization suggestions
                if "organization_preferences" in data:
                    org_prefs = data["organization_preferences"]
                    if "folder_structure" in org_prefs:
                        recommendations.append(f"Consider organizing in: {org_prefs['folder_structure']}")
                
                # Extract quality suggestions
                if "quality_indicators" in data:
                    quality = data["quality_indicators"]
                    if quality.get("score", 0) > 8:
                        recommendations.append("This file type typically achieves high quality scores")
                
            except Exception:
                continue
        
        return list(set(recommendations))  # Remove duplicates
    
    async def process_feedback(self, feedback: LearningFeedback):
        """Process user feedback to improve recommendations"""
        try:
            async with AsyncSession(self.db_engine) as session:
                # Update learning data with feedback
                result = await session.execute(
                    sa.text("""
                    UPDATE learning_data 
                    SET feedback_score = :score
                    WHERE session_id = :session_id AND file_id = :file_id
                    """),
                    {
                        "score": feedback.score,
                        "session_id": feedback.session_id,
                        "file_id": feedback.file_id
                    }
                )
                await session.commit()
            
            self.logger.info(f"Processed feedback for session {feedback.session_id}")
            
        except Exception as e:
            self.logger.error(f"Error processing feedback: {e}")

# Browser Integration
class BrowserService:
    def __init__(self, config: OrganizerConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session = None
    
    async def initialize(self):
        """Initialize browser session"""
        if not self.config.enable_browser:
            return
        
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.browser_timeout)
        )
        self.logger.info("✅ Browser service initialized")
    
    async def fetch_url_content(self, url: str) -> Dict[str, Any]:
        """Fetch and analyze content from URL"""
        if not self.session:
            return {"error": "Browser service not initialized"}
        
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return {"error": f"HTTP {response.status}"}
                
                content_type = response.headers.get('content-type', '')
                content = await response.text()
                
                # Parse based on content type
                if 'html' in content_type:
                    parsed_content = self._parse_html(content)
                elif 'json' in content_type:
                    parsed_content = self._parse_json(content)
                else:
                    parsed_content = {"raw_content": content}
                
                return {
                    "url": url,
                    "content_type": content_type,
                    "status": response.status,
                    "content": parsed_content,
                    "fetched_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error fetching URL {url}: {e}")
            return {"error": str(e)}
    
    def _parse_html(self, html_content: str) -> Dict[str, Any]:
        """Parse HTML content"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract meaningful content
            title = soup.find('title')
            title_text = title.get_text().strip() if title else ""
            
            # Remove script and style tags
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text_content = soup.get_text()
            lines = (line.strip() for line in text_content.splitlines())
            text_content = '\n'.join(line for line in lines if line)
            
            # Convert to markdown
            markdown_content = md(html_content)
            
            return {
                "title": title_text,
                "text_content": text_content[:10000],  # Limit size
                "markdown_content": markdown_content[:10000],
                "links": [a.get('href') for a in soup.find_all('a', href=True)][:50],
                "images": [img.get('src') for img in soup.find_all('img', src=True)][:20]
            }
            
        except Exception as e:
            return {"error": f"HTML parsing error: {e}"}
    
    def _parse_json(self, json_content: str) -> Dict[str, Any]:
        """Parse JSON content"""
        try:
            data = json.loads(json_content)
            return {"json_data": data}
        except Exception as e:
            return {"error": f"JSON parsing error: {e}"}
    
    async def close(self):
        """Close browser session"""
        if self.session:
            await self.session.close()

# Main Organizer Class
class CodeDocumentationOrganizer:
    def __init__(self, config: OrganizerConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.llm_manager = MultiLLMManager(config)
        self.file_processor = FileProcessor(config, self.llm_manager)
        self.organization_engine = OrganizationEngine(config, self.llm_manager)
        self.browser_service = BrowserService(config)
        
        # Database
        self.db_engine = None
        self.learning_engine = None
        
        # Redis cache
        self.redis_client = None
        
        # Thread pool for CPU-bound tasks
        self.thread_pool = ThreadPoolExecutor(max_workers=config.max_workers)
    
    async def initialize(self):
        """Initialize all components"""
        try:
            self.logger.info("🚀 Initializing YMERA Code & Documentation Organizer...")
            
            # Initialize database
            self.db_engine = create_async_engine(
                self.config.database_url,
                echo=False,
                pool_pre_ping=True
            )
            
            # Create tables
            async with self.db_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            # Initialize Redis
            self.redis_client = redis.from_url(self.config.redis_url)
            await self.redis_client.ping()
            
            # Initialize components
            await self.llm_manager.initialize()
            self.learning_engine = LearningEngine(self.config, self.db_engine)
            await self.browser_service.initialize()
            
            # Create storage directories
            Path(self.config.storage_root).mkdir(parents=True, exist_ok=True)
            
            self.logger.info("✅ YMERA Organizer fully initialized")
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            raise
    
    async def create_analysis_session(self, name: str, description: str = "") -> str:
        """Create a new analysis session"""
        try:
            session_id = f"session_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
            
            async with AsyncSession(self.db_engine) as session:
                analysis_session = AnalysisSession(
                    id=session_id,
                    name=name,
                    description=description,
                    configuration=asdict(self.config)
                )
                session.add(analysis_session)
                await session.commit()
            
            # Cache session info
            await self.redis_client.setex(
                f"session:{session_id}",
                3600,  # 1 hour TTL
                json.dumps({
                    "id": session_id,
                    "name": name,
                    "created_at": datetime.utcnow().isoformat()
                })
            )
            
            self.logger.info(f"Created analysis session: {session_id}")
            return session_id
            
        except Exception as e:
            self.logger.error(f"Error creating session: {e}")
            raise
    
    async def analyze_files(self, session_id: str, file_paths: List[str]) -> Dict[str, Any]:
        """Analyze multiple files"""
        try:
            results = {
                "session_id": session_id,
                "total_files": len(file_paths),
                "processed_files": [],
                "failed_files": [],
                "started_at": datetime.utcnow().isoformat()
            }
            
            # Process files concurrently
            tasks = []
            for file_path in file_paths:
                task = asyncio.create_task(
                    self._process_single_file(session_id, file_path)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            file_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect results
            for i, result in enumerate(file_results):
                if isinstance(result, Exception):
                    results["failed_files"].append({
                        "path": file_paths[i],
                        "error": str(result)
                    })
                else:
                    if "error" in result:
                        results["failed_files"].append({
                            "path": file_paths[i],
                            "error": result["error"]
                        })
                    else:
                        results["processed_files"].append(result)
                        
                        # Store in database
                        await self._store_file_record(result)
                        
                        # Learn from analysis
                        await self.learning_engine.learn_from_analysis(session_id, result)
            
            # Update session status
            await self._update_session_status(session_id, ProcessingStatus.COMPLETED, results)
            
            results["completed_at"] = datetime.utcnow().isoformat()
            results["success_rate"] = len(results["processed_files"]) / len(file_paths)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error analyzing files: {e}")
            await self._update_session_status(session_id, ProcessingStatus.FAILED, {"error": str(e)})
            raise
    
    async def _process_single_file(self, session_id: str, file_path: str) -> Dict[str, Any]:
        """Process a single file with error handling"""
        try:
            # Check if file exists and is readable
            if not os.path.exists(file_path):
                return {"error": f"File not found: {file_path}"}
            
            file_size = os.path.getsize(file_path)
            if file_size > self.config.max_file_size:
                return {"error": f"File too large: {file_size} bytes"}
            
            # Process the file
            return await self.file_processor.process_file(file_path, session_id)
            
        except Exception as e:
            return {"error": f"Processing error: {str(e)}"}
    
    async def _store_file_record(self, file_data: Dict[str, Any]):
        """Store file analysis record in database"""
        try:
            file_info = file_data["file_info"]
            
            async with AsyncSession(self.db_engine) as session:
                file_record = FileRecord(
                    id=file_info["hash"],
                    original_name=file_info["name"],
                    file_type=FileType(file_info["type"]),
                    size=file_info["size"],
                    hash_md5=file_info["hash"],
                    storage_path=file_info["path"],
                    mime_type=file_info.get("mime_type"),
                    processing_status=ProcessingStatus.COMPLETED,
                    metadata=file_info,
                    analysis_results=file_data.get("analysis", {}),
                    organization_data=file_data.get("llm_metadata", {})
                )
                
                # Use merge to handle duplicates
                merged = await session.merge(file_record)
                await session.commit()
            
        except Exception as e:
            self.logger.error(f"Error storing file record: {e}")
    
    async def _update_session_status(self, session_id: str, status: ProcessingStatus, results: Dict[str, Any]):
        """Update session status in database"""
        try:
            async with AsyncSession(self.db_engine) as session:
                result = await session.execute(
                    sa.text("""
                    UPDATE analysis_sessions 
                    SET status = :status, results_summary = :results, updated_at = :updated_at,
                        file_count = :file_count
                    WHERE id = :session_id
                    """),
                    {
                        "status": status.value,
                        "results": json.dumps(results),
                        "updated_at": datetime.utcnow(),
                        "file_count": results.get("total_files", 0),
                        "session_id": session_id
                    }
                )
                await session.commit()
            
        except Exception as e:
            self.logger.error(f"Error updating session status: {e}")
    
    async def organize_session_files(self, session_id: str, strategy: str = "intelligent") -> Dict[str, Any]:
        """Organize all files from an analysis session"""
        try:
            # Get all processed files from session
            async with AsyncSession(self.db_engine) as db_session:
                result = await db_session.execute(
                    sa.text("""
                    SELECT metadata, analysis_results, organization_data
                    FROM file_records fr
                    JOIN learning_data ld ON fr.id = ld.file_id
                    WHERE ld.session_id = :session_id
                    """),
                    {"session_id": session_id}
                )
                records = result.fetchall()
            
            if not records:
                return {"error": "No files found for session"}
            
            # Prepare files data for organization
            files_data = []
            for record in records:
                file_data = {
                    "file_info": record[0],  # metadata
                    "analysis": record[1],   # analysis_results
                    "llm_metadata": record[2]  # organization_data
                }
                files_data.append(file_data)
            
            # Organize files
            organization_result = await self.organization_engine.organize_files(
                session_id, files_data
            )
            
            # Update session with organization results
            await self._update_session_status(
                session_id, 
                ProcessingStatus.COMPLETED, 
                organization_result
            )
            
            return organization_result
            
        except Exception as e:
            self.logger.error(f"Error organizing session files: {e}")
            raise
    
    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get detailed session status"""
        try:
            # Check cache first
            cached = await self.redis_client.get(f"session_status:{session_id}")
            if cached:
                return json.loads(cached)
            
            # Get from database
            async with AsyncSession(self.db_engine) as session:
                result = await session.execute(
                    sa.text("""
                    SELECT * FROM analysis_sessions WHERE id = :session_id
                    """),
                    {"session_id": session_id}
                )
                session_record = result.fetchone()
            
            if not session_record:
                return {"error": "Session not found"}
            
            # Get file statistics
            async with AsyncSession(self.db_engine) as session:
                stats_result = await session.execute(
                    sa.text("""
                    SELECT 
                        COUNT(*) as total_files,
                        COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed_files,
                        COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed_files,
                        AVG(size) as avg_file_size
                    FROM file_records fr
                    JOIN learning_data ld ON fr.id = ld.file_id
                    WHERE ld.session_id = :session_id
                    """),
                    {"session_id": session_id}
                )
                stats = stats_result.fetchone()
            
            status_data = {
                "session_id": session_id,
                "name": session_record.name,
                "description": session_record.description,
                "status": session_record.status.value,
                "created_at": session_record.created_at.isoformat(),
                "updated_at": session_record.updated_at.isoformat(),
                "statistics": {
                    "total_files": stats[0] or 0,
                    "completed_files": stats[1] or 0,
                    "failed_files": stats[2] or 0,
                    "avg_file_size": float(stats[3]) if stats[3] else 0
                },
                "results_summary": session_record.results_summary
            }
            
            # Cache for 5 minutes
            await self.redis_client.setex(
                f"session_status:{session_id}",
                300,
                json.dumps(status_data)
            )
            
            return status_data
            
        except Exception as e:
            self.logger.error(f"Error getting session status: {e}")
            return {"error": str(e)}
    
    async def search_files(self, query: str, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search files using semantic search"""
        try:
            # This would integrate with your vector database for semantic search
            # For now, implementing simple text search
            
            search_conditions = ["LOWER(original_name) LIKE LOWER(:query)"]
            params = {"query": f"%{query}%"}
            
            if session_id:
                # Join with learning_data to filter by session
                query_sql = """
                SELECT fr.*, ld.session_id
                FROM file_records fr
                JOIN learning_data ld ON fr.id = ld.file_id
                WHERE ld.session_id = :session_id AND (""" + " OR ".join(search_conditions) + ")"
                params["session_id"] = session_id
            else:
                query_sql = "SELECT * FROM file_records WHERE " + " OR ".join(search_conditions)
            
            async with AsyncSession(self.db_engine) as session:
                result = await session.execute(sa.text(query_sql), params)
                records = result.fetchall()
            
            return [dict(record._mapping) for record in records]
            
        except Exception as e:
            self.logger.error(f"Error searching files: {e}")
            return []
    
    async def get_learning_insights(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get learning insights and patterns"""
        try:
            conditions = []
            params = {}
            
            if session_id:
                conditions.append("session_id = :session_id")
                params["session_id"] = session_id
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            async with AsyncSession(self.db_engine) as session:
                # Get pattern statistics
                result = await session.execute(
                    sa.text(f"""
                    SELECT 
                        pattern_type,
                        COUNT(*) as pattern_count,
                        AVG(confidence_score) as avg_confidence,
                        AVG(feedback_score) as avg_feedback
                    FROM learning_data 
                    {where_clause}
                    GROUP BY pattern_type
                    ORDER BY pattern_count DESC
                    """),
                    params
                )
                pattern_stats = result.fetchall()
                
                # Get top patterns
                result = await session.execute(
                    sa.text(f"""
                    SELECT pattern_type, pattern_data, confidence_score
                    FROM learning_data 
                    {where_clause}
                    ORDER BY confidence_score DESC
                    LIMIT 20
                    """),
                    params
                )
                top_patterns = result.fetchall()
            
            return {
                "pattern_statistics": [
                    {
                        "type": stat.pattern_type,
                        "count": stat.pattern_count,
                        "avg_confidence": float(stat.avg_confidence or 0),
                        "avg_feedback": float(stat.avg_feedback or 0)
                    }
                    for stat in pattern_stats
                ],
                "top_patterns": [
                    {
                        "type": pattern.pattern_type,
                        "data": json.loads(pattern.pattern_data) if isinstance(pattern.pattern_data, str) else pattern.pattern_data,
                        "confidence": float(pattern.confidence_score)
                    }
                    for pattern in top_patterns
                ],
                "total_patterns": sum(stat.pattern_count for stat in pattern_stats),
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting learning insights: {e}")
            return {"error": str(e)}
    
    async def analyze_url(self, url: str, session_id: str) -> Dict[str, Any]:
        """Analyze content from a URL"""
        try:
            # Fetch content from URL
            web_content = await self.browser_service.fetch_url_content(url)
            
            if "error" in web_content:
                return web_content
            
            # Analyze the content with LLM
            content_text = web_content["content"].get("text_content", "")
            if content_text:
                analysis_result = await self.llm_manager.analyze_with_best_model(
                    content_text, "documentation"
                )
                
                # Structure the result
                result = {
                    "url": url,
                    "session_id": session_id,
                    "web_content": web_content,
                    "analysis": analysis_result,
                    "analyzed_at": datetime.utcnow().isoformat()
                }
                
                # Store as virtual file record
                file_data = {
                    "file_info": {
                        "name": f"web_content_{hashlib.md5(url.encode()).hexdigest()[:8]}.md",
                        "path": url,
                        "type": "documentation",
                        "size": len(content_text),
                        "hash": hashlib.md5(content_text.encode()).hexdigest(),
                        "mime_type": "text/html"
                    },
                    "analysis": json.loads(analysis_result["analysis"]) if analysis_result.get("analysis") else {},
                    "llm_metadata": {
                        "provider": analysis_result.get("provider"),
                        "source": "web_analysis"
                    }
                }
                
                # Learn from web content analysis
                await self.learning_engine.learn_from_analysis(session_id, file_data)
                
                return result
            else:
                return {"error": "No analyzable content found"}
                
        except Exception as e:
            self.logger.error(f"Error analyzing URL {url}: {e}")
            return {"error": str(e)}
    
    async def export_session(self, session_id: str, format: str = "zip") -> str:
        """Export session results in specified format"""
        try:
            # Get session data
            session_status = await self.get_session_status(session_id)
            if "error" in session_ async def export_session(self, session_id: str, format: str = "zip") -> str:
        """Export session results in specified format"""
        try:
            # Get session data
            session_status = await self.get_session_status(session_id)
            if "error" in session_status:
                raise ValueError(f"Session error: {session_status['error']}")
            
            # Create export directory
            export_dir = Path(self.config.storage_root) / "exports" / session_id
            export_dir.mkdir(parents=True, exist_ok=True)
            
            # Get all files from session
            async with AsyncSession(self.db_engine) as session:
                result = await session.execute(
                    sa.text("""
                    SELECT fr.*, ld.pattern_data, ld.confidence_score
                    FROM file_records fr
                    JOIN learning_data ld ON fr.id = ld.file_id
                    WHERE ld.session_id = :session_id
                    ORDER BY fr.original_name
                    """),
                    {"session_id": session_id}
                )
                files = result.fetchall()
            
            # Export files and metadata
            exported_files = []
            for file_record in files:
                file_info = {
                    "original_name": file_record.original_name,
                    "file_type": file_record.file_type.value,
                    "size": file_record.size,
                    "analysis_results": file_record.analysis_results,
                    "organization_data": file_record.organization_data,
                    "confidence_score": float(file_record.confidence_score or 0)
                }
                exported_files.append(file_info)
                
                # Copy actual file if it exists
                if file_record.storage_path and os.path.exists(file_record.storage_path):
                    dest_path = export_dir / "files" / file_record.original_name
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    async with aiofiles.open(file_record.storage_path, 'rb') as src:
                        content = await src.read()
                        async with aiofiles.open(dest_path, 'wb') as dst:
                            await dst.write(content)
            
            # Create session summary
            session_summary = {
                "session_info": session_status,
                "files": exported_files,
                "learning_insights": await self.get_learning_insights(session_id),
                "export_metadata": {
                    "exported_at": datetime.utcnow().isoformat(),
                    "export_format": format,
                    "total_files": len(exported_files),
                    "ymera_version": "1.0.0"
                }
            }
            
            # Save summary as JSON
            summary_path = export_dir / "session_summary.json"
            async with aiofiles.open(summary_path, 'w') as f:
                await f.write(json.dumps(session_summary, indent=2, ensure_ascii=False))
            
            # Create README
            readme_content = f"""# YMERA Session Export: {session_status['name']}

## Session Information
- **Session ID**: {session_id}
- **Created**: {session_status.get('created_at', 'Unknown')}
- **Status**: {session_status.get('status', 'Unknown')}
- **Total Files**: {len(exported_files)}

## Contents
- `session_summary.json` - Complete session metadata and analysis results
- `files/` - Directory containing all processed files
- `README.md` - This file

## Analysis Statistics
{json.dumps(session_status.get('statistics', {}), indent=2)}

Generated by YMERA Enterprise Code & Documentation Organizer
Export Date: {datetime.utcnow().isoformat()}
"""
            
            readme_path = export_dir / "README.md"
            async with aiofiles.open(readme_path, 'w') as f:
                await f.write(readme_content)
            
            # Create archive based on format
            if format.lower() == "zip":
                archive_path = export_dir.parent / f"{session_id}_export.zip"
                with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(export_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arc_path = os.path.relpath(file_path, export_dir)
                            zipf.write(file_path, arc_path)
            
            elif format.lower() in ["tar", "tar.gz"]:
                mode = "w:gz" if format.lower() == "tar.gz" else "w"
                archive_path = export_dir.parent / f"{session_id}_export.{format.lower()}"
                with tarfile.open(archive_path, mode) as tarf:
                    tarf.add(export_dir, arcname=f"{session_id}_export")
            else:
                # Return directory path for other formats
                return str(export_dir)
            
            self.logger.info(f"Session {session_id} exported to {archive_path}")
            return str(archive_path)
            
        except Exception as e:
            self.logger.error(f"Error exporting session {session_id}: {e}")
            raise
    
    async def import_session(self, import_path: str, new_session_name: str) -> str:
        """Import a previously exported session"""
        try:
            import_path = Path(import_path)
            temp_dir = Path(self.config.storage_root) / "temp" / f"import_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract archive if needed
            if import_path.suffix == '.zip':
                with zipfile.ZipFile(import_path, 'r') as zipf:
                    zipf.extractall(temp_dir)
            elif import_path.suffix in ['.tar', '.gz']:
                with tarfile.open(import_path, 'r') as tarf:
                    tarf.extractall(temp_dir)
            else:
                # Assume it's a directory
                temp_dir = import_path
            
            # Load session summary
            summary_file = None
            for root, dirs, files in os.walk(temp_dir):
                if 'session_summary.json' in files:
                    summary_file = os.path.join(root, 'session_summary.json')
                    break
            
            if not summary_file:
                raise ValueError("Invalid export: session_summary.json not found")
            
            async with aiofiles.open(summary_file, 'r') as f:
                session_data = json.loads(await f.read())
            
            # Create new session
            new_session_id = await self.create_analysis_session(
                new_session_name,
                f"Imported from {import_path.name}"
            )
            
            # Import files
            files_dir = Path(summary_file).parent / "files"
            if files_dir.exists():
                imported_files = []
                for file_data in session_data.get("files", []):
                    file_path = files_dir / file_data["original_name"]
                    if file_path.exists():
                        # Process imported file
                        result = await self._process_single_file(new_session_id, str(file_path))
                        if "error" not in result:
                            imported_files.append(result)
                            await self._store_file_record(result)
                
                # Update session with import results
                await self._update_session_status(
                    new_session_id,
                    ProcessingStatus.COMPLETED,
                    {
                        "imported_from": str(import_path),
                        "original_session": session_data.get("session_info", {}),
                        "imported_files": len(imported_files),
                        "import_date": datetime.utcnow().isoformat()
                    }
                )
            
            self.logger.info(f"Session imported as {new_session_id}")
            return new_session_id
            
        except Exception as e:
            self.logger.error(f"Error importing session from {import_path}: {e}")
            raise
    
    async def get_system_statistics(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        try:
            async with AsyncSession(self.db_engine) as session:
                # Session statistics
                sessions_result = await session.execute(
                    sa.text("""
                    SELECT 
                        COUNT(*) as total_sessions,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_sessions,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_sessions,
                        AVG(file_count) as avg_files_per_session
                    FROM analysis_sessions
                    """)
                )
                session_stats = sessions_result.fetchone()
                
                # File statistics
                files_result = await session.execute(
                    sa.text("""
                    SELECT 
                        COUNT(*) as total_files,
                        COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as processed_files,
                        SUM(size) as total_size,
                        AVG(size) as avg_file_size,
                        file_type,
                        COUNT(*) as type_count
                    FROM file_records
                    GROUP BY file_type
                    """)
                )
                file_stats = files_result.fetchall()
                
                # Learning statistics
                learning_result = await session.execute(
                    sa.text("""
                    SELECT 
                        COUNT(*) as total_patterns,
                        AVG(confidence_score) as avg_confidence,
                        pattern_type,
                        COUNT(*) as pattern_count
                    FROM learning_data
                    GROUP BY pattern_type
                    """)
                )
                learning_stats = learning_result.fetchall()
                
                # Recent activity
                recent_result = await session.execute(
                    sa.text("""
                    SELECT name, status, created_at, file_count
                    FROM analysis_sessions
                    ORDER BY created_at DESC
                    LIMIT 10
                    """)
                )
                recent_sessions = recent_result.fetchall()
            
            # LLM usage statistics
            llm_stats = await self.llm_manager.get_usage_statistics()
            
            return {
                "system_overview": {
                    "total_sessions": session_stats[0] or 0,
                    "completed_sessions": session_stats[1] or 0,
                    "failed_sessions": session_stats[2] or 0,
                    "avg_files_per_session": float(session_stats[3] or 0),
                    "success_rate": (session_stats[1] or 0) / max(session_stats[0] or 1, 1)
                },
                "file_statistics": {
                    "by_type": [
                        {
                            "type": stat.file_type.value if hasattr(stat.file_type, 'value') else str(stat.file_type),
                            "count": stat.type_count,
                            "total_size": sum(s[2] for s in file_stats if s[4] == stat.file_type) or 0
                        }
                        for stat in file_stats
                    ],
                    "totals": {
                        "total_files": sum(stat.type_count for stat in file_stats),
                        "total_size": sum(stat[2] for stat in file_stats if stat[2]) or 0,
                        "avg_file_size": sum(stat[3] for stat in file_stats if stat[3]) / len(file_stats) if file_stats else 0
                    }
                },
                "learning_insights": {
                    "by_type": [
                        {
                            "pattern_type": stat.pattern_type,
                            "count": stat.pattern_count,
                            "avg_confidence": float(stat[1] or 0)
                        }
                        for stat in learning_stats
                    ],
                    "totals": {
                        "total_patterns": sum(stat.pattern_count for stat in learning_stats),
                        "overall_confidence": sum(stat[1] for stat in learning_stats if stat[1]) / len(learning_stats) if learning_stats else 0
                    }
                },
                "llm_usage": llm_stats,
                "recent_activity": [
                    {
                        "session_name": session.name,
                        "status": session.status.value if hasattr(session.status, 'value') else str(session.status),
                        "created_at": session.created_at.isoformat(),
                        "file_count": session.file_count or 0
                    }
                    for session in recent_sessions
                ],
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system statistics: {e}")
            return {"error": str(e)}
    
    async def cleanup_old_data(self, days_old: int = 30) -> Dict[str, Any]:
        """Clean up old sessions and temporary files"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            cleanup_stats = {"deleted_sessions": 0, "deleted_files": 0, "freed_space": 0}
            
            async with AsyncSession(self.db_engine) as session:
                # Get old sessions
                result = await session.execute(
                    sa.text("""
                    SELECT id, name FROM analysis_sessions
                    WHERE created_at < :cutoff_date AND status IN ('completed', 'failed')
                    """),
                    {"cutoff_date": cutoff_date}
                )
                old_sessions = result.fetchall()
                
                for old_session in old_sessions:
                    session_id = old_session.id
                    
                    # Get associated files
                    files_result = await session.execute(
                        sa.text("""
                        SELECT fr.storage_path, fr.size
                        FROM file_records fr
                        JOIN learning_data ld ON fr.id = ld.file_id
                        WHERE ld.session_id = :session_id
                        """),
                        {"session_id": session_id}
                    )
                    files = files_result.fetchall()
                    
                    # Delete physical files
                    for file_record in files:
                        if file_record.storage_path and os.path.exists(file_record.storage_path):
                            try:
                                os.remove(file_record.storage_path)
                                cleanup_stats["freed_space"] += file_record.size or 0
                                cleanup_stats["deleted_files"] += 1
                            except Exception as e:
                                self.logger.warning(f"Could not delete file {file_record.storage_path}: {e}")
                    
                    # Delete database records
                    await session.execute(
                        sa.text("DELETE FROM learning_data WHERE session_id = :session_id"),
                        {"session_id": session_id}
                    )
                    
                    await session.execute(
                        sa.text("""
                        DELETE FROM file_records WHERE id IN (
                            SELECT file_id FROM learning_data WHERE session_id = :session_id
                        )
                        """),
                        {"session_id": session_id}
                    )
                    
                    await session.execute(
                        sa.text("DELETE FROM analysis_sessions WHERE id = :session_id"),
                        {"session_id": session_id}
                    )
                    
                    cleanup_stats["deleted_sessions"] += 1
                
                await session.commit()
            
            # Clean up temporary directories
            temp_dir = Path(self.config.storage_root) / "temp"
            if temp_dir.exists():
                for item in temp_dir.iterdir():
                    if item.is_dir() and item.stat().st_mtime < cutoff_date.timestamp():
                        import shutil
                        shutil.rmtree(item)
            
            cleanup_stats["cleanup_date"] = datetime.utcnow().isoformat()
            cleanup_stats["cutoff_date"] = cutoff_date.isoformat()
            cleanup_stats["freed_space_mb"] = cleanup_stats["freed_space"] / (1024 * 1024)
            
            self.logger.info(f"Cleanup completed: {cleanup_stats}")
            return cleanup_stats
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive system health check"""
        try:
            health_status = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {}
            }
            
            # Database health
            try:
                async with AsyncSession(self.db_engine) as session:
                    await session.execute(sa.text("SELECT 1"))
                health_status["components"]["database"] = {"status": "healthy", "message": "Connected"}
            except Exception as e:
                health_status["components"]["database"] = {"status": "unhealthy", "message": str(e)}
                health_status["status"] = "degraded"
            
            # Redis health
            try:
                await self.redis_client.ping()
                health_status["components"]["redis"] = {"status": "healthy", "message": "Connected"}
            except Exception as e:
                health_status["components"]["redis"] = {"status": "unhealthy", "message": str(e)}
                health_status["status"] = "degraded"
            
            # LLM services health
            llm_health = await self.llm_manager.health_check()
            health_status["components"]["llm_services"] = llm_health
            if not all(service.get("available", False) for service in llm_health.values()):
                health_status["status"] = "degraded"
            
            # Storage health
            try:
                storage_path = Path(self.config.storage_root)
                storage_path.mkdir(parents=True, exist_ok=True)
                
                # Check disk space
                import shutil
                disk_usage = shutil.disk_usage(storage_path)
                free_space_gb = disk_usage.free / (1024**3)
                
                if free_space_gb < 1:  # Less than 1GB free
                    health_status["components"]["storage"] = {
                        "status": "warning", 
                        "message": f"Low disk space: {free_space_gb:.2f}GB free"
                    }
                    health_status["status"] = "degraded"
                else:
                    health_status["components"]["storage"] = {
                        "status": "healthy",
                        "message": f"Storage available: {free_space_gb:.2f}GB free"
                    }
            except Exception as e:
                health_status["components"]["storage"] = {"status": "unhealthy", "message": str(e)}
                health_status["status"] = "unhealthy"
            
            # Browser service health
            if self.config.enable_browser:
                try:
                    if self.browser_service.session:
                        health_status["components"]["browser"] = {"status": "healthy", "message": "Browser service active"}
                    else:
                        health_status["components"]["browser"] = {"status": "inactive", "message": "Browser service not initialized"}
                except Exception as e:
                    health_status["components"]["browser"] = {"status": "unhealthy", "message": str(e)}
            else:
                health_status["components"]["browser"] = {"status": "disabled", "message": "Browser service disabled"}
            
            return health_status
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def shutdown(self):
        """Gracefully shutdown all services"""
        try:
            self.logger.info("🔄 Shutting down YMERA Organizer...")
            
            # Close browser service
            if self.browser_service:
                await self.browser_service.close()
            
            # Close LLM manager
            if self.llm_manager:
                await self.llm_manager.close()
            
            # Close database connections
            if self.db_engine:
                await self.db_engine.dispose()
            
            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()
            
            # Shutdown thread pool
            if self.thread_pool:
                self.thread_pool.shutdown(wait=True)
            
            self.logger.info("✅ YMERA Organizer shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")


# CLI Interface and Main Application
class YMERAOrganizer:
    """Main application interface"""
    
    def __init__(self, config: Optional[OrganizerConfig] = None):
        self.config = config or OrganizerConfig()
        self.organizer = None
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('ymera_organizer.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self):
        """Initialize the organizer"""
        self.organizer = CodeDocumentationOrganizer(self.config)
        await self.organizer.initialize()
        self.logger.info("🚀 YMERA Enterprise Organizer ready!")
    
    async def create_session(self, name: str, description: str = "") -> str:
        """Create new analysis session"""
        return await self.organizer.create_analysis_session(name, description)
    
    async def analyze_files(self, session_id: str, file_paths: List[str]) -> Dict[str, Any]:
        """Analyze files in session"""
        return await self.organizer.analyze_files(session_id, file_paths)
    
    async def organize_files(self, session_id: str, strategy: str = "intelligent") -> Dict[str, Any]:
        """Organize files in session"""
        return await self.organizer.organize_session_files(session_id, strategy)
    
    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get session status"""
        return await self.organizer.get_session_status(session_id)
    
    async def export_session(self, session_id: str, format: str = "zip") -> str:
        """Export session"""
        return await self.organizer.export_session(session_id, format)
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get system statistics"""
        return await self.organizer.get_system_statistics()
    
    async def health_check(self) -> Dict[str, Any]:
        """System health check"""
        return await self.organizer.health_check()
    
    async def cleanup(self, days_old: int = 30) -> Dict[str, Any]:
        """Clean up old data"""
        return await self.organizer.cleanup_old_data(days_old)
    
    async def shutdown(self):
        """Shutdown organizer"""
        if self.organizer:
            await self.organizer.shutdown()


# Example usage and testing
async def main():
    """Example usage of YMERA Organizer"""
    
    # Initialize organizer
    config = OrganizerConfig(
        # Set your API keys in environment variables or here
        storage_root="./ymera_demo_storage",
        max_workers=5
    )
    
    app = YMERAOrganizer(config)
    
    try:
        await app.initialize()
        
        # Create a session
        session_id = await app.create_session(
            "Demo Analysis Session",
            "Testing YMERA Enterprise Code & Documentation Organizer"
        )
        print(f"Created session: {session_id}")
        
        # Example file paths (replace with actual files)
        file_paths = [
            "./example_code.py",
            "./README.md",
            "./config.json"
        ]
        
        # Analyze files (only if files exist)
        existing_files = [path for path in file_paths if os.path.exists(path)]
        if existing_files:
            analysis_result = await app.analyze_files(session_id, existing_files)
            print(f"Analysis complete: {len(analysis_result.get('processed_files', []))} files processed")
            
            # Organize files
            organization_result = await app.organize_files(session_id)
            print(f"Organization complete: {organization_result.get('organization_strategy', 'unknown')} strategy used")
            
            # Export session
            export_path = await app.export_session(session_id, "zip")
            print(f"Session exported to: {export_path}")
        
        # Get system statistics
        stats = await app.get_statistics()
        print(f"System stats: {stats['system_overview']}")
        
        # Health check
        health = await app.health_check()
        print(f"System health: {health['status']}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        await app.shutdown()


if __name__ == "__main__":
    # Run the main example
    asyncio.run(main())
