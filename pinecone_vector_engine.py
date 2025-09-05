# YMERA Enterprise Pinecone Vector Database Engine
# Semantic code search and pattern matching system

import asyncio
import hashlib
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np
import os
import re
from pathlib import Path

try:
    from pinecone import Pinecone, ServerlessSpec
except ImportError:
    print("Pinecone not installed. Run: pip install pinecone-client")

@dataclass
class CodeChunk:
    """Represents a chunk of code with metadata"""
    id: str
    content: str
    file_path: str
    language: str
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    complexity_score: float = 0.0
    quality_score: float = 0.0
    security_score: float = 0.0
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

@dataclass 
class SimilarityMatch:
    """Represents a similarity match result"""
    id: str
    score: float
    metadata: Dict[str, Any]
    content: str
    match_type: str  # 'exact', 'semantic', 'structural'

class YMERAPineconeEngine:
    """Advanced vector database engine for semantic code analysis"""
    
    def __init__(self, api_key: str = None, environment: str = "us-west1-gcp"):
        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        self.environment = environment
        self.pc = None
        self.index_name = "ymera-enterprise-v1"
        self.index = None
        
        # Performance tracking
        self.query_count = 0
        self.total_query_time = 0.0
        self.cache = {}
        
        # Code analysis patterns
        self.code_patterns = {
            'sql_injection': r'(SELECT|INSERT|UPDATE|DELETE).*(\+|\|\||format|%)',
            'xss_vulnerable': r'(innerHTML|document\.write|eval)\s*\(',
            'hardcoded_secrets': r'(password|api_key|secret)\s*=\s*["\'][^"\']+["\']',
            'security_headers': r'(X-Frame-Options|Content-Security-Policy|X-XSS-Protection)',
            'async_patterns': r'(async|await|Promise|then|catch)',
            'performance_issues': r'(for.*in.*|nested.*loop|O\(n\^2\))'
        }
        
    async def initialize(self) -> bool:
        """Initialize Pinecone connection and create index if needed"""
        try:
            self.pc = Pinecone(api_key=self.api_key)
            
            # Check if index exists, create if not
            if not self.pc.has_index(self.index_name):
                print(f"Creating Pinecone index: {self.index_name}")
                
                self.pc.create_index_for_model(
                    name=self.index_name,
                    cloud="aws",
                    region="us-east-1", 
                    embed={
                        "model": "llama-text-embed-v2",
                        "field_map": {"text": "code_chunk"}
                    }
                )
                
                # Wait for index to be ready
                await asyncio.sleep(5)
            
            self.index = self.pc.Index(self.index_name)
            print(f"✅ Pinecone index '{self.index_name}' ready")
            return True
            
        except Exception as e:
            print(f"❌ Pinecone initialization failed: {str(e)}")
            return False
    
    def _generate_chunk_id(self, content: str, file_path: str) -> str:
        """Generate unique ID for code chunk"""
        combined = f"{file_path}:{content}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _extract_code_features(self, code: str) -> Dict[str, Any]:
        """Extract features from code for enhanced search"""
        
        features = {
            'line_count': len(code.split('\n')),
            'char_count': len(code),
            'has_functions': bool(re.search(r'def\s+\w+\s*\(', code)),
            'has_classes': bool(re.search(r'class\s+\w+', code)),
            'has_imports': bool(re.search(r'^(import|from)\s+', code, re.MULTILINE)),
            'complexity_indicators': []
        }
        
        # Pattern matching for security and quality indicators
        for pattern_name, pattern in self.code_patterns.items():
            if re.search(pattern, code, re.IGNORECASE):
                features['complexity_indicators'].append(pattern_name)
        
        # Language detection (simplified)
        if any(keyword in code for keyword in ['def ', 'import ', 'class ', 'if __name__']):
            features['language'] = 'python'
        elif any(keyword in code for keyword in ['function', 'const', 'let', 'var']):
            features['language'] = 'javascript'
        elif any(keyword in code for keyword in ['public class', 'private', 'public static']):
            features['language'] = 'java'
        else:
            features['language'] = 'unknown'
            
        return features
    
    def _chunk_code(self, code: str, file_path: str, chunk_size: int = 500) -> List[CodeChunk]:
        """Split code into semantic chunks for vector storage"""
        
        chunks = []
        lines = code.split('\n')
        
        # Try to chunk by functions/classes first
        current_chunk = []
        current_function = None
        current_class = None
        indent_level = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Detect class definitions
            if stripped.startswith('class '):
                if current_chunk:
                    chunk_content = '\n'.join(current_chunk)
                    if len(chunk_content.strip()) > 20:  # Minimum chunk size
                        chunks.append(self._create_code_chunk(
                            chunk_content, file_path, current_function, current_class
                        ))
                current_chunk = [line]
                current_class = stripped.split()[1].split('(')[0].split(':')[0]
                current_function = None
                
            # Detect function definitions
            elif stripped.startswith('def ') or stripped.startswith('async def '):
                if current_chunk:
                    chunk_content = '\n'.join(current_chunk)
                    if len(chunk_content.strip()) > 20:
                        chunks.append(self._create_code_chunk(
                            chunk_content, file_path, current_function, current_class
                        ))
                current_chunk = [line]
                current_function = stripped.split()[1].split('(')[0]
                
            else:
                current_chunk.append(line)
                
                # If chunk gets too large, split it
                if len('\n'.join(current_chunk)) > chunk_size:
                    chunk_content = '\n'.join(current_chunk)
                    chunks.append(self._create_code_chunk(
                        chunk_content, file_path, current_function, current_class
                    ))
                    current_chunk = []
        
        # Add remaining chunk
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            if len(chunk_content.strip()) > 20:
                chunks.append(self._create_code_chunk(
                    chunk_content, file_path, current_function, current_class
                ))
        
        return chunks
    
    def _create_code_chunk(self, content: str, file_path: str, function_name: str, class_name: str) -> CodeChunk:
        """Create a CodeChunk with extracted features"""
        
        chunk_id = self._generate_chunk_id(content, file_path)
        features = self._extract_code_features(content)
        
        return CodeChunk(
            id=chunk_id,
            content=content,
            file_path=file_path,
            language=features.get('language', 'unknown'),
            function_name=function_name,
            class_name=class_name,
            complexity_score=len(features.get('complexity_indicators', [])) / 10.0,
            quality_score=1.0 - (len(features.get('complexity_indicators', [])) / 10.0),
            security_score=1.0 if not any(sec in features.get('complexity_indicators', []) 
                                        for sec in ['sql_injection', 'xss_vulnerable', 'hardcoded_secrets']) else 0.5
        )
    
    async def index_code_repository(self, repository_path: str, supported_extensions: List[str] = None) -> Dict[str, Any]:
        """Index entire code repository for semantic search"""
        
        if not self.index:
            if not await self.initialize():
                return {"error": "Failed to initialize Pinecone"}
        
        if supported_extensions is None:
            supported_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs']
        
        start_time = time.time()
        total_chunks = 0
        processed_files = 0
        
        # Collect all code files
        code_files = []
        for ext in supported_extensions:
            code_files.extend(Path(repository_path).rglob(f"*{ext}"))
        
        # Process files in batches
        batch_size = 100
        vectors_to_upsert = []
        
        for file_path in code_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Skip empty files or files that are too small
                if len(content.strip()) < 50:
                    continue
                
                # Chunk the code
                chunks = self._chunk_code(content, str(file_path))
                
                for chunk in chunks:
                    vector_data = {
                        "id": chunk.id,
                        "values": [],  # Pinecone will generate embeddings
                        "metadata": {
                            "content": chunk.content[:1000],  # Truncate for metadata storage
                            "file_path": chunk.file_path,
                            "language": chunk.language,
                            "function_name": chunk.function_name,
                            "class_name": chunk.class_name,
                            "complexity_score": chunk.complexity_score,
                            "quality_score": chunk.quality_score,
                            "security_score": chunk.security_score,
                            "created_at": chunk.created_at,
                            "chunk_type": "code"
                        }
                    }
                    
                    vectors_to_upsert.append(vector_data)
                    total_chunks += 1
                
                processed_files += 1
                
                # Upsert in batches
                if len(vectors_to_upsert) >= batch_size:
                    await self._upsert_vectors(vectors_to_upsert)
                    vectors_to_upsert = []
                
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
                continue
        
        # Upsert remaining vectors
        if vectors_to_upsert:
            await self._upsert_vectors(vectors_to_upsert)
        
        processing_time = time.time() - start_time
        
        return {
            "status": "success",
            "processed_files": processed_files,
            "total_chunks": total_chunks,
            "processing_time": processing_time,
            "chunks_per_second": total_chunks / processing_time if processing_time > 0 else 0
        }
    
    async def _upsert_vectors(self, vectors: List[Dict]) -> bool:
        """Upsert vectors to Pinecone with error handling"""
        try:
            # Since we're using create_index_for_model, Pinecone handles embeddings
            # We need to format for text embedding
            upsert_data = []
            for vector in vectors:
                upsert_data.append({
                    "id": vector["id"],
                    "metadata": vector["metadata"]
                })
            
            # Use the text field for embedding
            text_data = [{"id": v["id"], "text": v["metadata"]["content"]} for v in vectors]
            
            # Upsert to Pinecone
            self.index.upsert_from_dataframe(
                df=text_data,
                batch_size=50
            )
            
            return True
            
        except Exception as e:
            print(f"Error upserting vectors: {str(e)}")
            return False
    
    async def find_similar_code(self, query_code: str, top_k: int = 5, min_score: float = 0.7) -> List[SimilarityMatch]:
        """Find similar code patterns using semantic search"""
        
        if not self.index:
            if not await self.initialize():
                return []
        
        start_time = time.time()
        
        # Generate cache key
        cache_key = hashlib.md5(f"{query_code}{top_k}{min_score}".encode()).hexdigest()
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Query Pinecone with the code text
            query_results = self.index.query(
                vector=query_code,  # Pinecone will embed this
                top_k=top_k,
                include_metadata=True,
                filter={"chunk_type": "code"}
            )
            
            # Process results
            matches = []
            for match in query_results.get("matches", []):
                if match["score"] >= min_score:
                    similarity_match = SimilarityMatch(
                        id=match["id"],
                        score=match["score"],
                        metadata=match.get("metadata", {}),
                        content=match.get("metadata", {}).get("content", ""),
                        match_type=self._determine_match_type(match["score"])
                    )
                    matches.append(similarity_match)
            
            # Update performance metrics
            query_time = time.time() - start_time
            self.query_count += 1
            self.total_query_time += query_time
            
            # Cache results
            self.cache[cache_key] = matches
            
            return matches
            
        except Exception as e:
            print(f"Error querying Pinecone: {str(e)}")
            return []
    
    def _determine_match_type(self, score: float) -> str:
        """Determine the type of match based on similarity score"""
        if score >= 0.95:
            return "exact"
        elif score >= 0.8:
            return "semantic"
        else:
            return "structural"
    
    async def find_code_patterns(self, pattern_type: str, language: str = None) -> List[SimilarityMatch]:
        """Find specific code patterns (security issues, performance problems, etc.)"""
        
        if not self.index:
            if not await self.initialize():
                return []
        
        # Define filter criteria
        filter_criteria = {"chunk_type": "code"}
        if language:
            filter_criteria["language"] = language
        
        # Pattern-specific queries
        pattern_queries = {
            "security_vulnerabilities": "SQL injection vulnerability XSS hardcoded password",
            "performance_issues": "nested loop O(n^2) inefficient algorithm slow query",
            "code_smells": "long method duplicate code god class feature envy",
            "async_patterns": "async await Promise then catch asynchronous",
            "error_handling": "try catch exception error handling finally"
        }
        
        query_text = pattern_queries.get(pattern_type, pattern_type)
        
        try:
            results = self.index.query(
                vector=query_text,
                top_k=20,
                include_metadata=True,
                filter=filter_criteria
            )
            
            matches = []
            for match in results.get("matches", []):
                # Additional filtering based on pattern type
                metadata = match.get("metadata", {})
                content = metadata.get("content", "")
                
                # Pattern-specific filtering
                if pattern_type == "security_vulnerabilities":
                    if any(pattern in content.lower() for pattern in ['select', 'insert', 'password', 'api_key']):
                        matches.append(SimilarityMatch(
                            id=match["id"],
                            score=match["score"],
                            metadata=metadata,
                            content=content,
                            match_type="security_pattern"
                        ))
                else:
                    matches.append(SimilarityMatch(
                        id=match["id"],
                        score=match["score"],
                        metadata=metadata,
                        content=content,
                        match_type=f"{pattern_type}_pattern"
                    ))
            
            return matches
            
        except Exception as e:
            print(f"Error finding patterns: {str(e)}")
            return []
    
    async def get_repository_insights(self) -> Dict[str, Any]:
        """Get insights about the indexed repository"""
        
        if not self.index:
            return {"error": "Index not initialized"}
        
        try:
            # Get index stats
            stats = self.index.describe_index_stats()
            
            # Query for different languages
            languages = ['python', 'javascript', 'java', 'typescript']
            language_stats = {}
            
            for lang in languages:
                results = self.index.query(
                    vector="sample code",
                    top_k=1,
                    include_metadata=True,
                    filter={"language": lang}
                )
                language_stats[lang] = len(results.get("matches", []))
            
            # Security analysis
            security_issues = await self.find_code_patterns("security_vulnerabilities")
            performance_issues = await self.find_code_patterns("performance_issues")
            
            return {
                "total_vectors": stats.get("total_vector_count", 0),
                "language_distribution": language_stats,
                "security_issues_found": len(security_issues),
                "performance_issues_found": len(performance_issues),
                "query_performance": {
                    "total_queries": self.query_count,
                    "average_query_time": self.total_query_time / max(self.query_count, 1),
                    "cache_size": len(self.cache)
                }
            }
            
        except Exception as e:
            return {"error": f"Failed to get insights: {str(e)}"}
    
    async def delete_repository_data(self, file_path_prefix: str = None) -> Dict[str, Any]:
        """Delete vectors associated with a specific repository or file path"""
        
        try:
            if file_path_prefix:
                # Delete specific file/directory
                filter_criteria = {"file_path": {"$regex": f"^{file_path_prefix}"}}
            else:
                # Delete all code chunks
                filter_criteria = {"chunk_type": "code"}
            
            # Note: Pinecone delete_many is not available in all tiers
            # This is a simplified implementation
            delete_response = self.index.delete(filter=filter_criteria)
            
            return {
                "status": "success",
                "message": f"Deleted vectors matching filter: {filter_criteria}"
            }
            
        except Exception as e:
            return {"error": f"Failed to delete data: {str(e)}"}

