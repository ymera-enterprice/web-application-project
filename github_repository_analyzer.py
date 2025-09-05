"""
YMERA Enterprise GitHub Repository Analyzer
Production-Ready GitHub Integration with Advanced Analysis Capabilities
"""

import asyncio
import base64
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

import aiohttp
import asyncpg
from aiofiles import open as aio_open
from github import Github
from github.GithubException import GithubException, RateLimitExceededException
from pydantic import BaseModel, validator

from ymera_core.exceptions import YMERAException
from ymera_core.logging.structured_logger import StructuredLogger
from ymera_core.metrics.collector import MetricsCollector
from ymera_services.ai.multi_llm_manager import MultiLLMManager


class AnalysisType(str, Enum):
    """Types of repository analysis supported"""
    COMPREHENSIVE = "comprehensive"
    SECURITY_FOCUSED = "security_focused"
    CODE_QUALITY = "code_quality"
    ARCHITECTURE = "architecture"
    DEPENDENCIES = "dependencies"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    TESTING = "testing"


class RepositoryLanguage(str, Enum):
    """Supported programming languages with analysis capabilities"""
    PYTHON = "Python"
    JAVASCRIPT = "JavaScript"
    TYPESCRIPT = "TypeScript"
    JAVA = "Java"
    CSHARP = "C#"
    CPP = "C++"
    C = "C"
    GO = "Go"
    RUST = "Rust"
    PHP = "PHP"
    RUBY = "Ruby"
    SWIFT = "Swift"
    KOTLIN = "Kotlin"
    SCALA = "Scala"
    R = "R"
    SHELL = "Shell"
    DOCKERFILE = "Dockerfile"
    YAML = "YAML"
    JSON = "JSON"
    UNKNOWN = "Unknown"


@dataclass
class FileAnalysis:
    """Detailed analysis of a single file"""
    path: str
    language: str
    size: int
    lines_of_code: int
    complexity_score: float
    security_issues: List[Dict[str, Any]] = field(default_factory=list)
    quality_issues: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    classes: List[Dict[str, Any]] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    documentation_coverage: float = 0.0
    test_coverage: Optional[float] = None
    last_modified: Optional[datetime] = None
    author_info: Optional[Dict[str, Any]] = None


