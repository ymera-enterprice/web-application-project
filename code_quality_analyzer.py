"""
YMERA Enterprise Code Quality Analyzer
Production-Ready Code Analysis Service with AI Learning Integration
"""

import ast
import asyncio
import json
import re
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import logging
import hashlib
import mimetypes
import os

import aiofiles
import networkx as nx
import radon.complexity as complexity
import radon.metrics as metrics
from radon.visitors import ComplexityVisitor
from bandit.core import manager as bandit_manager
from bandit.core import config as bandit_config
from pylint import lint
from pylint.reporters import JSONReporter
from mypy import api as mypy_api
import black
import isort
from flake8.api import legacy as flake8
import vulture

from ymera_core.exceptions import YMERAException
from ymera_core.logging.structured_logger import StructuredLogger
from ymera_core.cache.redis_cache import RedisCacheManager
from ymera_services.ai.multi_llm_manager import MultiLLMManager


class QualityMetricType(Enum):
    """Types of quality metrics"""
    COMPLEXITY = "complexity"
    MAINTAINABILITY = "maintainability"
    TESTABILITY = "testability"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    STYLE = "style"
    ARCHITECTURE = "architecture"


class SeverityLevel(Enum):
    """Issue severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class CodeMetrics:
    """Comprehensive code metrics"""
    # Complexity Metrics
    cyclomatic_complexity: float = 0.0
    cognitive_complexity: float = 0.0
    halstead_metrics: Dict[str, float] = field(default_factory=dict)
    
    # Size Metrics
    lines_of_code: int = 0
    source_lines_of_code: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    
    # Quality Metrics
    maintainability_index: float = 0.0
    test_coverage: float = 0.0
    documentation_coverage: float = 0.0
    
    # Architecture Metrics
    coupling_between_objects: float = 0.0
    depth_of_inheritance: int = 0
    number_of_children: int = 0
    lack_of_cohesion: float = 0.0
    
    # Performance Metrics
    estimated_execution_time: float = 0.0
    memory_complexity: str = "O(1)"
    
    # Security Metrics
    security_score: float = 100.0
    vulnerability_count: int = 0


@dataclass
class QualityIssue:
    """Quality issue representation"""
    id: str
    type: QualityMetricType
    severity: SeverityLevel
    title: str
    description: str
    file_path: str
    line_number: int
    column_number: int = 0
    rule_id: str = ""
    suggestion: str = ""
    confidence: float = 1.0
    estimated_fix_time: int = 0  # minutes
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Complete analysis result"""
    analysis_id: str
    timestamp: datetime
    file_path: str
    metrics: CodeMetrics
    issues: List[QualityIssue]
    suggestions: List[str]
    overall_score: float
    grade: str
    estimated_refactor_time: int  # minutes
    learning_insights: Dict[str, Any] = field(default_factory=dict)


