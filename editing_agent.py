“””
YMERA Enterprise Multi-Agent System v3.0
Editing Agent - Advanced Code Editing and Manipulation
Enterprise-Grade Code Editing with AI-Native Capabilities and Learning Loop
“””

import ast
import asyncio
import difflib
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import uuid

import aiofiles
import anthropic
import openai
from groq import Groq
import google.generativeai as genai
import numpy as np
import tiktoken
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import structlog
import yaml
from git import Repo
from github import Github
import pylint.lint
from bandit import runner as bandit_runner
import semgrep

# Import base classes (assuming they exist in your system)

from base_agent import BaseAgent, AgentCapability, AgentStatus
from additional_components import (
AIModelManager, SecurityValidator, PerformanceMonitor,
CacheManager, LearningEngine, ComplianceChecker
)

logger = structlog.get_logger(“editing_agent”)

class EditingOperation(Enum):
“”“Types of editing operations supported”””
REFACTOR = “refactor”
OPTIMIZE = “optimize”
FIX_BUG = “fix_bug”
ADD_FEATURE = “add_feature”
STYLE_CORRECTION = “style_correction”
SECURITY_FIX = “security_fix”
PERFORMANCE_IMPROVEMENT = “performance_improvement”
DOCUMENTATION = “documentation”
TEST_GENERATION = “test_generation”
CODE_REVIEW = “code_review”

class EditingStrategy(Enum):
“”“Editing strategies for different scenarios”””
CONSERVATIVE = “conservative”  # Minimal changes, high safety
BALANCED = “balanced”         # Moderate changes, balanced safety/improvement
AGGRESSIVE = “aggressive”     # Maximum improvements, calculated risks
CUSTOM = “custom”            # User-defined strategy

class EditingComplexity(Enum):
“”“Complexity levels for editing operations”””
SIMPLE = “simple”      # Single-line edits, formatting
MODERATE = “moderate”  # Function-level changes
COMPLEX = “complex”    # Multi-file refactoring
CRITICAL = “critical”  # Architecture changes

@dataclass
class EditingContext:
“”“Context information for editing operations”””
project_id: str
file_path: str
operation_type: EditingOperation
strategy: EditingStrategy = EditingStrategy.BALANCED
complexity: EditingComplexity = EditingComplexity.MODERATE
target_language: str = “python”
requirements: Dict[str, Any] = None
constraints: Dict[str, Any] = None
metadata: Dict[str, Any] = None

```
def __post_init__(self):
    if self.requirements is None:
        self.requirements = {}
    if self.constraints is None:
        self.constraints = {}
    if self.metadata is None:
        self.metadata = {}
```

@dataclass
class EditingResult:
“”“Result of an editing operation”””
operation_id: str
success: bool
original_content: str
modified_content: str
changes_summary: List[Dict[str, Any]]
metrics: Dict[str, Any]
warnings: List[str]
errors: List[str]
confidence_score: float
execution_time: float
created_at: datetime = None

```
def __post_init__(self):
    if self.created_at is None:
        self.created_at = datetime.utcnow()
```

@dataclass
class CodeAnalysis:
“”“Comprehensive code analysis results”””
file_path: str
language: str
complexity_score: float
quality_score: float
security_score: float
performance_score: float
maintainability_score: float
test_coverage: float
issues: List[Dict[str, Any]]
suggestions: List[Dict[str, Any]]
dependencies: List[str]
functions: List[Dict[str, Any]]
classes: List[Dict[str, Any]]
metrics: Dict[str, Any]

class CodeTransformer(ABC):
“”“Abstract base class for code transformers”””

```
@abstractmethod
async def transform(self, content: str, context: EditingContext) -> str:
    """Transform the given code content"""
    pass

@abstractmethod
def get_supported_languages(self) -> List[str]:
    """Get list of supported programming languages"""
    pass
```

class PythonTransformer(CodeTransformer):
“”“Python-specific code transformer”””

```
def __init__(self):
    self.supported_languages = ["python", "py"]

async def transform(self, content: str, context: EditingContext) -> str:
    """Transform Python code based on the editing context"""
    try:
        # Parse AST to ensure valid syntax
        tree = ast.parse(content)
        
        # Apply transformations based on operation type
        if context.operation_type == EditingOperation.REFACTOR:
            return await self._refactor_code(content, tree, context)
        elif context.operation_type == EditingOperation.OPTIMIZE:
            return await self._optimize_code(content, tree, context)
        elif context.operation_type == EditingOperation.FIX_BUG:
            return await self._fix_bugs(content, tree, context)
        elif context.operation_type == EditingOperation.STYLE_CORRECTION:
            return await self._apply_style_corrections(content, context)
        else:
            return content
            
    except SyntaxError as e:
        logger.error(f"Syntax error in Python code: {e}")
        return content

async def _refactor_code(self, content: str, tree: ast.AST, context: EditingContext) -> str:
    """Refactor Python code for better structure and readability"""
    # Implementation for code refactoring
    # This is a simplified example - real implementation would be more sophisticated
    lines = content.split('\n')
    refactored_lines = []
    
    for line in lines:
        # Remove unnecessary blank lines
        if line.strip() or (refactored_lines and refactored_lines[-1].strip()):
            refactored_lines.append(line)
    
    return '\n'.join(refactored_lines)

async def _optimize_code(self, content: str, tree: ast.AST, context: EditingContext) -> str:
    """Optimize Python code for better performance"""
    # Implementation for code optimization
    return content

async def _fix_bugs(self, content: str, tree: ast.AST, context: EditingContext) -> str:
    """Fix common bugs in Python code"""
    # Implementation for bug fixing
    return content

async def _apply_style_corrections(self, content: str, context: EditingContext) -> str:
    """Apply PEP8 and other style corrections"""
    # Use black or autopep8 for formatting
    try:
        import black
        return black.format_str(content, mode=black.FileMode())
    except ImportError:
        logger.warning("Black formatter not available")
        return content

def get_supported_languages(self) -> List[str]:
    return self.supported_languages
```