# FastAPI Integration for YMERA Platform
class YMERAPineconeAPI:
    """API wrapper for YMERA platform integration"""
    
    def __init__(self):
        self.engine = YMERAPineconeEngine()
    
    async def setup_vector_database(self) -> Dict[str, Any]:
        """Initialize vector database for YMERA platform"""
        success = await self.engine.initialize()
        
        if success:
            return {
                "status": "success",
                "message": "Pinecone vector database initialized successfully",
                "index_name": self.engine.index_name
            }
        else:
            return {
                "status": "error", 
                "message": "Failed to initialize Pinecone vector database"
            }
    
    async def index_project_code(self, project_path: str) -> Dict[str, Any]:
        """Index a project's code for semantic search"""
        return await self.engine.index_code_repository(project_path)
    
    async def semantic_code_search(self, query: str, filters: Dict = None) -> Dict[str, Any]:
        """Perform semantic search on indexed code"""
        
        # Apply filters if provided
        top_k = filters.get("limit", 5) if filters else 5
        min_score = filters.get("min_score", 0.7) if filters else 0.7
        
        matches = await self.engine.find_similar_code(query, top_k, min_score)
        
        return {
            "status": "success",
            "query": query,
            "matches_found": len(matches),
            "matches": [asdict(match) for match in matches],
            "processing_time": self.engine.total_query_time / max(self.engine.query_count, 1)
        }
    
    async def security_pattern_analysis(self, language: str = None) -> Dict[str, Any]:
        """Find security vulnerabilities using pattern matching"""
        
        security_matches = await self.engine.find_code_patterns("security_vulnerabilities", language)
        
        # Categorize findings
        sql_injection = [m for m in security_matches if 'sql' in m.content.lower()]
        xss_vulnerabilities = [m for m in security_matches if 'xss' in m.content.lower() or 'innerhtml' in m.content.lower()]
        hardcoded_secrets = [m for m in security_matches if any(secret in m.content.lower() for secret in ['password', 'api_key', 'secret'])]
        
        return {
            "status": "success",
            "total_security_issues": len(security_matches),
            "categorized_findings": {
                "sql_injection_risks": len(sql_injection),
                "xss_vulnerabilities": len(xss_vulnerabilities), 
                "hardcoded_secrets": len(hardcoded_secrets)
            },
            "detailed_findings": [asdict(match) for match in security_matches[:10]]  # Top 10
        }
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics"""
        return await self.engine.get_repository_insights()

# Usage Examples and Testing
async def ymera_pinecone_demo():
    """Demonstration of YMERA Pinecone integration"""
    
    print("🚀 YMERA Pinecone Vector Database Demo")
    print("=" * 50)
    
    # Initialize engine
    api = YMERAPineconeAPI()
    
    # Setup database
    print("1. Setting up vector database...")
    setup_result = await api.setup_vector_database()
    print(f"   Result: {setup_result}")
    
    # Index sample code (simulate)
    sample_code_snippets = [
        {
            "content": """
