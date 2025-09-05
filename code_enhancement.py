"""
YMERA Enterprise Code Enhancement, Upgrade & Debug System
Production-Ready with Multi-LLM Integration and Advanced Code Intelligence
"""
import os
import asyncio
import json
import hashlib
import ast
import re
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union, Set
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
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Float, Boolean, ForeignKey
from pydantic import BaseModel, Field
import redis.asyncio as redis
import tempfile
import difflib
import bandit
from bandit.core import manager as bandit_manager
import safety
import vulture
import mypy.api
import pylint.lint
from radon.complexity import cc_visit
from radon.metrics import mi_visit
import coverage


# Configuration
@dataclass
class EnhancementConfig:
    # API Keys (same as organizer)
    openai_api_key: str = os.getenv("OPENAI_API_KEY")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY")
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/ymera_enhancement")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Storage
    storage_root: str = os.getenv("STORAGE_ROOT", "./ymera_enhancement_storage")
    max_file_size: int = int(os.getenv("MAX_FILE_SIZE", "100000000"))  # 100MB
    
    # Processing
    max_workers: int = int(os.getenv("MAX_WORKERS", "10"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "4000"))
    overlap_size: int = int(os.getenv("OVERLAP_SIZE", "200"))
    
    # Enhancement settings
    max_enhancement_iterations: int = int(os.getenv("MAX_ENHANCEMENT_ITERATIONS", "5"))
    min_quality_threshold: float = float(os.getenv("MIN_QUALITY_THRESHOLD", "7.0"))
    enable_security_scanning: bool = os.getenv("ENABLE_SECURITY_SCANNING", "true").lower() == "true"
    enable_performance_analysis: bool = os.getenv("ENABLE_PERFORMANCE_ANALYSIS", "true").lower() == "true"
    enable_code_coverage: bool = os.getenv("ENABLE_CODE_COVERAGE", "true").lower() == "true"
    
    # Browser
    enable_browser: bool = os.getenv("ENABLE_BROWSER", "true").lower() == "true"
    browser_timeout: int = int(os.getenv("BROWSER_TIMEOUT", "30"))


# Enums
class EnhancementType(Enum):
    CODE_QUALITY = "code_quality"
    PERFORMANCE = "performance"
    SECURITY = "security"
    MODERNIZATION = "modernization"
    REFACTORING = "refactoring"
    BUG_FIXING = "bug_fixing"
    DOCUMENTATION = "documentation"
    TESTING = "testing"


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class SeverityLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"


# Database Models
Base = declarative_base()


class EnhancementSession(Base):
    __tablename__ = "enhancement_sessions"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    source_session_id = Column(String)  # Link to organizer session
    status = Column(String, nullable=False, default="pending")
    configuration = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)
    results_summary = Column(JSON)
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    enhancement_score = Column(Float)


class CodeFile(Base):
    __tablename__ = "code_files"
    
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("enhancement_sessions.id"))
    original_path = Column(String, nullable=False)
    current_path = Column(String, nullable=False)
    language = Column(String)
    file_type = Column(String)
    original_hash = Column(String)
    current_hash = Column(String)
    size = Column(Integer)
    complexity_score = Column(Float)
    quality_score = Column(Float)
    security_score = Column(Float)
    performance_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON)


class EnhancementTask(Base):
    __tablename__ = "enhancement_tasks"
    
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("enhancement_sessions.id"))
    file_id = Column(String, ForeignKey("code_files.id"))
    task_type = Column(String, nullable=False)
    priority = Column(Integer, default=5)
    severity = Column(String, default="medium")
    status = Column(String, default="pending")
    title = Column(String, nullable=False)
    description = Column(Text)
    original_code = Column(Text)
    enhanced_code = Column(Text)
    diff_content = Column(Text)
    llm_provider = Column(String)
    confidence_score = Column(Float)
    review_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)
    metadata = Column(JSON)


class QualityMetric(Base):
    __tablename__ = "quality_metrics"
    
    id = Column(String, primary_key=True)
    file_id = Column(String, ForeignKey("code_files.id"))
    task_id = Column(String, ForeignKey("enhancement_tasks.id"))
    metric_type = Column(String, nullable=False)
    before_value = Column(Float)
    after_value = Column(Float)
    improvement = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON)


class SecurityFinding(Base):
    __tablename__ = "security_findings"
    
    id = Column(String, primary_key=True)
    file_id = Column(String, ForeignKey("code_files.id"))
    task_id = Column(String, ForeignKey("enhancement_tasks.id"))
    finding_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    line_number = Column(Integer)
    column_number = Column(Integer)
    description = Column(Text)
    recommendation = Column(Text)
    cwe_id = Column(String)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)
    metadata = Column(JSON)


class LearningPattern(Base):
    __tablename__ = "learning_patterns"
    
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("enhancement_sessions.id"))
    pattern_type = Column(String, nullable=False)
    pattern_data = Column(JSON)
    confidence_score = Column(Float)
    success_rate = Column(Float)
    usage_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Multi-LLM Manager