class AIEditingEngine:
“”“AI-powered editing engine with multiple model support”””

```
def __init__(self, ai_manager: AIModelManager):
    self.ai_manager = ai_manager
    self.model_rotation_index = 0
    self.performance_metrics = {}
    
async def generate_edit_suggestions(self, 
                                  content: str, 
                                  context: EditingContext) -> List[Dict[str, Any]]:
    """Generate AI-powered edit suggestions"""
    try:
        prompt = self._build_editing_prompt(content, context)
        
        # Try multiple AI models for best results
        models = ["claude-3-opus", "gpt-4o", "deepseek-coder", "groq-llama"]
        suggestions = []
        
        for model in models:
            try:
                response = await self.ai_manager.generate_response(
                    prompt=prompt,
                    model=model,
                    temperature=0.1,
                    max_tokens=4096
                )
                
                parsed_suggestions = self._parse_ai_response(response, model)
                suggestions.extend(parsed_suggestions)
                
            except Exception as e:
                logger.warning(f"Model {model} failed: {e}")
                continue
        
        # Rank and filter suggestions
        ranked_suggestions = self._rank_suggestions(suggestions, context)
        return ranked_suggestions
        
    except Exception as e:
        logger.error(f"Error generating AI edit suggestions: {e}")
        return []

def _build_editing_prompt(self, content: str, context: EditingContext) -> str:
    """Build optimized prompt for AI editing"""
    operation_descriptions = {
        EditingOperation.REFACTOR: "refactor for better structure and maintainability",
        EditingOperation.OPTIMIZE: "optimize for better performance and efficiency",
        EditingOperation.FIX_BUG: "identify and fix bugs or potential issues",
        EditingOperation.STYLE_CORRECTION: "apply style corrections and formatting",
        EditingOperation.SECURITY_FIX: "identify and fix security vulnerabilities",
        EditingOperation.ADD_FEATURE: "add the requested feature or functionality"
    }
    
    operation_desc = operation_descriptions.get(
        context.operation_type, 
        "improve the code quality"
    )
    
    prompt = f"""
```

You are an expert software engineer tasked to {operation_desc} for the following {context.target_language} code.

Context:

- Operation: {context.operation_type.value}
- Strategy: {context.strategy.value}
- Complexity: {context.complexity.value}
- File: {context.file_path}

Requirements: {json.dumps(context.requirements, indent=2)}
Constraints: {json.dumps(context.constraints, indent=2)}

Original Code:

```{context.target_language}
{content}
```

Please provide:

1. Detailed analysis of the current code
1. Specific improvement suggestions with explanations
1. Modified code with changes highlighted
1. Risk assessment for each change
1. Performance impact analysis

Format your response as JSON with the following structure:
{{
“analysis”: “detailed code analysis”,
“suggestions”: [
{{
“type”: “suggestion_type”,
“description”: “what to change and why”,
“priority”: “high|medium|low”,
“risk_level”: “low|medium|high”,
“confidence”: 0.95,
“impact”: “performance|readability|maintainability|security”
}}
],
“modified_code”: “the improved code”,
“changes_summary”: [
{{
“line_number”: 10,
“change_type”: “modification|addition|deletion”,
“description”: “what was changed”,
“reasoning”: “why the change was made”
}}
],
“performance_impact”: “expected performance improvement or impact”,
“risk_assessment”: “overall risk assessment of the changes”
}}
“””
return prompt