class CodeQualityAnalyzer:
    """
    Enterprise-grade code quality analyzer with AI-powered insights and learning capabilities
    """
    
    def __init__(
        self,
        ai_manager: MultiLLMManager,
        cache_manager: RedisCacheManager,
        logger: Optional[StructuredLogger] = None
    ):
        self.ai_manager = ai_manager
        self.cache_manager = cache_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # Analysis configuration
        self.supported_languages = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.kt': 'kotlin',
            '.swift': 'swift'
        }
        
        self.quality_thresholds = {
            'complexity_warning': 10,
            'complexity_error': 20,
            'maintainability_warning': 50,
            'maintainability_error': 25,
            'coverage_warning': 80,
            'coverage_error': 60,
            'documentation_warning': 70,
            'documentation_error': 50
        }
        
        # Learning and adaptation
        self.pattern_cache = {}
        self.analysis_history = defaultdict(list)
        self.learning_feedback = {}
        
        # Analysis tools configuration
        self.tools_config = {
            'pylint': {'enabled': True, 'config_file': None},
            'flake8': {'enabled': True, 'max_line_length': 88},
            'mypy': {'enabled': True, 'strict': False},
            'bandit': {'enabled': True, 'severity': 'medium'},
            'black': {'enabled': True, 'line_length': 88},
            'isort': {'enabled': True, 'profile': 'black'},
            'vulture': {'enabled': True, 'min_confidence': 80}
        }
        
        self.initialized = False
    
    async def initialize(self) -> None:
        """Initialize the analyzer"""
        try:
            self.logger.info("Initializing CodeQualityAnalyzer...")
            
            # Load cached patterns and configurations
            await self._load_cached_patterns()
            await self._initialize_analysis_tools()
            await self._load_learning_data()
            
            self.initialized = True
            self.logger.info("CodeQualityAnalyzer initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize CodeQualityAnalyzer: {str(e)}")
            raise YMERAException(f"Analyzer initialization failed: {str(e)}")
    
    async def analyze_code(
        self,
        code: str,
        file_path: str,
        language: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """
        Perform comprehensive code quality analysis
        
        Args:
            code: Source code to analyze
            file_path: Path to the file being analyzed
            language: Programming language (auto-detected if None)
            context: Additional context for analysis
            
        Returns:
            AnalysisResult: Comprehensive analysis results
        """
        if not self.initialized:
            await self.initialize()
        
        analysis_id = hashlib.sha256(
            f"{file_path}{code}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
        self.logger.info(f"Starting code analysis for {file_path}", extra={
            "analysis_id": analysis_id,
            "file_path": file_path,
            "code_length": len(code)
        })
        
        try:
            # Check cache first
            cache_key = f"analysis:{hashlib.sha256(code.encode()).hexdigest()}"
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result:
                self.logger.info("Returning cached analysis result")
                return AnalysisResult(**json.loads(cached_result))
            
            # Detect language if not provided
            if not language:
                language = self._detect_language(file_path)
            
            # Initialize metrics and results
            metrics = CodeMetrics()
            issues = []
            suggestions = []
            
            # Run parallel analysis tasks
            analysis_tasks = await self._create_analysis_tasks(
                code, file_path, language, context
            )
            
            results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.warning(f"Analysis task {i} failed: {str(result)}")
                    continue
                
                if isinstance(result, tuple):
                    task_metrics, task_issues, task_suggestions = result
                    await self._merge_metrics(metrics, task_metrics)
                    issues.extend(task_issues)
                    suggestions.extend(task_suggestions)
            
            # Calculate overall scores and grades
            overall_score = await self._calculate_overall_score(metrics, issues)
            grade = self._calculate_grade(overall_score)
            estimated_time = self._estimate_refactor_time(issues)
            
            # Generate AI-powered insights
            learning_insights = await self._generate_learning_insights(
                code, metrics, issues, context
            )
            
            # Create final result
            analysis_result = AnalysisResult(
                analysis_id=analysis_id,
                timestamp=datetime.utcnow(),
                file_path=file_path,
                metrics=metrics,
                issues=sorted(issues, key=lambda x: (x.severity.value, x.line_number)),
                suggestions=suggestions,
                overall_score=overall_score,
                grade=grade,
                estimated_refactor_time=estimated_time,
                learning_insights=learning_insights
            )
            
            # Cache the result
            await self.cache_manager.set(
                cache_key, 
                json.dumps(analysis_result.__dict__, default=str),
                ttl=3600
            )
            
            # Update learning data
            await self._update_learning_data(analysis_result)
            
            self.logger.info(f"Analysis completed for {file_path}", extra={
                "analysis_id": analysis_id,
                "overall_score": overall_score,
                "grade": grade,
                "issues_count": len(issues)
            })
            
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"Code analysis failed: {str(e)}")
            raise YMERAException(f"Analysis failed: {str(e)}")
    
    async def analyze_project(
        self,
        project_path: str,
        include_patterns: List[str] = None,
        exclude_patterns: List[str] = None,
        max_files: int = 1000
    ) -> Dict[str, AnalysisResult]:
        """
        Analyze an entire project
        
        Args:
            project_path: Path to the project root
            include_patterns: File patterns to include
            exclude_patterns: File patterns to exclude
            max_files: Maximum number of files to analyze
            
        Returns:
            Dict[str, AnalysisResult]: Analysis results by file path
        """
        self.logger.info(f"Starting project analysis: {project_path}")
        
        try:
            # Find files to analyze
            files_to_analyze = await self._find_files_to_analyze(
                project_path, include_patterns, exclude_patterns, max_files
            )
            
            if not files_to_analyze:
                raise YMERAException("No analyzable files found in project")
            
            # Analyze files concurrently
            analysis_tasks = []
            for file_path in files_to_analyze:
                try:
                    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                        code = await f.read()
                    
                    task = self.analyze_code(code, file_path)
                    analysis_tasks.append(task)
                    
                except Exception as e:
                    self.logger.warning(f"Could not read file {file_path}: {str(e)}")
                    continue
            
            # Execute analysis with concurrency limit
            semaphore = asyncio.Semaphore(10)  # Limit concurrent analyses
            
            async def analyze_with_semaphore(task):
                async with semaphore:
                    return await task
            
            results = await asyncio.gather(
                *[analyze_with_semaphore(task) for task in analysis_tasks],
                return_exceptions=True
            )
            
            # Process results
            project_results = {}
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.warning(f"File analysis failed: {str(result)}")
                    continue
                
                if isinstance(result, AnalysisResult):
                    project_results[result.file_path] = result
            
            # Generate project-level insights
            await self._generate_project_insights(project_results)
            
            self.logger.info(f"Project analysis completed: {len(project_results)} files analyzed")
            return project_results
            
        except Exception as e:
            self.logger.error(f"Project analysis failed: {str(e)}")
            raise YMERAException(f"Project analysis failed: {str(e)}")
    
    async def get_improvement_suggestions(
        self,
        analysis_result: AnalysisResult,
        priority: str = "high"
    ) -> List[Dict[str, Any]]:
        """
        Generate AI-powered improvement suggestions
        
        Args:
            analysis_result: Analysis result to improve
            priority: Priority level for suggestions
            
        Returns:
            List of improvement suggestions
        """
        try:
            # Filter issues by priority
            priority_issues = [
                issue for issue in analysis_result.issues
                if issue.severity.value == priority or priority == "all"
            ]
            
            if not priority_issues:
                return []
            
            # Generate contextual suggestions using AI
            prompt = await self._create_improvement_prompt(
                analysis_result, priority_issues
            )
            
            ai_response = await self.ai_manager.generate_response(
                prompt=prompt,
                provider="gpt-4",
                temperature=0.3,
                max_tokens=2000
            )
            
            # Parse and structure suggestions
            suggestions = await self._parse_ai_suggestions(ai_response, priority_issues)
            
            # Add learning-based suggestions
            learning_suggestions = await self._get_learning_suggestions(analysis_result)
            suggestions.extend(learning_suggestions)
            
            return sorted(suggestions, key=lambda x: x.get("impact_score", 0), reverse=True)
            
        except Exception as e:
            self.logger.error(f"Failed to generate suggestions: {str(e)}")
            return []
    
    async def learn_from_feedback(
        self,
        analysis_id: str,
        feedback: Dict[str, Any]
    ) -> None:
        """
        Learn from user feedback on analysis results
        
        Args:
            analysis_id: ID of the analysis
            feedback: User feedback data
        """
        try:
            self.learning_feedback[analysis_id] = {
                "feedback": feedback,
                "timestamp": datetime.utcnow(),
                "processed": False
            }
            
            # Process feedback for immediate learning
            await self._process_feedback(analysis_id, feedback)
            
            # Update learning patterns
            await self._update_learning_patterns(feedback)
            
            self.logger.info(f"Feedback processed for analysis {analysis_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to process feedback: {str(e)}")
    
    # Private methods
    
    async def _create_analysis_tasks(
        self,
        code: str,
        file_path: str,
        language: str,
        context: Optional[Dict[str, Any]]
    ) -> List[asyncio.Task]:
        """Create parallel analysis tasks"""
        tasks = []
        
        if language == 'python':
            # Python-specific analysis tasks
            tasks.append(asyncio.create_task(
                self._analyze_python_complexity(code, file_path)
            ))
            tasks.append(asyncio.create_task(
                self._analyze_python_style(code, file_path)
            ))
            tasks.append(asyncio.create_task(
                self._analyze_python_security(code, file_path)
            ))
            tasks.append(asyncio.create_task(
                self._analyze_python_types(code, file_path)
            ))
            tasks.append(asyncio.create_task(
                self._analyze_python_dead_code(code, file_path)
            ))
        
        # Language-agnostic tasks
        tasks.append(asyncio.create_task(
            self._analyze_documentation(code, file_path, language)
        ))
        tasks.append(asyncio.create_task(
            self._analyze_architecture(code, file_path, language)
        ))
        tasks.append(asyncio.create_task(
            self._analyze_with_ai(code, file_path, language, context)
        ))
        
        return tasks
    
    async def _analyze_python_complexity(
        self,
        code: str,
        file_path: str
    ) -> Tuple[CodeMetrics, List[QualityIssue], List[str]]:
        """Analyze Python code complexity"""
        metrics = CodeMetrics()
        issues = []
        suggestions = []
        
        try:
            # Parse AST
            tree = ast.parse(code)
            
            # Calculate cyclomatic complexity
            complexity_visitor = ComplexityVisitor.from_ast(tree)
            
            total_complexity = 0
            for item in complexity_visitor.functions + complexity_visitor.methods:
                complexity_score = item.complexity
                total_complexity += complexity_score
                
                if complexity_score > self.quality_thresholds['complexity_error']:
                    issues.append(QualityIssue(
                        id=f"complexity_{item.name}_{item.lineno}",
                        type=QualityMetricType.COMPLEXITY,
                        severity=SeverityLevel.HIGH,
                        title=f"High cyclomatic complexity in {item.name}",
                        description=f"Function {item.name} has cyclomatic complexity of {complexity_score}",
                        file_path=file_path,
                        line_number=item.lineno,
                        rule_id="C901",
                        suggestion="Consider breaking this function into smaller functions",
                        estimated_fix_time=complexity_score * 5
                    ))
                elif complexity_score > self.quality_thresholds['complexity_warning']:
                    issues.append(QualityIssue(
                        id=f"complexity_{item.name}_{item.lineno}",
                        type=QualityMetricType.COMPLEXITY,
                        severity=SeverityLevel.MEDIUM,
                        title=f"Moderate cyclomatic complexity in {item.name}",
                        description=f"Function {item.name} has cyclomatic complexity of {complexity_score}",
                        file_path=file_path,
                        line_number=item.lineno,
                        rule_id="C901",
                        suggestion="Consider simplifying this function",
                        estimated_fix_time=complexity_score * 3
                    ))
            
            metrics.cyclomatic_complexity = total_complexity / max(
                len(complexity_visitor.functions + complexity_visitor.methods), 1
            )
            
            # Calculate Halstead metrics
            halstead = metrics.report_halstead(code)
            if halstead:
                metrics.halstead_metrics = {
                    'difficulty': halstead[0],
                    'effort': halstead[1],
                    'bugs': halstead[2],
                    'time': halstead[3]
                }
            
            # Calculate maintainability index
            mi_result = metrics.mi_visit(code, multi=False)
            if mi_result:
                metrics.maintainability_index = mi_result
                
                if mi_result < self.quality_thresholds['maintainability_error']:
                    issues.append(QualityIssue(
                        id="maintainability_low",
                        type=QualityMetricType.MAINTAINABILITY,
                        severity=SeverityLevel.HIGH,
                        title="Low maintainability index",
                        description=f"Code maintainability index is {mi_result:.2f}",
                        file_path=file_path,
                        line_number=1,
                        suggestion="Refactor code to improve maintainability",
                        estimated_fix_time=60
                    ))
            
        except Exception as e:
            self.logger.warning(f"Complexity analysis failed: {str(e)}")
        
        return metrics, issues, suggestions
    
    async def _analyze_python_style(
        self,
        code: str,
        file_path: str
    ) -> Tuple[CodeMetrics, List[QualityIssue], List[str]]:
        """Analyze Python code style"""
        metrics = CodeMetrics()
        issues = []
        suggestions = []
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name
            
            try:
                # Run Flake8
                style_guide = flake8.get_style_guide(
                    max_line_length=self.tools_config['flake8']['max_line_length']
                )
                report = style_guide.check_files([temp_path])
                
                for error in report.get_statistics('E'):
                    error_parts = error.split(':')
                    if len(error_parts) >= 4:
                        line_no = int(error_parts[1])
                        col_no = int(error_parts[2])
                        error_code = error_parts[3].strip().split()[0]
                        message = ':'.join(error_parts[3:]).strip()
                        
                        severity = SeverityLevel.LOW
                        if error_code.startswith('E9') or error_code.startswith('F'):
                            severity = SeverityLevel.HIGH
                        elif error_code.startswith('E7') or error_code.startswith('E5'):
                            severity = SeverityLevel.MEDIUM
                        
                        issues.append(QualityIssue(
                            id=f"style_{error_code}_{line_no}_{col_no}",
                            type=QualityMetricType.STYLE,
                            severity=severity,
                            title=f"Style issue: {error_code}",
                            description=message,
                            file_path=file_path,
                            line_number=line_no,
                            column_number=col_no,
                            rule_id=error_code,
                            estimated_fix_time=2
                        ))
                
                # Check Black formatting
                try:
                    formatted_code = black.format_str(code, mode=black.FileMode(
                        line_length=self.tools_config['black']['line_length']
                    ))
                    
                    if formatted_code != code:
                        suggestions.append("Code can be auto-formatted with Black")
                        issues.append(QualityIssue(
                            id="formatting_black",
                            type=QualityMetricType.STYLE,
                            severity=SeverityLevel.LOW,
                            title="Code formatting issues",
                            description="Code doesn't follow Black formatting standards",
                            file_path=file_path,
                            line_number=1,
                            suggestion="Run Black formatter to fix formatting issues",
                            estimated_fix_time=1
                        ))
                
                except Exception:
                    pass
                
                # Check import sorting
                try:
                    sorted_code = isort.code(code, profile=self.tools_config['isort']['profile'])
                    if sorted_code != code:
                        suggestions.append("Imports can be sorted with isort")
                        issues.append(QualityIssue(
                            id="imports_sorting",
                            type=QualityMetricType.STYLE,
                            severity=SeverityLevel.LOW,
                            title="Import sorting issues",
                            description="Imports are not properly sorted",
                            file_path=file_path,
                            line_number=1,
                            suggestion="Run isort to fix import ordering",
                            estimated_fix_time=1
                        ))
                
                except Exception:
                    pass
            
            finally:
                os.unlink(temp_path)
        
        except Exception as e:
            self.logger.warning(f"Style analysis failed: {str(e)}")
        
        return metrics, issues, suggestions
    
    async def _analyze_python_security(
        self,
        code: str,
        file_path: str
    ) -> Tuple[CodeMetrics, List[QualityIssue], List[str]]:
        """Analyze Python code security"""
        metrics = CodeMetrics()
        issues = []
        suggestions = []
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name
            
            try:
                # Run Bandit security analysis
                config = bandit_config.BanditConfig()
                manager = bandit_manager.BanditManager(config, 'file')
                manager.discover_files([temp_path])
                manager.run_tests()
                
                for issue in manager.get_issue_list():
                    severity_map = {
                        'HIGH': SeverityLevel.CRITICAL,
                        'MEDIUM': SeverityLevel.HIGH,
                        'LOW': SeverityLevel.MEDIUM
                    }
                    
                    confidence_map = {
                        'HIGH': 0.9,
                        'MEDIUM': 0.7,
                        'LOW': 0.5
                    }
                    
                    issues.append(QualityIssue(
                        id=f"security_{issue.test_id}_{issue.lineno}",
                        type=QualityMetricType.SECURITY,
                        severity=severity_map.get(issue.severity, SeverityLevel.MEDIUM),
                        title=f"Security issue: {issue.test_id}",
                        description=issue.text,
                        file_path=file_path,
                        line_number=issue.lineno,
                        rule_id=issue.test_id,
                        confidence=confidence_map.get(issue.confidence, 0.5),
                        estimated_fix_time=15,
                        tags=['security', 'vulnerability']
                    ))
                
                # Calculate security score
                critical_issues = sum(1 for issue in issues if issue.severity == SeverityLevel.CRITICAL)
                high_issues = sum(1 for issue in issues if issue.severity == SeverityLevel.HIGH)
                medium_issues = sum(1 for issue in issues if issue.severity == SeverityLevel.MEDIUM)
                
                metrics.security_score = max(0, 100 - (critical_issues * 20 + high_issues * 10 + medium_issues * 5))
                metrics.vulnerability_count = len(issues)
            
            finally:
                os.unlink(temp_path)
        
        except Exception as e:
            self.logger.warning(f"Security analysis failed: {str(e)}")
        
        return metrics, issues, suggestions
    
    async def _analyze_python_types(
        self,
        code: str,
        file_path: str
    ) -> Tuple[CodeMetrics, List[QualityIssue], List[str]]:
        """Analyze Python type annotations"""
        metrics = CodeMetrics()
        issues = []
        suggestions = []
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name
            
            try:
                # Run MyPy type checking
                result = mypy_api.run([temp_path, '--show-error-codes', '--json-report', '/tmp/mypy_report'])
                
                if result[2] != 0:  # MyPy found issues
                    error_lines = result[0].split('\n')
                    for line in error_lines:
                        if ':' in line and 'error:' in line:
                            parts = line.split(':')
                            if len(parts) >= 4:
                                try:
                                    line_no = int(parts[1])
                                    message = ':'.join(parts[3:]).strip()
                                    
                                    issues.append(QualityIssue(
                                        id=f"type_{hashlib.sha256(line.encode()).hexdigest()[:8]}",
                                        type=QualityMetricType.TESTABILITY,
                                        severity=SeverityLevel.MEDIUM,
                                        title="Type annotation issue",
                                        description=message,
                                        file_path=file_path,
                                        line_number=line_no,
                                        rule_id="mypy",
                                        suggestion="Add or fix type annotations",
                                        estimated_fix_time=5
                                    ))
                                except ValueError:
                                    continue
                
                # Check type annotation coverage
                tree = ast.parse(code)
                total_functions = 0
                annotated_functions = 0
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        total_functions += 1
                        if (node.returns or 
                            any(arg.annotation for arg in node.args.args) or
                            any(arg.annotation for arg in node.args.kwonlyargs)):
                            annotated_functions += 1
                
                if total_functions > 0:
                    annotation_coverage = (annotated_functions / total_functions) * 100
                    if annotation_coverage < 50:
                        suggestions.append("Consider adding more type annotations")
            
            finally:
                os.unlink(temp_path)
        
        except Exception as e:
            self.logger.warning(f"Type analysis failed: {str(e)}")
        
        return metrics, issues, suggestions
    
    async def _analyze_python_dead_code(
        self,
        code: str,
        file_path: str
    ) -> Tuple[CodeMetrics, List[QualityIssue], List[str]]:
        """Analyze Python dead code"""
        metrics = CodeMetrics()
        issues = []
        suggestions = []
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name
            
            try:
                # Run Vulture for dead code detection
                vulture_instance = vulture.Vulture(verbose=False)
                vulture_instance.scavenge([temp_path])
                
                for item in vulture_instance.get_unused_code():
                    if item.confidence >= self.tools_config['vulture']['min_confidence']:
                        issues.append(QualityIssue(
                            id=f"dead_code_{item.first_lineno}",
                            type=QualityMetricType.MAINTAINABILITY,
                            severity=SeverityLevel.LOW,
                            title=f"Unused {item.typ}: {item.name}",
                            description=f"Unused {item.typ} '{item.name}' detected",
                            file_path=file_path,
                            line_number=item.first_lineno,
                            rule_id="vulture",
                            confidence=item.confidence / 100.0,
                            suggestion=f"Consider removing unused {item.typ}",
                            estimated_fix_time=2
                        ))
            
            finally:
                os.unlink(temp_path)
        
        except Exception as e:
            self.logger.warning(f"Dead code analysis failed: {str(e)}")
        
        return metrics, issues, suggestions
    
    async def _analyze_documentation(
        self,
        code: str,
        file_path: str,
        language: str
    ) -> Tuple[CodeMetrics, List[QualityIssue], List[str]]:
        """Analyze code documentation"""
        metrics = CodeMetrics()
        issues = []
        suggestions = []
        
        try:
            if language == 'python':
                tree = ast.parse(code)
                
                total_functions = 0
                documented_functions = 0
                total_classes = 0
                documented_classes = 0
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        total_functions += 1
                        if (ast.get_docstring(node) or 
                            (len(node.body) > 0 and isinstance(node.body[0], ast.Expr) and 
                             isinstance(node.body[0].value, ast.Constant) and 
                             isinstance(node.body[0].value.value, str))):
                            documented_functions += 1
                        else:
                            # Skip private methods and test methods for documentation requirements
                            if not node.name.startswith('_') and not node.name.startswith('test_'):
                                issues.append(QualityIssue(
                                    id=f"doc_missing_func_{node.name}_{node.lineno}",
                                    type=QualityMetricType.DOCUMENTATION,
                                    severity=SeverityLevel.LOW,
                                    title=f"Missing docstring for function {node.name}",
                                    description=f"Function '{node.name}' lacks documentation",
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    suggestion="Add docstring to describe function purpose and parameters",
                                    estimated_fix_time=5
                                ))
                    
                    elif isinstance(node, ast.ClassDef):
                        total_classes += 1
                        if ast.get_docstring(node):
                            documented_classes += 1
                        else:
                            if not node.name.startswith('_'):
                                issues.append(QualityIssue(
                                    id=f"doc_missing_class_{node.name}_{node.lineno}",
                                    type=QualityMetricType.DOCUMENTATION,
                                    severity=SeverityLevel.MEDIUM,
                                    title=f"Missing docstring for class {node.name}",
                                    description=f"Class '{node.name}' lacks documentation",
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    suggestion="Add class docstring to describe purpose and usage",
                                    estimated_fix_time=10
                                ))
                
                # Calculate documentation coverage
                total_items = total_functions + total_classes
                documented_items = documented_functions + documented_classes
                
                if total_items > 0:
                    doc_coverage = (documented_items / total_items) * 100
                    metrics.documentation_coverage = doc_coverage
                    
                    if doc_coverage < self.quality_thresholds['documentation_error']:
                        issues.append(QualityIssue(
                            id="doc_coverage_low",
                            type=QualityMetricType.DOCUMENTATION,
                            severity=SeverityLevel.HIGH,
                            title="Low documentation coverage",
                            description=f"Documentation coverage is {doc_coverage:.1f}%",
                            file_path=file_path,
                            line_number=1,
                            suggestion="Improve documentation coverage by adding docstrings",
                            estimated_fix_time=total_items * 3
                        ))
                    elif doc_coverage < self.quality_thresholds['documentation_warning']:
                        issues.append(QualityIssue(
                            id="doc_coverage_medium",
                            type=QualityMetricType.DOCUMENTATION,
                            severity=SeverityLevel.MEDIUM,
                            title="Moderate documentation coverage",
                            description=f"Documentation coverage is {doc_coverage:.1f}%",
                            file_path=file_path,
                            line_number=1,
                            suggestion="Consider improving documentation coverage",
                            estimated_fix_time=total_items * 2
                        ))
            
            # Check for TODO/FIXME comments
            lines = code.split('\n')
            for i, line in enumerate(lines, 1):
                line_lower = line.lower()
                if 'todo' in line_lower or 'fixme' in line_lower or 'hack' in line_lower:
                    issues.append(QualityIssue(
                        id=f"todo_comment_{i}",
                        type=QualityMetricType.MAINTAINABILITY,
                        severity=SeverityLevel.INFO,
                        title="TODO/FIXME comment found",
                        description=f"Comment indicates incomplete work: {line.strip()}",
                        file_path=file_path,
                        line_number=i,
                        suggestion="Address the TODO/FIXME or create a proper issue",
                        estimated_fix_time=15
                    ))
        
        except Exception as e:
            self.logger.warning(f"Documentation analysis failed: {str(e)}")
        
        return metrics, issues, suggestions
    
    async def _analyze_architecture(
        self,
        code: str,
        file_path: str,
        language: str
    ) -> Tuple[CodeMetrics, List[QualityIssue], List[str]]:
        """Analyze code architecture and design patterns"""
        metrics = CodeMetrics()
        issues = []
        suggestions = []
        
        try:
            if language == 'python':
                tree = ast.parse(code)
                
                # Analyze class relationships
                classes = {}
                imports = set()
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        base_classes = [base.id if isinstance(base, ast.Name) else str(base) 
                                      for base in node.bases]
                        classes[node.name] = {
                            'bases': base_classes,
                            'methods': [],
                            'line_number': node.lineno
                        }
                        
                        # Count methods
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                classes[node.name]['methods'].append(item.name)
                    
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.add(alias.name)
                        else:
                            module = node.module or ''
                            for alias in node.names:
                                imports.add(f"{module}.{alias.name}")
                
                # Calculate inheritance depth
                def calculate_depth(class_name, visited=None):
                    if visited is None:
                        visited = set()
                    if class_name in visited or class_name not in classes:
                        return 0
                    visited.add(class_name)
                    max_depth = 0
                    for base in classes[class_name]['bases']:
                        if base in classes:
                            depth = calculate_depth(base, visited.copy())
                            max_depth = max(max_depth, depth)
                    return max_depth + 1
                
                max_inheritance_depth = 0
                for class_name in classes:
                    depth = calculate_depth(class_name)
                    max_inheritance_depth = max(max_inheritance_depth, depth)
                    
                    if depth > 5:  # Deep inheritance hierarchy
                        issues.append(QualityIssue(
                            id=f"deep_inheritance_{class_name}",
                            type=QualityMetricType.ARCHITECTURE,
                            severity=SeverityLevel.MEDIUM,
                            title=f"Deep inheritance hierarchy in {class_name}",
                            description=f"Class {class_name} has inheritance depth of {depth}",
                            file_path=file_path,
                            line_number=classes[class_name]['line_number'],
                            suggestion="Consider using composition over inheritance",
                            estimated_fix_time=30
                        ))
                
                metrics.depth_of_inheritance = max_inheritance_depth
                
                # Analyze method counts (God class detection)
                for class_name, class_info in classes.items():
                    method_count = len(class_info['methods'])
                    if method_count > 20:  # God class threshold
                        issues.append(QualityIssue(
                            id=f"god_class_{class_name}",
                            type=QualityMetricType.ARCHITECTURE,
                            severity=SeverityLevel.HIGH,
                            title=f"God class detected: {class_name}",
                            description=f"Class {class_name} has {method_count} methods",
                            file_path=file_path,
                            line_number=class_info['line_number'],
                            suggestion="Consider breaking this class into smaller, focused classes",
                            estimated_fix_time=method_count * 5
                        ))
                
                # Analyze coupling (import analysis)
                coupling_score = len(imports) / max(len(classes), 1)
                metrics.coupling_between_objects = coupling_score
                
                if coupling_score > 10:  # High coupling
                    issues.append(QualityIssue(
                        id="high_coupling",
                        type=QualityMetricType.ARCHITECTURE,
                        severity=SeverityLevel.MEDIUM,
                        title="High coupling detected",
                        description=f"File has {len(imports)} imports, indicating high coupling",
                        file_path=file_path,
                        line_number=1,
                        suggestion="Consider reducing dependencies and improving modularity",
                        estimated_fix_time=45
                    ))
                
                # Check for long parameter lists
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        param_count = len(node.args.args) + len(node.args.kwonlyargs)
                        if param_count > 7:  # Long parameter list
                            issues.append(QualityIssue(
                                id=f"long_params_{node.name}_{node.lineno}",
                                type=QualityMetricType.ARCHITECTURE,
                                severity=SeverityLevel.MEDIUM,
                                title=f"Long parameter list in {node.name}",
                                description=f"Function {node.name} has {param_count} parameters",
                                file_path=file_path,
                                line_number=node.lineno,
                                suggestion="Consider using a parameter object or splitting the function",
                                estimated_fix_time=20
                            ))
        
        except Exception as e:
            self.logger.warning(f"Architecture analysis failed: {str(e)}")
        
        return metrics, issues, suggestions
    
    async def _analyze_with_ai(
        self,
        code: str,
        file_path: str,
        language: str,
        context: Optional[Dict[str, Any]]
    ) -> Tuple[CodeMetrics, List[QualityIssue], List[str]]:
        """Perform AI-powered code analysis"""
        metrics = CodeMetrics()
        issues = []
        suggestions = []
        
        try:
            # Create AI analysis prompt
            prompt = f"""
            Analyze the following {language} code for quality issues, performance problems, 
            and improvement opportunities. Focus on:
            1. Logic errors and edge cases
            2. Performance bottlenecks
            3. Best practices violations
            4. Code smells
            5. Design pattern improvements
            
            Code to analyze:
            ```{language}
            {code[:4000]}  # Limit code size for AI analysis
            ```
            
            File: {file_path}
            Context: {json.dumps(context) if context else 'None'}
            
            Provide analysis in JSON format with the following structure:
            {{
                "performance_issues": [
                    {{
                        "type": "performance",
                        "severity": "high|medium|low",
                        "description": "Issue description",
                        "line_number": 0,
                        "suggestion": "How to fix"
                    }}
                ],
                "logic_issues": [...],
                "best_practices": [...],
                "suggestions": ["General improvement suggestion 1", ...]
            }}
            """
            
            try:
                ai_response = await self.ai_manager.generate_response(
                    prompt=prompt,
                    provider="gpt-4",
                    temperature=0.1,
                    max_tokens=1500
                )
                
                # Parse AI response
                ai_analysis = json.loads(ai_response)
                
                # Process performance issues
                for issue in ai_analysis.get('performance_issues', []):
                    issues.append(QualityIssue(
                        id=f"ai_perf_{issue.get('line_number', 1)}",
                        type=QualityMetricType.PERFORMANCE,
                        severity=self._parse_severity(issue.get('severity', 'medium')),
                        title="AI-detected performance issue",
                        description=issue.get('description', ''),
                        file_path=file_path,
                        line_number=issue.get('line_number', 1),
                        suggestion=issue.get('suggestion', ''),
                        confidence=0.7,
                        estimated_fix_time=20
                    ))
                
                # Process logic issues
                for issue in ai_analysis.get('logic_issues', []):
                    issues.append(QualityIssue(
                        id=f"ai_logic_{issue.get('line_number', 1)}",
                        type=QualityMetricType.MAINTAINABILITY,
                        severity=self._parse_severity(issue.get('severity', 'high')),
                        title="AI-detected logic issue",
                        description=issue.get('description', ''),
                        file_path=file_path,
                        line_number=issue.get('line_number', 1),
                        suggestion=issue.get('suggestion', ''),
                        confidence=0.8,
                        estimated_fix_time=30
                    ))
                
                # Process best practices
                for issue in ai_analysis.get('best_practices', []):
                    issues.append(QualityIssue(
                        id=f"ai_bp_{issue.get('line_number', 1)}",
                        type=QualityMetricType.STYLE,
                        severity=self._parse_severity(issue.get('severity', 'low')),
                        title="Best practices violation",
                        description=issue.get('description', ''),
                        file_path=file_path,
                        line_number=issue.get('line_number', 1),
                        suggestion=issue.get('suggestion', ''),
                        confidence=0.6,
                        estimated_fix_time=10
                    ))
                
                # Add general suggestions
                suggestions.extend(ai_analysis.get('suggestions', []))
                
            except (json.JSONDecodeError, KeyError) as e:
                self.logger.warning(f"Failed to parse AI analysis response: {str(e)}")
                
                # Fallback: extract insights from raw response
                if "performance" in ai_response.lower():
                    suggestions.append("AI detected potential performance improvements")
                if "refactor" in ai_response.lower():
                    suggestions.append("AI suggests code refactoring opportunities")
            
        except Exception as e:
            self.logger.warning(f"AI analysis failed: {str(e)}")
        
        return metrics, issues, suggestions
    
    async def _merge_metrics(self, base_metrics: CodeMetrics, new_metrics: CodeMetrics) -> None:
        """Merge metrics from different analysis tasks"""
        # Combine numerical metrics (take max or sum as appropriate)
        base_metrics.cyclomatic_complexity = max(
            base_metrics.cyclomatic_complexity, 
            new_metrics.cyclomatic_complexity
        )
        base_metrics.cognitive_complexity = max(
            base_metrics.cognitive_complexity, 
            new_metrics.cognitive_complexity
        )
        base_metrics.maintainability_index = min(
            base_metrics.maintainability_index or 100, 
            new_metrics.maintainability_index or 100
        )
        base_metrics.security_score = min(
            base_metrics.security_score, 
            new_metrics.security_score
        )
        base_metrics.documentation_coverage = max(
            base_metrics.documentation_coverage, 
            new_metrics.documentation_coverage
        )
        base_metrics.depth_of_inheritance = max(
            base_metrics.depth_of_inheritance, 
            new_metrics.depth_of_inheritance
        )
        base_metrics.coupling_between_objects = max(
            base_metrics.coupling_between_objects, 
            new_metrics.coupling_between_objects
        )
        base_metrics.vulnerability_count += new_metrics.vulnerability_count
        
        # Merge complex metrics
        if new_metrics.halstead_metrics:
            base_metrics.halstead_metrics.update(new_metrics.halstead_metrics)
    
    async def _calculate_overall_score(
        self,
        metrics: CodeMetrics,
        issues: List[QualityIssue]
    ) -> float:
        """Calculate overall quality score"""
        try:
            # Base score starts at 100
            score = 100.0
            
            # Deduct points for issues by severity
            for issue in issues:
                if issue.severity == SeverityLevel.CRITICAL:
                    score -= 20
                elif issue.severity == SeverityLevel.HIGH:
                    score -= 10
                elif issue.severity == SeverityLevel.MEDIUM:
                    score -= 5
                elif issue.severity == SeverityLevel.LOW:
                    score -= 2
                else:  # INFO
                    score -= 0.5
            
            # Factor in metrics
            if metrics.maintainability_index > 0:
                score = (score + metrics.maintainability_index) / 2
            
            if metrics.security_score < 100:
                score = (score + metrics.security_score) / 2
            
            if metrics.documentation_coverage > 0:
                doc_factor = metrics.documentation_coverage / 100
                score = score * (0.7 + 0.3 * doc_factor)
            
            # Complexity penalty
            if metrics.cyclomatic_complexity > 10:
                complexity_penalty = min(20, (metrics.cyclomatic_complexity - 10) * 2)
                score -= complexity_penalty
            
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            self.logger.warning(f"Score calculation failed: {str(e)}")
            return 50.0  # Default middle score
    
    def _calculate_grade(self, score: float) -> str:
        """Calculate letter grade from score"""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
    
    def _estimate_refactor_time(self, issues: List[QualityIssue]) -> int:
        """Estimate total refactoring time in minutes"""
        return sum(issue.estimated_fix_time for issue in issues)
    
    async def _generate_learning_insights(
        self,
        code: str,
        metrics: CodeMetrics,
        issues: List[QualityIssue],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate learning insights from analysis"""
        insights = {}
        
        try:
            # Pattern recognition
            patterns = await self._identify_patterns(code, issues)
            insights['patterns'] = patterns
            
            # Trend analysis
            trends = await self._analyze_trends(metrics, issues)
            insights['trends'] = trends
            
            # Personalized recommendations
            recommendations = await self._generate_recommendations(code, issues, context)
            insights['recommendations'] = recommendations
            
            # Learning opportunities
            learning_ops = await self._identify_learning_opportunities(issues)
            insights['learning_opportunities'] = learning_ops
            
        except Exception as e:
            self.logger.warning(f"Learning insights generation failed: {str(e)}")
        
        return insights
    
    async def _identify_patterns(
        self,
        code: str,
        issues: List[QualityIssue]
    ) -> List[Dict[str, Any]]:
        """Identify recurring patterns in code and issues"""
        patterns = []
        
        try:
            # Group issues by type and rule
            issue_groups = defaultdict(list)
            for issue in issues:
                key = f"{issue.type.value}:{issue.rule_id}"
                issue_groups[key].append(issue)
            
            # Identify frequent issue patterns
            for key, group in issue_groups.items():
                if len(group) > 2:  # Pattern threshold
                    patterns.append({
                        'type': 'recurring_issue',
                        'pattern': key,
                        'frequency': len(group),
                        'description': f"Recurring {group[0].type.value} issues",
                        'suggestion': f"Focus on addressing {key} patterns"
                    })
            
            # Code structure patterns
            if 'class' in code.lower() and 'def ' in code:
                patterns.append({
                    'type': 'architecture',
                    'pattern': 'object_oriented',
                    'description': 'Object-oriented code structure detected'
                })
            
            if 'async def' in code or 'await ' in code:
                patterns.append({
                    'type': 'architecture',
                    'pattern': 'asynchronous',
                    'description': 'Asynchronous programming patterns detected'
                })
            
        except Exception as e:
            self.logger.warning(f"Pattern identification failed: {str(e)}")
        
        return patterns
    
    async def _analyze_trends(
        self,
        metrics: CodeMetrics,
        issues: List[QualityIssue]
    ) -> Dict[str, Any]:
        """Analyze trends in code quality"""
        trends = {}
        
        try:
            # Issue severity distribution
            severity_counts = defaultdict(int)
            for issue in issues:
                severity_counts[issue.severity.value] += 1
            
            trends['severity_distribution'] = dict(severity_counts)
            
            # Quality focus areas
            issue_types = defaultdict(int)
            for issue in issues:
                issue_types[issue.type.value] += 1
            
            if issue_types:
                primary_concern = max(issue_types.items(), key=lambda x: x[1])
                trends['primary_concern'] = primary_concern[0]
                trends['concern_count'] = primary_concern[1]
            
            # Quality indicators
            trends['quality_indicators'] = {
                'complexity': 'high' if metrics.cyclomatic_complexity > 15 else 'acceptable',
                'maintainability': 'good' if metrics.maintainability_index > 70 else 'needs_improvement',
                'security': 'good' if metrics.security_score > 80 else 'needs_attention',
                'documentation': 'good' if metrics.documentation_coverage > 70 else 'insufficient'
            }
            
        except Exception as e:
            self.logger.warning(f"Trend analysis failed: {str(e)}")
        
        return trends
    
    async def _generate_recommendations(
        self,
        code: str,
        issues: List[QualityIssue],
        context: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Generate personalized recommendations"""
        recommendations = []
        
        try:
            # Issue-based recommendations
            high_severity_issues = [i for i in issues if i.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]]
            if high_severity_issues:
                recommendations.append(f"Priority: Address {len(high_severity_issues)} high-severity issues")
            
            # Pattern-based recommendations
            security_issues = [i for i in issues if i.type == QualityMetricType.SECURITY]
            if security_issues:
                recommendations.append("Implement security best practices review process")
            
            complexity_issues = [i for i in issues if i.type == QualityMetricType.COMPLEXITY]
            if len(complexity_issues) > 3:
                recommendations.append("Consider refactoring for improved maintainability")
            
            # Context-based recommendations
            if context:
                if context.get('team_size', 1) > 1:
                    recommendations.append("Establish code review guidelines for team collaboration")
                
                if context.get('project_type') == 'production':
                    recommendations.append("Implement automated quality gates in CI/CD pipeline")
            
        except Exception as e:
            self.logger.warning(f"Recommendations generation failed: {str(e)}")
        
        return recommendations
    
    async def _identify_learning_opportunities(
        self,
        issues: List[QualityIssue]
    ) -> List[Dict[str, Any]]:
        """Identify learning opportunities based on issues"""
        opportunities = []
        
        try:
            # Group by issue type for learning topics
            issue_types = defaultdict(int)
            for issue in issues:
                issue_types[issue.type] += 1
            
            for issue_type, count in issue_types.items():
                if count > 1:  # Learning opportunity threshold
                    opportunities.append({
                        'topic': issue_type.value,
                        'count': count,
                        'priority': 'high' if count > 5 else 'medium',
                        'resources': self._get_learning_resources(issue_type)
                    })
        
        except Exception as e:
            self.logger.warning(f"Learning opportunities identification failed: {str(e)}")
        
        return opportunities
    
    def _get_learning_resources(self, issue_type: QualityMetricType) -> List[str]:
        """Get learning resources for specific issue types"""
        resources = {
            QualityMetricType.COMPLEXITY: [
                "Refactoring: Improving the Design of Existing Code",
                "Clean Code: A Handbook of Agile Software Craftsmanship"
            ],
            QualityMetricType.SECURITY: [
                "OWASP Security Guidelines",
                "Secure Coding Practices"
            ],
            QualityMetricType.PERFORMANCE: [
                "Performance Optimization Patterns",
                "Algorithmic Complexity Analysis"
            ],
            QualityMetricType.DOCUMENTATION: [
                "Writing Effective Documentation",
                "API Documentation Best Practices"
            ],
            QualityMetricType.STYLE: [
                "PEP 8 Style Guide",
                "Code Style Consistency Tools"
            ]
        }
        return resources.get(issue_type, ["General Software Quality Resources"])
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension"""
        extension = Path(file_path).suffix.lower()
        return self.supported_languages.get(extension, 'unknown')
    
    def _parse_severity(self, severity_str: str) -> SeverityLevel:
        """Parse severity string to enum"""
        severity_map = {
            'critical': SeverityLevel.CRITICAL,
            'high': SeverityLevel.HIGH,
            'medium': SeverityLevel.MEDIUM,
            'low': SeverityLevel.LOW,
            'info': SeverityLevel.INFO
        }
        return severity_map.get(severity_str.lower(), SeverityLevel.MEDIUM)
    
    async def _find_files_to_analyze(
        self,
        project_path: str,
        include_patterns: List[str] = None,
        exclude_patterns: List[str] = None,
        max_files: int = 1000
    ) -> List[str]:
        """Find files to analyze in project"""
        files = []
        
        # Default patterns
        if include_patterns is None:
            include_patterns = ['*.py', '*.js', '*.ts', '*.java', '*.go', '*.rs']
        
        if exclude_patterns is None:
            exclude_patterns = [
                '*/venv/*', '*/node_modules/*', '*/build/*', '*/dist/*',
                '*/__pycache__/*', '*.pyc', '*/.git/*', '*/test/*', '*/tests/*'
            ]
        
        try:
            project_root = Path(project_path)
            
            for pattern in include_patterns:
                for file_path in project_root.rglob(pattern):
                    if file_path.is_file() and len(files) < max_files:
                        # Check exclude patterns
                        exclude = False
                        for exclude_pattern in exclude_patterns:
                            if file_path.match(exclude_pattern):
                                exclude = True
                                break
                        
                        if not exclude:
                            files.append(str(file_path))
        
        except Exception as e:
            self.logger.warning(f"File discovery failed: {str(e)}")
        
        return files
    
    async def _generate_project_insights(
        self,
        project_results: Dict[str, AnalysisResult]
    ) -> Dict[str, Any]:
        """Generate project-level insights"""
        insights = {}
        
        try:
            if not project_results:
                return insights
            
            # Aggregate metrics
            total_issues = sum(len(result.issues) for result in project_results.values())
            average_score = sum(result.overall_score for result in project_results.values()) / len(project_results)
            total_refactor_time = sum(result.estimated_refactor_time for result in project_results.values())
            
            insights['summary'] = {
                'files_analyzed': len(project_results),
                'total_issues': total_issues,
                'average_score': round(average_score, 1),
                'total_refactor_time_hours': round(total_refactor_time / 60, 1),
                'overall_grade': self._calculate_grade(average_score)
            }
            
            # Top issues across project
            all_issues = []
            for result in project_results.values():
                all_issues.extend(result.issues)
            
            # Sort by severity and frequency
            severity_order = {
                SeverityLevel.CRITICAL: 5,
                SeverityLevel.HIGH: 4,
                SeverityLevel.MEDIUM: 3,
                SeverityLevel.LOW: 2,
                SeverityLevel.INFO: 1
            }
            
            sorted_issues = sorted(all_issues, 
                                 key=lambda x: (severity_order.get(x.severity, 0), x.confidence), 
                                 reverse=True)
            
            insights['top_issues'] = [
                {
                    'title': issue.title,
                    'severity': issue.severity.value,
                    'file': issue.file_path,
                    'type': issue.type.value
                }
                for issue in sorted_issues[:10]  # Top 10 issues
            ]
            
            # Quality trends
            issue_types = defaultdict(int)
            for issue in all_issues:
                issue_types[issue.type.value] += 1
            
            insights['issue_distribution'] = dict(issue_types)
            
            # Files needing attention
            file_scores = {path: result.overall_score for path, result in project_results.items()}
            worst_files = sorted(file_scores.items(), key=lambda x: x[1])[:5]
            
            insights['files_needing_attention'] = [
                {'file': path, 'score': score} 
                for path, score in worst_files
            ]
            
        except Exception as e:
            self.logger.warning(f"Project insights generation failed: {str(e)}")
        
        return insights

    async def _initialize_ai_services(self) -> None:
        """Initialize AI services with multiple providers"""
        try:
            # Initialize Multi-LLM Manager with all available providers
            ai_config = {
                'providers': {
                    'openai': {
                        'api_key': os.getenv('OPENAI_API_KEY'),
                        'model': 'gpt-4',
                        'enabled': bool(os.getenv('OPENAI_API_KEY'))
                    },
                    'claude': {
                        'api_key': os.getenv('ANTHROPIC_API_KEY'),
                        'model': 'claude-3-sonnet-20240229',
                        'enabled': bool(os.getenv('ANTHROPIC_API_KEY'))
                    },
                    'gemini': {
                        'api_key': os.getenv('GEMINI_API_KEY'),
                        'model': 'gemini-pro',
                        'enabled': bool(os.getenv('GEMINI_API_KEY'))
                    },
                    'deepseek': {
                        'api_key': os.getenv('DEEPSEEK_API_KEY'),
                        'base_url': 'https://api.deepseek.com/v1',
                        'model': 'deepseek-coder',
                        'enabled': bool(os.getenv('DEEPSEEK_API_KEY'))
                    }
                },
                'fallback_order': ['claude', 'openai', 'deepseek', 'gemini'],
                'enable_browser_access': os.getenv('ENABLE_BROWSER_ACCESS', 'false').lower() == 'true',
                'browser_config': {
                    'search_engine': 'duckduckgo',
                    'max_results': 5,
                    'timeout': 10
                }
            }
            
            self.ai_manager = MultiLLMManager(ai_config)
            await self.ai_manager.initialize()
            
            self.logger.info("AI services initialized successfully")
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize AI services: {str(e)}")
            self.ai_manager = None

    async def _enhanced_ai_analysis(
        self,
        code: str,
        file_path: str,
        language: str,
        existing_issues: List[QualityIssue]
    ) -> Tuple[List[str], List[QualityIssue]]:
        """Enhanced AI analysis using multiple providers"""
        suggestions = []
        ai_issues = []
        
        if not self.ai_manager:
            return suggestions, ai_issues
        
        try:
            # Prepare analysis prompt
            analysis_prompt = self._create_analysis_prompt(
                code, file_path, language, existing_issues
            )
            
            # Get AI analysis with fallback across providers
            ai_response = await self.ai_manager.generate_response(
                prompt=analysis_prompt,
                provider_preference=['claude', 'deepseek', 'openai', 'gemini'],
                max_tokens=2000,
                temperature=0.1
            )
            
            if ai_response and ai_response.get('success'):
                response_text = ai_response.get('content', '')
                
                # Parse structured response
                parsed_analysis = self._parse_ai_analysis(response_text)
                
                suggestions.extend(parsed_analysis.get('suggestions', []))
                ai_issues.extend(parsed_analysis.get('issues', []))
                
                # If browser access is enabled, get additional context
                if self.ai_manager.browser_enabled:
                    additional_context = await self._get_web_context(
                        language, existing_issues
                    )
                    suggestions.extend(additional_context)
            
        except Exception as e:
            self.logger.warning(f"Enhanced AI analysis failed: {str(e)}")
        
        return suggestions, ai_issues

    def _create_analysis_prompt(
        self,
        code: str,
        file_path: str,
        language: str,
        existing_issues: List[QualityIssue]
    ) -> str:
        """Create comprehensive analysis prompt for AI"""
        
        issue_summary = self._summarize_existing_issues(existing_issues)
        
        prompt = f"""
Analyze the following {language} code for quality, security, performance, and maintainability issues.

File: {file_path}
Language: {language}

Existing Issues Found:
{issue_summary}

Code:
```{language}
{code[:4000]}  # Limit code size for prompt
```

Please provide analysis in the following JSON format:
{{
    "suggestions": [
        "Specific actionable suggestions for improvement"
    ],
    "issues": [
        {{
            "type": "security|performance|maintainability|style",
            "severity": "critical|high|medium|low|info",
            "title": "Brief issue title",
            "description": "Detailed description",
            "line_number": 0,
            "suggestion": "How to fix this issue",
            "confidence": 0.95,
            "estimated_fix_time": 15
        }}
    ],
    "patterns": [
        "Identified code patterns and architectural insights"
    ],
    "best_practices": [
        "Language-specific best practices recommendations"
    ]
}}

Focus on:
1. Security vulnerabilities and potential exploits
2. Performance bottlenecks and optimization opportunities
3. Code maintainability and readability issues
4. Architectural improvements and design patterns
5. Language-specific best practices
6. Test coverage and testability improvements
"""
        return prompt

    def _summarize_existing_issues(self, issues: List[QualityIssue]) -> str:
        """Summarize existing issues for AI context"""
        if not issues:
            return "No existing issues found."
        
        summary = []
        issue_counts = defaultdict(int)
        
        for issue in issues:
            issue_counts[f"{issue.severity.value}_{issue.type.value}"] += 1
        
        for key, count in issue_counts.items():
            severity, issue_type = key.split('_', 1)
            summary.append(f"- {count} {severity} {issue_type} issues")
        
        return '\n'.join(summary)

    def _parse_ai_analysis(self, response_text: str) -> Dict[str, Any]:
        """Parse AI analysis response"""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                analysis = json.loads(json_str)
                
                # Convert issue dictionaries to QualityIssue objects
                if 'issues' in analysis:
                    parsed_issues = []
                    for issue_data in analysis['issues']:
                        try:
                            issue = QualityIssue(
                                id=hashlib.md5(str(issue_data).encode()).hexdigest()[:8],
                                type=QualityMetricType(issue_data.get('type', 'style')),
                                severity=self._parse_severity(issue_data.get('severity', 'medium')),
                                title=issue_data.get('title', 'AI Detected Issue'),
                                description=issue_data.get('description', ''),
                                file_path='',  # Will be set by caller
                                line_number=issue_data.get('line_number', 0),
                                suggestion=issue_data.get('suggestion', ''),
                                confidence=issue_data.get('confidence', 0.8),
                                estimated_fix_time=issue_data.get('estimated_fix_time', 10),
                                tags=['ai-generated']
                            )
                            parsed_issues.append(issue)
                        except (ValueError, KeyError) as e:
                            self.logger.warning(f"Failed to parse AI issue: {e}")
                    
                    analysis['issues'] = parsed_issues
                
                return analysis
        
        except (json.JSONDecodeError, AttributeError) as e:
            self.logger.warning(f"Failed to parse AI analysis JSON: {e}")
        
        # Fallback: extract suggestions from plain text
        suggestions = []
        lines = response_text.split('\n')
        for line in lines:
            if any(keyword in line.lower() for keyword in ['suggest', 'recommend', 'improve', 'consider']):
                suggestions.append(line.strip())
        
        return {'suggestions': suggestions[:5], 'issues': []}

    async def _get_web_context(
        self,
        language: str,
        issues: List[QualityIssue]
    ) -> List[str]:
        """Get additional context from web search"""
        web_suggestions = []
        
        try:
            if not self.ai_manager.browser_enabled:
                return web_suggestions
            
            # Create search queries based on common issues
            search_queries = []
            
            # Language-specific best practices
            search_queries.append(f"{language} code quality best practices 2024")
            
            # Issue-specific searches
            issue_types = set(issue.type.value for issue in issues)
            for issue_type in list(issue_types)[:3]:  # Limit searches
                search_queries.append(f"{language} {issue_type} common issues solutions")
            
            # Perform web searches
            for query in search_queries:
                try:
                    search_results = await self.ai_manager.web_search(
                        query=query,
                        max_results=3
                    )
                    
                    if search_results:
                        # Extract relevant suggestions from search results
                        context_suggestions = await self._extract_suggestions_from_web(
                            search_results, language
                        )
                        web_suggestions.extend(context_suggestions)
                
                except Exception as e:
                    self.logger.warning(f"Web search failed for query '{query}': {e}")
                    continue
        
        except Exception as e:
            self.logger.warning(f"Web context retrieval failed: {e}")
        
        return web_suggestions[:5]  # Limit to top 5 suggestions

    async def _extract_suggestions_from_web(
        self,
        search_results: List[Dict],
        language: str
    ) -> List[str]:
        """Extract actionable suggestions from web search results"""
        suggestions = []
        
        try:
            for result in search_results:
                title = result.get('title', '')
                snippet = result.get('snippet', '')
                
                # Use AI to extract relevant suggestions
                extraction_prompt = f"""
                Extract 1-2 specific, actionable {language} code quality suggestions from:
                
                Title: {title}
                Content: {snippet}
                
                Return only practical suggestions that can be applied to code, one per line.
                Focus on concrete actions, not general advice.
                """
                
                ai_response = await self.ai_manager.generate_response(
                    prompt=extraction_prompt,
                    max_tokens=200,
                    temperature=0.3
                )
                
                if ai_response and ai_response.get('success'):
                    content = ai_response.get('content', '')
                    extracted_suggestions = [
                        line.strip() 
                        for line in content.split('\n') 
                        if line.strip() and len(line.strip()) > 10
                    ]
                    suggestions.extend(extracted_suggestions)
        
        except Exception as e:
            self.logger.warning(f"Suggestion extraction failed: {e}")
        
        return suggestions

    async def generate_improvement_plan(
        self,
        analysis_result: AnalysisResult,
        target_score: float = 85.0,
        time_budget_hours: int = 8
    ) -> Dict[str, Any]:
        """Generate an AI-powered improvement plan"""
        
        if not self.ai_manager:
            return self._generate_basic_improvement_plan(analysis_result, target_score)
        
        try:
            plan_prompt = f"""
            Create a detailed code improvement plan based on this analysis:
            
            Current Score: {analysis_result.overall_score}/100
            Target Score: {target_score}/100
            Time Budget: {time_budget_hours} hours
            
            Issues Summary:
            - Total Issues: {len(analysis_result.issues)}
            - Critical: {len([i for i in analysis_result.issues if i.severity == SeverityLevel.CRITICAL])}
            - High: {len([i for i in analysis_result.issues if i.severity == SeverityLevel.HIGH])}
            - Medium: {len([i for i in analysis_result.issues if i.severity == SeverityLevel.MEDIUM])}
            
            Top Issues:
            {self._format_top_issues(analysis_result.issues[:5])}
            
            Generate a JSON improvement plan with:
            {{
                "phases": [
                    {{
                        "name": "Phase name",
                        "priority": "high|medium|low",
                        "estimated_hours": 2.5,
                        "tasks": ["Specific task 1", "Specific task 2"],
                        "expected_score_improvement": 10.0,
                        "issues_addressed": ["issue_id_1", "issue_id_2"]
                    }}
                ],
                "quick_wins": [
                    "Quick improvements that provide immediate value"
                ],
                "long_term_recommendations": [
                    "Strategic improvements for maintainability"
                ],
                "tools_and_resources": [
                    "Recommended tools, linters, or resources"
                ]
            }}
            """
            
            ai_response = await self.ai_manager.generate_response(
                prompt=plan_prompt,
                max_tokens=1500,
                temperature=0.2
            )
            
            if ai_response and ai_response.get('success'):
                plan_data = self._parse_ai_analysis(ai_response.get('content', ''))
                return self._enhance_improvement_plan(plan_data, analysis_result)
        
        except Exception as e:
            self.logger.warning(f"AI improvement plan generation failed: {e}")
        
        return self._generate_basic_improvement_plan(analysis_result, target_score)

    def _format_top_issues(self, issues: List[QualityIssue]) -> str:
        """Format top issues for AI prompt"""
        formatted = []
        for i, issue in enumerate(issues, 1):
            formatted.append(
                f"{i}. {issue.severity.value.upper()}: {issue.title} "
                f"(Line {issue.line_number}, Est. fix: {issue.estimated_fix_time}min)"
            )
        return '\n'.join(formatted)

    def _enhance_improvement_plan(
        self,
        plan_data: Dict[str, Any],
        analysis_result: AnalysisResult
    ) -> Dict[str, Any]:
        """Enhance the improvement plan with additional context"""
        
        enhanced_plan = {
            'metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'current_score': analysis_result.overall_score,
                'current_grade': analysis_result.grade,
                'total_issues': len(analysis_result.issues),
                'estimated_total_time': analysis_result.estimated_refactor_time
            },
            'executive_summary': self._generate_executive_summary(analysis_result),
            'phases': plan_data.get('phases', []),
            'quick_wins': plan_data.get('quick_wins', []),
            'long_term_recommendations': plan_data.get('long_term_recommendations', []),
            'tools_and_resources': plan_data.get('tools_and_resources', []),
            'risk_assessment': self._assess_improvement_risks(analysis_result),
            'success_metrics': self._define_success_metrics(analysis_result)
        }
        
        return enhanced_plan

    def _generate_executive_summary(self, analysis_result: AnalysisResult) -> str:
        """Generate executive summary"""
        critical_issues = len([i for i in analysis_result.issues if i.severity == SeverityLevel.CRITICAL])
        high_issues = len([i for i in analysis_result.issues if i.severity == SeverityLevel.HIGH])
        
        return f"""
        Code quality analysis reveals a score of {analysis_result.overall_score}/100 (Grade {analysis_result.grade}).
        
        Key findings:
        - {critical_issues} critical issues requiring immediate attention
        - {high_issues} high-priority issues impacting maintainability
        - Estimated {analysis_result.estimated_refactor_time // 60} hours of refactoring needed
        
        Primary focus areas: {', '.join(self._get_top_issue_types(analysis_result.issues))}
        """

    def _get_top_issue_types(self, issues: List[QualityIssue]) -> List[str]:
        """Get the most common issue types"""
        issue_types = defaultdict(int)
        for issue in issues:
            issue_types[issue.type.value] += 1
        
        return [
            issue_type for issue_type, _ in 
            sorted(issue_types.items(), key=lambda x: x[1], reverse=True)[:3]
        ]

    def _assess_improvement_risks(self, analysis_result: AnalysisResult) -> Dict[str, str]:
        """Assess risks of improvement activities"""
        risks = {}
        
        if analysis_result.overall_score < 50:
            risks['high_technical_debt'] = "Extensive refactoring may introduce new bugs"
        
        security_issues = [i for i in analysis_result.issues if i.type == QualityMetricType.SECURITY]
        if security_issues:
            risks['security_vulnerabilities'] = "Security fixes should be prioritized and tested thoroughly"
        
        complex_issues = [i for i in analysis_result.issues if i.type == QualityMetricType.COMPLEXITY]
        if len(complex_issues) > 10:
            risks['complexity_refactoring'] = "Large-scale refactoring requires comprehensive testing"
        
        return risks

    def _define_success_metrics(self, analysis_result: AnalysisResult) -> List[str]:
        """Define success metrics for improvement"""
        return [
            f"Achieve code quality score > 80 (current: {analysis_result.overall_score})",
            "Reduce critical and high severity issues by 80%",
            "Improve maintainability index above 70",
            "Increase test coverage to >85%",
            "Achieve zero security vulnerabilities",
            "Reduce cyclomatic complexity average to <10"
        ]

    def _generate_basic_improvement_plan(
        self,
        analysis_result: AnalysisResult,
        target_score: float
    ) -> Dict[str, Any]:
        """Generate basic improvement plan without AI"""
        
        critical_issues = [i for i in analysis_result.issues if i.severity == SeverityLevel.CRITICAL]
        high_issues = [i for i in analysis_result.issues if i.severity == SeverityLevel.HIGH]
        
        phases = []
        
        # Phase 1: Critical Issues
        if critical_issues:
            phases.append({
                'name': 'Critical Issues Resolution',
                'priority': 'high',
                'estimated_hours': sum(i.estimated_fix_time for i in critical_issues) / 60,
                'tasks': [f"Fix: {issue.title}" for issue in critical_issues[:5]],
                'expected_score_improvement': 20.0,
                'issues_addressed': [i.id for i in critical_issues]
            })
        
        # Phase 2: High Priority Issues
        if high_issues:
            phases.append({
                'name': 'High Priority Improvements',
                'priority': 'high',
                'estimated_hours': sum(i.estimated_fix_time for i in high_issues) / 60,
                'tasks': [f"Address: {issue.title}" for issue in high_issues[:5]],
                'expected_score_improvement': 15.0,
                'issues_addressed': [i.id for i in high_issues]
            })
        
        return {
            'metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'current_score': analysis_result.overall_score,
                'target_score': target_score
            },
            'phases': phases,
            'quick_wins': [
                "Run automated code formatting (black, prettier)",
                "Fix obvious style violations",
                "Add missing docstrings"
            ],
            'long_term_recommendations': [
                "Implement automated testing pipeline",
                "Set up continuous code quality monitoring",
                "Establish code review process"
            ]
        }


# Configuration and Environment Setup
class YMERAAnalyzerConfig:
    """Configuration management for YMERA Code Quality Analyzer"""
    
    def __init__(self):
        self.validate_environment()
        self.setup_logging()
    
    def validate_environment(self) -> None:
        """Validate required environment variables and API keys"""
        required_vars = []
        optional_vars = {
            'OPENAI_API_KEY': 'OpenAI GPT models',
            'ANTHROPIC_API_KEY': 'Claude AI models', 
            'GEMINI_API_KEY': 'Google Gemini models',
            'DEEPSEEK_API_KEY': 'DeepSeek coding models',
            'ENABLE_BROWSER_ACCESS': 'Web browsing capabilities'
        }
        
        available_providers = []
        for var, description in optional_vars.items():
            if os.getenv(var):
                available_providers.append(description)
        
        if not available_providers:
            logging.warning(
                "No AI provider API keys found. AI-powered analysis will be disabled. "
                "Set OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, or DEEPSEEK_API_KEY "
                "to enable AI features."
            )
        else:
            logging.info(f"Available AI providers: {', '.join(available_providers)}")
    
    def setup_logging(self) -> None:
        """Setup logging configuration"""
        log_level = os.getenv('YMERA_LOG_LEVEL', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )


# Usage Example and Testing
async def main():
    """Example usage of the YMERA Code Quality Analyzer"""
    
    # Initialize configuration
    config = YMERAAnalyzerConfig()
    
    # Create analyzer instance
    analyzer = YMERACodeQualityAnalyzer(
        cache_ttl=3600,  # 1 hour cache
        enable_ai_analysis=True,
        enable_learning=True
    )
    
    # Example: Analyze a single file
    sample_code = '''
def poorly_written_function(a, b, c, d, e, f):
    """A function with many parameters and complex logic"""
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        if f > 0:
                            result = a + b + c + d + e + f
                            return result * 2
                        else:
                            return 0
                    else:
                        return -1
                else:
                    return -2
            else:
                return -3
        else:
            return -4
    else:
        return -5
    '''
    
    try:
        # Analyze the sample code
        result = await analyzer.analyze_code(
            code=sample_code,
            file_path="example.py",
            context={
                'project_type': 'production',
                'team_size': 5
            }
        )
        
        # Print results
        print(f"Analysis Results:")
        print(f"Overall Score: {result.overall_score}/100 (Grade: {result.grade})")
        print(f"Total Issues: {len(result.issues)}")
        print(f"Estimated Refactor Time: {result.estimated_refactor_time} minutes")
        print("\nTop Issues:")
        
        for i, issue in enumerate(result.issues[:5], 1):
            print(f"{i}. {issue.severity.value.upper()}: {issue.title}")
            print(f"   Line {issue.line_number}: {issue.description}")
            print(f"   Suggestion: {issue.suggestion}")
            print()
        
        # Generate improvement plan
        improvement_plan = await analyzer.generate_improvement_plan(
            result, 
            target_score=85.0,
            time_budget_hours=4
        )
        
        print("Improvement Plan:")
        for phase in improvement_plan.get('phases', []):
            print(f"- {phase['name']}: {phase['estimated_hours']} hours")
            for task in phase['tasks'][:3]:
                print(f"  • {task}")
        
        print(f"\nQuick Wins:")
        for win in improvement_plan.get('quick_wins', [])[:3]:
            print(f"• {win}")
    
    except Exception as e:
        print(f"Analysis failed: {e}")
    
    finally:
        # Cleanup
        await analyzer.close()

if __name__ == "__main__":
    asyncio.run(main())