def authenticate_user(username, password):
    # Vulnerable to SQL injection
    query = "SELECT * FROM users WHERE username = '" + username + "' AND password = '" + password + "'"
    return execute_query(query)
            """,
            "file_path": "auth/login.py",
            "language": "python"
        },
        {
            "content": """
async function processUserData(userData) {
    // Performance issue - nested loops
    for (let i = 0; i < userData.length; i++) {
        for (let j = 0; j < userData[i].items.length; j++) {
            await processItem(userData[i].items[j]);
        }
    }
}
            """,
            "file_path": "utils/processor.js",
            "language": "javascript"
        }
    ]
    
    # Simulate indexing (in real scenario, would use index_project_code)
    print("\n2. Indexing sample code...")
    
    # Semantic search demonstration
    print("\n3. Performing semantic search...")
    search_result = await api.semantic_code_search("SQL injection vulnerability authentication")
    print(f"   Found {search_result['matches_found']} similar patterns")
    
    # Security analysis
    print("\n4. Security pattern analysis...")
    security_result = await api.security_pattern_analysis()
    print(f"   Security issues found: {security_result['total_security_issues']}")
    
    # Database statistics
    print("\n5. Database statistics...")
    stats = await api.get_database_stats()
    print(f"   Total vectors: {stats.get('total_vectors', 0)}")
    print(f"   Query performance: {stats.get('query_performance', {})}")
    
    print("\n✅ YMERA Pinecone integration demo completed!")

# FastAPI endpoints for YMERA integration
def create_ymera_pinecone_routes():
    """Create FastAPI routes for Pinecone integration"""
    
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    
    app = FastAPI()
    pinecone_api = YMERAPineconeAPI()
    
    class SearchRequest(BaseModel):
        query: str
        filters: Optional[Dict] = None
    
    class IndexRequest(BaseModel):
        project_path: str
        supported_extensions: Optional[List[str]] = None
    
    @app.post("/api/vector/setup")
    async def setup_vector_db():
        """Initialize Pinecone vector database"""
        return await pinecone_api.setup_vector_database()
    
    @app.post("/api/vector/index")
    async def index_project(request: IndexRequest):
        """Index a project for semantic search"""
        return await pinecone_api.index_project_code(request.project_path)
    
    @app.post("/api/vector/search")
    async def semantic_search(request: SearchRequest):
        """Perform semantic code search"""
        return await pinecone_api.semantic_code_search(request.query, request.filters)
    
    @app.get("/api/vector/security-analysis")
    async def security_analysis(language: Optional[str] = None):
        """Analyze code for security patterns"""
        return await pinecone_api.security_pattern_analysis(language)
    
    @app.get("/api/vector/stats")
    async def database_stats():
        """Get vector database statistics"""
        return await pinecone_api.get_database_stats()
    
    return app

if __name__ == "__main__":
    asyncio.run(ymera_pinecone_demo())