```
def _parse_ai_response(self, response: str, model: str) -> List[Dict[str, Any]]:
    """Parse AI response into structured suggestions"""
    try:
        parsed = json.loads(response)
        
        # Add model source to each suggestion
        if "suggestions" in parsed:
            for suggestion in parsed["suggestions"]:
                suggestion["source_model"] = model
                suggestion["timestamp"] = datetime.utcnow().isoformat()
        
        return [parsed] if isinstance(parsed, dict) else parsed
        
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON response from {model}: {e}")
        # Try to extract code blocks if JSON parsing fails
        return self._extract_code_suggestions(response, model)

def _extract_code_suggestions(self, response: str, model: str) -> List[Dict[str, Any]]:
    """Extract suggestions from non-JSON responses"""
    suggestions = []
    
    # Look for code blocks
    code_pattern = r'```(?:python|py)?\s*\n(.*?)\n```'
    code_matches = re.findall(code_pattern, response, re.DOTALL)
    
    for i, code in enumerate(code_matches):
        suggestions.append({
            "type": "code_improvement",
            "description": f"Code improvement suggestion {i+1}",
            "modified_code": code.strip(),
            "priority": "medium",
            "risk_level": "medium",
            "confidence": 0.7,
            "source_model": model,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    return suggestions

def _rank_suggestions(self, suggestions: List[Dict[str, Any]], 
                     context: EditingContext) -> List[Dict[str, Any]]:
    """Rank suggestions based on relevance, confidence, and strategy"""
    if not suggestions:
        return []
    
    # Score each suggestion
    for suggestion in suggestions:
        score = 0.0
        
        # Confidence weight
        confidence = suggestion.get("confidence", 0.5)
        score += confidence * 0.4
        
        # Priority weight
        priority_weights = {"high": 0.3, "medium": 0.2, "low": 0.1}
        priority = suggestion.get("priority", "medium")
        score += priority_weights.get(priority, 0.2)
        
        # Risk assessment (lower risk = higher score for conservative strategy)
        risk_weights = {"low": 0.3, "medium": 0.2, "high": 0.1}
        if context.strategy == EditingStrategy.CONSERVATIVE:
            risk = suggestion.get("risk_level", "medium")
            score += risk_weights.get(risk, 0.2)
        
        # Model reputation (can be enhanced with historical performance)
        model_weights = {
            "claude-3-opus": 0.1,
            "gpt-4o": 0.09,
            "deepseek-coder": 0.08,
            "groq-llama": 0.07
        }
        model = suggestion.get("source_model", "")
        score += model_weights.get(model, 0.05)
        
        suggestion["ranking_score"] = score
    
    # Sort by score (descending)
    return sorted(suggestions, key=lambda x: x.get("ranking_score", 0), reverse=True)
```

class EditingAgent(BaseAgent):
“”“Enterprise-grade code editing agent with AI capabilities”””