class MultiLLMManager:
    def __init__(self, config: EnhancementConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.clients = {}
        self.usage_stats = {}
        
    async def initialize(self):
        """Initialize all LLM providers"""
        providers_initialized = []
        
        # OpenAI
        if self.config.openai_api_key:
            try:
                self.clients[LLMProvider.OPENAI] = openai.AsyncOpenAI(
                    api_key=self.config.openai_api_key
                )
                providers_initialized.append("OpenAI")
            except Exception as e:
                self.logger.warning(f"OpenAI initialization failed: {e}")
        
        # Anthropic
        if self.config.anthropic_api_key:
            try:
                self.clients[LLMProvider.ANTHROPIC] = anthropic.AsyncAnthropic(
                    api_key=self.config.anthropic_api_key
                )
                providers_initialized.append("Anthropic")
            except Exception as e:
                self.logger.warning(f"Anthropic initialization failed: {e}")
        
        # Gemini
        if self.config.gemini_api_key:
            try:
                genai.configure(api_key=self.config.gemini_api_key)
                self.clients[LLMProvider.GEMINI] = GenerativeModel('gemini-pro')
                providers_initialized.append("Gemini")
            except Exception as e:
                self.logger.warning(f"Gemini initialization failed: {e}")
        
        # DeepSeek
        if self.config.deepseek_api_key:
            try:
                self.clients[LLMProvider.DEEPSEEK] = openai.AsyncOpenAI(
                    api_key=self.config.deepseek_api_key,
                    base_url="https://api.deepseek.com"
                )
                providers_initialized.append("DeepSeek")
            except Exception as e:
                self.logger.warning(f"DeepSeek initialization failed: {e}")
        
        self.logger.info(f"✅ LLM providers initialized: {', '.join(providers_initialized)}")
    
    def _get_best_provider_for_task(self, task_type: EnhancementType) -> LLMProvider:
        """Select best LLM provider based on task type"""
        # Task-specific provider preferences
        preferences = {
            EnhancementType.CODE_QUALITY: [LLMProvider.ANTHROPIC, LLMProvider.OPENAI, LLMProvider.DEEPSEEK, LLMProvider.GEMINI],
            EnhancementType.SECURITY: [LLMProvider.ANTHROPIC, LLMProvider.OPENAI, LLMProvider.DEEPSEEK, LLMProvider.GEMINI],
            EnhancementType.PERFORMANCE: [LLMProvider.DEEPSEEK, LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.GEMINI],
            EnhancementType.MODERNIZATION: [LLMProvider.OPENAI, LLMProvider.DEEPSEEK, LLMProvider.ANTHROPIC, LLMProvider.GEMINI],
            EnhancementType.REFACTORING: [LLMProvider.ANTHROPIC, LLMProvider.OPENAI, LLMProvider.DEEPSEEK, LLMProvider.GEMINI],
            EnhancementType.BUG_FIXING: [LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.DEEPSEEK, LLMProvider.GEMINI],
            EnhancementType.DOCUMENTATION: [LLMProvider.ANTHROPIC, LLMProvider.OPENAI, LLMProvider.GEMINI, LLMProvider.DEEPSEEK],
            EnhancementType.TESTING: [LLMProvider.OPENAI, LLMProvider.DEEPSEEK, LLMProvider.ANTHROPIC, LLMProvider.GEMINI]
        }
        
        for provider in preferences.get(task_type, list(self.clients.keys())):
            if provider in self.clients:
                return provider
        
        return list(self.clients.keys())[0] if self.clients else None
    
    async def enhance_code(self, code: str, language: str, task_type: EnhancementType, 
                          context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Enhance code using the best available LLM"""
        provider = self._get_best_provider_for_task(task_type)
        if not provider:
            raise Exception("No LLM providers available")
        
        prompt = self._build_enhancement_prompt(code, language, task_type, context or {})
        
        try:
            if provider == LLMProvider.OPENAI:
                response = await self._call_openai(prompt, self.clients[provider])
            elif provider == LLMProvider.ANTHROPIC:
                response = await self._call_anthropic(prompt, self.clients[provider])
            elif provider == LLMProvider.GEMINI:
                response = await self._call_gemini(prompt, self.clients[provider])
            elif provider == LLMProvider.DEEPSEEK:
                response = await self._call_deepseek(prompt, self.clients[provider])
            else:
                raise Exception(f"Unsupported provider: {provider}")
            
            # Update usage stats
            self.usage_stats[provider.value] = self.usage_stats.get(provider.value, 0) + 1
            
            return {
                "enhanced_code": response["enhanced_code"],
                "explanation": response["explanation"],
                "improvements": response["improvements"],
                "confidence": response["confidence"],
                "provider": provider.value,
                "task_type": task_type.value
            }
            
        except Exception as e:
            self.logger.error(f"Error enhancing code with {provider.value}: {e}")
            raise
    
    def _build_enhancement_prompt(self, code: str, language: str, task_type: EnhancementType, context: Dict[str, Any]) -> str:
        """Build enhancement prompt based on task type"""
        base_prompt = f"""
You are an expert software engineer specializing in code enhancement and optimization. 

TASK: {task_type.value.replace('_', ' ').title()}
LANGUAGE: {language}
CONTEXT: {json.dumps(context, indent=2)}

ORIGINAL CODE:
```{language}
{code}
```

Please provide enhanced code that addresses the following requirements:
"""
        
        requirements = {
            EnhancementType.CODE_QUALITY: [
                "Improve code readability and maintainability",
                "Follow language-specific best practices and conventions",
                "Optimize variable names and function structure",
                "Add appropriate comments and documentation",
                "Remove code smells and anti-patterns"
            ],
            EnhancementType.SECURITY: [
                "Fix security vulnerabilities and weaknesses",
                "Implement proper input validation and sanitization",
                "Add authentication and authorization checks",
                "Handle sensitive data securely",
                "Prevent common security attacks (XSS, SQL injection, etc.)"
            ],
            EnhancementType.PERFORMANCE: [
                "Optimize algorithms and data structures",
                "Reduce time and space complexity",
                "Implement caching where appropriate",
                "Minimize unnecessary computations",
                "Optimize database queries and I/O operations"
            ],
            EnhancementType.MODERNIZATION: [
                "Update to modern language features and syntax",
                "Replace deprecated functions and libraries",
                "Implement current design patterns",
                "Use modern frameworks and tools",
                "Improve type safety and error handling"
            ],
            EnhancementType.REFACTORING: [
                "Improve code structure and organization",
                "Extract reusable functions and classes",
                "Reduce code duplication",
                "Simplify complex logic",
                "Improve separation of concerns"
            ],
            EnhancementType.BUG_FIXING: [
                "Identify and fix logical errors",
                "Handle edge cases and error conditions",
                "Fix runtime errors and exceptions",
                "Resolve memory leaks and resource issues",
                "Ensure proper error propagation"
            ],
            EnhancementType.DOCUMENTATION: [
                "Add comprehensive docstrings and comments",
                "Document function parameters and return values",
                "Explain complex algorithms and business logic",
                "Add usage examples",
                "Create clear inline documentation"
            ],
            EnhancementType.TESTING: [
                "Add unit tests for functions and methods",
                "Implement integration tests",
                "Add edge case and error condition tests",
                "Improve test coverage",
                "Create mock objects and test fixtures"
            ]
        }
        
        task_requirements = requirements.get(task_type, ["General code improvement"])
        for req in task_requirements:
            base_prompt += f"- {req}\n"
        
        base_prompt += """
Respond with a JSON object containing:
{
  "enhanced_code": "The improved code",
  "explanation": "Detailed explanation of changes made",
  "improvements": ["List of specific improvements"],
  "confidence": 0.95,
  "metrics": {
    "complexity_reduction": 0.2,
    "readability_improvement": 0.3,
    "performance_gain": 0.15
  }
}
"""
        return base_prompt
    
    async def _call_openai(self, prompt: str, client) -> Dict[str, Any]:
        """Call OpenAI API"""
        response = await client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4000
        )
        
        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Fallback parsing if JSON is malformed
            return self._fallback_parse(content)
    
    async def _call_anthropic(self, prompt: str, client) -> Dict[str, Any]:
        """Call Anthropic API"""
        response = await client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=4000,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}]
        )
        
        content = response.content[0].text
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return self._fallback_parse(content)
    
    async def _call_gemini(self, prompt: str, client) -> Dict[str, Any]:
        """Call Gemini API"""
        response = await asyncio.to_thread(client.generate_content, prompt)
        content = response.text
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return self._fallback_parse(content)
    
    async def _call_deepseek(self, prompt: str, client) -> Dict[str, Any]:
        """Call DeepSeek API"""
        response = await client.chat.completions.create(
            model="deepseek-coder",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4000
        )
        
        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return self._fallback_parse(content)
    
    def _fallback_parse(self, content: str) -> Dict[str, Any]:
        """Fallback parsing when JSON is malformed"""
        return {
            "enhanced_code": content,
            "explanation": "Response parsing failed, raw content returned",
            "improvements": ["Response format error"],
            "confidence": 0.5,
            "metrics": {}
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of all LLM providers"""
        health_status = {}
        
        for provider, client in self.clients.items():
            try:
                test_prompt = "Hello, are you working?"
                
                if provider == LLMProvider.OPENAI:
                    await client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": test_prompt}],
                        max_tokens=10
                    )
                elif provider == LLMProvider.ANTHROPIC:
                    await client.messages.create(
                        model="claude-3-haiku-20240307",
                        max_tokens=10,
                        messages=[{"role": "user", "content": test_prompt}]
                    )
                elif provider == LLMProvider.GEMINI:
                    await asyncio.to_thread(client.generate_content, test_prompt)
                elif provider == LLMProvider.DEEPSEEK:
                    await client.chat.completions.create(
                        model="deepseek-coder",
                        messages=[{"role": "user", "content": test_prompt}],
                        max_tokens=10
                    )
                
                health_status[provider.value] = {
                    "status": "healthy",
                    "available": True,
                    "usage_count": self.usage_stats.get(provider.value, 0)
                }
                
            except Exception as e:
                health_status[provider.value] = {
                    "status": "unhealthy",
                    "available": False,
                    "error": str(e),
                    "usage_count": self.usage_stats.get(provider.value, 0)
                }
        
        return health_status
    
    async def get_usage_statistics(self) -> Dict[str, Any]:
        """Get LLM usage statistics"""
        return {
            "total_requests": sum(self.usage_stats.values()),
            "by_provider": self.usage_stats,
            "available_providers": list(self.clients.keys()),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def close(self):
        """Close all LLM connections"""
        for client in self.clients.values():
            if hasattr(client, 'close'):
                await client.close()


# Code Analysis Engine
class CodeAnalysisEngine:
    def __init__(self, config: EnhancementConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    async def analyze_file(self, file_path: str, content: str, language: str) -> Dict[str, Any]:
        """Comprehensive code analysis"""
        analysis_results = {
            "file_path": file_path,
            "language": language,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {},
            "issues": [],
            "security_findings": [],
            "suggestions": []
        }
        
        try:
            # Basic metrics
            analysis_results["metrics"] = await self._calculate_basic_metrics(content, language)
            
            # Language-specific analysis
            if language.lower() == "python":
                analysis_results.update(await self._analyze_python_code(file_path, content))
            elif language.lower() in ["javascript", "typescript"]:
                analysis_results.update(await self._analyze_js_code(file_path, content))
            elif language.lower() in ["java"]:
                analysis_results.update(await self._analyze_java_code(file_path, content))
            
            # Security analysis
            if self.config.enable_security_scanning:
                security_results = await self._security_analysis(file_path, content, language)
                analysis_results["security_findings"].extend(security_results)
            
            # Performance analysis
            if self.config.enable_performance_analysis:
                performance_results = await self._performance_analysis(content, language)
                analysis_results["performance_metrics"] = performance_results
            
            return analysis_results
            
        except Exception as e:
            self.logger.error(f"Error analyzing file {file_path}: {e}")
            analysis_results["error"] = str(e)
            return analysis_results
    
    async def _calculate_basic_metrics(self, content: str, language: str) -> Dict[str, Any]:
        """Calculate basic code metrics"""
        lines = content.split('\n')
        
        return {
            "lines_of_code": len(lines),
            "blank_lines": len([line for line in lines if not line.strip()]),
            "comment_lines": self._count_comment_lines(lines, language),
            "file_size": len(content),
            "avg_line_length": sum(len(line) for line in lines) / max(len(lines), 1),
            "max_line_length": max(len(line) for line in lines) if lines else 0
        }
    
    def _count_comment_lines(self, lines: List[str], language: str) -> int:
        """Count comment lines based on language"""
        comment_patterns = {
            "python": [r'^\s*#', r'^\s*""".*"""$', r"^\s*'''.*'''$"],
            "javascript": [r'^\s*//', r'^\s*/\*.*\*/$'],
            "typescript": [r'^\s*//', r'^\s*/\*.*\*/$'],
            "java": [r'^\s*//', r'^\s*/\*.*\*/$'],
            "c": [r'^\s*//', r'^\s*/\*.*\*/$'],
            "cpp": [r'^\s*//', r'^\s*/\*.*\*/$']
        }
        
        patterns = comment_patterns.get(language.lower(), [r'^\s*#'])
        comment_count = 0
        
        for line in lines:
            for pattern in patterns:
                if re.match(pattern, line.strip()):
                    comment_count += 1
                    break
        
        return comment_count
    
    async def _analyze_python_code(self, file_path: str, content: str) -> Dict[str, Any]:
        """Python-specific code analysis"""
        results = {
            "syntax_errors": [],
            "complexity_metrics": {},
            "maintainability_index": 0,
            "imports": [],
            "functions": [],
            "classes": []
        }
        
        try:
            # Parse AST
            tree = ast.parse(content)
            
            # Extract imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        results["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        results["imports"].append(f"{module}.{alias.name}")
            
            # Extract functions and classes
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    results["functions"].append({
                        "name": node.name,
                        "line_number": node.lineno,
                        "args_count": len(node.args.args),
                        "has_docstring": ast.get_docstring(node) is not None
                    })
                elif isinstance(node, ast.ClassDef):
                    results["classes"].append({
                        "name": node.name,
                        "line_number": node.lineno,
                        "method_count": len([n for n in node.body if isinstance(n, ast.FunctionDef)]),
                        "has_docstring": ast.get_docstring(node) is not None
                    })
            
            # Complexity analysis using radon
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
                    tmp.write(content)
                    tmp.flush()
                    
                    # Cyclomatic complexity
                    complexity_results = cc_visit(content)
                    results["complexity_metrics"]["cyclomatic_complexity"] = [
                        {
                            "name": result.name,
                            "complexity": result.complexity,
                            "line_number": result.lineno
                        }
                        for result in complexity_results
                    ]
                    
                    # Maintainability index
                    mi_results = mi_visit(content, multi=True)
                    results["maintainability_index"] = mi_results
                    
                os.unlink(tmp.name)
                
            except Exception as e:
                self.logger.warning(f"Complexity analysis failed: {e}")
            
            # Type checking with mypy (if available)
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
                    tmp.write(content)
                    tmp.flush()
                    
                    mypy_results = mypy.api.run([tmp.name])
                    if mypy_results[1]:  # stderr contains type errors
                        results["type_errors"] = mypy_results[1].split('\n')
                    
                os.unlink(tmp.name)
                
            except Exception as e:
                self.logger.warning(f"Type checking failed: {e}")
                
        except SyntaxError as e:
            results["syntax_errors"].append({
                "line": e.lineno,
                "message": str(e),
                "type": "syntax_error"
            })
        
        return results
    
    async def _analyze_js_code(self, file_path: str, content: str) -> Dict[str, Any]:
        """JavaScript/TypeScript-specific analysis"""
        results = {
            "syntax_errors": [],
            "functions": [],
            "classes": [],
            "imports": [],
            "exports": []
        }
        
        try:
            # Basic pattern matching for JS/TS constructs
            
            # Find functions
            function_patterns = [
                r'function\s+(\w+)\s*\(',
                r'(\w function_patterns = [
                r'function\s+(\w+)\s*\(',
                r'(\w+)\s*=\s*function\s*\(',
                r'(\w+)\s*=>\s*{',
                r'(\w+)\s*:\s*function\s*\(',
                r'async\s+function\s+(\w+)\s*\('
            ]
            
            for pattern in function_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    func_name = match.group(1)
                    line_num = content[:match.start()].count('\n') + 1
                    results["functions"].append({
                        "name": func_name,
                        "line_number": line_num,
                        "type": "function"
                    })
            
            # Find classes
            class_pattern = r'class\s+(\w+)\s*(?:extends\s+\w+)?\s*{'
            for match in re.finditer(class_pattern, content):
                class_name = match.group(1)
                line_num = content[:match.start()].count('\n') + 1
                results["classes"].append({
                    "name": class_name,
                    "line_number": line_num
                })
            
            # Find imports/requires
            import_patterns = [
                r'import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]',
                r'require\([\'"]([^\'"]+)[\'"]\)',
                r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
            ]
            
            for pattern in import_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    results["imports"].append(match.group(1))
            
            # Find exports
            export_patterns = [
                r'export\s+(?:default\s+)?(?:function|class|const|let|var)\s+(\w+)',
                r'export\s*{\s*([^}]+)\s*}',
                r'module\.exports\s*=\s*(\w+)'
            ]
            
            for pattern in export_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    results["exports"].append(match.group(1))
            
        except Exception as e:
            results["syntax_errors"].append({
                "message": str(e),
                "type": "analysis_error"
            })
        
        return results
    
    async def _analyze_java_code(self, file_path: str, content: str) -> Dict[str, Any]:
        """Java-specific code analysis"""
        results = {
            "syntax_errors": [],
            "classes": [],
            "methods": [],
            "imports": [],
            "packages": []
        }
        
        try:
            # Package declaration
            package_match = re.search(r'package\s+([a-zA-Z_][a-zA-Z0-9_.]*);', content)
            if package_match:
                results["packages"].append(package_match.group(1))
            
            # Imports
            import_matches = re.finditer(r'import\s+(?:static\s+)?([a-zA-Z_][a-zA-Z0-9_.]*);', content)
            for match in import_matches:
                results["imports"].append(match.group(1))
            
            # Classes and interfaces
            class_pattern = r'(?:public\s+|private\s+|protected\s+)?(?:abstract\s+)?(?:class|interface)\s+(\w+)'
            for match in re.finditer(class_pattern, content):
                class_name = match.group(1)
                line_num = content[:match.start()].count('\n') + 1
                results["classes"].append({
                    "name": class_name,
                    "line_number": line_num
                })
            
            # Methods
            method_pattern = r'(?:public|private|protected)?\s*(?:static\s+)?(?:abstract\s+)?(?:final\s+)?(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*(?:throws\s+[^{]+)?\s*{'
            for match in re.finditer(method_pattern, content):
                method_name = match.group(1)
                line_num = content[:match.start()].count('\n') + 1
                results["methods"].append({
                    "name": method_name,
                    "line_number": line_num
                })
                
        except Exception as e:
            results["syntax_errors"].append({
                "message": str(e),
                "type": "analysis_error"
            })
        
        return results
    
    async def _security_analysis(self, file_path: str, content: str, language: str) -> List[Dict[str, Any]]:
        """Security vulnerability analysis"""
        findings = []
        
        try:
            if language.lower() == "python":
                # Use bandit for Python security analysis
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
                    tmp.write(content)
                    tmp.flush()
                    
                    try:
                        # Initialize bandit manager
                        b_mgr = bandit_manager.BanditManager(
                            bandit.config.BanditConfig(),
                            'file'
                        )
                        
                        b_mgr.discover_files([tmp.name])
                        b_mgr.run_tests()
                        
                        for issue in b_mgr.get_issue_list():
                            findings.append({
                                "type": "security_vulnerability",
                                "severity": issue.severity.lower(),
                                "confidence": issue.confidence.lower(),
                                "line_number": issue.lineno,
                                "test_id": issue.test_id,
                                "description": issue.text,
                                "more_info": issue.more_info
                            })
                    
                    except Exception as e:
                        self.logger.warning(f"Bandit analysis failed: {e}")
                    
                    finally:
                        os.unlink(tmp.name)
            
            # Generic security pattern detection
            security_patterns = self._get_security_patterns(language)
            for pattern_name, pattern in security_patterns.items():
                matches = re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    findings.append({
                        "type": "security_pattern",
                        "severity": "medium",
                        "line_number": line_num,
                        "pattern_name": pattern_name,
                        "description": f"Potential security issue: {pattern_name}",
                        "matched_text": match.group(0)
                    })
            
        except Exception as e:
            self.logger.error(f"Security analysis failed: {e}")
        
        return findings
    
    def _get_security_patterns(self, language: str) -> Dict[str, str]:
        """Get security patterns for different languages"""
        common_patterns = {
            "hardcoded_password": r'(?i)(password|pwd|pass)\s*=\s*["\'](?!.*\$\{)[^"\']{4,}["\']',
            "hardcoded_api_key": r'(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*=\s*["\'][^"\']{10,}["\']',
            "sql_injection": r'(?i)(select|insert|update|delete|drop|create).*\+.*["\']',
            "exec_command": r'(?i)(exec|eval|system|shell_exec|passthru)\s*\(',
            "file_inclusion": r'(?i)(include|require|import).*\$',
            "xss_vulnerability": r'(?i)(innerHTML|outerHTML|document\.write).*\+',
            "csrf_missing": r'(?i)(<form(?!.*csrf))',
        }
        
        language_specific = {
            "python": {
                **common_patterns,
                "pickle_unsafe": r'(?i)(pickle\.loads|cPickle\.loads)',
                "yaml_unsafe": r'(?i)yaml\.load\s*\([^)]*\)',
                "subprocess_shell": r'(?i)subprocess\.[^(]*\([^)]*shell\s*=\s*True',
            },
            "javascript": {
                **common_patterns,
                "dangerous_functions": r'(?i)(eval|Function|setTimeout|setInterval)\s*\(',
                "prototype_pollution": r'(?i)(__proto__|constructor\.prototype)',
            },
            "java": {
                **common_patterns,
                "deserialization": r'(?i)(ObjectInputStream|readObject)',
                "reflection_unsafe": r'(?i)(Class\.forName|Method\.invoke)',
            }
        }
        
        return language_specific.get(language.lower(), common_patterns)
    
    async def _performance_analysis(self, content: str, language: str) -> Dict[str, Any]:
        """Performance analysis of code"""
        metrics = {
            "potential_bottlenecks": [],
            "optimization_suggestions": [],
            "complexity_hotspots": []
        }
        
        try:
            # Common performance anti-patterns
            performance_patterns = {
                "nested_loops": r'for\s*\([^)]*\)\s*{[^}]*for\s*\([^)]*\)',
                "string_concatenation": r'\+\s*["\'].*["\']|\s*\+=\s*["\']',
                "inefficient_search": r'\.indexOf\s*\(|\.find\s*\(',
                "synchronous_io": r'(?i)(sync|blocking).*(?:read|write|request)',
                "memory_leaks": r'(?i)(closure|setInterval|setTimeout).*(?!clear)',
            }
            
            for pattern_name, pattern in performance_patterns.items():
                matches = list(re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE))
                if matches:
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        metrics["potential_bottlenecks"].append({
                            "type": pattern_name,
                            "line_number": line_num,
                            "severity": "medium",
                            "suggestion": self._get_performance_suggestion(pattern_name)
                        })
            
            # Language-specific analysis
            if language.lower() == "python":
                metrics.update(await self._python_performance_analysis(content))
            elif language.lower() in ["javascript", "typescript"]:
                metrics.update(await self._js_performance_analysis(content))
            
        except Exception as e:
            self.logger.error(f"Performance analysis failed: {e}")
        
        return metrics
    
    def _get_performance_suggestion(self, pattern_name: str) -> str:
        """Get performance improvement suggestions"""
        suggestions = {
            "nested_loops": "Consider using more efficient algorithms or data structures to reduce complexity",
            "string_concatenation": "Use string builders or template literals for better performance",
            "inefficient_search": "Consider using hash maps or sets for O(1) lookups",
            "synchronous_io": "Use asynchronous I/O operations to prevent blocking",
            "memory_leaks": "Ensure proper cleanup of event listeners and timers"
        }
        return suggestions.get(pattern_name, "Review for potential optimization")
    
    async def _python_performance_analysis(self, content: str) -> Dict[str, Any]:
        """Python-specific performance analysis"""
        results = {
            "list_comprehensions": 0,
            "generator_expressions": 0,
            "global_variables": 0
        }
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ListComp):
                    results["list_comprehensions"] += 1
                elif isinstance(node, ast.GeneratorExp):
                    results["generator_expressions"] += 1
                elif isinstance(node, ast.Global):
                    results["global_variables"] += len(node.names)
            
        except Exception as e:
            self.logger.warning(f"Python performance analysis failed: {e}")
        
        return results
    
    async def _js_performance_analysis(self, content: str) -> Dict[str, Any]:
        """JavaScript-specific performance analysis"""
        results = {
            "dom_queries": 0,
            "event_listeners": 0,
            "async_functions": 0
        }
        
        try:
            # Count DOM queries
            dom_patterns = [
                r'document\.getElementById',
                r'document\.querySelector',
                r'document\.getElementsByClassName',
                r'\$\s*\('
            ]
            
            for pattern in dom_patterns:
                results["dom_queries"] += len(re.findall(pattern, content))
            
            # Count event listeners
            event_patterns = [
                r'addEventListener',
                r'\.on\w+\s*=',
                r'\.click\s*\(',
                r'\.hover\s*\('
            ]
            
            for pattern in event_patterns:
                results["event_listeners"] += len(re.findall(pattern, content))
            
            # Count async functions
            results["async_functions"] = len(re.findall(r'async\s+function', content))
            
        except Exception as e:
            self.logger.warning(f"JavaScript performance analysis failed: {e}")
        
        return results


# Enhancement Task Manager
class EnhancementTaskManager:
    def __init__(self, config: EnhancementConfig, llm_manager: MultiLLMManager, 
                 analysis_engine: CodeAnalysisEngine, db_session: AsyncSession):
        self.config = config
        self.llm_manager = llm_manager
        self.analysis_engine = analysis_engine
        self.db_session = db_session
        self.logger = logging.getLogger(__name__)
    
    async def create_enhancement_tasks(self, session_id: str, file_id: str, 
                                     analysis_results: Dict[str, Any]) -> List[str]:
        """Create enhancement tasks based on analysis results"""
        task_ids = []
        
        try:
            # Determine enhancement priorities
            enhancement_priorities = self._determine_enhancement_priorities(analysis_results)
            
            for enhancement_type, priority_score in enhancement_priorities.items():
                if priority_score > 0.3:  # Only create tasks above threshold
                    task_id = self._generate_id()
                    
                    task = EnhancementTask(
                        id=task_id,
                        session_id=session_id,
                        file_id=file_id,
                        task_type=enhancement_type.value,
                        priority=int(priority_score * 10),
                        title=f"{enhancement_type.value.replace('_', ' ').title()} Enhancement",
                        description=self._generate_task_description(enhancement_type, analysis_results),
                        original_code="",  # Will be set when processing
                        metadata={
                            "analysis_results": analysis_results,
                            "priority_score": priority_score,
                            "created_from": "analysis"
                        }
                    )
                    
                    self.db_session.add(task)
                    task_ids.append(task_id)
            
            await self.db_session.commit()
            self.logger.info(f"Created {len(task_ids)} enhancement tasks for file {file_id}")
            
        except Exception as e:
            self.logger.error(f"Error creating enhancement tasks: {e}")
            await self.db_session.rollback()
        
        return task_ids
    
    def _determine_enhancement_priorities(self, analysis_results: Dict[str, Any]) -> Dict[EnhancementType, float]:
        """Determine enhancement priorities based on analysis"""
        priorities = {}
        
        # Security priority (highest)
        security_score = len(analysis_results.get("security_findings", [])) / 10.0
        priorities[EnhancementType.SECURITY] = min(security_score, 1.0)
        
        # Code quality priority
        metrics = analysis_results.get("metrics", {})
        complexity_score = 0.0
        
        if "complexity_metrics" in analysis_results:
            avg_complexity = sum([
                item.get("complexity", 0) 
                for item in analysis_results["complexity_metrics"].get("cyclomatic_complexity", [])
            ]) / max(len(analysis_results["complexity_metrics"].get("cyclomatic_complexity", [])), 1)
            complexity_score = min(avg_complexity / 10.0, 1.0)
        
        priorities[EnhancementType.CODE_QUALITY] = complexity_score
        
        # Performance priority
        performance_issues = len(analysis_results.get("performance_metrics", {}).get("potential_bottlenecks", []))
        priorities[EnhancementType.PERFORMANCE] = min(performance_issues / 5.0, 1.0)
        
        # Bug fixing priority
        syntax_errors = len(analysis_results.get("syntax_errors", []))
        priorities[EnhancementType.BUG_FIXING] = min(syntax_errors / 3.0, 1.0)
        
        # Documentation priority
        functions_without_docs = 0
        if "functions" in analysis_results:
            functions_without_docs = len([
                f for f in analysis_results["functions"] 
                if not f.get("has_docstring", True)
            ])
        priorities[EnhancementType.DOCUMENTATION] = min(functions_without_docs / 5.0, 1.0)
        
        # Testing priority
        priorities[EnhancementType.TESTING] = 0.6  # Default medium priority
        
        # Modernization priority
        old_patterns = self._count_old_patterns(analysis_results)
        priorities[EnhancementType.MODERNIZATION] = min(old_patterns / 5.0, 1.0)
        
        # Refactoring priority
        refactor_score = (complexity_score + min(metrics.get("lines_of_code", 0) / 1000.0, 1.0)) / 2
        priorities[EnhancementType.REFACTORING] = refactor_score
        
        return priorities
    
    def _count_old_patterns(self, analysis_results: Dict[str, Any]) -> int:
        """Count outdated patterns in code"""
        # This would contain language-specific old pattern detection
        return 0
    
    def _generate_task_description(self, enhancement_type: EnhancementType, 
                                 analysis_results: Dict[str, Any]) -> str:
        """Generate detailed task description"""
        base_descriptions = {
            EnhancementType.SECURITY: "Address security vulnerabilities and implement security best practices",
            EnhancementType.CODE_QUALITY: "Improve code readability, maintainability, and follow best practices",
            EnhancementType.PERFORMANCE: "Optimize performance and reduce computational complexity",
            EnhancementType.BUG_FIXING: "Fix identified bugs, errors, and edge cases",
            EnhancementType.DOCUMENTATION: "Add comprehensive documentation and comments",
            EnhancementType.TESTING: "Implement unit tests and improve test coverage",
            EnhancementType.MODERNIZATION: "Update to modern language features and patterns",
            EnhancementType.REFACTORING: "Restructure code for better organization and maintainability"
        }
        
        description = base_descriptions.get(enhancement_type, "Code enhancement task")
        
        # Add specific details based on analysis
        if enhancement_type == EnhancementType.SECURITY and "security_findings" in analysis_results:
            finding_count = len(analysis_results["security_findings"])
            description += f"\n\nFound {finding_count} security issues to address."
        
        if enhancement_type == EnhancementType.PERFORMANCE and "performance_metrics" in analysis_results:
            bottleneck_count = len(analysis_results["performance_metrics"].get("potential_bottlenecks", []))
            description += f"\n\nIdentified {bottleneck_count} potential performance bottlenecks."
        
        return description
    
    async def process_enhancement_task(self, task_id: str) -> Dict[str, Any]:
        """Process a single enhancement task"""
        try:
            # Get task from database
            task = await self.db_session.get(EnhancementTask, task_id)
            if not task:
                raise Exception(f"Task {task_id} not found")
            
            # Get associated file
            code_file = await self.db_session.get(CodeFile, task.file_id)
            if not code_file:
                raise Exception(f"File {task.file_id} not found")
            
            # Read current file content
            file_path = Path(code_file.current_path)
            if not file_path.exists():
                raise Exception(f"File {file_path} does not exist")
            
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            task.original_code = content
            task.status = TaskStatus.IN_PROGRESS.value
            task.llm_provider = "auto"
            
            # Enhance the code using LLM
            enhancement_type = EnhancementType(task.task_type)
            context = {
                "file_path": code_file.original_path,
                "task_description": task.description,
                "analysis_results": task.metadata.get("analysis_results", {}),
                "priority": task.priority
            }
            
            enhancement_result = await self.llm_manager.enhance_code(
                content, code_file.language, enhancement_type, context
            )
            
            # Store results
            task.enhanced_code = enhancement_result["enhanced_code"]
            task.confidence_score = enhancement_result["confidence"]
            task.llm_provider = enhancement_result["provider"]
            
            # Generate diff
            diff = list(difflib.unified_diff(
                content.splitlines(keepends=True),
                enhancement_result["enhanced_code"].splitlines(keepends=True),
                fromfile=f"a/{code_file.original_path}",
                tofile=f"b/{code_file.original_path}"
            ))
            task.diff_content = ''.join(diff)
            
            # Update task metadata
            task.metadata.update({
                "enhancement_result": enhancement_result,
                "processing_timestamp": datetime.utcnow().isoformat(),
                "diff_stats": {
                    "additions": len([line for line in diff if line.startswith('+')]),
                    "deletions": len([line for line in diff if line.startswith('-')])
                }
            })
            
            # Determine if task needs review
            if enhancement_result["confidence"] < 0.8:
                task.status = TaskStatus.REQUIRES_REVIEW.value
                task.review_notes = "Low confidence score - requires manual review"
            else:
                task.status = TaskStatus.COMPLETED.value
            
            task.completed_at = datetime.utcnow()
            task.updated_at = datetime.utcnow()
            
            await self.db_session.commit()
            
            self.logger.info(f"✅ Enhanced task {task_id} with confidence {enhancement_result['confidence']}")
            
            return {
                "task_id": task_id,
                "status": task.status,
                "confidence": enhancement_result["confidence"],
                "provider": enhancement_result["provider"],
                "improvements": enhancement_result.get("improvements", []),
                "diff_stats": task.metadata.get("diff_stats", {})
            }
            
        except Exception as e:
            self.logger.error(f"Error processing task {task_id}: {e}")
            
            # Update task status to failed
            try:
                task = await self.db_session.get(EnhancementTask, task_id)
                if task:
                    task.status = TaskStatus.FAILED.value
                    task.review_notes = f"Processing failed: {str(e)}"
                    task.updated_at = datetime.utcnow()
                    await self.db_session.commit()
            except:
                pass
            
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(e)
            }
    
    async def apply_enhancement(self, task_id: str) -> Dict[str, Any]:
        """Apply approved enhancement to file"""
        try:
            task = await self.db_session.get(EnhancementTask, task_id)
            if not task or task.status != TaskStatus.APPROVED.value:
                raise Exception(f"Task {task_id} not approved or not found")
            
            code_file = await self.db_session.get(CodeFile, task.file_id)
            if not code_file:
                raise Exception(f"File {task.file_id} not found")
            
            file_path = Path(code_file.current_path)
            
            # Backup current file
            backup_path = file_path.with_suffix(f"{file_path.suffix}.backup.{int(datetime.utcnow().timestamp())}")
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as src:
                content = await src.read()
            async with aiofiles.open(backup_path, 'w', encoding='utf-8') as backup:
                await backup.write(content)
            
            # Apply enhancement
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(task.enhanced_code)
            
            # Update file hash
            new_hash = hashlib.md5(task.enhanced_code.encode()).hexdigest()
            code_file.current_hash = new_hash
            code_file.updated_at = datetime.utcnow()
            
            task.status = TaskStatus.COMPLETED.value
            task.updated_at = datetime.utcnow()
            
            await self.db_session.commit()
            
            self.logger.info(f"✅ Applied enhancement {task_id} to {file_path}")
            
            return {
                "task_id": task_id,
                "file_path": str(file_path),
                "backup_path": str(backup_path),
                "status": "applied"
            }
            
        except Exception as e:
            self.logger.error(f"Error applying enhancement {task_id}: {e}")
            await self.db_session.rollback()
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(e)
            }
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get detailed task status"""
        try:
            task = await self.db_session.get(EnhancementTask, task_id)
            if not task:
                return {"error": "Task not found"}
            
            return {
                "task_id": task.id,
                "status": task.status,
                "task_type": task.task_type,
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "confidence_score": task.confidence_score,
                "llm_provider": task.llm_provider,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "has_enhanced_code": bool(task.enhanced_code),
                "has_diff": bool(task.diff_content),
                "review_notes": task.review_notes,
                "metadata": task.metadata or {}
            }
            
        except Exception as e:
            self.logger.error(f"Error getting task status {task_id}: {e}")
            return {"error": str(e)}
    
    async def batch_process_tasks(self, session_id: str, max_concurrent: int = 5) -> Dict[str, Any]:
        """Process multiple tasks concurrently"""
        try:
            # Get pending tasks for session
            from sqlalchemy import select
            
            stmt = select(EnhancementTask).where(
                EnhancementTask.session_id == session_id,
                EnhancementTask.status == TaskStatus.PENDING.value
            ).order_by(EnhancementTask.priority.desc())
            
            result = await self.db_session.execute(stmt)
            tasks = result.scalars().all()
            
            if not tasks:
                return {"message": "No pending tasks found", "processed": 0}
            
            self.logger.info(f"Processing {len(tasks)} tasks for session {session_id}")
            
            # Process tasks in batches
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def process_with_semaphore(task_id):
                async with semaphore:
                    return await self.process_enhancement_task(task_id)
            
            # Process all tasks
            task_ids = [task.id for task in tasks]
            results = await asyncio.gather(
                *[process_with_semaphore(task_id) for task_id in task_ids],
                return_exceptions=True
            )
            
            # Summarize results
            successful = len([r for r in results if isinstance(r, dict) and r.get("status") != "failed"])
            failed = len([r for r in results if isinstance(r, dict) and r.get("status") == "failed"])
            errors = len([r for r in results if isinstance(r, Exception)])
            
            return {
                "session_id": session_id,
                "total_tasks": len(tasks),
                "successful": successful,
                "failed": failed,
                "errors": errors,
                "results": [r for r in results if not isinstance(r, Exception)]
            }
            
        except Exception as e:
            self.logger.error(f"Error in batch processing: {e}")
            return {"error": str(e)}
    
    def _generate_id(self) -> str:
        """Generate unique ID"""
        return hashlib.md5(f"{datetime.utcnow().isoformat()}{os.urandom(8)}".encode()).hexdigest()


# File Processing Engine
class FileProcessingEngine:
    def __init__(self, config: EnhancementConfig, analysis_engine: CodeAnalysisEngine, 
                 task_manager: EnhancementTaskManager, db_session: AsyncSession):
        self.config = config
        self.analysis_engine = analysis_engine
        self.task_manager = task_manager
        self.db_session = db_session
        self.logger = logging.getLogger(__name__)
        
        # Supported file extensions
        self.supported_extensions = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.php': ''php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.r': 'r',
            '.m': 'matlab',
            '.sql': 'sql',
            '.sh': 'bash',
            '.ps1': 'powershell',
            '.html': 'html',
            '.css': 'css',
            '.jsx': 'javascript',
            '.tsx': 'typescript'
        }
    
    async def process_directory(self, directory_path: str, session_id: str, 
                              recursive: bool = True, ignore_patterns: List[str] = None) -> Dict[str, Any]:
        """Process all code files in a directory"""
        if ignore_patterns is None:
            ignore_patterns = [
                '*.pyc', '*.pyo', '*.pyd', '__pycache__', '.git', '.svn', 
                'node_modules', '.env', '.venv', 'venv', 'env',
                '*.min.js', '*.min.css', '.DS_Store', 'Thumbs.db'
            ]
        
        directory_path = Path(directory_path)
        if not directory_path.exists() or not directory_path.is_dir():
            raise ValueError(f"Invalid directory path: {directory_path}")
        
        results = {
            "session_id": session_id,
            "directory": str(directory_path),
            "processed_files": [],
            "skipped_files": [],
            "errors": [],
            "total_files": 0,
            "total_lines": 0,
            "languages": {},
            "processing_time": 0
        }
        
        start_time = time.time()
        
        try:
            # Get all code files
            files_to_process = []
            pattern = "**/*" if recursive else "*"
            
            for file_path in directory_path.glob(pattern):
                if file_path.is_file() and self._should_process_file(file_path, ignore_patterns):
                    files_to_process.append(file_path)
            
            results["total_files"] = len(files_to_process)
            self.logger.info(f"Found {len(files_to_process)} files to process in {directory_path}")
            
            # Process files
            for file_path in files_to_process:
                try:
                    file_result = await self.process_file(str(file_path), session_id)
                    
                    if file_result.get("status") == "success":
                        results["processed_files"].append({
                            "file_path": str(file_path),
                            "file_id": file_result["file_id"],
                            "language": file_result["language"],
                            "lines_of_code": file_result.get("lines_of_code", 0),
                            "task_count": len(file_result.get("task_ids", []))
                        })
                        
                        # Update language statistics
                        language = file_result["language"]
                        if language not in results["languages"]:
                            results["languages"][language] = {"files": 0, "lines": 0}
                        results["languages"][language]["files"] += 1
                        results["languages"][language]["lines"] += file_result.get("lines_of_code", 0)
                        results["total_lines"] += file_result.get("lines_of_code", 0)
                    
                    else:
                        results["skipped_files"].append({
                            "file_path": str(file_path),
                            "reason": file_result.get("error", "Unknown error")
                        })
                
                except Exception as e:
                    error_msg = f"Error processing {file_path}: {str(e)}"
                    self.logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            results["processing_time"] = time.time() - start_time
            
            # Create session summary
            await self._create_session_summary(session_id, results)
            
            self.logger.info(f"✅ Processed directory {directory_path}: "
                           f"{len(results['processed_files'])} files, "
                           f"{results['total_lines']} lines, "
                           f"{results['processing_time']:.2f}s")
            
        except Exception as e:
            self.logger.error(f"Error processing directory {directory_path}: {e}")
            results["errors"].append(str(e))
        
        return results
    
    async def process_file(self, file_path: str, session_id: str) -> Dict[str, Any]:
        """Process a single code file"""
        file_path = Path(file_path)
        
        try:
            if not file_path.exists():
                return {"status": "error", "error": "File does not exist"}
            
            # Determine language
            language = self._detect_language(file_path)
            if not language:
                return {"status": "skipped", "error": "Unsupported file type"}
            
            # Read file content
            async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = await f.read()
            
            if not content.strip():
                return {"status": "skipped", "error": "Empty file"}
            
            # Calculate file hash
            file_hash = hashlib.md5(content.encode()).hexdigest()
            
            # Check if file already exists in database
            from sqlalchemy import select
            stmt = select(CodeFile).where(
                CodeFile.original_path == str(file_path),
                CodeFile.original_hash == file_hash
            )
            result = await self.db_session.execute(stmt)
            existing_file = result.scalar_one_or_none()
            
            if existing_file:
                self.logger.info(f"File {file_path} already processed with same hash")
                return {
                    "status": "exists", 
                    "file_id": existing_file.id,
                    "language": language
                }
            
            # Create new file record
            file_id = self._generate_id()
            
            code_file = CodeFile(
                id=file_id,
                session_id=session_id,
                original_path=str(file_path),
                current_path=str(file_path),
                language=language,
                original_hash=file_hash,
                current_hash=file_hash,
                size_bytes=len(content.encode()),
                metadata={
                    "encoding": "utf-8",
                    "processed_at": datetime.utcnow().isoformat(),
                    "file_extension": file_path.suffix
                }
            )
            
            self.db_session.add(code_file)
            await self.db_session.flush()  # Get the ID
            
            # Analyze the code
            analysis_results = await self.analysis_engine.analyze_code(
                str(file_path), content, language
            )
            
            # Create enhancement tasks
            task_ids = await self.task_manager.create_enhancement_tasks(
                session_id, file_id, analysis_results
            )
            
            # Update file metadata with analysis results
            code_file.metadata.update({
                "analysis_results": analysis_results,
                "task_count": len(task_ids),
                "lines_of_code": len(content.splitlines())
            })
            
            await self.db_session.commit()
            
            self.logger.info(f"✅ Processed file {file_path}: {len(task_ids)} tasks created")
            
            return {
                "status": "success",
                "file_id": file_id,
                "language": language,
                "lines_of_code": len(content.splitlines()),
                "task_ids": task_ids,
                "analysis_summary": {
                    "functions": len(analysis_results.get("functions", [])),
                    "classes": len(analysis_results.get("classes", [])),
                    "security_findings": len(analysis_results.get("security_findings", [])),
                    "syntax_errors": len(analysis_results.get("syntax_errors", []))
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}")
            await self.db_session.rollback()
            return {"status": "error", "error": str(e)}
    
    def _should_process_file(self, file_path: Path, ignore_patterns: List[str]) -> bool:
        """Check if file should be processed"""
        # Check file extension
        if file_path.suffix not in self.supported_extensions:
            return False
        
        # Check ignore patterns
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(file_path.name, pattern):
                return False
            if fnmatch.fnmatch(str(file_path), pattern):
                return False
        
        # Check file size (skip very large files)
        try:
            if file_path.stat().st_size > 1024 * 1024:  # 1MB limit
                return False
        except:
            return False
        
        return True
    
    def _detect_language(self, file_path: Path) -> Optional[str]:
        """Detect programming language from file extension"""
        return self.supported_extensions.get(file_path.suffix.lower())
    
    async def _create_session_summary(self, session_id: str, results: Dict[str, Any]):
        """Create a summary of the processing session"""
        try:
            from sqlalchemy import select, func
            
            # Get session statistics
            stmt = select(func.count(CodeFile.id)).where(CodeFile.session_id == session_id)
            result = await self.db_session.execute(stmt)
            total_files = result.scalar()
            
            stmt = select(func.count(EnhancementTask.id)).where(EnhancementTask.session_id == session_id)
            result = await self.db_session.execute(stmt)
            total_tasks = result.scalar()
            
            # Create or update session record (if you have a Session model)
            # This would depend on your session model implementation
            
            self.logger.info(f"Session {session_id} summary: {total_files} files, {total_tasks} tasks")
            
        except Exception as e:
            self.logger.warning(f"Could not create session summary: {e}")
    
    async def get_file_info(self, file_id: str) -> Dict[str, Any]:
        """Get detailed information about a processed file"""
        try:
            code_file = await self.db_session.get(CodeFile, file_id)
            if not code_file:
                return {"error": "File not found"}
            
            # Get associated tasks
            from sqlalchemy import select
            stmt = select(EnhancementTask).where(EnhancementTask.file_id == file_id)
            result = await self.db_session.execute(stmt)
            tasks = result.scalars().all()
            
            task_summary = {}
            for task in tasks:
                status = task.status
                if status not in task_summary:
                    task_summary[status] = 0
                task_summary[status] += 1
            
            return {
                "file_id": code_file.id,
                "original_path": code_file.original_path,
                "current_path": code_file.current_path,
                "language": code_file.language,
                "size_bytes": code_file.size_bytes,
                "created_at": code_file.created_at.isoformat(),
                "updated_at": code_file.updated_at.isoformat(),
                "metadata": code_file.metadata,
                "task_summary": task_summary,
                "total_tasks": len(tasks)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting file info {file_id}: {e}")
            return {"error": str(e)}
    
    async def delete_file(self, file_id: str) -> Dict[str, Any]:
        """Delete a file and all associated tasks"""
        try:
            code_file = await self.db_session.get(CodeFile, file_id)
            if not code_file:
                return {"error": "File not found"}
            
            # Delete associated tasks first
            from sqlalchemy import delete
            stmt = delete(EnhancementTask).where(EnhancementTask.file_id == file_id)
            result = await self.db_session.execute(stmt)
            tasks_deleted = result.rowcount
            
            # Delete the file record
            await self.db_session.delete(code_file)
            await self.db_session.commit()
            
            self.logger.info(f"Deleted file {file_id} and {tasks_deleted} associated tasks")
            
            return {
                "file_id": file_id,
                "status": "deleted",
                "tasks_deleted": tasks_deleted
            }
            
        except Exception as e:
            self.logger.error(f"Error deleting file {file_id}: {e}")
            await self.db_session.rollback()
            return {"error": str(e)}
    
    def _generate_id(self) -> str:
        """Generate unique ID"""
        return hashlib.md5(f"{datetime.utcnow().isoformat()}{os.urandom(8)}".encode()).hexdigest()


# Main Enhancement Service
class CodeEnhancementService:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = EnhancementConfig.from_yaml(config_path)
        self.logger = self._setup_logging()
        
        # Initialize components
        self.db_manager = DatabaseManager(self.config)
        self.llm_manager = MultiLLMManager(self.config)
        self.analysis_engine = None
        self.task_manager = None
        self.file_processor = None
        
    async def initialize(self):
        """Initialize the service and all components"""
        try:
            # Initialize database
            await self.db_manager.initialize()
            
            # Get database session
            db_session = self.db_manager.get_session()
            
            # Initialize components
            self.analysis_engine = CodeAnalysisEngine(self.config, db_session)
            self.task_manager = EnhancementTaskManager(
                self.config, self.llm_manager, self.analysis_engine, db_session
            )
            self.file_processor = FileProcessingEngine(
                self.config, self.analysis_engine, self.task_manager, db_session
            )
            
            self.logger.info("✅ Code Enhancement Service initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize service: {e}")
            raise
    
    async def create_session(self) -> str:
        """Create a new enhancement session"""
        session_id = hashlib.md5(f"{datetime.utcnow().isoformat()}{os.urandom(8)}".encode()).hexdigest()
        self.logger.info(f"Created new session: {session_id}")
        return session_id
    
    async def process_directory(self, directory_path: str, session_id: str = None, 
                              recursive: bool = True, ignore_patterns: List[str] = None) -> Dict[str, Any]:
        """Process all files in a directory"""
        if not session_id:
            session_id = await self.create_session()
        
        return await self.file_processor.process_directory(
            directory_path, session_id, recursive, ignore_patterns
        )
    
    async def process_file(self, file_path: str, session_id: str = None) -> Dict[str, Any]:
        """Process a single file"""
        if not session_id:
            session_id = await self.create_session()
        
        return await self.file_processor.process_file(file_path, session_id)
    
    async def enhance_code(self, session_id: str, max_concurrent: int = 5) -> Dict[str, Any]:
        """Process all enhancement tasks for a session"""
        return await self.task_manager.batch_process_tasks(session_id, max_concurrent)
    
    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get status of all tasks in a session"""
        try:
            db_session = self.db_manager.get_session()
            from sqlalchemy import select, func
            
            # Get file statistics
            stmt = select(
                func.count(CodeFile.id).label('total_files'),
                func.sum(CodeFile.size_bytes).label('total_bytes')
            ).where(CodeFile.session_id == session_id)
            result = await db_session.execute(stmt)
            file_stats = result.first()
            
            # Get task statistics
            stmt = select(
                EnhancementTask.status,
                func.count(EnhancementTask.id).label('count')
            ).where(
                EnhancementTask.session_id == session_id
            ).group_by(EnhancementTask.status)
            result = await db_session.execute(stmt)
            task_stats = {row.status: row.count for row in result}
            
            return {
                "session_id": session_id,
                "files": {
                    "total": file_stats.total_files or 0,
                    "total_bytes": file_stats.total_bytes or 0
                },
                "tasks": task_stats,
                "total_tasks": sum(task_stats.values())
            }
            
        except Exception as e:
            self.logger.error(f"Error getting session status: {e}")
            return {"error": str(e)}
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration"""
        logging.basicConfig(
            level=getattr(logging, self.config.logging.level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('code_enhancement.log')
            ]
        )
        return logging.getLogger(__name__)
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.db_manager:
            await self.db_manager.close()
        self.logger.info("Code Enhancement Service cleaned up")


# CLI Interface
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="AI-Powered Code Enhancement Service")
    parser.add_argument("command", choices=["process", "enhance", "status"], help="Command to execute")
    parser.add_argument("--directory", "-d", help="Directory to process")
    parser.add_argument("--file", "-f", help="Single file to process")
    parser.add_argument("--session", "-s", help="Session ID")
    parser.add_argument("--config", "-c", default="config.yaml", help="Config file path")
    parser.add_argument("--recursive", "-r", action="store_true", help="Process directories recursively")
    parser.add_argument("--concurrent", default=5, type=int, help="Max concurrent tasks")
    
    args = parser.parse_args()
    
    # Initialize service
    service = CodeEnhancementService(args.config)
    await service.initialize()
    
    try:
        if args.command == "process":
            if args.directory:
                result = await service.process_directory(
                    args.directory, args.session, args.recursive
                )
            elif args.file:
                result = await service.process_file(args.file, args.session)
            else:
                print("Error: Must specify either --directory or --file")
                return
            
            print(f"Processing completed: {json.dumps(result, indent=2)}")
        
        elif args.command == "enhance":
            if not args.session:
                print("Error: Must specify --session for enhance command")
                return
            
            result = await service.enhance_code(args.session, args.concurrent)
            print(f"Enhancement completed: {json.dumps(result, indent=2)}")
        
        elif args.command == "status":
            if not args.session:
                print("Error: Must specify --session for status command")
                return
            
            result = await service.get_session_status(args.session)
            print(f"Session status: {json.dumps(result, indent=2)}")
    
    finally:
        await service.cleanup()


if __name__ == "__main__":
    asyncio.run(main())