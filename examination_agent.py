“””
AI-Native Development Environment - Examination Agent
Code analysis, architecture review, and quality assessment
“””

import asyncio
import ast
import json
import logging
import re
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import subprocess
import hashlib

from base_agent import BaseAgent, AgentCapability, TaskPriority

# Configure logging

logger = logging.getLogger(**name**)

@dataclass
class CodeAnalysis:
file_path: str
language: str
lines_of_code: int
complexity_score: float
quality_metrics: Dict[str, Any]
security_issues: List[Dict[str, Any]]
performance_insights: List[str]
architecture_patterns: List[str]
dependencies: List[str]
test_coverage: float
maintainability_index: float
technical_debt: List[Dict[str, Any]]

@dataclass
class ArchitectureAssessment:
project_structure: Dict[str, Any]
design_patterns: List[str]
coupling_analysis: Dict[str, float]
cohesion_metrics: Dict[str, float]
scalability_score: float
maintainability_score: float
recommendations: List[str]
anti_patterns: List[str]

class ExaminationAgent(BaseAgent):
“””
Examination Agent - Comprehensive code and architecture analysis
“””

```
def __init__(self):
    super().__init__(
        "examination",
        "AI-Native Code and Architecture Examiner",
        [
            AgentCapability.CODE_ANALYSIS,
            AgentCapability.ARCHITECTURE_REVIEW,
            AgentCapability.SECURITY_ASSESSMENT,
            AgentCapability.PERFORMANCE_ANALYSIS,
            AgentCapability.QUALITY_ASSURANCE
        ]
    )
    
    # Analysis tools and configurations
    self.supported_languages = {
        'python': ['.py'],
        'javascript': ['.js', '.ts', '.jsx', '.tsx'],
        'java': ['.java'],
        'csharp': ['.cs'],
        'cpp': ['.cpp', '.cc', '.cxx', '.c'],
        'go': ['.go'],
        'rust': ['.rs'],
        'php': ['.php'],
        'ruby': ['.rb'],
        'swift': ['.swift'],
        'kotlin': ['.kt']
    }
    
    # Quality thresholds
    self.quality_thresholds = {
        'complexity_max': 10,
        'maintainability_min': 70,
        'test_coverage_min': 80,
        'duplication_max': 5,
        'debt_ratio_max': 5
    }
    
    # Security patterns to detect
    self.security_patterns = {
        'sql_injection': [
            r'SELECT.*\+.*',
            r'INSERT.*\+.*',
            r'UPDATE.*\+.*',
            r'DELETE.*\+.*'
        ],
        'xss': [
            r'innerHTML.*\+',
            r'document\.write.*\+',
            r'eval\(',
            r'dangerouslySetInnerHTML'
        ],
        'hardcoded_secrets': [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'api_key\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
            r'token\s*=\s*["\'][^"\']+["\']'
        ],
        'weak_crypto': [
            r'md5\(',
            r'sha1\(',
            r'DES\(',
            r'RC4\('
        ]
    }
    
    # Performance anti-patterns
    self.performance_antipatterns = {
        'n_plus_one': r'for.*in.*:\s*.*\.get\(',
        'inefficient_loops': r'for.*in.*:\s*.*\.append\(.*\.pop\(',
        'string_concatenation': r'.*\+=.*str\(',
        'repeated_calculations': r'for.*in.*:.*math\.',
        'memory_leaks': r'while\s+True:.*(?!break).*$'
    }
    
    # Architecture patterns
    self.architecture_patterns = {
        'mvc': ['models', 'views', 'controllers'],
        'mvp': ['models', 'views', 'presenters'],
        'mvvm': ['models', 'views', 'viewmodels'],
        'repository': ['repository', 'repositories'],
        'factory': ['factory', 'factories'],
        'singleton': ['singleton'],
        'observer': ['observer', 'listeners', 'events'],
        'strategy': ['strategy', 'strategies'],
        'decorator': ['decorator', 'decorators'],
        'adapter': ['adapter', 'adapters']
    }
    
    logger.info("Examination Agent initialized")

async def examine_codebase(self, 
                         project_path: str,
                         include_architecture: bool = True,
                         include_security: bool = True,
                         include_performance: bool = True) -> Dict[str, Any]:
    """
    Comprehensive codebase examination
    """
    
    try:
        logger.info("Starting codebase examination", project_path=project_path)
        
        # Get all source files
        source_files = await self._discover_source_files(project_path)
        
        if not source_files:
            return {"error": "No source files found in project"}
        
        # Parallel analysis of files
        analysis_tasks = []
        for file_path in source_files:
            task = self._analyze_single_file(file_path)
            analysis_tasks.append(task)
        
        file_analyses = await asyncio.gather(*analysis_tasks, return_exceptions=True)
        
        # Filter successful analyses
        successful_analyses = [
            analysis for analysis in file_analyses 
            if isinstance(analysis, CodeAnalysis)
        ]
        
        # Generate project-wide metrics
        project_metrics = await self._generate_project_metrics(successful_analyses)
        
        # Architecture assessment if requested
        architecture_assessment = None
        if include_architecture:
            architecture_assessment = await self._assess_architecture(
                project_path, successful_analyses
            )
        
        # Security assessment if requested
        security_assessment = None
        if include_security:
            security_assessment = await self._assess_security(successful_analyses)
        
        # Performance assessment if requested
        performance_assessment = None
        if include_performance:
            performance_assessment = await self._assess_performance(successful_analyses)
        
        # Generate comprehensive report
        examination_report = {
            "project_path": project_path,
            "timestamp": datetime.utcnow().isoformat(),
            "files_analyzed": len(successful_analyses),
            "languages_detected": list(set(analysis.language for analysis in successful_analyses)),
            "project_metrics": project_metrics,
            "file_analyses": [self._serialize_analysis(analysis) for analysis in successful_analyses],
            "architecture_assessment": self._serialize_architecture_assessment(architecture_assessment) if architecture_assessment else None,
            "security_assessment": security_assessment,
            "performance_assessment": performance_assessment,
            "recommendations": await self._generate_recommendations(successful_analyses, architecture_assessment),
            "quality_score": await self._calculate_quality_score(successful_analyses),
            "next_steps": await self._suggest_next_steps(successful_analyses)
        }
        
        logger.info("Codebase examination completed", 
                   files_analyzed=len(successful_analyses),
                   quality_score=examination_report["quality_score"])
        
        return examination_report
        
    except Exception as e:
        logger.error("Codebase examination failed", error=str(e))
        return {"error": f"Examination failed: {str(e)}"}

async def _discover_source_files(self, project_path: str) -> List[str]:
    """Discover all source code files in project"""
    
    source_files = []
    
    # Get all supported extensions
    all_extensions = []
    for extensions in self.supported_languages.values():
        all_extensions.extend(extensions)
    
    # Walk through project directory
    for root, dirs, files in os.walk(project_path):
        # Skip common non-source directories
        dirs[:] = [d for d in dirs if d not in [
            '.git', '.svn', 'node_modules', '__pycache__', 
            '.pytest_cache', 'venv', 'env', 'build', 'dist'
        ]]
        
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file)
            
            if ext.lower() in all_extensions:
                source_files.append(file_path)
    
    return source_files

async def _analyze_single_file(self, file_path: str) -> CodeAnalysis:
    """Analyze a single source code file"""
    
    try:
        # Read file content
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Detect language
        language = self._detect_language(file_path)
        
        # Basic metrics
        lines = content.split('\n')
        lines_of_code = len([line for line in lines if line.strip() and not line.strip().startswith('#')])
        
        # Complexity analysis
        complexity_score = await self._calculate_complexity(content, language)
        
        # Quality metrics
        quality_metrics = await self._analyze_quality_metrics(content, language)
        
        # Security analysis
        security_issues = await self._analyze_security_issues(content, language)
        
        # Performance insights
        performance_insights = await self._analyze_performance(content, language)
        
        # Architecture patterns
        architecture_patterns = self._detect_architecture_patterns(content, file_path)
        
        # Dependencies
        dependencies = await self._extract_dependencies(content, language)
        
        # Test coverage (estimated)
        test_coverage = await self._estimate_test_coverage(file_path, content)
        
        # Maintainability index
        maintainability_index = await self._calculate_maintainability_index(
            content, complexity_score, lines_of_code
        )
        
        # Technical debt
        technical_debt = await self._analyze_technical_debt(content, language)
        
        return CodeAnalysis(
            file_path=file_path,
            language=language,
            lines_of_code=lines_of_code,
            complexity_score=complexity_score,
            quality_metrics=quality_metrics,
            security_issues=security_issues,
            performance_insights=performance_insights,
            architecture_patterns=architecture_patterns,
            dependencies=dependencies,
            test
```test_coverage=test_coverage,
maintainability_index=maintainability_index,
technical_debt=technical_debt
)