```
def __init__(self, agent_id: str = None):
    super().__init__(
        agent_id=agent_id or str(uuid.uuid4()),
        name="EditingAgent",
        agent_type="editing",
        capabilities=[
            AgentCapability.CODE_ANALYSIS,
            AgentCapability.CODE_GENERATION,
            AgentCapability.CODE_OPTIMIZATION,
            AgentCapability.BUG_DETECTION,
            AgentCapability.REFACTORING,
            AgentCapability.SECURITY_ANALYSIS
        ]
    )
    
    # Initialize components
    self.ai_manager = AIModelManager()
    self.ai_engine = AIEditingEngine(self.ai_manager)
    self.security_validator = SecurityValidator()
    self.performance_monitor = PerformanceMonitor()
    self.cache_manager = CacheManager()
    self.learning_engine = LearningEngine()
    self.compliance_checker = ComplianceChecker()
    
    # Initialize transformers
    self.transformers = {
        "python": PythonTransformer(),
        # Add more language transformers as needed
    }
    
    # Performance metrics
    self.operation_count = 0
    self.success_rate = 1.0
    self.average_execution_time = 0.0
    self.confidence_scores = []
    
    # Thread pool for CPU-intensive operations
    self.executor = ThreadPoolExecutor(max_workers=4)
    
    logger.info(f"EditingAgent {self.agent_id} initialized with {len(self.transformers)} transformers")

async def initialize(self) -> bool:
    """Initialize the editing agent"""
    try:
        # Initialize AI models
        await self.ai_manager.initialize()
        
        # Initialize embedding models for similarity search
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize tokenizers
        self.tokenizers = {
            "gpt-4o": tiktoken.encoding_for_model("gpt-4o"),
            "claude": tiktoken.get_encoding("cl100k_base")
        }
        
        # Load learned patterns and preferences
        await self._load_learning_data()
        
        self.status = AgentStatus.ACTIVE
        logger.info(f"EditingAgent {self.agent_id} successfully initialized")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize EditingAgent: {e}")
        self.status = AgentStatus.ERROR
        return False

async def process_editing_request(self, 
                                content: str, 
                                context: EditingContext) -> EditingResult:
    """Process a code editing request"""
    operation_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Update status
        self.status = AgentStatus.BUSY
        
        # Validate input
        if not content.strip():
            raise ValueError("Empty content provided")
        
        # Security validation
        security_issues = await self.security_validator.scan_code(content)
        if security_issues and context.strategy == EditingStrategy.CONSERVATIVE:
            logger.warning(f"Security issues found: {len(security_issues)}")
        
        # Check cache for similar requests
        cache_key = self._generate_cache_key(content, context)
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result and context.strategy != EditingStrategy.CUSTOM:
            logger.info(f"Cache hit for operation {operation_id}")
            return EditingResult(**cached_result)
        
        # Analyze code before editing
        analysis = await self._analyze_code(content, context)
        
        # Generate AI-powered suggestions
        ai_suggestions = await self.ai_engine.generate_edit_suggestions(content, context)
        
        # Apply appropriate transformer
        transformer = self._get_transformer(context.target_language)
        if transformer:
            transformed_content = await transformer.transform(content, context)
        else:
            transformed_content = content
        
        # Apply AI suggestions selectively
        modified_content = await self._apply_suggestions(
            transformed_content, ai_suggestions, context
        )
        
        # Validate the modified code
        validation_result = await self._validate_changes(
            content, modified_content, context
        )
        
        # Calculate confidence score
        confidence_score = await self._calculate_confidence_score(
            content, modified_content, ai_suggestions, validation_result
        )
        
        # Generate changes summary
        changes_summary = await self._generate_changes_summary(
            content, modified_content
        )
        
        # Performance metrics
        execution_time = time.time() - start_time
        
        # Create result
        result = EditingResult(
            operation_id=operation_id,
            success=True,
            original_content=content,
            modified_content=modified_content,
            changes_summary=changes_summary,
            metrics={
                "lines_changed": len(changes_summary),
                "analysis": asdict(analysis),
                "ai_suggestions_count": len(ai_suggestions),
                "confidence_score": confidence_score,
                "security_issues": len(security_issues),
                "validation_score": validation_result.get("score", 0.0)
            },
            warnings=validation_result.get("warnings", []),
            errors=validation_result.get("errors", []),
            confidence_score=confidence_score,
            execution_time=execution_time
        )
        
        # Update performance metrics
        await self._update_performance_metrics(result)
        
        # Cache result for future use
        await self.cache_manager.set(cache_key, asdict(result), ttl=3600)
        
        # Learn from this operation
        await self._learn_from_operation(context, result, ai_suggestions)
        
        # Update status
        self.status = AgentStatus.ACTIVE
        
        logger.info(f"Successfully processed editing request {operation_id} "
                   f"in {execution_time:.2f}s with confidence {confidence_score:.2f}")
        
        return result
        
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Error processing editing request {operation_id}: {e}")
        
        self.status = AgentStatus.ERROR
        
        return EditingResult(
            operation_id=operation_id,
            success=False,
            original_content=content,
            modified_content=content,
            changes_summary=[],
            metrics={"error": str(e)},
            warnings=[],
            errors=[str(e)],
            confidence_score=0.0,
            execution_time=execution_time
        )

async def _analyze_code(self, content: str, context: EditingContext) -> CodeAnalysis:
    """Perform comprehensive code analysis"""
    try:
        # Initialize analysis result
        analysis = CodeAnalysis(
            file_path=context.file_path,
            language=context.target_language,
            complexity_score=0.0,
            quality_score=0.0,
            security_score=0.0,
            performance_score=0.0,
            maintainability_score=0.0,
            test_coverage=0.0,
            issues=[],
            suggestions=[],
            dependencies=[],
            functions=[],
            classes=[],
            metrics={}
        )
        
        if context.target_language.lower() == "python":
            analysis = await self._analyze_python_code(content, analysis)
        
        # Additional analysis with external tools
        if context.complexity != EditingComplexity.SIMPLE:
            await self._run_static_analysis_tools(content, analysis, context)
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing code: {e}")
        # Return basic analysis on error
        return CodeAnalysis(
            file_path=context.file_path,
            language=context.target_language,
            complexity_score=0.5,
            quality_score=0.5,
            security_score=0.5,
            performance_score=0.5,
            maintainability_score=0.5,
            test_coverage=0.0,
            issues=[{"type": "analysis_error", "message": str(e)}],
            suggestions=[],
            dependencies=[],
            functions=[],
            classes=[],
            metrics={}
        )

async def _analyze_python_code(self, content: str, analysis: CodeAnalysis) -> CodeAnalysis:
    """Analyze Python code using AST"""
    try:
        tree = ast.parse(content)
        
        # Extract functions and classes
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                analysis.functions.append({
                    "name": node.name,
                    "line_number": node.lineno,
                    "args_count": len(node.args.args),
                    "returns": node.returns is not None,
                    "docstring": ast.get_docstring(node) is not None
                })
            elif isinstance(node, ast.ClassDef):
                analysis.classes.append({
                    "name": node.name,
                    "line_number": node.lineno,
                    "methods_count": sum(1 for n in node.body if isinstance(n, ast.FunctionDef)),
                    "docstring": ast.get_docstring(node) is not None
                })
        
        # Calculate complexity metrics
        lines = content.split('\n')
        analysis.metrics.update({
            "total_lines": len(lines),
            "non_empty_lines": sum(1 for line in lines if line.strip()),
            "functions_count": len(analysis.functions),
            "classes_count": len(analysis.classes),
            "complexity_per_function": len(analysis.functions) / max(1, len(lines)) * 100
        })
        
        # Score calculations
        analysis.complexity_score = min(1.0, analysis.metrics["complexity_per_function"] / 10)
        analysis.quality_score = self._calculate_quality_score(analysis)
        analysis.maintainability_score = self._calculate_maintainability_score(analysis)
        
    except SyntaxError as e:
        analysis.issues.append({
            "type": "syntax_error",
            "message": str(e),
            "line_number": getattr(e, 'lineno', 0),
            "severity": "high"
        })
    
    return analysis

def _calculate_quality_score(self, analysis: CodeAnalysis) -> float:
    """Calculate code quality score based on various metrics"""
    score = 0.0
    
    # Docstring coverage
    documented_functions = sum(1 for f in analysis.functions if f.get("docstring"))
    total_functions = len(analysis.functions)
    if total_functions > 0:
        score += (documented_functions / total_functions) * 0.3
    else:
        score += 0.3
    
    # Class documentation
    documented_classes = sum(1 for c in analysis.classes if c.get("docstring"))
    total_classes = len(analysis.classes)
    if total_classes > 0:
        score += (documented_classes / total_classes) * 0.2
    else:
        score += 0.2
    
    # Code organization (reasonable function sizes)
    if total_functions > 0:
        lines_per_function = analysis.metrics.get("total_lines", 0) / total_functions
        if lines_per_function <= 50:  # Good function size
            score += 0.3
        elif lines_per_function <= 100:  # Acceptable
            score += 0.2
        else:  # Large functions
            score += 0.1
    else:
        score += 0.2
    
    # Issue penalty
    high_severity_issues = sum(1 for issue in analysis.issues 
                             if issue.get("severity") == "high")
    score -= high_severity_issues * 0.1
    
    return max(0.0, min(1.0, score))

def _calculate_maintainability_score(self, analysis: CodeAnalysis) -> float:
    """Calculate maintainability score"""
    score = 0.5  # Base score
    
    # Factor in complexity
    if analysis.complexity_score < 0.3:
        score += 0.3
    elif analysis.complexity_score < 0.6:
        score += 0.1
    
    # Factor in documentation
    score += analysis.quality_score * 0.2
    
    return max(0.0, min(1.0, score))

async def _run_static_analysis_tools(self, content: str, 
                                   analysis: CodeAnalysis, 
                                   context: EditingContext):
    """Run external static analysis tools"""
    try:
        # Create temporary file for analysis
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp_file:
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Run pylint analysis
            if context.target_language.lower() == "python":
                await self._run_pylint_analysis(tmp_file_path, analysis)
                await self._run_bandit_analysis(tmp_file_path, analysis)
            
        finally:
            # Clean up temporary file
            os.unlink(tmp_file_path)
            
    except Exception as e:
        logger.warning(f"Static analysis tools failed: {e}")

async def _run_pylint_analysis(self, file_path: str, analysis: CodeAnalysis):
    """Run pylint analysis"""
    try:
        # Run pylint in a subprocess to capture output
        process = await asyncio.create_subprocess_exec(
            'pylint', file_path, '--output-format=json',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if stdout:
            try:
                pylint_results = json.loads(stdout.decode())
                for result in pylint_results:
                    analysis.issues.append({
                        "type": "pylint",
                        "message": result.get("message", ""),
                        "line_number": result.get("line", 0),
                        "severity": self._map_pylint_severity(result.get("type", ""))
                    })
            except json.JSONDecodeError:
                logger.warning("Failed to parse pylint JSON output")
        
    except FileNotFoundError:
        logger.debug("Pylint not available")
    except Exception as e:
        logger.warning(f"Pylint analysis failed: {e}")

async def _run_bandit_analysis(self, file_path: str, analysis: CodeAnalysis):
    """Run bandit security analysis"""
    try:
        # Run bandit
        process = await asyncio.create_subprocess_exec(
            'bandit', '-f', 'json', file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if stdout:
            try:
                bandit_results = json.loads(stdout.decode())
                for result in bandit_results.get("results", []):
                    analysis.issues.append({
                        "type": "security",
                        "message": result.get("issue_text", ""),
                        "line_number": result.get("line_number", 0),
                        "severity": result.get("issue_severity", "medium").lower()
                    })
                    
                # Update security score
                total_issues = len(bandit_results.get("results", []))
                if total_issues == 0:
                    analysis.security_score = 1.0
                else:
                    analysis.security_score = max(0.0, 1.0 - (total_issues * 0.1))
                    
            except json.JSONDecodeError:
                logger.warning("Failed to parse bandit JSON output")
        
    except FileNotFoundError:
        logger.debug("Bandit not available")
    except Exception as e:
        logger.warning(f"Bandit analysis failed: {e}")

def _map_pylint_severity(self, pylint_type: str) -> str:
    """Map pylint message types to severity levels"""
    severity_map = {
        "error": "high",
        "warning": "medium",
        "refactor": "low",
        "convention": "low",
        "info": "low"
    }
    return severity_map.get(pylint_type.lower(), "medium")

async def _apply_suggestions(self, content: str, 
                           suggestions: List[Dict[str, Any]], 
                           context: EditingContext) -> str:
    """Apply AI suggestions to the code content"""
    if not suggestions:
        return content
    
    modified_content = content
    applied_changes = 0
    max_changes = self._get_max_changes_for_strategy(context.strategy)
    
    # Sort suggestions by ranking score
    sorted_suggestions = sorted(suggestions, 
                              key=lambda x: x.get("ranking_score", 0), 
                              reverse=True)
    
    for suggestion in sorted_suggestions:
        if applied_changes >= max_changes:
            break
            
        if self._should_apply_suggestion(suggestion, context):
            try:
                # Apply the suggestion
                if "modified_code" in suggestion:
                    # For now, use the modified code if available
                    # In production, this would need more sophisticated merging
                    potential_content = suggestion["modified_code"]
                    
                    # Validate the change
                    if await self._is_valid_change(content, potential_content, context):
                        modified_content = potential_content
                        applied_changes += 1
                        logger.info(f"Applied suggestion: {suggestion.get('description', 'N/A')}")
            
            except Exception as e:
                logger.warning(f"Failed to apply suggestion: {e}")
                continue
    
    logger.info(f"Applied {applied_changes} out of {len(suggestions)} suggestions")
    return modified_content

def _get_max_changes_for_strategy(self, strategy: EditingStrategy) -> int:
    """Get maximum number of changes based on strategy"""
    strategy_limits = {
        EditingStrategy.CONSERVATIVE: 3,
        EditingStrategy.BALANCED: 5,
        EditingStrategy.AGGRESSIVE: 10,
        EditingStrategy.CUSTOM: 100
    }
    return strategy_limits.get(strategy, 5)

def _should_apply_suggestion(self, suggestion: Dict[str, Any], 
                           context: EditingContext) -> bool:
    """Determine if a suggestion should be applied"""
    # Check confidence threshold
    min_confidence = {
        EditingStrategy.CONSERVATIVE: 0.8,
        EditingStrategy.BALANCED: 0.6,
        EditingStrategy.AGGRESSIVE: 0.4,
        EditingStrategy.CUSTOM: 0.5
    }.get(context.strategy, 0.6)
    
    if suggestion.get("confidence", 0) < min_confidence:
        return False
    
    # Check risk tolerance
    max_risk = {
        EditingStrategy.CONSERVATIVE: "low",
        EditingStrategy.BALANCED: "medium",
        EditingStrategy.AGGRESSIVE: "high",
        EditingStrategy.CUSTOM: "high"
    }.get(context.strategy, "medium")
    
    suggestion_risk = suggestion.get("risk_level", "medium")
    risk_levels = ["low", "medium", "high"]
    
    if risk_levels.index(suggestion_risk) > risk_levels.index(max_risk):
        return False
    
    return True

async def _is_valid_change(self, original: str, modified: str, 
                         context: EditingContext) -> bool:
    """Validate that a proposed change is safe and correct"""
    try:
        # Basic syntax check
        if context.target_language.lower() == "python":
            try:
                ast.parse(modified)
            except SyntaxError:
                return False
        
        # Check if change is too drastic
        similarity = self._calculate_similarity(original, modified)
        if similarity < 0.3:  # Too different
            return False
        
        # Security check
        security_issues = await self.security_validator.scan_code(modified)
        if len(security_issues) > len(await self.security_validator.scan_code(original)):
            return False
        
        return True
        
    except Exception:
        return False

def _calculate_similarity(self, text1: str, text2: str) -> float:
    """Calculate similarity between two text strings"""
    try:
        # Use embedding similarity for better semantic comparison
        embeddings1 = self.embedding_model.encode([text1])
        embeddings2 = self.embedding_model.encode([text2])
        similarity = cosine_similarity(embeddings1, embeddings2)[0][0]
        return float(similarity)
    except Exception:
        # Fallback to sequence matcher
        return difflib.SequenceMatcher(None, text1, text2).ratio()

async def _validate_changes(self, original: str, modified: str, 
                          context: EditingContext) -> Dict[str, Any]:
    """Validate the changes made to the code"""
    validation_result = {
        "score": 0.0,
        "warnings": [],
        "errors": [],
        "metrics": {}
    }
    
    try:
        # Syntax validation
        if context.target_language.lower() == "python":
            try:
                ast.parse(modified)
                validation_result["score"] += 0.3
            except SyntaxError as e:
                validation_result["errors"].append(f"Syntax error: {e}")
                return validation_result
        
        # Semantic preservation check
        similarity = self._calculate_similarity(original, modified)
        validation_result["metrics"]["similarity"] = similarity
        
        if similarity > 0.8:
            validation_result["score"] += 0.3
        elif similarity > 0.6:
            validation_result["score"] += 0.2
            validation_result["warnings"].append("Significant semantic changes detected")
        else:
            validation_result["warnings"].append("Major semantic changes detected")
        
        # Security validation
        original_issues = await self.security_validator.scan_code(original)
        modified_issues = await self.security_validator.scan_code(modified)
        
        if len(modified_issues) <= len(original_issues):
            validation_result["score"] += 0.2
        else:
            validation_result["warnings"].append("New security issues introduced")
        
        # Complexity validation
        original_complexity = self._calculate_cyclomatic_complexity(original)
        modified_complexity = self._calculate_cyclomatic_complexity(modified)
        
        validation_result["metrics"]["complexity_change"] = modified_complexity - original_complexity
        
        if modified_complexity <= original_complexity:
            validation_result["score"] += 0.2
        elif modified_complexity > original_complexity * 1.5:
            validation_result["warnings"].append("Significant complexity increase")
        
        # Final score normalization
        validation_result["score"] = min(1.0, validation_result["score"])
        
    except Exception as e:
        validation_result["errors"].append(f"Validation error: {e}")
    
    return validation_result

def _calculate_cyclomatic_complexity(self, code: str) -> int:
    """Calculate cyclomatic complexity of the code"""
    try:
        tree = ast.parse(code)
        complexity = 1  # Base complexity
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
            elif isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp)):
                complexity += 1
        
        return complexity
        
    except Exception:
        return 1

async def _calculate_confidence_score(self, original: str, modified: str,
                                    suggestions: List[Dict[str, Any]],
                                    validation_result: Dict[str, Any]) -> float:
    """Calculate confidence score for the editing operation"""
    try:
        base_confidence = 0.5
        
        # Factor in validation score
        base_confidence += validation_result.get("score", 0) * 0.3
        
        # Factor in AI suggestion confidence
        if suggestions:
            avg_ai_confidence = sum(s.get("confidence", 0) for s in suggestions) / len(suggestions)
            base_confidence += avg_ai_confidence * 0.3
        
        # Factor in similarity (controlled changes are more confident)
        similarity = validation_result.get("metrics", {}).get("similarity", 0.5)
        if 0.7 <= similarity <= 0.95:  # Sweet spot for controlled improvements
            base_confidence += 0.2
        
        # Penalty for errors
        error_penalty = len(validation_result.get("errors", [])) * 0.1
        base_confidence -= error_penalty
        
        # Bonus for successful static analysis
        if not validation_result.get("errors") and validation_result.get("score", 0) > 0.8:
            base_confidence += 0.1
        
        return max(0.0, min(1.0, base_confidence))
        
    except Exception:
        return 0.5

async def _generate_changes_summary(self, original: str, modified: str) -> List[Dict[str, Any]]:
    """Generate a summary of changes made"""
    changes = []
    
    try:
        # Use difflib to find differences
        original_lines = original.split('\n')
        modified_lines = modified.split('\n')
        
        differ = difflib.unified_diff(
            original_lines, modified_lines,
            fromfile='original', tofile='modified',
            lineterm='', n=3
        )
        
        diff_lines = list(differ)
        
        current_line = 0
        for line in diff_lines:
            if line.startswith('@@'):
                # Extract line numbers
                match = re.search(r'-(\d+),?(\d+)? \+(\d+),?(\d+)?', line)
                if match:
                    current_line = int(match.group(3))
            elif line.startswith('+') and not line.startswith('+++'):
                changes.append({
                    "line_number": current_line,
                    "change_type": "addition",
                    "content": line[1:],
                    "description": f"Added line: {line[1:].strip()}"
                })
                current_line += 1
            elif line.startswith('-') and not line.startswith('---'):
                changes.append({
                    "line_number": current_line,
                    "change_type": "deletion",
                    "content": line[1:],
                    "description": f"Removed line: {line[1:].strip()}"
                })
            elif line.startswith(' '):
                current_line += 1
        
    except Exception as e:
        logger.warning(f"Error generating changes summary: {e}")
        changes.append({
            "line_number": 0,
            "change_type": "modification",
            "content": "",
            "description": f"Code modified (summary generation failed: {e})"
        })
    
    return changes

async def _update_performance_metrics(self, result: EditingResult):
    """Update agent performance metrics"""
    self.operation_count += 1
    
    # Update success rate
    if result.success:
        self.success_rate = ((self.success_rate * (self.operation_count - 1)) + 1) / self.operation_count
    else:
        self.success_rate = (self.success_rate * (self.operation_count - 1)) / self.operation_count
    
    # Update average execution time
    self.average_execution_time = (
        (self.average_execution_time * (self.operation_count - 1) + result.execution_time) 
        / self.operation_count
    )
    
    # Update confidence scores
    self.confidence_scores.append(result.confidence_score)
    if len(self.confidence_scores) > 100:  # Keep only recent scores
        self.confidence_scores = self.confidence_scores[-100:]
    
    # Report to performance monitor
    await self.performance_monitor.record_operation(
        agent_id=self.agent_id,
        operation_type="editing",
        duration=result.execution_time,
        success=result.success,
        confidence=result.confidence_score
    )

async def _learn_from_operation(self, context: EditingContext, 
                              result: EditingResult,
                              suggestions: List[Dict[str, Any]]):
    """Learn from the editing operation to improve future performance"""
    try:
        learning_data = {
            "operation_type": context.operation_type.value,
            "strategy": context.strategy.value,
            "language": context.target_language,
            "complexity": context.complexity.value,
            "success": result.success,
            "confidence_score": result.confidence_score,
            "execution_time": result.execution_time,
            "changes_count": len(result.changes_summary),
            "ai_suggestions_used": len(suggestions),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store learning data
        await self.learning_engine.record_operation(
            agent_id=self.agent_id,
            operation_data=learning_data
        )
        
        # Update model preferences based on success
        for suggestion in suggestions:
            model = suggestion.get("source_model")
            if model and result.success:
                await self.learning_engine.update_model_preference(
                    agent_id=self.agent_id,
                    model=model,
                    success=result.success,
                    confidence=suggestion.get("confidence", 0)
                )
        
        logger.debug(f"Recorded learning data for operation {result.operation_id}")
        
    except Exception as e:
        logger.warning(f"Failed to record learning data: {e}")

async def _load_learning_data(self):
    """Load learned patterns and preferences"""
    try:
        # Load model preferences
        self.model_preferences = await self.learning_engine.get_model_preferences(
            self.agent_id
        )
        
        # Load successful patterns
        self.successful_patterns = await self.learning_engine.get_successful_patterns(
            self.agent_id
        )
        
        logger.info(f"Loaded learning data: {len(self.model_preferences)} model preferences, "
                   f"{len(self.successful_patterns)} successful patterns")
        
    except Exception as e:
        logger.warning(f"Failed to load learning data: {e}")
        self.model_preferences = {}
        self.successful_patterns = []

def _get_transformer(self, language: str) -> Optional[CodeTransformer]:
    """Get the appropriate code transformer for the language"""
    return self.transformers.get(language.lower())

def _generate_cache_key(self, content: str, context: EditingContext) -> str:
    """Generate cache key for the editing request"""
    key_data = {
        "content_hash": hashlib.md5(content.encode()).hexdigest(),
        "operation": context.operation_type.value,
        "strategy": context.strategy.value,
        "language": context.target_language,
        "requirements": context.requirements,
        "constraints": context.constraints
    }
    key_string = json.dumps(key_data, sort_keys=True)
    return f"edit_{hashlib.sha256(key_string.encode()).hexdigest()[:16]}"

async def get_agent_status(self) -> Dict[str, Any]:
    """Get current agent status and metrics"""
    avg_confidence = (sum(self.confidence_scores) / len(self.confidence_scores) 
                     if self.confidence_scores else 0.0)
    
    return {
        "agent_id": self.agent_id,
        "status": self.status.value,
        "operation_count": self.operation_count,
        "success_rate": self.success_rate,
        "average_execution_time": self.average_execution_time,
        "average_confidence": avg_confidence,
        "supported_languages": list(self.transformers.keys()),
        "capabilities": [cap.value for cap in self.capabilities],
        "learning_data": {
            "model_preferences": len(getattr(self, 'model_preferences', {})),
            "successful_patterns": len(getattr(self, 'successful_patterns', []))
        }
    }

async def shutdown(self):
    """Shutdown the editing agent gracefully"""
    try:
        logger.info(f"Shutting down EditingAgent {self.agent_id}")
        
        # Update status
        self.status = AgentStatus.STOPPING
        
        # Save final learning data
        await self.learning_engine.flush_pending_data(self.agent_id)
        
        # Shutdown executor
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)
        
        # Close AI connections
        await self.ai_manager.shutdown()
        
        self.status = AgentStatus.STOPPED
        logger.info(f"EditingAgent {self.agent_id} shutdown completed")
        
    except Exception as e:
        logger.error(f"Error during EditingAgent shutdown: {e}")
        self.status = AgentStatus.ERROR
```

