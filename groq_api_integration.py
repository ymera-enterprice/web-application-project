# YMERA Enterprise GROQ API Integration
# Advanced AI-powered code analysis with ultra-fast inference

import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import os
from datetime import datetime

class AnalysisType(Enum):
    CODE_QUALITY = "code_quality"
    SECURITY_SCAN = "security_scan"
    PERFORMANCE = "performance"
    BUG_DETECTION = "bug_detection"
    ENHANCEMENT = "enhancement"

@dataclass
class AnalysisResult:
    type: AnalysisType
    confidence: float
    findings: List[Dict[str, Any]]
    processing_time: float
    recommendations: List[Dict[str, Any]]

class YMERAGroqEngine:
    """Ultra-fast AI code analysis using GROQ's high-performance inference"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"
        self.session = None
        
        # Performance tracking
        self.total_requests = 0
        self.total_processing_time = 0.0
        self.cache = {}
        
    async def __aenter__(self):
        """Async context manager for HTTP session"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up HTTP session"""
        if self.session:
            await self.session.close()
    
    def _create_system_prompt(self, analysis_type: AnalysisType) -> str:
        """Generate specialized system prompts for different analysis types"""
        
        base_prompt = """You are a YMERA Enterprise AI code analyst. Provide rapid, actionable insights in JSON format.
        Focus on: accuracy, specificity, and actionable recommendations.
        Response format: {"findings": [...], "severity": "CRITICAL|HIGH|MEDIUM|LOW", "recommendations": [...], "confidence": 0.0-1.0}"""
        
        type_specific = {
            AnalysisType.CODE_QUALITY: """
            Analyze code quality including: readability, maintainability, complexity, naming conventions, documentation.
            Focus on: cyclomatic complexity, code smells, SOLID principles, design patterns.
            """,
            AnalysisType.SECURITY_SCAN: """
            Perform security analysis including: vulnerabilities, injection risks, authentication issues, data exposure.
            Focus on: OWASP Top 10, input validation, encryption, access control, SQL injection, XSS.
            """,
            AnalysisType.PERFORMANCE: """
            Analyze performance issues including: bottlenecks, memory usage, algorithmic complexity, database queries.
            Focus on: time complexity, space complexity, I/O operations, caching opportunities.
            """,
            AnalysisType.BUG_DETECTION: """
            Detect potential bugs including: logic errors, null pointer exceptions, race conditions, edge cases.
            Focus on: error handling, boundary conditions, concurrency issues, type mismatches.
            """,
            AnalysisType.ENHANCEMENT: """
            Suggest code improvements including: refactoring opportunities, modern language features, best practices.
            Focus on: code optimization, readability improvements, architectural suggestions.
            """
        }
        
        return base_prompt + type_specific.get(analysis_type, "")
    
    async def _make_groq_request(self, messages: List[Dict], temperature: float = 0.1) -> Dict:
        """Make async request to GROQ API with error handling and retries"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 2000,
            "temperature": temperature,
            "stream": False
        }
        
        start_time = time.time()
        
        try:
            async with self.session.post(self.base_url, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    processing_time = time.time() - start_time
                    
                    # Update performance metrics
                    self.total_requests += 1
                    self.total_processing_time += processing_time
                    
                    return {
                        "success": True,
                        "content": result["choices"][0]["message"]["content"],
                        "processing_time": processing_time,
                        "tokens_used": result.get("usage", {}).get("total_tokens", 0)
                    }
                else:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {error_text}",
                        "processing_time": time.time() - start_time
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "processing_time": time.time() - start_time
            }
    
    async def analyze_code_parallel(self, code: str, analysis_types: List[AnalysisType], context: Optional[Dict] = None) -> Dict[str, AnalysisResult]:
        """Perform multiple types of analysis in parallel for maximum speed"""
        
        # Generate cache key
        cache_key = hash(code + str(sorted(analysis_types)))
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Create tasks for parallel execution
        tasks = []
        for analysis_type in analysis_types:
            task = self._analyze_single_type(code, analysis_type, context)
            tasks.append((analysis_type, task))
        
        # Execute all analyses in parallel
        results = {}
        completed_tasks = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        for i, (analysis_type, result) in enumerate(zip([t[0] for t in tasks], completed_tasks)):
            if isinstance(result, Exception):
                results[analysis_type.value] = AnalysisResult(
                    type=analysis_type,
                    confidence=0.0,
                    findings=[{"error": str(result)}],
                    processing_time=0.0,
                    recommendations=[]
                )
            else:
                results[analysis_type.value] = result
        
        # Cache results for future requests
        self.cache[cache_key] = results
        return results
    
    async def _analyze_single_type(self, code: str, analysis_type: AnalysisType, context: Optional[Dict] = None) -> AnalysisResult:
        """Perform single type analysis with GROQ"""
        
        system_prompt = self._create_system_prompt(analysis_type)
        
        # Build context-aware user prompt
        user_prompt = f"""
        ANALYZE THIS CODE:
        ```
        {code}
        ```
        
        CONTEXT: {json.dumps(context) if context else "None provided"}
        
        ANALYSIS TYPE: {analysis_type.value}
        
        Provide detailed findings with specific line references where possible.
        Include severity levels and actionable recommendations.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Make GROQ API call
        response = await self._make_groq_request(messages)
        
        if response["success"]:
            try:
                # Parse JSON response
                content = response["content"]
                if content.startswith("```json"):
                    content = content.split("```json")[1].split("```")[0]
                elif content.startswith("```"):
                    content = content.split("```")[1].split("```")[0]
                
                analysis_data = json.loads(content)
                
                return AnalysisResult(
                    type=analysis_type,
                    confidence=analysis_data.get("confidence", 0.8),
                    findings=analysis_data.get("findings", []),
                    processing_time=response["processing_time"],
                    recommendations=analysis_data.get("recommendations", [])
                )
                
            except json.JSONDecodeError:
                # Fallback to text parsing if JSON fails
                return AnalysisResult(
                    type=analysis_type,
                    confidence=0.7,
                    findings=[{"raw_analysis": response["content"]}],
                    processing_time=response["processing_time"],
                    recommendations=[]
                )
        else:
            return AnalysisResult(
                type=analysis_type,
                confidence=0.0,
                findings=[{"error": response["error"]}],
                processing_time=response["processing_time"],
                recommendations=[]
            )
    
    async def rapid_code_scan(self, code: str, priority_focus: str = "security") -> Dict:
        """Ultra-fast code scan focusing on most critical issues"""
        
        # Determine analysis types based on priority
        if priority_focus == "security":
            analysis_types = [AnalysisType.SECURITY_SCAN, AnalysisType.BUG_DETECTION]
        elif priority_focus == "performance":
            analysis_types = [AnalysisType.PERFORMANCE, AnalysisType.CODE_QUALITY]
        elif priority_focus == "quality":
            analysis_types = [AnalysisType.CODE_QUALITY, AnalysisType.ENHANCEMENT]
        else:
            analysis_types = [AnalysisType.SECURITY_SCAN, AnalysisType.CODE_QUALITY]
        
        start_time = time.time()
        results = await self.analyze_code_parallel(code, analysis_types)
        total_time = time.time() - start_time
        
        # Aggregate critical findings
        critical_findings = []
        all_recommendations = []
        
        for analysis_result in results.values():
            for finding in analysis_result.findings:
                if finding.get("severity") in ["CRITICAL", "HIGH"]:
                    critical_findings.append(finding)
            all_recommendations.extend(analysis_result.recommendations)
        
        return {
            "status": "COMPLETE",
            "total_processing_time": total_time,
            "critical_findings_count": len(critical_findings),
            "critical_findings": critical_findings[:5],  # Top 5 most critical
            "top_recommendations": all_recommendations[:3],  # Top 3 recommendations
            "detailed_results": results,
            "performance_metrics": {
                "groq_requests": len(analysis_types),
                "avg_response_time": total_time / len(analysis_types),
                "cache_hit": len(self.cache) > 0
            }
        }
    
    def get_performance_stats(self) -> Dict:
        """Get performance statistics for monitoring"""
        avg_time = self.total_processing_time / max(self.total_requests, 1)
        
        return {
            "total_requests": self.total_requests,
            "total_processing_time": self.total_processing_time,
            "average_processing_time": avg_time,
            "cache_size": len(self.cache),
            "requests_per_second": self.total_requests / max(self.total_processing_time, 0.1)
        }