```
except Exception as e:
    logger.error(f"Failed to analyze file {file_path}: {str(e)}")
    # Return a minimal analysis for failed files
    return CodeAnalysis(
        file_path=file_path,
        language="unknown",
        lines_of_code=0,
        complexity_score=0.0,
        quality_metrics={},
        security_issues=[],
        performance_insights=[],
        architecture_patterns=[],
        dependencies=[],
        test_coverage=0.0,
        maintainability_index=0.0,
        technical_debt=[]
    )

def _detect_language(self, file_path: str) -> str:
    """Detect programming language from file extension"""
    
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    for language, extensions in self.supported_languages.items():
        if ext in extensions:
            return language
    
    return "unknown"

async def _calculate_complexity(self, content: str, language: str) -> float:
    """Calculate cyclomatic complexity"""
    
    complexity = 1  # Base complexity
    
    # Language-specific complexity patterns
    complexity_patterns = {
        'python': [r'\bif\b', r'\belif\b', r'\bfor\b', r'\bwhile\b', 
                  r'\bexcept\b', r'\band\b', r'\bor\b', r'\btry\b'],
        'javascript': [r'\bif\b', r'\belse if\b', r'\bfor\b', r'\bwhile\b',
                      r'\bcatch\b', r'\b&&\b', r'\b\|\|\b', r'\btry\b'],
        'java': [r'\bif\b', r'\belse if\b', r'\bfor\b', r'\bwhile\b',
                r'\bcatch\b', r'\b&&\b', r'\b\|\|\b', r'\btry\b'],
        'csharp': [r'\bif\b', r'\belse if\b', r'\bfor\b', r'\bwhile\b',
                  r'\bcatch\b', r'\b&&\b', r'\b\|\|\b', r'\btry\b']
    }
    
    patterns = complexity_patterns.get(language, complexity_patterns['python'])
    
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        complexity += len(matches)
    
    return min(complexity, 50)  # Cap at 50 for extreme cases

async def _analyze_quality_metrics(self, content: str, language: str) -> Dict[str, Any]:
    """Analyze code quality metrics"""
    
    lines = content.split('\n')
    total_lines = len(lines)
    blank_lines = len([line for line in lines if not line.strip()])
    comment_lines = 0
    
    # Language-specific comment patterns
    comment_patterns = {
        'python': [r'#.*$'],
        'javascript': [r'//.*$', r'/\*.*?\*/'],
        'java': [r'//.*$', r'/\*.*?\*/'],
        'csharp': [r'//.*$', r'/\*.*?\*/'],
        'cpp': [r'//.*$', r'/\*.*?\*/']
    }
    
    patterns = comment_patterns.get(language, comment_patterns['python'])
    
    for line in lines:
        for pattern in patterns:
            if re.search(pattern, line):
                comment_lines += 1
                break
    
    code_lines = total_lines - blank_lines - comment_lines
    
    # Calculate metrics
    comment_ratio = (comment_lines / total_lines * 100) if total_lines > 0 else 0
    code_density = (code_lines / total_lines * 100) if total_lines > 0 else 0
    
    # Code duplication estimation (simplified)
    lines_hash = {}
    duplicate_lines = 0
    for line in lines:
        line_clean = line.strip()
        if len(line_clean) > 10:  # Only check substantial lines
            line_hash = hashlib.md5(line_clean.encode()).hexdigest()
            if line_hash in lines_hash:
                duplicate_lines += 1
            lines_hash[line_hash] = True
    
    duplication_ratio = (duplicate_lines / code_lines * 100) if code_lines > 0 else 0
    
    return {
        "total_lines": total_lines,
        "code_lines": code_lines,
        "comment_lines": comment_lines,
        "blank_lines": blank_lines,
        "comment_ratio": round(comment_ratio, 2),
        "code_density": round(code_density, 2),
        "duplication_ratio": round(duplication_ratio, 2),
        "average_line_length": sum(len(line) for line in lines) / len(lines) if lines else 0
    }

async def _analyze_security_issues(self, content: str, language: str) -> List[Dict[str, Any]]:
    """Analyze potential security vulnerabilities"""
    
    security_issues = []
    
    for issue_type, patterns in self.security_patterns.items():
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                line_number = content[:match.start()].count('\n') + 1
                security_issues.append({
                    "type": issue_type,
                    "severity": self._get_security_severity(issue_type),
                    "line": line_number,
                    "description": self._get_security_description(issue_type),
                    "code_snippet": match.group(0)[:100],  # First 100 chars
                    "recommendation": self._get_security_recommendation(issue_type)
                })
    
    return security_issues

def _get_security_severity(self, issue_type: str) -> str:
    """Get severity level for security issue"""
    severity_map = {
        'sql_injection': 'HIGH',
        'xss': 'HIGH',
        'hardcoded_secrets': 'MEDIUM',
        'weak_crypto': 'MEDIUM'
    }
    return severity_map.get(issue_type, 'LOW')

def _get_security_description(self, issue_type: str) -> str:
    """Get description for security issue"""
    descriptions = {
        'sql_injection': 'Potential SQL injection vulnerability',
        'xss': 'Potential Cross-Site Scripting vulnerability',
        'hardcoded_secrets': 'Hardcoded sensitive information detected',
        'weak_crypto': 'Use of weak cryptographic algorithm'
    }
    return descriptions.get(issue_type, 'Security issue detected')

def _get_security_recommendation(self, issue_type: str) -> str:
    """Get recommendation for security issue"""
    recommendations = {
        'sql_injection': 'Use parameterized queries or prepared statements',
        'xss': 'Sanitize user input and use safe rendering methods',
        'hardcoded_secrets': 'Store secrets in environment variables or secure vaults',
        'weak_crypto': 'Use strong cryptographic algorithms (SHA-256, AES-256)'
    }
    return recommendations.get(issue_type, 'Review and remediate security issue')

async def _analyze_performance(self, content: str, language: str) -> List[str]:
    """Analyze potential performance issues"""
    
    performance_insights = []
    
    for antipattern_type, pattern in self.performance_antipatterns.items():
        if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
            insights = {
                'n_plus_one': 'Potential N+1 query problem detected',
                'inefficient_loops': 'Inefficient loop operations found',
                'string_concatenation': 'Inefficient string concatenation in loops',
                'repeated_calculations': 'Repeated calculations in loops detected',
                'memory_leaks': 'Potential memory leak in infinite loop'
            }
            performance_insights.append(insights.get(antipattern_type, f'{antipattern_type} detected'))
    
    # Add language-specific performance insights
    if language == 'python':
        if 'pandas' in content and '.apply(' in content:
            performance_insights.append('Consider vectorized operations instead of apply()')
        if 'for' in content and '.append(' in content:
            performance_insights.append('Consider list comprehensions for better performance')
    
    elif language == 'javascript':
        if 'document.getElementById' in content and 'for' in content:
            performance_insights.append('Cache DOM queries outside of loops')
        if '$.each' in content or 'forEach' in content:
            performance_insights.append('Consider using for...of loops for better performance')
    
    return performance_insights

def _detect_architecture_patterns(self, content: str, file_path: str) -> List[str]:
    """Detect architecture patterns in code"""
    
    detected_patterns = []
    file_name = os.path.basename(file_path).lower()
    dir_path = os.path.dirname(file_path).lower()
    
    # Pattern detection based on file structure and naming
    for pattern, indicators in self.architecture_patterns.items():
        for indicator in indicators:
            if (indicator in file_name or 
                indicator in dir_path or 
                indicator in content.lower()):
                if pattern not in detected_patterns:
                    detected_patterns.append(pattern)
    
    # Additional pattern detection based on code structure
    if re.search(r'class.*Factory', content):
        if 'factory' not in detected_patterns:
            detected_patterns.append('factory')
    
    if re.search(r'class.*Singleton', content):
        if 'singleton' not in detected_patterns:
            detected_patterns.append('singleton')
    
    if re.search(r'def notify|def update.*observer', content, re.IGNORECASE):
        if 'observer' not in detected_patterns:
            detected_patterns.append('observer')
    
    return detected_patterns

async def _extract_dependencies(self, content: str, language: str) -> List[str]:
    """Extract dependencies from source code"""
    
    dependencies = []
    
    # Language-specific import patterns
    import_patterns = {
        'python': [
            r'^\s*import\s+([^\s;]+)',
            r'^\s*from\s+([^\s;]+)\s+import'
        ],
        'javascript': [
            r'^\s*import.*from\s+["\']([^"\']+)["\']',
            r'^\s*require\(["\']([^"\']+)["\']\)',
            r'^\s*import\(["\']([^"\']+)["\']\)'
        ],
        'java': [
            r'^\s*import\s+([^\s;]+);'
        ],
        'csharp': [
            r'^\s*using\s+([^\s;]+);'
        ]
    }
    
    patterns = import_patterns.get(language, [])
    
    for pattern in patterns:
        matches = re.finditer(pattern, content, re.MULTILINE)
        for match in matches:
            dep = match.group(1).strip()
            if dep and dep not in dependencies:
                dependencies.append(dep)
    
    return dependencies

async def _estimate_test_coverage(self, file_path: str, content: str) -> float:
    """Estimate test coverage (simplified approach)"""
    
    # Check if this is a test file
    if any(indicator in file_path.lower() for indicator in ['test_', '_test', 'tests/']):
        return 100.0  # Test files have 100% "coverage"
    
    # Look for corresponding test files
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    dir_path = os.path.dirname(file_path)
    
    possible_test_files = [
        os.path.join(dir_path, f"test_{base_name}.py"),
        os.path.join(dir_path, f"{base_name}_test.py"),
        os.path.join(dir_path, "tests", f"test_{base_name}.py"),
        os.path.join(os.path.dirname(dir_path), "tests", f"test_{base_name}.py")
    ]
    
    test_file_exists = any(os.path.exists(test_file) for test_file in possible_test_files)
    
    if test_file_exists:
        # Simple heuristic: estimate coverage based on function count
        function_count = len(re.findall(r'def\s+\w+', content))
        if function_count > 0:
            return min(85.0, max(60.0, 100.0 / function_count * 5))  # Rough estimate
        return 75.0
    
    return 0.0  # No tests found

async def _calculate_maintainability_index(self, content: str, complexity: float, lines_of_code: int) -> float:
    """Calculate maintainability index (0-100 scale)"""
    
    # Simplified maintainability index calculation
    # Based on Halstead volume, cyclomatic complexity, and lines of code
    
    if lines_of_code == 0:
        return 0.0
    
    # Halstead metrics (simplified)
    operators = len(re.findall(r'[+\-*/=<>!&|]', content))
    operands = len(re.findall(r'\b\w+\b', content))
    
    if operators == 0 or operands == 0:
        halstead_volume = 1
    else:
        vocabulary = operators + operands
        length = len(re.findall(r'\S+', content))
        halstead_volume = length * (vocabulary.bit_length() if vocabulary > 0 else 1)
    
    # Maintainability Index formula (simplified)
    maintainability = max(0, 171 - 5.2 * complexity - 0.23 * (halstead_volume / 1000) - 16.2 * (lines_of_code / 1000))
    
    return min(100.0, max(0.0, maintainability))

async def _analyze_technical_debt(self, content: str, language: str) -> List[Dict[str, Any]]:
    """Analyze technical debt indicators"""
    
    technical_debt = []
    lines = content.split('\n')
    
    # Debt patterns
    debt_patterns = {
        'todo_fixme': r'(TODO|FIXME|HACK|XXX|BUG)[\s:]+(.+)',
        'long_methods': r'def\s+\w+.*:',
        'long_classes': r'class\s+\w+.*:',
        'magic_numbers': r'\b\d{2,}\b',
        'long_parameter_lists': r'def\s+\w+\([^)]{50,}\)'
    }
    
    for line_num, line in enumerate(lines, 1):
        # TODO/FIXME comments
        todo_match = re.search(debt_patterns['todo_fixme'], line, re.IGNORECASE)
        if todo_match:
            technical_debt.append({
                'type': 'todo_comment',
                'line': line_num,
                'severity': 'LOW',
                'description': f"TODO/FIXME comment: {todo_match.group(2).strip()}",
                'recommendation': 'Address the TODO/FIXME item or remove if no longer relevant'
            })
        
        # Magic numbers
        if re.search(debt_patterns['magic_numbers'], line):
            # Skip common acceptable numbers
            if not re.search(r'\b(0|1|2|10|100|1000)\b', line):
                technical_debt.append({
                    'type': 'magic_number',
                    'line': line_num,
                    'severity': 'LOW',
                    'description': 'Magic number detected',
                    'recommendation': 'Replace with named constant'
                })
        
        # Long parameter lists
        if re.search(debt_patterns['long_parameter_lists'], line):
            technical_debt.append({
                'type': 'long_parameter_list',
                'line': line_num,
                'severity': 'MEDIUM',
                'description': 'Method has too many parameters',
                'recommendation': 'Consider using parameter objects or breaking down the method'
            })
    
    # Detect long methods (simplified - count lines between def and next def/class)
    method_starts = []
    for line_num, line in enumerate(lines, 1):
        if re.match(r'\s*def\s+\w+', line):
            method_starts.append(line_num)
    
    for i, start_line in enumerate(method_starts):
        end_line = method_starts[i + 1] if i + 1 < len(method_starts) else len(lines)
        method_length = end_line - start_line
        
        if method_length > 30:  # Methods longer than 30 lines
            technical_debt.append({
                'type': 'long_method',
                'line': start_line,
                'severity': 'MEDIUM',
                'description': f'Long method ({method_length} lines)',
                'recommendation': 'Consider breaking down into smaller methods'
            })
    
    return technical_debt

async def _generate_project_metrics(self, analyses: List[CodeAnalysis]) -> Dict[str, Any]:
    """Generate project-wide metrics from file analyses"""
    
    if not analyses:
        return {}
    
    total_files = len(analyses)
    total_lines = sum(analysis.lines_of_code for analysis in analyses)
    avg_complexity = sum(analysis.complexity_score for analysis in analyses) / total_files
    avg_maintainability = sum(analysis.maintainability_index for analysis in analyses) / total_files
    avg_test_coverage = sum(analysis.test_coverage for analysis in analyses) / total_files
    
    # Language distribution
    language_counts = {}
    for analysis in analyses:
        language = analysis.language
        language_counts[language] = language_counts.get(language, 0) + 1
    
    # Security issues summary
    total_security_issues = sum(len(analysis.security_issues) for analysis in analyses)
    security_by_severity = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    for analysis in analyses:
        for issue in analysis.security_issues:
            severity = issue.get('severity', 'LOW')
            security_by_severity[severity] += 1
    
    # Technical debt summary
    total_debt_items = sum(len(analysis.technical_debt) for analysis in analyses)
    debt_by_type = {}
    for analysis in analyses:
        for debt in analysis.technical_debt:
            debt_type = debt.get('type', 'unknown')
            debt_by_type[debt_type] = debt_by_type.get(debt_type, 0) + 1
    
    return {
        "total_files": total_files,
        "total_lines_of_code": total_lines,
        "average_complexity": round(avg_complexity, 2),
        "average_maintainability": round(avg_maintainability, 2),
        "average_test_coverage": round(avg_test_coverage, 2),
        "language_distribution": language_counts,
        "security_issues": {
            "total": total_security_issues,
            "by_severity": security_by_severity
        },
        "technical_debt": {
            "total_items": total_debt_items,
            "by_type": debt_by_type
        },
        "files_with_high_complexity": len([a for a in analyses if a.complexity_score > self.quality_thresholds['complexity_max']]),
        "files_with_low_maintainability": len([a for a in analyses if a.maintainability_index < self.quality_thresholds['maintainability_min']]),
        "files_without_tests": len([a for a in analyses if a.test_coverage == 0])
    }

async def _assess_architecture(self, project_path: str, analyses: List[CodeAnalysis]) -> ArchitectureAssessment:
    """Assess overall architecture of the project"""
    
    # Analyze project structure
    project_structure = await self._analyze_project_structure(project_path)
    
    # Collect all detected patterns
    all_patterns = []
    for analysis in analyses:
        all_patterns.extend(analysis.architecture_patterns)
    
    design_patterns = list(set(all_patterns))
    
    # Calculate coupling and cohesion metrics (simplified)
    coupling_analysis = await self._analyze_coupling(analyses)
    cohesion_metrics = await self._analyze_cohesion(analyses)
    
    # Calculate scalability and maintainability scores
    scalability_score = await self._calculate_scalability_score(project_structure, analyses)
    maintainability_score = sum(a.maintainability_index for a in analyses) / len(analyses) if analyses else 0
    
    # Generate recommendations
    recommendations = await self._generate_architecture_recommendations(
        project_structure, design_patterns, coupling_analysis
    )
    
    # Detect anti-patterns
    anti_patterns = await self._detect_anti_patterns(analyses, project_structure)
    
    return ArchitectureAssessment(
        project_structure=project_structure,
        design_patterns=design_patterns,
        coupling_analysis=coupling_analysis,
        cohesion_metrics=cohesion_metrics,
        scalability_score=scalability_score,
        maintainability_score=maintainability_score,
        recommendations=recommendations,
        anti_patterns=anti_patterns
    )

async def _analyze_project_structure(self, project_path: str) -> Dict[str, Any]:
    """Analyze the overall structure of the project"""
    
    structure = {
        "directories": {},
        "depth": 0,
        "files_per_directory": {},
        "naming_conventions": []
    }
    
    max_depth = 0
    for root, dirs, files in os.walk(project_path):
        relative_path = os.path.relpath(root, project_path)
        depth = len(relative_path.split(os.sep)) if relative_path != '.' else 0
        max_depth = max(max_depth, depth)
        
        structure["directories"][relative_path] = {
            "subdirs": len(dirs),
            "files": len(files),
            "depth": depth
        }
        structure["files_per_directory"][relative_path] = len(files)
    
    structure["depth"] = max_depth
    
    # Analyze naming conventions
    dir_names = list(structure["directories"].keys())
    if any('_' in name for name in dir_names):
        structure["naming_conventions"].append("snake_case")
    if any('-' in name for name in dir_names):
        structure["naming_conventions"].append("kebab-case")
    if any(name[0].isupper() for name in dir_names if name != '.'):
        structure["naming_conventions"].append("PascalCase")
    
    return structure

async def _analyze_coupling(self, analyses: List[CodeAnalysis]) -> Dict[str, float]:
    """Analyze coupling between modules"""
    
    coupling_metrics = {
        "afferent_coupling": 0.0,  # Incoming dependencies
        "efferent_coupling": 0.0,   # Outgoing dependencies
        "instability": 0.0          # Efferent / (Afferent + Efferent)
    }
    
    if not analyses:
        return coupling_metrics
    
    # Simple coupling analysis based on imports
    all_dependencies = []
    for analysis in analyses:
        all_dependencies.extend(analysis.dependencies)
    
    total_deps = len(all_dependencies)
    unique_deps = len(set(all_dependencies))
    
    if total_deps > 0:
        coupling_metrics["efferent_coupling"] = unique_deps / len(analyses)
        coupling_metrics["afferent_coupling"] = total_deps / len(analyses)
        coupling_metrics["instability"] = coupling_metrics["efferent_coupling"] / (
            coupling_metrics["efferent_coupling"] + coupling_metrics["afferent_coupling"]
        ) if (coupling_metrics["efferent_coupling"] + coupling_metrics["afferent_coupling"]) > 0 else 0
    
    return coupling_metrics

async def _analyze_cohesion(self, analyses: List[CodeAnalysis]) -> Dict[str, float]:
    """Analyze cohesion within modules"""
    
    cohesion_metrics = {
        "functional_cohesion": 0.0,
        "data_cohesion": 0.0,
        "temporal_cohesion": 0.0
    }
    
    # Simplified cohesion analysis
    # This would need more sophisticated analysis in a real implementation
    if analyses:
        avg_complexity = sum(a.complexity_score for a in analyses) / len(analyses)
        cohesion_metrics["functional_cohesion"] = max(0, min(100, 100 - (avg_complexity * 5)))
        cohesion_metrics["data_cohesion"] = 75.0  # Placeholder
        cohesion_metrics["temporal_cohesion"] = 80.0  # Placeholder
    
    return cohesion_metrics

async def _calculate_scalability_score(self, structure: Dict[str, Any], analyses: List[CodeAnalysis]) -> float:
    """Calculate overall scalability score"""
    
    score = 100.0
    
    # Penalize deep nesting
    if structure["depth"] > 5:
        score -= (structure["depth"] - 5) * 5
    
    # Penalize high average complexity
    if analyses:
        avg_complexity = sum(a.complexity_score for a in analyses) / len(analyses)
        if avg_complexity > 10:
            score -= (avg_complexity - 10) * 3
    
    # Penalize low test coverage
    if analyses:
        avg_coverage = sum(a.test_coverage for a in analyses) / len(analyses)
        if avg_coverage < 70:
            score -= (70 - avg_coverage) * 0.5
    
    return max(0.0, min(100.0, score))

async def _generate_architecture_recommendations(self, structure: Dict[str, Any], 
                                               patterns: List[str], 
                                               coupling: Dict[str, float]) -> List[str]:
    """Generate architecture improvement recommendations"""
    
    recommendations = []
    
    # Structure recommendations
    if structure["depth"] > 6:
        recommendations.append("Consider flattening directory structure to improve navigation")
    
    # Pattern recommendations
    if 'mvc' not in patterns and len(structure["directories"]) > 5:
        recommendations.append("Consider implementing MVC pattern for better separation of concerns")
    
    if 'repository' not in patterns:
        recommendations.append("Consider implementing Repository pattern for data access")
    
    # Coupling recommendations
    if coupling["instability"] > 0.8:
        recommendations.append("High instability detected - consider stabilizing core components")
    
    if coupling["efferent_coupling"] > 10:
        recommendations.append("High efferent coupling - consider reducing external dependencies")
    
    return recommendations

async def _detect_anti_patterns(self, analyses: List[CodeAnalysis], 
                              structure: Dict[str, Any]) -> List[str]:
    """Detect architecture anti-patterns"""
    
    anti_patterns = []
    
    # God object detection
    large_files = [a for a in analyses if a.lines_of_code > 1000]
    if large_files:
        anti_patterns.append(f"God object detected - {len(large_files)} files exceed 1000 lines")
    
    # Spaghetti code detection
    high_complexity_files = [a for a in analyses if a.complexity_score > 20]
    if len(high_complexity_files) > len(analyses) * 0.3:
        anti_patterns.append("Spaghetti code - high complexity in multiple files")
    
    # Copy-paste programming
    high_duplication = [a for a in analyses 
                       if a.quality_metrics.get('duplication_ratio', 0) > 15]
    if high_duplication:
        anti_patterns.append("Copy-paste programming detected - high code duplication")
    
    return anti_patterns

async def _assess_security(self, analyses: List[CodeAnalysis]) -> Dict[str, Any]:
    """Comprehensive security assessment"""
    
    all_issues = []
    for analysis in analyses:
        all_issues.extend(analysis.security_issues)
    
    # Categorize issues
    issues_by_severity = {'HIGH': [], 'MEDIUM': [], 'LOW': []}
    issues_by_type = {}
    
    for issue in all_issues:
        severity = issue.get('severity', 'LOW')
        issue_type = issue.get('type', 'unknown')
        
        issues_by_severity[severity].append(issue)
        if issue_type not in issues_by_type:
            issues_by_type[issue_type] = []
        issues_by_type[issue_type].append(issue)
    
    # Calculate security score
    security_score = 100.0
    security_score -= len(issues_by_severity['HIGH']) * 15
    security_score -= len(issues_by_severity['MEDIUM']) * 5
    security_score -= len(issues_by_severity['LOW']) * 1
    security_score = max(0.0, security_score)
    
    return {
        "total_issues": len(all_issues),
        "issues_by_severity": {k: len(v) for k, v in issues_by_severity.items()},
        "issues_by_type": {k: len(v) for k, v in issues_by_type.items()},
        "security_score": round(security_score, 2),
        "critical_issues": issues_by_severity['HIGH'],
        "recommendations": self._generate_security_recommendations(issues_by_type)
    }

def _generate_security_recommendations(self, issues_by_type: Dict[str, List]) -> List[str]:
    """Generate security recommendations based on found issues"""
    
    recommendations = []
    
    if 'sql_injection' in issues_by_type:
        recommendations.append("Implement parameterized queries to prevent SQL injection")
    
    if 'xss' in issues_by_type:
        recommendations.append("Implement proper input sanitization and output encoding")
    
    if 'hardcoded_secrets' in issues_by_type:
        recommendations.append("Move secrets to environment variables or secure vaults")
    
    if 'weak_crypto' in issues_by_type:
        recommendations.append("Upgrade to stronger cryptographic algorithms")
    
    return recommendations

async def _assess_performance(self, analyses: List[CodeAnalysis]) -> Dict[str, Any]:
    """Comprehensive performance assessment"""
    
    all_insights = []
    for analysis in analyses:
        all_insights.extend(analysis.performance_insights)
    
    # Categorize performance issues
    issue_categories = {
        'database': [],
        'loops': [],
        'memory': [],
        'algorithms': [],
        'io': []
    }
    
    for insight in all_insights:
        if any(keyword in insight.lower() for keyword in ['query', 'database', 'sql']):
            issue_categories['database'].append(insight)
        elif any(keyword in insight.lower() for keyword in ['loop', 'iteration']):
            issue_categories['loops'].append(insight)
        elif any(keyword in insight.lower() for keyword in ['memory', 'leak']):
            issue_categories['memory'].append(insight)
        elif any(keyword in insight.lower() for keyword in ['algorithm', 'complexity']):
            issue_categories['algorithms'].append(insight)
        elif any(keyword in insight.lower() for keyword in ['io', 'file', 'network']):
            issue_categories['io'].append(insight)
    
    # Calculate performance score
    performance_score = 100.0
    performance_score -= len(all_insights) * 2  # Each issue reduces score by 2
    performance_score = max(0.0, performance_score)
    
    return {
        "total_issues": len(all_insights),
        "issues_by_category": {k: len(v) for k, v in issue_categories.items()},
        "performance_score": round(performance_score, 2),
        "top_issues": all_insights[:10],  # Top 10 issues
        "recommendations": self._generate_performance_recommendations(issue_categories)
    }

def _generate_performance_recommendations(self, issues_by_category: Dict[str, List]) -> List[str]:
    """Generate performance recommendations"""
    
    recommendations = []
    
    if issues_by_category['database']:
        recommendations.append("Optimize database queries and consider query caching")
    
    if issues_by_category['loops']:
        recommendations.append("Optimize loop operations and consider vectorization")
    
    if issues_by_category['memory']:
        recommendations.append("Review memory usage and implement proper cleanup")
    
    if issues_by_category['algorithms']:
        recommendations.append("Consider more efficient algorithms and data structures")
    
    if issues_by_category['io']:
        recommendations.append("Optimize I/O operations and consider async processing")
    
    return recommendations

async def _generate_recommendations(self, analyses: List[CodeAnalysis], 
                                  architecture: Optional[ArchitectureAssessment]) -> List[str]:
    """Generate overall project recommendations"""
    
    recommendations = []
    
    if not analyses:
        return ["No source files found to analyze"]
    
    # Code quality recommendations
    high_complexity_files = len([a for a in analyses if a.complexity_score > 10])
    if high_complexity_files > 0:
        recommendations.append(f"Reduce complexity in {high_complexity_files} files")
    
    low_maintainability_files = len([a for a in analyses if a.maintainability_index < 70])
    if low_maintainability_files > 0:
        recommendations.append(f"Improve maintainability in {low_maintainability_files} files")
    
    files_without_tests = len([a for a in analyses if a.test_coverage == 0])
    if files_without_tests > 0:
        recommendations.append(f"Add tests for {files_without_tests} files")
    
    # Security recommendations
    total_security_issues = sum(len(a.security_issues) for a in analyses)
    if total_security_issues > 0:
        recommendations.append(f"Address {total_security_issues} security issues")
    
    # Technical debt recommendations
    total_debt = sum(len(a.technical_debt) for a in analyses)
    if total_debt > 10:
        recommendations.append(f"Address technical debt ({total_debt} items)")
    
    # Architecture recommendations
    if architecture and architecture.recommendations:
        recommendations.extend(architecture.recommendations[:3])  # Top 3 architecture recommendations
    
    return recommendations[:10]  # Return top 10 recommendations

async def _calculate_quality_score(self, analyses: List[CodeAnalysis]) -> float:
    """Calculate overall project quality score"""
    
    if not analyses:
        return 0.0
    
    # Weight factors for different metrics
    weights = {
        'maintainability': 0.3,
        'test_coverage': 0.2,
        'complexity': 0.2,
        'security': 0.15,
        'technical_debt': 0.15
    }
    
    # Calculate individual scores
    avg_maintainability = sum(a.maintainability_index for a in analyses) / len(analyses)
    avg_test_coverage = sum(a.test_coverage for a in analyses) / len(analyses)
    
    # Complexity score (inverse - lower is better)
    avg_complexity = sum(a.complexity_score for a in analyses) / len(analyses)
    complexity_score = max(0, 100 - (avg_complexity * 5))
    
    # Security score (based on issues)
    total_security_issues = sum(len(a.security_issues) for a in analyses)
    security_score = max(0, 100 - (total_security_issues * 2))
    
    # Technical debt score (based on debt items)
    total_debt = sum(len(a.technical_debt) for a in analyses)
    debt_score = max(0, 100 - (total_debt / len(analyses) * 3))
    
    # Calculate weighted score
    quality_score = (
        avg_maintainability * weights['maintainability'] +
        avg_test_coverage * weights['test_coverage'] +
        complexity_score * weights['complexity'] +
        security_score * weights['security'] +
        debt_score * weights['technical_debt']
    )
    
    return round(quality_score, 2)

async def _suggest_next_steps(self, analyses: List[CodeAnalysis]) -> List[str]:
    """Suggest concrete next steps for improvement"""
    
    next_steps = []
    
    if not analyses:
        return ["Run examination on a codebase with source files"]
    
    # Prioritize based on impact and effort
    
    # High impact, low effort
    files_without_tests = [a for a in analyses if a.test_coverage == 0]
    if files_without_tests:
        next_steps.append(f"Start by adding tests to {min(3, len(files_without_tests))} critical files")
    
    # High impact, medium effort
    high_complexity_files = [a for a in analyses if a.complexity_score > 15]
    if high_complexity_files:
        next_steps.append("Refactor the most complex methods to reduce cyclomatic complexity")
    
    # Security issues (high priority)
    high_security_issues = []
    for analysis in analyses:
        high_security_issues.extend([i for i in analysis.security_issues if i.get('severity') == 'HIGH'])
    
    if high_security_issues:
        next_steps.append("Address high-severity security vulnerabilities immediately")
    
    # Technical debt
    todo_items = []
    for analysis in analyses:
        todo_items.extend([d for d in analysis.technical_debt if d.get('type') == 'todo_comment'])
    
    if len(todo_items) > 10:
        next_steps.append("Review and address TODO/FIXME comments")
    
    # Documentation
    low_comment_ratio_files = []
    for analysis in analyses:
        comment_ratio = analysis.quality_metrics.get('comment_ratio', 0)
        if comment_ratio < 10:
            low_comment_ratio_files.append(analysis)
    
    if len(low_comment_ratio_files) > len(analyses) * 0.5:
        next_steps.append("Improve code documentation and comments")
    
    return next_steps[:5]  # Return top 5 next steps

def _serialize_analysis(self, analysis: CodeAnalysis) -> Dict[str, Any]:
    """Convert CodeAnalysis to serializable dictionary"""
    
    return {
        "file_path": analysis.file_path,
        "language": analysis.language,
        "lines_of_code": analysis.lines_of_code,
        "complexity_score": analysis.complexity_score,
        "quality_metrics": analysis.quality_metrics,
        "security_issues": analysis.security_issues,
        "performance_insights": analysis.performance_insights,
        "architecture_patterns": analysis.architecture_patterns,
        "dependencies": analysis.dependencies,
        "test_coverage": analysis.test_coverage,
        "maintainability_index": analysis.maintainability_index,
        "technical_debt": analysis.technical_debt
    }

def _serialize_architecture_assessment(self, assessment: ArchitectureAssessment) -> Dict[str, Any]:
    """Convert ArchitectureAssessment to serializable dictionary"""
    
    return {
        "project_structure": assessment.project_structure,
        "design_patterns": assessment.design_patterns,
        "coupling_analysis": assessment.coupling_analysis,
        "cohesion_metrics": assessment.cohesion_metrics,
        "scalability_score": assessment.scalability_score,
        "maintainability_score": assessment.maintainability_score,
        "recommendations": assessment.recommendations,
        "anti_patterns": assessment.anti_patterns
    }

async def generate_report(self, examination_results: Dict[str, Any]) -> str:
    """Generate a comprehensive examination report"""
    
    if "error" in examination_results:
        return f"Examination failed: {examination_results['error']}"
    
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("AI-NATIVE DEVELOPMENT ENVIRONMENT - CODE EXAMINATION REPORT")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    # Project summary
    report_lines.append("PROJECT SUMMARY")
    report_lines.append("-" * 40)
    report_lines.append(f"Project Path: {examination_results['project_path']}")
    report_lines.append(f"Files Analyzed: {examination_results['files_analyzed']}")
    report_lines.append(f"Languages: {', '.join(examination_results['languages_detected'])}")
    report_lines.append(f"Analysis Date: {examination_results['timestamp']}")
    report_lines.append(f"Overall Quality Score: {examination_results['quality_score']}/100")
    report_lines.append("")
    
    # Project metrics
    metrics = examination_results.get('project_metrics', {})
    if metrics:
        report_lines.append("PROJECT METRICS")
        report_lines.append("-" * 40)
        report_lines.append(f"Total Lines of Code: {metrics.get('total_lines_of_code', 0):,}")
        report_lines.append(f"Average Complexity: {metrics.get('average_complexity', 0)}")
        report_lines.append(f"Average Maintainability: {metrics.get('average_maintainability', 0)}")
        report_lines.append(f"Average Test Coverage: {metrics.get('average_test_coverage', 0)}%")
        report_lines.append("")
        
        # Language distribution
        if 'language_distribution' in metrics:
            report_lines.append("Language Distribution:")
            for lang, count in metrics['language_distribution'].items():
                report_lines.append(f"  {lang}: {count} files")
        report_lines.append("")
    
    # Security assessment
    security = examination_results.get('security_assessment')
    if security:
        report_lines.append("SECURITY ASSESSMENT")
        report_lines.append("-" * 40)
        report_lines.append(f"Security Score: {security['security_score']}/100")
        report_lines.append(f"Total Issues: {security['total_issues']}")
        
        severity = security['issues_by_severity']
        report_lines.append(f"  High: {severity.get('HIGH', 0)}")
        report_lines.append(f"  Medium: {severity.get('MEDIUM', 0)}")
        report_lines.append(f"  Low: {severity.get('LOW', 0)}")
        report_lines.append("")
    
    # Performance assessment
    performance = examination_results.get('performance_assessment')
    if performance:
        report_lines.append("PERFORMANCE ASSESSMENT")
        report_lines.append("-" * 40)
        report_lines.append(f"Performance Score: {performance['performance_score']}/100")
        report_lines.append(f"Total Issues: {performance['total_issues']}")
        report_lines.append("")
    
    # Architecture assessment
    architecture = examination_results.get('architecture_assessment')
    if architecture:
        report_lines.append("ARCHITECTURE ASSESSMENT")
        report_lines.append("-" * 40)
        report_lines.append(f"Scalability Score: {architecture['scalability_score']}/100")
        report_lines.append(f"Maintainability Score: {architecture['maintainability_score']:.1f}/100")
        
        if architecture['design_patterns']:
            report_lines.append(f"Design Patterns: {', '.join(architecture['design_patterns'])}")
        
        if architecture['anti_patterns']:
            report_lines.append("Anti-patterns Detected:")
            for pattern in architecture['anti_patterns']:
                report_lines.append(f"  • {pattern}")
        report_lines.append("")
    
    # Recommendations
    recommendations = examination_results.get('recommendations', [])
    if recommendations:
        report_lines.append("RECOMMENDATIONS")
        report_lines.append("-" * 40)
        for i, rec in enumerate(recommendations, 1):
            report_lines.append(f"{i}. {rec}")
        report_lines.append("")
    
    # Next steps
    next_steps = examination_results.get('next_steps', [])
    if next_steps:
        report_lines.append("NEXT STEPS")
        report_lines.append("-" * 40)
        for i, step in enumerate(next_steps, 1):
            report_lines.append(f"{i}. {step}")
        report_lines.append("")
    
    report_lines.append("=" * 80)
    report_lines.append("End of Report")
    report_lines.append("=" * 80)
    
    return "\n".join(report_lines)

async def quick_scan(self, project_path: str) -> Dict[str, Any]:
    """Perform a quick scan of the codebase (lightweight analysis)"""
    
    try:
        logger.info("Starting quick scan", project_path=project_path)
        
        source_files = await self._discover_source_files(project_path)
        if not source_files:
            return {"error": "No source files found"}
        
        # Limit to first 20 files for quick scan
        limited_files = source_files[:20]
        
        quick_results = {
            "project_path": project_path,
            "total_files_found": len(source_files),
            "files_scanned": len(limited_files),
            "languages": {},
            "total_lines": 0,
            "large_files": [],
            "potential_issues": []
        }
        
        for file_path in limited_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                language = self._detect_language(file_path)
                lines = len(content.split('\n'))
                
                quick_results["languages"][language] = quick_results["languages"].get(language, 0) + 1
                quick_results["total_lines"] += lines
                
                # Check for large files
                if lines > 500:
                    quick_results["large_files"].append({
                        "file": file_path,
                        "lines": lines
                    })
                
                # Quick issue detection
                if 'TODO' in content or 'FIXME' in content:
                    quick_results["potential_issues"].append(f"TODO/FIXME in {file_path}")
                
                if len(re.findall(r'def\s+\w+', content)) > 20:  # Many functions
                    quick_results["potential_issues"].append(f"Large file with many functions: {file_path}")
            
            except Exception as e:
                logger.warning(f"Failed to scan {file_path}: {str(e)}")
        
        logger.info("Quick scan completed", files_scanned=len(limited_files))
        return quick_results
    
    except Exception as e:
        logger.error("Quick scan failed", error=str(e))
        return {"error": f"Quick scan failed: {str(e)}"}
```

# Example usage and testing

if **name** == “**main**”:
async def main():
“”“Example usage of the Examination Agent”””

```
    # Initialize the agent
    agent = ExaminationAgent()
    
    # Example project path (replace with actual path)
    project_path = "/path/to/your/project"
    
    try:
        print("Starting comprehensive examination...")
        results = await agent.examine_codebase(
            project_path=project_path,
            include_architecture=True,
            include_security=True,
            include_performance=True
        )
        
        if "error" in results:
            print(f"Examination failed: {results['error']}")
        else:
            # Generate and display report
            report = await agent.generate_report(results)
            print(report)
            
            # Save detailed results to JSON
            with open("examination_results.json", "w") as f:
                json.dump(results, f, indent=2)
            print("\nDetailed results saved to examination_results.json")
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")

# Run the example
asyncio.run(main())
```