# Factory function for creating editing agents

async def create_editing_agent(agent_id: str = None) -> EditingAgent:
“”“Factory function to create and initialize an editing agent”””
agent = EditingAgent(agent_id)

```
if await agent.initialize():
    return agent
else:
    raise RuntimeError(f"Failed to initialize EditingAgent {agent.agent_id}")
```

# Main execution for standalone testing

if **name** == “**main**”:
async def test_editing_agent():
“”“Test the editing agent functionality”””

```
    # Sample Python code for testing
    test_code = '''
```

def calculate_sum(numbers):
total = 0
for num in numbers:
total = total + num
return total

def main():
nums = [1, 2, 3, 4, 5]
result = calculate_sum(nums)
print(“Sum is:”, result)

if **name** == “**main**”:
main()
‘’’

```
    try:
        # Create and initialize agent
        agent = await create_editing_agent()
        
        # Create editing context
        context = EditingContext(
            project_id="test_project",
            file_path="test_file.py",
            operation_type=EditingOperation.OPTIMIZE,
            strategy=EditingStrategy.BALANCED,
            target_language="python"
        )
        
        # Process editing request
        result = await agent.process_editing_request(test_code, context)
        
        # Print results
        print(f"Operation ID: {result.operation_id}")
        print(f"Success: {result.success}")
        print(f"Confidence: {result.confidence_score:.2f}")
        print(f"Execution Time: {result.execution_time:.2f}s")
        print(f"Changes: {len(result.changes_summary)}")
        
        if result.modified_content != test_code:
            print("\nModified Code:")
            print(result.modified_content)
        else:
            print("\nNo changes were made to the code.")
        
        # Get agent status
        status = await agent.get_agent_status()
        print(f"\nAgent Status: {status}")
        
        # Shutdown agent
        await agent.shutdown()
        
    except Exception as e:
        logger.error(f"Test failed: {e}")

# Run the test
asyncio.run(test_editing_agent())
```