# FastAPI Integration Example
async def ymera_groq_analysis_endpoint(code: str, analysis_types: List[str], context: Optional[Dict] = None):
    """FastAPI endpoint for YMERA platform integration"""
    
    # Convert string types to enum
    enum_types = []
    for atype in analysis_types:
        try:
            enum_types.append(AnalysisType(atype))
        except ValueError:
            continue
    
    async with YMERAGroqEngine() as groq_engine:
        if len(enum_types) == 1:
            # Single analysis for fastest response
            result = await groq_engine._analyze_single_type(code, enum_types[0], context)
            return {
                "status": "success",
                "processing_time": result.processing_time,
                "analysis": result.__dict__
            }
        else:
            # Parallel analysis for comprehensive results
            results = await groq_engine.analyze_code_parallel(code, enum_types, context)
            return {
                "status": "success", 
                "processing_time": sum(r.processing_time for r in results.values()),
                "analyses": {k: v.__dict__ for k, v in results.items()}
            }

# Usage Example
async def main():
    """Example usage of YMERA GROQ integration"""
    
    sample_code = """
    def process_user_data(user_input):
        # Potential security issue - no input validation
        query = "SELECT * FROM users WHERE id = " + user_input
        result = execute_query(query)
        return result
    """
    
    async with YMERAGroqEngine() as groq_engine:
        # Rapid security-focused scan
        rapid_results = await groq_engine.rapid_code_scan(sample_code, "security")
        print("Rapid Scan Results:")
        print(json.dumps(rapid_results, indent=2))
        
        # Comprehensive parallel analysis
        all_types = list(AnalysisType)
        comprehensive_results = await groq_engine.analyze_code_parallel(sample_code, all_types)
        print("\nComprehensive Analysis:")
        for analysis_type, result in comprehensive_results.items():
            print(f"{analysis_type}: {len(result.findings)} findings")

if __name__ == "__main__":
    asyncio.run(main())