@dataclass
class DependencyAnalysis:
    """Analysis of project dependencies"""
    direct_dependencies: Dict[str, str] = field(default_factory=dict)
    dev_dependencies: Dict[str, str] = field(default_factory=dict)
    transitive_dependencies: Dict[str, str] = field(default_factory=dict)
    vulnerable_dependencies: List[Dict[str, Any]] = field(default_factory=list)
    outdated_dependencies: List[Dict[str, Any]] = field(default_factory=list)
    license_analysis: Dict[str, Any] = field(default_factory=dict)
    dependency_tree: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityAnalysis:
    """Comprehensive security analysis results"""
    critical_vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)
    high_vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)
    medium_vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)
    low_vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)
    secrets_detected: List[Dict[str, Any]] = field(default_factory=list)
    security_score: float = 0.0
    compliance_status: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class ArchitectureAnalysis:
    """Software architecture analysis"""
    patterns_detected: List[str] = field(default_factory=list)
    layer_structure: Dict[str, List[str]] = field(default_factory=dict)
    coupling_metrics: Dict[str, float] = field(default_factory=dict)
    cohesion_metrics: Dict[str, float] = field(default_factory=dict)
    complexity_metrics: Dict[str, Any] = field(default_factory=dict)
    design_principles_adherence: Dict[str, float] = field(default_factory=dict)
    refactoring_suggestions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RepositoryAnalysisResult:
    """Comprehensive repository analysis result"""
    repository_url: str
    repository_name: str
    owner: str
    analysis_timestamp: datetime
    analysis_type: AnalysisType
    
    # Basic repository information
    description: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    languages: Dict[str, int] = field(default_factory=dict)
    primary_language: Optional[str] = None
    size_kb: int = 0
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    open_issues: int = 0
    
    # Repository health metrics
    has_readme: bool = False
    has_license: bool = False
    has_contributing: bool = False
    has_code_of_conduct: bool = False
    has_security_policy: bool = False
    has_ci_cd: bool = False
    has_tests: bool = False
    has_documentation: bool = False
    
    # Analysis results
    file_analyses: List[FileAnalysis] = field(default_factory=list)
    dependency_analysis: Optional[DependencyAnalysis] = None
    security_analysis: Optional[SecurityAnalysis] = None
    architecture_analysis: Optional[ArchitectureAnalysis] = None
    
    # Quality metrics
    overall_quality_score: float = 0.0
    maintainability_score: float = 0.0
    reliability_score: float = 0.0
    security_score: float = 0.0
    performance_score: float = 0.0
    
    # Learning and insights
    ai_insights: List[str] = field(default_factory=list)
    improvement_recommendations: List[Dict[str, Any]] = field(default_factory=list)
    best_practices_adherence: Dict[str, float] = field(default_factory=dict)
    
    # Metadata
    analysis_duration_seconds: float = 0.0
    files_analyzed: int = 0
    lines_of_code_total: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis result to dictionary"""
        return {
            'repository_url': self.repository_url,
            'repository_name': self.repository_name,
            'owner': self.owner,
            'analysis_timestamp': self.analysis_timestamp.isoformat(),
            'analysis_type': self.analysis_type.value,
            'description': self.description,
            'topics': self.topics,
            'languages': self.languages,
            'primary_language': self.primary_language,
            'size_kb': self.size_kb,
            'stars': self.stars,
            'forks': self.forks,
            'watchers': self.watchers,
            'open_issues': self.open_issues,
            'repository_health': {
                'has_readme': self.has_readme,
                'has_license': self.has_license,
                'has_contributing': self.has_contributing,
                'has_code_of_conduct': self.has_code_of_conduct,
                'has_security_policy': self.has_security_policy,
                'has_ci_cd': self.has_ci_cd,
                'has_tests': self.has_tests,
                'has_documentation': self.has_documentation
            },
            'quality_metrics': {
                'overall_quality_score': self.overall_quality_score,
                'maintainability_score': self.maintainability_score,
                'reliability_score': self.reliability_score,
                'security_score': self.security_score,
                'performance_score': self.performance_score
            },
            'file_analyses': [
                {
                    'path': fa.path,
                    'language': fa.language,
                    'size': fa.size,
                    'lines_of_code': fa.lines_of_code,
                    'complexity_score': fa.complexity_score,
                    'security_issues_count': len(fa.security_issues),
                    'quality_issues_count': len(fa.quality_issues),
                    'dependencies_count': len(fa.dependencies),
                    'functions_count': len(fa.functions),
                    'classes_count': len(fa.classes),
                    'documentation_coverage': fa.documentation_coverage
                } for fa in self.file_analyses
            ],
            'dependency_analysis': self._serialize_dependency_analysis(),
            'security_analysis': self._serialize_security_analysis(),
            'architecture_analysis': self._serialize_architecture_analysis(),
            'ai_insights': self.ai_insights,
            'improvement_recommendations': self.improvement_recommendations,
            'best_practices_adherence': self.best_practices_adherence,
            'metadata': {
                'analysis_duration_seconds': self.analysis_duration_seconds,
                'files_analyzed': self.files_analyzed,
                'lines_of_code_total': self.lines_of_code_total
            }
        }
    
    def _serialize_dependency_analysis(self) -> Optional[Dict[str, Any]]:
        """Serialize dependency analysis for JSON storage"""
        if not self.dependency_analysis:
            return None
        
        return {
            'direct_dependencies_count': len(self.dependency_analysis.direct_dependencies),
            'dev_dependencies_count': len(self.dependency_analysis.dev_dependencies),
            'vulnerable_dependencies_count': len(self.dependency_analysis.vulnerable_dependencies),
            'outdated_dependencies_count': len(self.dependency_analysis.outdated_dependencies),
            'license_analysis': self.dependency_analysis.license_analysis
        }
    
    def _serialize_security_analysis(self) -> Optional[Dict[str, Any]]:
        """Serialize security analysis for JSON storage"""
        if not self.security_analysis:
            return None
        
        return {
            'critical_vulnerabilities_count': len(self.security_analysis.critical_vulnerabilities),
            'high_vulnerabilities_count': len(self.security_analysis.high_vulnerabilities),
            'medium_vulnerabilities_count': len(self.security_analysis.medium_vulnerabilities),
            'low_vulnerabilities_count': len(self.security_analysis.low_vulnerabilities),
            'secrets_detected_count': len(self.security_analysis.secrets_detected),
            'security_score': self.security_analysis.security_score,
            'compliance_status': self.security_analysis.compliance_status,
            'recommendations_count': len(self.security_analysis.recommendations)
        }
    
    def _serialize_architecture_analysis(self) -> Optional[Dict[str, Any]]:
        """Serialize architecture analysis for JSON storage"""
        if not self.architecture_analysis:
            return None
        
        return {
            'patterns_detected': self.architecture_analysis.patterns_detected,
            'coupling_metrics': self.architecture_analysis.coupling_metrics,
            'cohesion_metrics': self.architecture_analysis.cohesion_metrics,
            'complexity_metrics': self.architecture_analysis.complexity_metrics,
            'design_principles_adherence': self.architecture_analysis.design_principles_adherence,
            'refactoring_suggestions_count': len(self.architecture_analysis.refactoring_suggestions)
        }


class GitHubRepositoryAnalyzer:
    """
    Enterprise-grade GitHub repository analyzer with advanced AI-powered analysis capabilities.
    
    Features:
    - Comprehensive code quality analysis
    - Security vulnerability detection
    - Architecture pattern recognition
    - Dependency management analysis
    - Performance optimization recommendations
    - Learning engine integration
    - Rate limiting and error handling
    - Caching and optimization
    """
    
    def __init__(
        self,
        github_token: str,
        ai_manager: MultiLLMManager,
        logger: Optional[StructuredLogger] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_manager: Optional[Any] = None,
        max_files_per_analysis: int = 1000,
        max_file_size_kb: int = 500,
        rate_limit_buffer: int = 100
    ):
        """
        Initialize the GitHub Repository Analyzer
        
        Args:
            github_token: GitHub personal access token
            ai_manager: Multi-LLM manager for AI analysis
            logger: Structured logger instance
            metrics_collector: Metrics collector for monitoring
            cache_manager: Cache manager for optimization
            max_files_per_analysis: Maximum files to analyze per repository
            max_file_size_kb: Maximum file size to analyze in KB
            rate_limit_buffer: Rate limit buffer to prevent API exhaustion
        """
        self.github_token = github_token
        self.ai_manager = ai_manager
        self.logger = logger or logging.getLogger(__name__)
        self.metrics_collector = metrics_collector
        self.cache_manager = cache_manager
        self.max_files_per_analysis = max_files_per_analysis
        self.max_file_size_kb = max_file_size_kb
        self.rate_limit_buffer = rate_limit_buffer
        
        # GitHub API clients
        self.github_client: Optional[Github] = None
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Analysis configuration
        self.supported_languages = {
            '.py': RepositoryLanguage.PYTHON,
            '.js': RepositoryLanguage.JAVASCRIPT,
            '.ts': RepositoryLanguage.TYPESCRIPT,
            '.java': RepositoryLanguage.JAVA,
            '.cs': RepositoryLanguage.CSHARP,
            '.cpp': RepositoryLanguage.CPP,
            '.c': RepositoryLanguage.C,
            '.go': RepositoryLanguage.GO,
            '.rs': RepositoryLanguage.RUST,
            '.php': RepositoryLanguage.PHP,
            '.rb': RepositoryLanguage.RUBY,
            '.swift': RepositoryLanguage.SWIFT,
            '.kt': RepositoryLanguage.KOTLIN,
            '.scala': RepositoryLanguage.SCALA,
            '.r': RepositoryLanguage.R,
            '.sh': RepositoryLanguage.SHELL,
            '.dockerfile': RepositoryLanguage.DOCKERFILE,
            '.yml': RepositoryLanguage.YAML,
            '.yaml': RepositoryLanguage.YAML,
            '.json': RepositoryLanguage.JSON
        }
        
        # Security patterns
        self.secret_patterns = {
            'api_key': re.compile(r'(?i)(api[_-]?key|apikey)[\s]*[:=][\s]*["\']?([a-zA-Z0-9_-]{20,})["\']?'),
            'aws_access_key': re.compile(r'AKIA[0-9A-Z]{16}'),
            'aws_secret_key': re.compile(r'(?i)(aws[_-]?secret[_-]?access[_-]?key|aws[_-]?secret)[\s]*[:=][\s]*["\']?([a-zA-Z0-9/+=]{40})["\']?'),
            'github_token': re.compile(r'gh[pousr]_[A-Za-z0-9_]{36}'),
            'private_key': re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
            'password': re.compile(r'(?i)(password|passwd|pwd)[\s]*[:=][\s]*["\']([^"\']{8,})["\']'),
            'jwt_token': re.compile(r'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*')
        }
        
        # Code quality patterns
        self.quality_patterns = {
            'todo_fixme': re.compile(r'(?i)(TODO|FIXME|HACK|XXX|BUG)'),
            'long_line': lambda line: len(line) > 120,
            'deep_nesting': lambda line: len(line) - len(line.lstrip()) > 16,
            'magic_numbers': re.compile(r'\b(?!0|1|2|100)\d{3,}\b'),
            'empty_catch': re.compile(r'except[^:]*:\s*pass'),
            'print_statement': re.compile(r'\bprint\s*\(')
        }
        
        # Performance monitoring
        self._analysis_start_time = None
        self._files_processed = 0
        self._api_calls_made = 0
        
    async def initialize(self) -> None:
        """Initialize the analyzer with GitHub API connection"""
        try:
            self.logger.info("Initializing GitHub Repository Analyzer...")
            
            # Initialize GitHub client
            self.github_client = Github(
                self.github_token,
                per_page=100,
                retry=3,
                timeout=30
            )
            
            # Test GitHub connection
            user = self.github_client.get_user()
            self.logger.info(f"GitHub connection established for user: {user.login}")
            
            # Initialize HTTP session
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    'Authorization': f'token {self.github_token}',
                    'Accept': 'application/vnd.github.v3+json',
                    'User-Agent': 'YMERA-Enterprise-Analyzer/2.0'
                }
            )
            
            self.logger.info("GitHub Repository Analyzer initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize GitHub Repository Analyzer: {str(e)}")
            raise YMERAException(f"GitHub analyzer initialization failed: {str(e)}")
    
    async def analyze_repository(
        self,
        repository_url: str,
        analysis_type: AnalysisType = AnalysisType.COMPREHENSIVE,
        include_ai_analysis: bool = True,
        branch: Optional[str] = None
    ) -> RepositoryAnalysisResult:
        """
        Perform comprehensive analysis of a GitHub repository
        
        Args:
            repository_url: URL of the GitHub repository
            analysis_type: Type of analysis to perform
            include_ai_analysis: Whether to include AI-powered insights
            branch: Specific branch to analyze (defaults to default branch)
            
        Returns:
            Comprehensive analysis result
        """
        self._analysis_start_time = time.time()
        self._files_processed = 0
        self._api_calls_made = 0
        
        try:
            self.logger.info(f"Starting repository analysis: {repository_url}")
            
            # Parse repository URL
            owner, repo_name = self._parse_repository_url(repository_url)
            
            # Check cache first
            cache_key = f"repo_analysis:{owner}:{repo_name}:{analysis_type.value}:{branch or 'default'}"
            if self.cache_manager:
                cached_result = await self.cache_manager.get(cache_key)
                if cached_result:
                    self.logger.info(f"Returning cached analysis for {repository_url}")
                    return RepositoryAnalysisResult(**json.loads(cached_result))
            
            # Get repository information
            repo = self.github_client.get_repo(f"{owner}/{repo_name}")
            self._api_calls_made += 1
            
            # Initialize analysis result
            result = RepositoryAnalysisResult(
                repository_url=repository_url,
                repository_name=repo_name,
                owner=owner,
                analysis_timestamp=datetime.utcnow(),
                analysis_type=analysis_type,
                description=repo.description,
                topics=repo.get_topics(),
                languages=repo.get_languages(),
                size_kb=repo.size,
                stars=repo.stargazers_count,
                forks=repo.forks_count,
                watchers=repo.watchers_count,
                open_issues=repo.open_issues_count
            )
            
            # Determine primary language
            if result.languages:
                result.primary_language = max(result.languages.items(), key=lambda x: x[1])[0]
            
            # Analyze security issues
            analysis.security_issues = self._detect_security_issues(content, file_path)
            
            # Analyze code quality issues
            analysis.quality_issues = self._detect_quality_issues(content, language)
            
            # Extract dependencies
            analysis.dependencies = self._extract_dependencies(content, language, file_path)
            
            # Extract functions and classes
            analysis.functions = self._extract_functions(content, language)
            analysis.classes = self._extract_classes(content, language)
            
            # Extract imports
            analysis.imports = self._extract_imports(content, language)
            
            # Calculate documentation coverage
            analysis.documentation_coverage = self._calculate_documentation_coverage(content, language)
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Error analyzing file {file_info['path']}: {str(e)}")
            return None
    
    def _calculate_complexity_score(self, content: str, language: str) -> float:
        """Calculate cyclomatic complexity score for the file"""
        try:
            lines = content.split('\n')
            complexity_score = 1.0  # Base complexity
            
            # Language-specific complexity patterns
            if language == RepositoryLanguage.PYTHON.value:
                complexity_patterns = [
                    r'\b(if|elif|while|for|except|with|and|or)\b',
                    r'\b(lambda)\b',
                    r'(?:^|\s)(def|class)\s+\w+'
                ]
            elif language in [RepositoryLanguage.JAVASCRIPT.value, RepositoryLanguage.TYPESCRIPT.value]:
                complexity_patterns = [
                    r'\b(if|else|while|for|switch|case|catch|&&|\|\|)\b',
                    r'\b(function|=>\s*{)\b',
                    r'\b(class)\s+\w+'
                ]
            elif language == RepositoryLanguage.JAVA.value:
                complexity_patterns = [
                    r'\b(if|else|while|for|switch|case|catch|&&|\|\|)\b',
                    r'\b(public|private|protected)\s+(static\s+)?[\w<>]+\s+\w+\s*\(',
                    r'\b(class|interface)\s+\w+'
                ]
            else:
                # Generic patterns
                complexity_patterns = [
                    r'\b(if|else|while|for|switch|case|catch)\b',
                    r'[{}()]'
                ]
            
            for line in lines:
                for pattern in complexity_patterns:
                    matches = re.findall(pattern, line, re.IGNORECASE)
                    complexity_score += len(matches) * 0.1
            
            # Normalize complexity score (0.0 to 10.0)
            return min(complexity_score, 10.0)
            
        except Exception:
            return 1.0
    
    def _detect_security_issues(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Detect security issues in file content"""
        security_issues = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Check for secrets
            for secret_type, pattern in self.secret_patterns.items():
                matches = pattern.finditer(line)
                for match in matches:
                    security_issues.append({
                        'type': 'secret_exposure',
                        'severity': 'high',
                        'secret_type': secret_type,
                        'line_number': line_num,
                        'description': f'Potential {secret_type} exposure detected',
                        'recommendation': f'Remove or secure the {secret_type}'
                    })
            
            # Check for SQL injection vulnerabilities
            if re.search(r'(?i)(SELECT|INSERT|UPDATE|DELETE).*\+.*\+', line):
                security_issues.append({
                    'type': 'sql_injection',
                    'severity': 'high',
                    'line_number': line_num,
                    'description': 'Potential SQL injection vulnerability',
                    'recommendation': 'Use parameterized queries'
                })
            
            # Check for XSS vulnerabilities
            if re.search(r'(?i)(innerHTML|outerHTML).*\+', line):
                security_issues.append({
                    'type': 'xss',
                    'severity': 'medium',
                    'line_number': line_num,
                    'description': 'Potential XSS vulnerability',
                    'recommendation': 'Sanitize user input before rendering'
                })
            
            # Check for command injection
            if re.search(r'(?i)(exec|eval|system|shell_exec|passthru).*\ repository health
            await self._analyze_repository_health(repo, result)
            
            # Get file contents for analysis
            files_to_analyze = await self._get_files_for_analysis(repo, branch)
            result.files_analyzed = len(files_to_analyze)
            
            # Perform file-level analysis
            if analysis_type in [AnalysisType.COMPREHENSIVE, AnalysisType.CODE_QUALITY]:
                await self._analyze_files(repo, files_to_analyze, result)
            
            # Perform dependency analysis
            if analysis_type in [AnalysisType.COMPREHENSIVE, AnalysisType.DEPENDENCIES]:
                result.dependency_analysis = await self._analyze_dependencies(repo, files_to_analyze)
            
            # Perform security analysis
            if analysis_type in [AnalysisType.COMPREHENSIVE, AnalysisType.SECURITY_FOCUSED]:
                result.security_analysis = await self._analyze_security(repo, files_to_analyze)
            
            # Perform architecture analysis
            if analysis_type in [AnalysisType.COMPREHENSIVE, AnalysisType.ARCHITECTURE]:
                result.architecture_analysis = await self._analyze_architecture(files_to_analyze, result.primary_language)
            
            # Calculate quality scores
            self._calculate_quality_scores(result)
            
            # AI-powered analysis and insights
            if include_ai_analysis and self.ai_manager:
                await self._generate_ai_insights(result)
            
            # Calculate analysis duration
            result.analysis_duration_seconds = time.time() - self._analysis_start_time
            
            # Cache the result
            if self.cache_manager:
                await self.cache_manager.set(
                    cache_key,
                    json.dumps(result.to_dict(), default=str),
                    ttl=3600  # Cache for 1 hour
                )
            
            # Record metrics
            if self.metrics_collector:
                await self.metrics_collector.record_metric(
                    "github_analysis_completed",
                    {
                        "repository": f"{owner}/{repo_name}",
                        "analysis_type": analysis_type.value,
                        "duration": result.analysis_duration_seconds,
                        "files_analyzed": result.files_analyzed,
                        "api_calls": self._api_calls_made
                    }
                )
            
            self.logger.info(f"Repository analysis completed: {repository_url} ({result.analysis_duration_seconds:.2f}s)")
            return result
            
        except Exception as e:
            self.logger.error(f"Repository analysis failed for {repository_url}: {str(e)}")
            raise YMERAException(f"Repository analysis failed: {str(e)}")
    
    def _parse_repository_url(self, url: str) -> Tuple[str, str]:
        """Parse GitHub repository URL to extract owner and repository name"""
        parsed = urlparse(url)
        
        if parsed.hostname != 'github.com':
            raise ValueError("Invalid GitHub repository URL")
        
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) < 2:
            raise ValueError("Invalid GitHub repository URL format")
        
        owner = path_parts[0]
        repo_name = path_parts[1].replace('.git', '')
        
        return owner, repo_name
    
    async def _analyze_repository_health(self, repo, result: RepositoryAnalysisResult) -> None:
        """Analyze repository health indicators"""
        try:
            # Check for standard files
            contents = repo.get_contents("")
            self._api_calls_made += 1
            
            file_names = {content.name.lower() for content in contents}
            
            result.has_readme = any(name.startswith('readme') for name in file_names)
            result.has_license = 'license' in file_names or 'license.txt' in file_names
            result.has_contributing = any('contributing' in name for name in file_names)
            result.has_code_of_conduct = any('code_of_conduct' in name or 'code-of-conduct' in name for name in file_names)
            result.has_security_policy = any('security' in name for name in file_names)
            
            # Check for CI/CD
            try:
                github_dir = repo.get_contents(".github")
                self._api_calls_made += 1
                github_files = [item.name.lower() for item in github_dir]
                result.has_ci_cd = any('workflow' in name for name in github_files) or 'main.yml' in github_files or 'ci.yml' in github_files
            except:
                # Check for other CI files
                result.has_ci_cd = any(name in file_names for name in ['.travis.yml', '.circleci', 'jenkinsfile', '.gitlab-ci.yml'])
            
            # Check for tests
            result.has_tests = any(
                'test' in name or 'spec' in name 
                for name in file_names
            )
            
            # Check for documentation
            result.has_documentation = any(
                name in file_names 
                for name in ['docs', 'documentation', 'doc']
            ) or result.has_readme
            
        except Exception as e:
            self.logger.warning(f"Error analyzing repository health: {str(e)}")
    
    async def _get_files_for_analysis(self, repo, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of files to analyze from the repository"""
        files_to_analyze = []
        
        try:
            # Get repository tree
            tree = repo.get_git_tree(branch or repo.default_branch, recursive=True)
            self._api_calls_made += 1
            
            for item in tree.tree:
                if item.type == 'blob':  # It's a file
                    file_path = item.path
                    file_size = item.size or 0
                    
                    # Skip files that are too large
                    if file_size > self.max_file_size_kb * 1024:
                        continue
                    
                    # Check if file extension is supported
                    file_ext = Path(file_path).suffix.lower()
                    if file_ext in self.supported_languages or self._is_text_file(file_path):
                        files_to_analyze.append({
                            'path': file_path,
                            'size': file_size,
                            'sha': item.sha,
                            'url': item.url
                        })
                    
                    # Limit number of files to prevent excessive processing
                    if len(files_to_analyze) >= self.max_files_per_analysis:
                        break
            
            self.logger.info(f"Selected {len(files_to_analyze)} files for analysis")
            return files_to_analyze
            
        except Exception as e:
            self.logger.error(f"Error getting files for analysis: {str(e)}")
            return []
    
    def _is_text_file(self, file_path: str) -> bool:
        """Check if file is a text file worth analyzing"""
        text_extensions = {
            '.md', '.txt', '.rst', '.cfg', '.ini', '.conf',
            '.xml', '.html', '.css', '.sql', '.gitignore',
            '.env', '.example', '.sample'
        }
        
        file_ext = Path(file_path).suffix.lower()
        filename = Path(file_path).name.lower()
        
        return (
            file_ext in text_extensions or
            filename in ['makefile', 'dockerfile', 'readme', 'changelog', 'license'] or
            file_path.startswith('.github/')
        )
    
    async def _analyze_files(self, repo, files_to_analyze: List[Dict[str, Any]], result: RepositoryAnalysisResult) -> None:
        """Analyze individual files in the repository"""
        semaphore = asyncio.Semaphore(10)  # Limit concurrent file analysis
        
        async def analyze_single_file(file_info: Dict[str, Any]) -> Optional[FileAnalysis]:
            async with semaphore:
                return await self._analyze_single_file(repo, file_info)
        
        # Analyze files concurrently
        tasks = [analyze_single_file(file_info) for file_info in files_to_analyze]
        file_analyses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful analyses
        for analysis in file_analyses:
            if isinstance(analysis, FileAnalysis):
                result.file_analyses.append(analysis)
                result.lines_of_code_total += analysis.lines_of_code
            elif isinstance(analysis, Exception):
                self.logger.warning(f"File analysis failed: {str(analysis)}")
        
        self._files_processed = len(result.file_analyses)
    
    async def _analyze_single_file(self, repo, file_info: Dict[str, Any]) -> Optional[FileAnalysis]:
        """Analyze a single file"""
        try:
            # Get file content
            file_path = file_info['path']
            file_content = repo.get_contents(file_path)
            self._api_calls_made += 1
            
            if file_content.encoding == 'base64':
                content = base64.b64decode(file_content.content).decode('utf-8', errors='ignore')
            else:
                content = file_content.content
            
            lines = content.split('\n')
            
            # Determine file language
            file_ext = Path(file_path).suffix.lower()
            language = self.supported_languages.get(file_ext, RepositoryLanguage.UNKNOWN).value
            
            # Create file analysis
            analysis = FileAnalysis(
                path=file_path,
                language=language,
                size=file_info['size'],
                lines_of_code=len([line for line in lines if line.strip()]),
                complexity_score=self._calculate_complexity_score(content, language),
                last_modified=file_content.last_modified
            )
            
            # Analyze, line):
                security_issues.append({
                    'type': 'command_injection',
                    'severity': 'critical',
                    'line_number': line_num,
                    'description': 'Potential command injection vulnerability',
                    'recommendation': 'Validate and sanitize input before executing commands'
                })
        
        return security_issues
    
    def _detect_quality_issues(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Detect code quality issues"""
        quality_issues = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Check for TODO/FIXME comments
            if self.quality_patterns['todo_fixme'].search(line):
                quality_issues.append({
                    'type': 'technical_debt',
                    'severity': 'low',
                    'line_number': line_num,
                    'description': 'TODO or FIXME comment found',
                    'recommendation': 'Address technical debt items'
                })
            
            # Check for long lines
            if self.quality_patterns['long_line'](line):
                quality_issues.append({
                    'type': 'formatting',
                    'severity': 'low',
                    'line_number': line_num,
                    'description': f'Line too long ({len(line)} characters)',
                    'recommendation': 'Break long lines for better readability'
                })
            
            # Check for deep nesting
            if self.quality_patterns['deep_nesting'](line):
                quality_issues.append({
                    'type': 'complexity',
                    'severity': 'medium',
                    'line_number': line_num,
                    'description': 'Deep nesting detected',
                    'recommendation': 'Consider refactoring to reduce nesting'
                })
            
            # Check for magic numbers
            if self.quality_patterns['magic_numbers'].search(line):
                quality_issues.append({
                    'type': 'maintainability',
                    'severity': 'low',
                    'line_number': line_num,
                    'description': 'Magic number detected',
                    'recommendation': 'Replace with named constant'
                })
            
            # Language-specific quality checks
            if language == RepositoryLanguage.PYTHON.value:
                if self.quality_patterns['empty_catch'].search(line):
                    quality_issues.append({
                        'type': 'error_handling',
                        'severity': 'medium',
                        'line_number': line_num,
                        'description': 'Empty except block',
                        'recommendation': 'Handle exceptions appropriately'
                    })
                
                if self.quality_patterns['print_statement'].search(line):
                    quality_issues.append({
                        'type': 'debugging',
                        'severity': 'low',
                        'line_number': line_num,
                        'description': 'Print statement found',
                        'recommendation': 'Use proper logging instead of print statements'
                    })
        
        return quality_issues
    
    def _extract_dependencies(self, content: str, language: str, file_path: str) -> List[str]:
        """Extract dependencies from file content"""
        dependencies = []
        
        try:
            if language == RepositoryLanguage.PYTHON.value:
                # Python imports
                import_patterns = [
                    r'from\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s+import',
                    r'import\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)'
                ]
            elif language in [RepositoryLanguage.JAVASCRIPT.value, RepositoryLanguage.TYPESCRIPT.value]:
                # JavaScript/TypeScript imports
                import_patterns = [
                    r"import.*from\s+['\"]([^'\"]+)['\"]",
                    r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
                ]
            elif language == RepositoryLanguage.JAVA.value:
                # Java imports
                import_patterns = [r'import\s+([a-zA-Z_][a-zA-Z0-9_.]*);']
            elif language == RepositoryLanguage.CSHARP.value:
                # C# using statements
                import_patterns = [r'using\s+([a-zA-Z_][a-zA-Z0-9_.]*);']
            else:
                return dependencies
            
            for pattern in import_patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                dependencies.extend(matches)
            
            return list(set(dependencies))  # Remove duplicates
            
        except Exception:
            return dependencies
    
    def _extract_functions(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Extract function definitions from content"""
        functions = []
        
        try:
            if language == RepositoryLanguage.PYTHON.value:
                pattern = r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\):'
            elif language in [RepositoryLanguage.JAVASCRIPT.value, RepositoryLanguage.TYPESCRIPT.value]:
                pattern = r'(?:function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(|([a-zA-Z_][a-zA-Z0-9_]*)\s*[=:]\s*(?:async\s+)?(?:function\s*)?\([^)]*\)\s*(?:=>|{))'
            elif language == RepositoryLanguage.JAVA.value:
                pattern = r'(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{'
            else:
                return functions
            
            lines = content.split('\n')
            for line_num, line in enumerate(lines, 1):
                matches = re.findall(pattern, line)
                for match in matches:
                    function_name = match if isinstance(match, str) else next(m for m in match if m)
                    functions.append({
                        'name': function_name,
                        'line_number': line_num,
                        'type': 'function'
                    })
            
            return functions
            
        except Exception:
            return functions
    
    def _extract_classes(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Extract class definitions from content"""
        classes = []
        
        try:
            if language == RepositoryLanguage.PYTHON.value:
                pattern = r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            elif language in [RepositoryLanguage.JAVASCRIPT.value, RepositoryLanguage.TYPESCRIPT.value]:
                pattern = r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            elif language == RepositoryLanguage.JAVA.value:
                pattern = r'(?:public|private|protected|\s)*class\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            elif language == RepositoryLanguage.CSHARP.value:
                pattern = r'(?:public|private|protected|internal|\s)*class\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            else:
                return classes
            
            lines = content.split('\n')
            for line_num, line in enumerate(lines, 1):
                matches = re.findall(pattern, line)
                for match in matches:
                    classes.append({
                        'name': match,
                        'line_number': line_num,
                        'type': 'class'
                    })
            
            return classes
            
        except Exception:
            return classes
    
    def _extract_imports(self, content: str, language: str) -> List[str]:
        """Extract import statements from content"""
        return self._extract_dependencies(content, language, "")  # Reuse dependency extraction
    
    def _calculate_documentation_coverage(self, content: str, language: str) -> float:
        """Calculate documentation coverage percentage"""
        try:
            lines = content.split('\n')
            total_functions_classes = 0
            documented_functions_classes = 0
            
            if language == RepositoryLanguage.PYTHON.value:
                # Python docstrings
                func_class_pattern = r'^\s*(?:def|class)\s+'
                docstring_pattern = r'^\s*"""'
                
                for i, line in enumerate(lines):
                    if re.search(func_class_pattern, line):
                        total_functions_classes += 1
                        # Check next few lines for docstring
                        for j in range(i + 1, min(i + 4, len(lines))):
                            if re.search(docstring_pattern, lines[j]):
                                documented_functions_classes += 1
                                break
            
            elif language in [RepositoryLanguage.JAVASCRIPT.value, RepositoryLanguage.TYPESCRIPT.value]:
                # JavaScript JSDoc comments
                func_pattern = r'^\s*(?:function|class|\w+\s*[:=]\s*function)'
                jsdoc_pattern = r'^\s*/\*\*'
                
                for i, line in enumerate(lines):
                    if re.search(func_pattern, line):
                        total_functions_classes += 1
                        # Check preceding lines for JSDoc
                        for j in range(max(0, i - 3), i):
                            if re.search(jsdoc_pattern, lines[j]):
                                documented_functions_classes += 1
                                break
            
            elif language == RepositoryLanguage.JAVA.value:
                # Java Javadoc comments
                func_class_pattern = r'^\s*(?:public|private|protected).*(?:class|interface|\w+\s*\()'
                javadoc_pattern = r'^\s*/\*\*'
                
                for i, line in enumerate(lines):
                    if re.search(func_class_pattern, line):
                        total_functions_classes += 1
                        # Check preceding lines for Javadoc
                        for j in range(max(0, i - 5), i):
                            if re.search(javadoc_pattern, lines[j]):
                                documented_functions_classes += 1
                                break
            
            if total_functions_classes == 0:
                return 1.0  # No functions/classes found, assume 100% coverage
            
            return documented_functions_classes / total_functions_classes
            
        except Exception:
            return 0.0
    
    async def _analyze_dependencies(self, repo, files_to_analyze: List[Dict[str, Any]]) -> Optional[DependencyAnalysis]:
        """Analyze project dependencies"""
        try:
            dependency_analysis = DependencyAnalysis()
            
            # Look for dependency files
            dependency_files = {
                'package.json': self._analyze_npm_dependencies,
                'requirements.txt': self._analyze_pip_dependencies,
                'Pipfile': self._analyze_pipenv_dependencies,
                'pom.xml': self._analyze_maven_dependencies,
                'build.gradle': self._analyze_gradle_dependencies,
                'Gemfile': self._analyze_ruby_dependencies,
                'composer.json': self._analyze_composer_dependencies,
                'go.mod': self._analyze_go_dependencies
            }
            
            for file_info in files_to_analyze:
                file_path = file_info['path']
                filename = Path(file_path).name
                
                if filename in dependency_files:
                    try:
                        file_content = repo.get_contents(file_path)
                        self._api_calls_made += 1
                        
                        if file_content.encoding == 'base64':
                            content = base64.b64decode(file_content.content).decode('utf-8', errors='ignore')
                        else:
                            content = file_content.content
                        
                        analyzer = dependency_files[filename]
                        file_dependencies = analyzer(content)
                        
                        # Merge dependencies
                        if file_dependencies.get('direct'):
                            dependency_analysis.direct_dependencies.update(file_dependencies['direct'])
                        if file_dependencies.get('dev'):
                            dependency_analysis.dev_dependencies.update(file_dependencies['dev'])
                        
                    except Exception as e:
                        self.logger.warning(f"Error analyzing dependency file {file_path}: {str(e)}")
            
            # Analyze dependency vulnerabilities (simplified)
            await self._check_vulnerable_dependencies(dependency_analysis)
            
            # Check for outdated dependencies (simplified)
            await self._check_outdated_dependencies(dependency_analysis)
            
            return dependency_analysis
            
        except Exception as e:
            self.logger.error(f"Error in dependency analysis: {str(e)}")
            return None
    
    def _analyze_npm_dependencies(self, content: str) -> Dict[str, Dict[str, str]]:
        """Analyze npm package.json dependencies"""
        try:
            package_data = json.loads(content)
            return {
                'direct': package_data.get('dependencies', {}),
                'dev': package_data.get('devDependencies', {})
            }
        except Exception:
            return {'direct': {}, 'dev': {}}
    
    def _analyze_pip_dependencies(self, content: str) -> Dict[str, Dict[str, str]]:
        """Analyze Python requirements.txt dependencies"""
        dependencies = {}
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                if '==' in line:
                    name, version = line.split('==', 1)
                    dependencies[name.strip()] = version.strip()
                else:
                    dependencies[line] = 'latest'
        
        return {'direct': dependencies, 'dev': {}}
    
    def _analyze_pipenv_dependencies(self, content: str) -> Dict[str, Dict[str, str]]:
        """Analyze Python Pipfile dependencies"""
        try:
            # Simple TOML-like parsing for Pipfile
            lines = content.split('\n')
            in_packages = False
            in_dev_packages = False
            direct_deps = {}
            dev_deps = {}
            
            for line in lines:
                line = line.strip()
                if line == '[packages]':
                    in_packages = True
                    in_dev_packages = False
                elif line == '[dev-packages]':
                    in_packages = False
                    in_dev_packages = True
                elif line.startswith('['):
                    in_packages = False
                    in_dev_packages = False
                elif '=' in line and (in_packages or in_dev_packages):
                    name, version = line.split('=', 1)
                    name = name.strip()
                    version = version.strip().strip('"\'')
                    
                    if in_packages:
                        direct_deps[name] = version
                    elif in_dev_packages:
                        dev_deps[name] = version
            
            return {'direct': direct_deps, 'dev': dev_deps}
        except Exception:
            return {'direct': {}, 'dev': {}}
    
    def _analyze_maven_dependencies(self, content: str) -> Dict[str, Dict[str, str]]:
        """Analyze Maven pom.xml dependencies"""
        dependencies = {}
        try:
            # Simple XML parsing for Maven dependencies
            import xml.etree.ElementTree as ET
            root = ET.fromstring(content)
            
            # Find dependencies in XML
            for dependency in root.findall('.//dependency'):
                group_id = dependency.find('groupId')
                artifact_id = dependency.find('artifactId')
                version = dependency.find('version')
                
                if group_id is not None and artifact_id is not None:
                    name = f"{group_id.text}:{artifact_id.text}"
                    ver = version.text if version is not None else 'latest'
                    dependencies[name] = ver
            
            return {'direct': dependencies, 'dev': {}}
        except Exception:
            return {'direct': {}, 'dev': {}}
    
    def _analyze_gradle_dependencies(self, content: str) -> Dict[str, Dict[str, str]]:
        """Analyze Gradle build.gradle dependencies"""
        dependencies = {}
        
        # Simple regex-based parsing for Gradle dependencies
        dep_pattern = r'(?:implementation|compile|api)\s+["\']([^"\']+):[^"\']+:([^"\']+)["\']'
        matches = re.findall(dep_pattern, content)
        
        for group_artifact, version in matches:
            dependencies[group_artifact] = version
        
        return {'direct': dependencies, 'dev': {}}
    
    def _analyze_ruby_dependencies(self, content: str) -> Dict[str, Dict[str, str]]:
        """Analyze Ruby Gemfile dependencies"""
        dependencies = {}
        
        # Simple regex-based parsing for Gemfile
        gem_pattern = r"gem\s+['\"]([^'\"]+)['\"](?:,\s*['\"]([^'\"]+)['\"])?"
        matches = re.findall(gem_pattern, content)
        
        for name, version in matches:
            dependencies[name] = version or 'latest'
        
        return {'direct': dependencies, 'dev': {}}
    
    def _analyze_composer_dependencies(self, content: str) -> Dict[str, Dict[str, str]]:
        """Analyze PHP composer.json dependencies"""
        try:
            composer_data = json.loads(content)
            return {
                'direct': composer_data.get('require', {}),
                'dev': composer_data.get('require-dev', {})
            }
        except Exception:
            return {'direct': {}, 'dev': {}}
    
    def _analyze_go_dependencies(self, content: str) -> Dict[str, Dict[str, str]]:
        """Analyze Go go.mod dependencies"""
        dependencies = {}
        
        # Simple parsing for go.mod
        require_pattern = r'require\s+([^\s]+)\s+([^\s]+)'
        matches = re.findall(require_pattern, content)
        
        for name, version in matches:
            dependencies[name] = version
        
        return {'direct': dependencies, 'dev': {}}
    
    async def _check_vulnerable_dependencies(self, dependency_analysis: DependencyAnalysis) -> None:
        """Check for vulnerable dependencies (simplified implementation)"""
        # This is a simplified implementation. In production, you would integrate
        # with vulnerability databases like Snyk, GitHub Advisory Database, etc.
        
        known_vulnerabilities = {
            # Example vulnerabilities
            'lodash': {'versions': ['<4.17.12'], 'severity': 'high', 'cve': 'CVE-2019-10744'},
            'axios': {'versions': ['<0.21.1'], 'severity': 'medium', 'cve': 'CVE-2020-28168'},
            'django': {'versions': ['<2.2.24'], 'severity': 'high', 'cve': 'CVE-2021-33203'},
            'flask': {'versions': ['<1.1.4'], 'severity': 'medium', 'cve': 'CVE-2021-23385'}
        }
        
        all_dependencies = {**dependency_analysis.direct_dependencies, **dependency_analysis.dev_dependencies}
        
        for dep_name, dep_version in all_dependencies.items():
            if dep_name in known_vulnerabilities:
                vuln_info = known_vulnerabilities[dep_name]
                # Simplified version check
                vulnerability = {
                    'name': dep_name,
                    'current_version': dep_version,
                    'vulnerable_versions': vuln_info['versions'],
                    'severity': vuln_info['severity'],
                    'cve': vuln_info['cve'],
                    'recommendation': f'Update {dep_name} to the latest secure version'
                }
                dependency_analysis.vulnerable_dependencies.append(vulnerability)
    
    async def _check_outdated_dependencies(self, dependency_analysis: DependencyAnalysis) -> None:
        """Check for outdated dependencies (simplified implementation)"""
        # This is a simplified implementation. In production, you would query
        # package registries to check for latest versions
        
        # Example outdated packages
        example_outdated = ['lodash', 'react', 'django', 'express']
        
        all_dependencies = {**dependency_analysis.direct_dependencies, **dependency_analysis.dev_dependencies}
        
        for dep_name in all_dependencies:
            if dep_name in example_outdated:
                outdated_info = {
                    'name': dep_name,
                    'current_version': all_dependencies[dep_name],
                    'latest_version': 'latest',  # Would be fetched from registry
                    'recommendation': f'Consider updating {dep_name} to the latest version'
                }
                dependency_analysis.outdated_dependencies.append(outdated_info)
    
    async def _analyze_security(self, repo, files_to_analyze: List[Dict[str, Any]]) -> Optional[SecurityAnalysis]:
        """Perform comprehensive security analysis"""
        try:
            security_analysis = SecurityAnalysis()
            
            all_security_issues = []
            secrets_found = []
            
            # Analyze each file for security issues
            for file_info in files_to_analyze:
                try:
                    file_content = repo.get_contents(file_info['path'])
                    self._api_calls_made += 1
                    
                    if file_content.encoding == 'base64':
                        content = base64.b64decode(file_content.content).decode('utf-8', errors='ignore')
                    else:
                        content = file_content.content
                    
                    # Detect security issues
                    file_security_issues = self._detect_security_issues(content, file_info['path'])
                    all_security_issues.extend(file_security_issues)
                    
                    # Separate secrets from other security issues
                    for issue in file_security_issues:
                        if issue['type'] == 'secret_exposure':
                            secrets_found.append({
                                'file_path': file_info['path'],
                                'secret_type': issue['secret_type'],
                                'line_number': issue['line_number'],
                                'severity': issue['severity']
                            })
                
                except Exception as e:
                    self.logger.warning(f"Error analyzing security for {file_info['path']}: {str(e)}")
            
            # Categorize vulnerabilities by severity
            for issue in all_security_issues:
                severity = issue['severity']
                if severity == 'critical':
                    security_analysis.critical_vulnerabilities.append(issue)
                elif severity == 'high':
                    security_analysis.high_vulnerabilities.append(issue)
                elif severity == 'medium':
                    security_analysis.medium_vulnerabilities.append(issue)
                elif severity == 'low':
                    security_analysis.low_vulnerabilities.append(issue)
            
            security_analysis.secrets_detected = secrets_found
            
            # Calculate security score
            total_issues = len(all_security_issues)
            critical_weight = len(security_analysis.critical_vulnerabilities) * 10
            high_weight = len(security_analysis.high_vulnerabilities) * 5
            medium_weight = len(security_analysis.medium_vulnerabilities) * 2
            low_weight = len(security_analysis.low_vulnerabilities) * 1
            
            penalty_score = critical_weight + high_weight + medium_weight + low_weight
            security_analysis.security_score = max(0.0, 10.0 - (penalty_score * 0.1))
            
            # Generate recommendations
            if security_analysis.critical_vulnerabilities:
                security_analysis.recommendations.append("Address critical vulnerabilities immediately")
            if security_analysis.secrets_detected:
                security_analysis.recommendations.append("Remove or secure exposed secrets")
            if security_analysis.high_vulnerabilities:
                security_analysis.recommendations.append("Fix high-severity security issues")
            
            # Basic compliance check
            security_analysis.compliance_status = {
                'has_security_policy': False,  # Would check for SECURITY.md
                'secrets_exposed': len(secrets_found) > 0,
                'critical_vulnerabilities': len(security_analysis.critical_vulnerabilities) > 0,
                'overall_compliant': (
                    len(security_analysis.critical_vulnerabilities) == 0 and 
                    len(secrets_found) == 0
                )
            }
            
            return security_analysis
            
        except Exception as e:
            self.logger.error(f"Error in security analysis: {str(e)}")
            return None
    
    async def _analyze_architecture(self, files_to_analyze: List[Dict[str, Any]], primary_language: Optional[str]) -> Optional[ArchitectureAnalysis]:
        """Analyze software architecture patterns and metrics"""
        try:
            architecture_analysis = ArchitectureAnalysis()
            
            # Detect common architectural patterns based on file structure
            file_paths = [f['path'] for f in files_to_analyze]
            
            # Pattern detection
            patterns = []
            
            # MVC Pattern
            if any('model' in path.lower() for path in file_paths) and \
               any('view' in path.lower() for path in file_paths) and \
               any('controller' in path.lower() for path in file_paths):
                patterns.append('MVC')
            
            # Microservices Pattern
            if any('service' in path.lower() for path in file_paths) and \
               len([p for p in file_paths if 'api' in p.lower()]) > 1:
                patterns.append('Microservices')
            
            # Layered Architecture
            layers = ['controller', 'service', 'repository', 'model', 'entity']
            found_layers = sum(1 for layer in layers if any(layer in path.lower() for path in file_paths))
            if found_layers >= 3:
                patterns.append('Layered Architecture')
            
            # Repository Pattern
            if any('repository' in path.lower() for path in file_paths):
                patterns.append('Repository Pattern')
            
            # Factory Pattern
            if any('factory' in path.lower() for path in file_paths):
                patterns.append('Factory Pattern')
            
            # Singleton Pattern (simple detection)
            if any('singleton' in path.lower() for path in file_paths):
                patterns.append('Singleton Pattern')
             repository health
            await self._analyze_repository_health(repo, result)
            
            # Get file contents for analysis
            files_to_analyze = await self._get_files_for_analysis(repo, branch)
            result.files_analyzed = len(files_to_analyze)
            
            # Perform file-level analysis
            if analysis_type in [AnalysisType.COMPREHENSIVE, AnalysisType.CODE_QUALITY]:
                await self._analyze_files(repo, files_to_analyze, result)
            
            # Perform dependency analysis
            if analysis_type in [AnalysisType.COMPREHENSIVE, AnalysisType.DEPENDENCIES]:
                result.dependency_analysis = await self._analyze_dependencies(repo, files_to_analyze)
            
            # Perform security analysis
            if analysis_type in [AnalysisType.COMPREHENSIVE, AnalysisType.SECURITY_FOCUSED]:
                result.security_analysis = await self._analyze_security(repo, files_to_analyze)
            
            # Perform architecture analysis
            if analysis_type in [AnalysisType.COMPREHENSIVE, AnalysisType.ARCHITECTURE]:
                result.architecture_analysis = await self._analyze_architecture(files_to_analyze, result.primary_language)
            
            # Calculate quality scores
            self._calculate_quality_scores(result)
            
            # AI-powered analysis and insights
            if include_ai_analysis and self.ai_manager:
                await self._generate_ai_insights(result)
            
            # Calculate analysis duration
            result.analysis_duration_seconds = time.time() - self._analysis_start_time
            
            # Cache the result
            if self.cache_manager:
                await self.cache_manager.set(
                    cache_key,
                    json.dumps(result.to_dict(), default=str),
                    ttl=3600  # Cache for 1 hour
                )
            
            # Record metrics
            if self.metrics_collector:
                await self.metrics_collector.record_metric(
                    "github_analysis_completed",
                    {
                        "repository": f"{owner}/{repo_name}",
                        "analysis_type": analysis_type.value,
                        "duration": result.analysis_duration_seconds,
                        "files_analyzed": result.files_analyzed,
                        "api_calls": self._api_calls_made
                    }
                )
            
            self.logger.info(f"Repository analysis completed: {repository_url} ({result.analysis_duration_seconds:.2f}s)")
            return result
            
        except Exception as e:
            self.logger.error(f"Repository analysis failed for {repository_url}: {str(e)}")
            raise YMERAException(f"Repository analysis failed: {str(e)}")
    
    def _parse_repository_url(self, url: str) -> Tuple[str, str]:
        """Parse GitHub repository URL to extract owner and repository name"""
        parsed = urlparse(url)
        
        if parsed.hostname != 'github.com':
            raise ValueError("Invalid GitHub repository URL")
        
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) < 2:
            raise ValueError("Invalid GitHub repository URL format")
        
        owner = path_parts[0]
        repo_name = path_parts[1].replace('.git', '')
        
        return owner, repo_name
    
    async def _analyze_repository_health(self, repo, result: RepositoryAnalysisResult) -> None:
        """Analyze repository health indicators"""
        try:
            # Check for standard files
            contents = repo.get_contents("")
            self._api_calls_made += 1
            
            file_names = {content.name.lower() for content in contents}
            
            result.has_readme = any(name.startswith('readme') for name in file_names)
            result.has_license = 'license' in file_names or 'license.txt' in file_names
            result.has_contributing = any('contributing' in name for name in file_names)
            result.has_code_of_conduct = any('code_of_conduct' in name or 'code-of-conduct' in name for name in file_names)
            result.has_security_policy = any('security' in name for name in file_names)
            
            # Check for CI/CD
            try:
                github_dir = repo.get_contents(".github")
                self._api_calls_made += 1
                github_files = [item.name.lower() for item in github_dir]
                result.has_ci_cd = any('workflow' in name for name in github_files) or 'main.yml' in github_files or 'ci.yml' in github_files
            except:
                # Check for other CI files
                result.has_ci_cd = any(name in file_names for name in ['.travis.yml', '.circleci', 'jenkinsfile', '.gitlab-ci.yml'])
            
            # Check for tests
            result.has_tests = any(
                'test' in name or 'spec' in name 
                for name in file_names
            )
            
            # Check for documentation
            result.has_documentation = any(
                name in file_names 
                for name in ['docs', 'documentation', 'doc']
            ) or result.has_readme
            
        except Exception as e:
            self.logger.warning(f"Error analyzing repository health: {str(e)}")
    
    async def _get_files_for_analysis(self, repo, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of files to analyze from the repository"""
        files_to_analyze = []
        
        try:
            # Get repository tree
            tree = repo.get_git_tree(branch or repo.default_branch, recursive=True)
            self._api_calls_made += 1
            
            for item in tree.tree:
                if item.type == 'blob':  # It's a file
                    file_path = item.path
                    file_size = item.size or 0
                    
                    # Skip files that are too large
                    if file_size > self.max_file_size_kb * 1024:
                        continue
                    
                    # Check if file extension is supported
                    file_ext = Path(file_path).suffix.lower()
                    if file_ext in self.supported_languages or self._is_text_file(file_path):
                        files_to_analyze.append({
                            'path': file_path,
                            'size': file_size,
                            'sha': item.sha,
                            'url': item.url
                        })
                    
                    # Limit number of files to prevent excessive processing
                    if len(files_to_analyze) >= self.max_files_per_analysis:
                        break
            
            self.logger.info(f"Selected {len(files_to_analyze)} files for analysis")
            return files_to_analyze
            
        except Exception as e:
            self.logger.error(f"Error getting files for analysis: {str(e)}")
            return []
    
    def _is_text_file(self, file_path: str) -> bool:
        """Check if file is a text file worth analyzing"""
        text_extensions = {
            '.md', '.txt', '.rst', '.cfg', '.ini', '.conf',
            '.xml', '.html', '.css', '.sql', '.gitignore',
            '.env', '.example', '.sample'
        }
        
        file_ext = Path(file_path).suffix.lower()
        filename = Path(file_path).name.lower()
        
        return (
            file_ext in text_extensions or
            filename in ['makefile', 'dockerfile', 'readme', 'changelog', 'license'] or
            file_path.startswith('.github/')
        )
    
    async def _analyze_files(self, repo, files_to_analyze: List[Dict[str, Any]], result: RepositoryAnalysisResult) -> None:
        """Analyze individual files in the repository"""
        semaphore = asyncio.Semaphore(10)  # Limit concurrent file analysis
        
        async def analyze_single_file(file_info: Dict[str, Any]) -> Optional[FileAnalysis]:
            async with semaphore:
                return await self._analyze_single_file(repo, file_info)
        
        # Analyze files concurrently
        tasks = [analyze_single_file(file_info) for file_info in files_to_analyze]
        file_analyses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful analyses
        for analysis in file_analyses:
            if isinstance(analysis, FileAnalysis):
                result.file_analyses.append(analysis)
                result.lines_of_code_total += analysis.lines_of_code
            elif isinstance(analysis, Exception):
                self.logger.warning(f"File analysis failed: {str(analysis)}")
        
        self._files_processed = len(result.file_analyses)
    
    async def _analyze_single_file(self, repo, file_info: Dict[str, Any]) -> Optional[FileAnalysis]:
        """Analyze a single file"""
        try:
            # Get file content
            file_path = file_info['path']
            file_content = repo.get_contents(file_path)
            self._api_calls_made += 1
            
            if file_content.encoding == 'base64':
                content = base64.b64decode(file_content.content).decode('utf-8', errors='ignore')
            else:
                content = file_content.content
            
            lines = content.split('\n')
            
            # Determine file language
            file_ext = Path(file_path).suffix.lower()
            language = self.supported_languages.get(file_ext, RepositoryLanguage.UNKNOWN).value
            
            # Create file analysis
            analysis = FileAnalysis(
                path=file_path,
                language=language,
                size=file_info['size'],
                lines_of_code=len([line for line in lines if line.strip()]),
                complexity_score=self._calculate_complexity_score(content, language),
                last_modified=file_content.last_modified
            )
            
            # Analyze # Analyze code quality metrics
            analysis.code_quality = self._analyze_code_quality(content, language)
            
            # Detect security issues
            analysis.security_issues = self._detect_security_issues(content, file_path)
            
            # Calculate maintainability score
            analysis.maintainability_score = self._calculate_maintainability_score(content, language)
            
            # Analyze documentation coverage
            analysis.documentation_coverage = self._calculate_documentation_coverage(content, language)
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Error analyzing file {file_info['path']}: {str(e)}")
            return None
    
    def _calculate_complexity_score(self, content: str, language: str) -> float:
        """Calculate cyclomatic complexity score for the file"""
        try:
            complexity_keywords = {
                'python': ['if', 'elif', 'for', 'while', 'try', 'except', 'with', 'and', 'or'],
                'javascript': ['if', 'else', 'for', 'while', 'switch', 'case', 'try', 'catch', '&&', '||'],
                'typescript': ['if', 'else', 'for', 'while', 'switch', 'case', 'try', 'catch', '&&', '||'],
                'java': ['if', 'else', 'for', 'while', 'switch', 'case', 'try', 'catch', '&&', '||'],
                'csharp': ['if', 'else', 'for', 'while', 'switch', 'case', 'try', 'catch', '&&', '||'],
                'cpp': ['if', 'else', 'for', 'while', 'switch', 'case', 'try', 'catch', '&&', '||']
            }
            
            keywords = complexity_keywords.get(language.lower(), ['if', 'for', 'while'])
            
            lines = content.split('\n')
            total_complexity = 0
            
            for line in lines:
                line_lower = line.lower()
                for keyword in keywords:
                    total_complexity += line_lower.count(keyword)
            
            # Normalize by lines of code
            lines_of_code = len([line for line in lines if line.strip()])
            if lines_of_code == 0:
                return 0.0
            
            return min(10.0, total_complexity / lines_of_code * 10)
            
        except Exception:
            return 5.0  # Default complexity score
    
    def _analyze_code_quality(self, content: str, language: str) -> Dict[str, Any]:
        """Analyze code quality metrics for the file"""
        quality_metrics = {
            'code_smells': [],
            'duplications': 0,
            'technical_debt': 0.0,
            'quality_score': 10.0
        }
        
        try:
            lines = content.split('\n')
            
            # Detect code smells
            code_smells = []
            
            # Long method detection
            current_function_length = 0
            in_function = False
            
            for i, line in enumerate(lines):
                stripped_line = line.strip()
                
                # Function start detection (simplified)
                if any(keyword in stripped_line for keyword in ['def ', 'function ', 'public ', 'private ', 'protected ']):
                    in_function = True
                    current_function_length = 0
                elif in_function and (stripped_line == '' or not line.startswith(' ') and not line.startswith('\t')):
                    if current_function_length > 50:
                        code_smells.append({
                            'type': 'long_method',
                            'line': i - current_function_length,
                            'severity': 'medium',
                            'description': f'Method is too long ({current_function_length} lines)'
                        })
                    in_function = False
                    current_function_length = 0
                
                if in_function:
                    current_function_length += 1
                
                # Long line detection
                if len(line) > 120:
                    code_smells.append({
                        'type': 'long_line',
                        'line': i + 1,
                        'severity': 'low',
                        'description': f'Line is too long ({len(line)} characters)'
                    })
                
                # TODO comments
                if 'TODO' in stripped_line.upper() or 'FIXME' in stripped_line.upper():
                    code_smells.append({
                        'type': 'todo_comment',
                        'line': i + 1,
                        'severity': 'low',
                        'description': 'TODO or FIXME comment found'
                    })
            
            # Simple duplication detection
            line_hashes = {}
            duplications = 0
            
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and not stripped.startswith('//'):
                    line_hash = hash(stripped)
                    if line_hash in line_hashes:
                        duplications += 1
                    else:
                        line_hashes[line_hash] = i
            
            quality_metrics['code_smells'] = code_smells
            quality_metrics['duplications'] = duplications
            quality_metrics['technical_debt'] = len(code_smells) * 0.5 + duplications * 0.1
            
            # Calculate overall quality score
            penalty = len(code_smells) * 0.2 + duplications * 0.1
            quality_metrics['quality_score'] = max(0.0, 10.0 - penalty)
            
            return quality_metrics
            
        except Exception as e:
            self.logger.warning(f"Error analyzing code quality: {str(e)}")
            return quality_metrics
    
    def _detect_security_issues(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Detect security issues in the file content"""
        security_issues = []
        
        try:
            lines = content.split('\n')
            
            # Security patterns to detect
            security_patterns = [
                {
                    'pattern': r'(?i)(password|pwd|pass)\s*[=:]\s*["\'][\w\d!@#$%^&*()]+["\']',
                    'type': 'hardcoded_password',
                    'severity': 'critical',
                    'secret_type': 'password'
                },
                {
                    'pattern': r'(?i)(api[_-]?key|apikey|access[_-]?key)\s*[=:]\s*["\'][A-Za-z0-9+/=]{20,}["\']',
                    'type': 'secret_exposure',
                    'severity': 'high',
                    'secret_type': 'api_key'
                },
                {
                    'pattern': r'(?i)(secret[_-]?key|secretkey)\s*[=:]\s*["\'][A-Za-z0-9+/=]{20,}["\']',
                    'type': 'secret_exposure',
                    'severity': 'high',
                    'secret_type': 'secret_key'
                },
                {
                    'pattern': r'(?i)(token)\s*[=:]\s*["\'][A-Za-z0-9+/=]{20,}["\']',
                    'type': 'secret_exposure',
                    'severity': 'high',
                    'secret_type': 'token'
                },
                {
                    'pattern': r'(?i)(private[_-]?key)\s*[=:]\s*["\'][\w\W]*["\']',
                    'type': 'secret_exposure',
                    'severity': 'critical',
                    'secret_type': 'private_key'
                },
                {
                    'pattern': r'(?i)eval\s*\(',
                    'type': 'code_injection',
                    'severity': 'high',
                    'secret_type': None
                },
                {
                    'pattern': r'(?i)exec\s*\(',
                    'type': 'code_injection',
                    'severity': 'high',
                    'secret_type': None
                },
                {
                    'pattern': r'(?i)shell_exec\s*\(',
                    'type': 'command_injection',
                    'severity': 'high',
                    'secret_type': None
                },
                {
                    'pattern': r'(?i)system\s*\(',
                    'type': 'command_injection',
                    'severity': 'medium',
                    'secret_type': None
                },
                {
                    'pattern': r'(?i)md5\s*\(',
                    'type': 'weak_crypto',
                    'severity': 'medium',
                    'secret_type': None
                },
                {
                    'pattern': r'(?i)sha1\s*\(',
                    'type': 'weak_crypto',
                    'severity': 'medium',
                    'secret_type': None
                }
            ]
            
            for i, line in enumerate(lines):
                for pattern_info in security_patterns:
                    matches = re.finditer(pattern_info['pattern'], line)
                    for match in matches:
                        issue = {
                            'type': pattern_info['type'],
                            'severity': pattern_info['severity'],
                            'line_number': i + 1,
                            'file_path': file_path,
                            'description': self._get_security_issue_description(pattern_info['type']),
                            'recommendation': self._get_security_recommendation(pattern_info['type'])
                        }
                        
                        if pattern_info['secret_type']:
                            issue['secret_type'] = pattern_info['secret_type']
                        
                        security_issues.append(issue)
            
            return security_issues
            
        except Exception as e:
            self.logger.warning(f"Error detecting security issues: {str(e)}")
            return []
    
    def _get_security_issue_description(self, issue_type: str) -> str:
        """Get description for security issue type"""
        descriptions = {
            'hardcoded_password': 'Hardcoded password detected in source code',
            'secret_exposure': 'Sensitive secret or credential exposed in source code',
            'code_injection': 'Potential code injection vulnerability detected',
            'command_injection': 'Potential command injection vulnerability detected',
            'weak_crypto': 'Weak cryptographic algorithm usage detected'
        }
        return descriptions.get(issue_type, 'Security issue detected')
    
    def _get_security_recommendation(self, issue_type: str) -> str:
        """Get recommendation for security issue type"""
        recommendations = {
            'hardcoded_password': 'Use environment variables or secure credential management',
            'secret_exposure': 'Move secrets to environment variables or secure vault',
            'code_injection': 'Validate and sanitize input, avoid dynamic code execution',
            'command_injection': 'Use parameterized commands and input validation',
            'weak_crypto': 'Use stronger cryptographic algorithms like SHA-256 or bcrypt'
        }
        return recommendations.get(issue_type, 'Review and remediate security issue')
    
    def _calculate_maintainability_score(self, content: str, language: str) -> float:
        """Calculate maintainability score based on various metrics"""
        try:
            lines = content.split('\n')
            total_lines = len(lines)
            code_lines = len([line for line in lines if line.strip()])
            
            if code_lines == 0:
                return 10.0
            
            # Calculate comment ratio
            comment_lines = 0
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('/*'):
                    comment_lines += 1
            
            comment_ratio = comment_lines / code_lines if code_lines > 0 else 0
            
            # Calculate average line length
            non_empty_lines = [line for line in lines if line.strip()]
            avg_line_length = sum(len(line) for line in non_empty_lines) / len(non_empty_lines) if non_empty_lines else 0
            
            # Calculate function count (simplified)
            function_count = len(re.findall(r'(?i)(def |function |public |private |protected )', content))
            
            # Maintainability scoring
            score = 10.0
            
            # Penalize low comment ratio
            if comment_ratio < 0.1:
                score -= 2.0
            elif comment_ratio < 0.2:
                score -= 1.0
            
            # Penalize long lines
            if avg_line_length > 120:
                score -= 1.5
            elif avg_line_length > 100:
                score -= 0.5
            
            # Penalize very long files
            if code_lines > 500:
                score -= 2.0
            elif code_lines > 300:
                score -= 1.0
            
            # Bonus for reasonable function density
            if function_count > 0:
                lines_per_function = code_lines / function_count
                if 10 <= lines_per_function <= 50:
                    score += 0.5
            
            return max(0.0, min(10.0, score))
            
        except Exception:
            return 5.0  # Default score
    
    def _calculate_documentation_coverage(self, content: str, language: str) -> float:
        """Calculate documentation coverage score"""
        try:
            lines = content.split('\n')
            
            # Count functions/methods
            function_patterns = {
                'python': r'^\s*def\s+\w+',
                'javascript': r'^\s*function\s+\w+|^\s*\w+\s*:\s*function',
                'typescript': r'^\s*function\s+\w+|^\s*\w+\s*\([^)]*\)\s*:\s*\w+\s*=>',
                'java': r'^\s*(public|private|protected).*\w+\s*\([^)]*\)\s*\{',
                'csharp': r'^\s*(public|private|protected|internal).*\w+\s*\([^)]*\)',
                'cpp': r'^\s*\w+\s+\w+\s*\([^)]*\)\s*\{'
            }
            
            pattern = function_patterns.get(language.lower(), r'^\s*def\s+\w+|^\s*function\s+\w+')
            functions = re.findall(pattern, content, re.MULTILINE)
            
            if not functions:
                return 10.0  # No functions to document
            
            # Count documented functions (simplified)
            documented_functions = 0
            function_lines = []
            
            for i, line in enumerate(lines):
                if re.match(pattern, line):
                    function_lines.append(i)
            
            # Check if functions have documentation
            for func_line in function_lines:
                # Look for documentation before or after function definition
                doc_found = False
                
                # Check lines before function
                for j in range(max(0, func_line - 3), func_line):
                    if j < len(lines):
                        line = lines[j].strip()
                        if (line.startswith('"""') or line.startswith("'''") or 
                            line.startswith('/*') or line.startswith('//')):
                            doc_found = True
                            break
                
                # Check lines after function
                if not doc_found:
                    for j in range(func_line + 1, min(len(lines), func_line + 4)):
                        line = lines[j].strip()
                        if (line.startswith('"""') or line.startswith("'''") or 
                            line.startswith('/*') or line.startswith('//')):
                            doc_found = True
                            break
                
                if doc_found:
                    documented_functions += 1
            
            coverage = (documented_functions / len(functions)) * 100 if functions else 100
            return min(100.0, coverage)
            
        except Exception:
            return 50.0  # Default coverage
    
    def _calculate_quality_scores(self, result: RepositoryAnalysisResult) -> None:
        """Calculate overall quality scores for the repository"""
        try:
            if not result.file_analyses:
                result.overall_quality_score = 5.0
                return
            
            # Calculate average complexity
            complexities = [fa.complexity_score for fa in result.file_analyses if fa.complexity_score is not None]
            result.average_complexity = sum(complexities) / len(complexities) if complexities else 5.0
            
            # Calculate average maintainability
            maintainability_scores = [fa.maintainability_score for fa in result.file_analyses if fa.maintainability_score is not None]
            result.average_maintainability = sum(maintainability_scores) / len(maintainability_scores) if maintainability_scores else 5.0
            
            # Calculate documentation coverage
            doc_coverages = [fa.documentation_coverage for fa in result.file_analyses if fa.documentation_coverage is not None]
            result.documentation_coverage = sum(doc_coverages) / len(doc_coverages) if doc_coverages else 50.0
            
            # Calculate overall quality score
            base_score = 10.0
            
            # Health indicators impact
            health_score = 0
            if result.has_readme:
                health_score += 1
            if result.has_license:
                health_score += 0.5
            if result.has_tests:
                health_score += 1.5
            if result.has_ci_cd:
                health_score += 1
            if result.has_documentation:
                health_score += 0.5
            if result.has_contributing:
                health_score += 0.5
            
            # Complexity impact (lower is better)
            complexity_penalty = max(0, (result.average_complexity - 5.0) * 0.3)
            
            # Maintainability impact
            maintainability_bonus = (result.average_maintainability - 5.0) * 0.2
            
            # Documentation impact
            doc_bonus = (result.documentation_coverage - 50.0) / 50.0
            
            # Security impact
            security_penalty = 0
            if result.security_analysis:
                security_penalty = (
                    len(result.security_analysis.critical_vulnerabilities) * 2.0 +
                    len(result.security_analysis.high_vulnerabilities) * 1.0 +
                    len(result.security_analysis.medium_vulnerabilities) * 0.5 +
                    len(result.security_analysis.low_vulnerabilities) * 0.1
                )
            
            # Calculate final score
            result.overall_quality_score = max(0.0, min(10.0, 
                base_score + health_score + maintainability_bonus + doc_bonus - complexity_penalty - security_penalty
            ))
            
        except Exception as e:
            self.logger.warning(f"Error calculating quality scores: {str(e)}")
            result.overall_quality_score = 5.0
    
    async def _generate_ai_insights(self, result: RepositoryAnalysisResult) -> None:
        """Generate AI-powered insights and recommendations"""
        try:
            if not self.ai_manager:
                return
            
            # Prepare context for AI analysis
            context = {
                'repository_info': {
                    'name': result.repository_name,
                    'language': result.primary_language,
                    'stars': result.stars_count,
                    'forks': result.forks_count,
                    'size': result.repository_size_kb
                },
                'health_metrics': {
                    'has_readme': result.has_readme,
                    'has_license': result.has_license,
                    'has_tests': result.has_tests,
                    'has_ci_cd': result.has_ci_cd
                },
                'quality_metrics': {
                    'overall_score': result.overall_quality_score,
                    'complexity': result.average_complexity,
                    'maintainability': result.average_maintainability,
                    'documentation_coverage': result.documentation_coverage
                }
            }
            
            # Add security context if available
            if result.security_analysis:
                context['security_metrics'] = {
                    'security_score': result.security_analysis.security_score,
                    'critical_vulnerabilities': len(result.security_analysis.critical_vulnerabilities),
                    'high_vulnerabilities': len(result.security_analysis.high_vulnerabilities),
                    'secrets_detected': len(result.security_analysis.secrets_detected)
                }
            
            # Generate insights
            insights = await self.ai_manager.generate_repository_insights(context)
            if insights:
                result.ai_insights = insights
                
        except Exception as e:
            self.logger.warning(f"Error generating AI insights: {str(e)}")
    
    async def get_analysis_status(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of an ongoing analysis"""
        # This would be implemented with a task queue system in production
        return {
            'analysis_id': analysis_id,
            'status': 'completed',
            'progress': 100,
            'files_processed': self._files_processed,
            'api_calls_made': self._api_calls_made,
            'estimated_completion': None
        }
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported programming languages"""
        return {ext: lang.value for ext, lang in self.supported_languages.items()}
    
    def get_analysis_limits(self) -> Dict[str, int]:
        """Get current analysis limits"""
        return {
            'max_files_per_analysis': self.max_files_per_analysis,
            'max_file_size_kb': self.max_file_size_kb,
            'rate_limit_per_hour': self.rate_limit_per_hour
        }