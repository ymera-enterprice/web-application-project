# YMERA Enterprise Vector Database Extensions
# NumPy integration and additional ML/AI libraries for enhanced vector operations

import numpy as np
import asyncio
import hashlib
import json
import time
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import os
import re
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.cluster import KMeans
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
import joblib
from sentence_transformers import SentenceTransformer
import torch

# Download required NLTK data
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except:
    print("Warning: Could not download NLTK data")

@dataclass
class VectorMetrics:
    """Enhanced vector operation metrics"""
    embedding_model: str
    vector_dimensions: int
    similarity_threshold: float
    processing_time: float
    memory_usage_mb: float
    accuracy_score: float = 0.0

@dataclass
class CodeEmbedding:
    """Represents code embeddings with NumPy arrays"""
    id: str
    vector: np.ndarray
    metadata: Dict[str, Any]
    model_version: str
    created_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'vector': self.vector.tolist(),
            'metadata': self.metadata,
            'model_version': self.model_version,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CodeEmbedding':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            vector=np.array(data['vector']),
            metadata=data['metadata'],
            model_version=data['model_version'],
            created_at=data['created_at']
        )

class EnhancedVectorProcessor:
    """Advanced vector processing with NumPy and ML libraries"""
    
    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        self.embedding_model_name = embedding_model
        self.sentence_transformer = None
        self.tfidf_vectorizer = None
        self.stemmer = PorterStemmer()
        self.stop_words = set(stopwords.words('english'))
        
        # Vector storage
        self.embeddings_cache: Dict[str, CodeEmbedding] = {}
        self.vector_matrix: Optional[np.ndarray] = None
        self.vector_ids: List[str] = []
        
        # ML models for clustering and dimensionality reduction
        self.pca_model: Optional[PCA] = None
        self.svd_model: Optional[TruncatedSVD] = None
        self.kmeans_model: Optional[KMeans] = None
        
        # Performance metrics
        self.metrics = VectorMetrics(
            embedding_model=embedding_model,
            vector_dimensions=384,  # Default for MiniLM
            similarity_threshold=0.7,
            processing_time=0.0,
            memory_usage_mb=0.0
        )
    
    async def initialize_models(self) -> bool:
        """Initialize ML models and embeddings"""
        try:
            print(f"🤖 Initializing sentence transformer: {self.embedding_model_name}")
            self.sentence_transformer = SentenceTransformer(self.embedding_model_name)
            
            # Initialize TF-IDF vectorizer
            self.tfidf_vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words='english',
                ngram_range=(1, 2),
                min_df=2,
                max_df=0.8
            )
            
            # Update vector dimensions based on model
            if hasattr(self.sentence_transformer, 'get_sentence_embedding_dimension'):
                self.metrics.vector_dimensions = self.sentence_transformer.get_sentence_embedding_dimension()
            
            print(f"✅ Models initialized. Vector dimensions: {self.metrics.vector_dimensions}")
            return True
            
        except Exception as e:
            print(f"❌ Model initialization failed: {str(e)}")
            return False
    
    def preprocess_code_text(self, code: str) -> str:
        """Advanced text preprocessing for code"""
        # Remove comments
        code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)  # Python comments
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)  # JS/Java comments
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)  # Block comments
        
        # Remove strings and numbers for better semantic matching
        code = re.sub(r'["\'].*?["\']', ' STRING ', code)
        code = re.sub(r'\b\d+\b', ' NUMBER ', code)
        
        # Extract identifiers and keywords
        tokens = word_tokenize(code.lower())
        
        # Filter tokens
        filtered_tokens = []
        for token in tokens:
            if (len(token) > 2 and 
                token not in self.stop_words and 
                re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', token)):
                # Apply stemming
                stemmed = self.stemmer.stem(token)
                filtered_tokens.append(stemmed)
        
        return ' '.join(filtered_tokens)
    
    async def generate_code_embedding(self, code: str, metadata: Dict[str, Any]) -> CodeEmbedding:
        """Generate vector embedding for code using multiple approaches"""
        
        if not self.sentence_transformer:
            await self.initialize_models()
        
        start_time = time.time()
        
        # Preprocess code
        processed_code = self.preprocess_code_text(code)
        
        # Generate sentence transformer embedding
        embedding_vector = self.sentence_transformer.encode(processed_code)
        
        # Ensure numpy array
        if not isinstance(embedding_vector, np.ndarray):
            embedding_vector = np.array(embedding_vector)
        
        # Normalize vector
        embedding_vector = embedding_vector / np.linalg.norm(embedding_vector)
        
        # Create embedding object
        code_embedding = CodeEmbedding(
            id=metadata.get('id', hashlib.md5(code.encode()).hexdigest()),
            vector=embedding_vector,
            metadata=metadata,
            model_version=self.embedding_model_name,
            created_at=datetime.now().isoformat()
        )
        
        # Cache embedding
        self.embeddings_cache[code_embedding.id] = code_embedding
        
        # Update processing time
        processing_time = time.time() - start_time
        self.metrics.processing_time = processing_time
        
        return code_embedding
    
    def build_vector_matrix(self) -> np.ndarray:
        """Build vector matrix from cached embeddings for batch operations"""
        
        if not self.embeddings_cache:
            return np.array([])
        
        vectors = []
        self.vector_ids = []
        
        for embedding_id, embedding in self.embeddings_cache.items():
            vectors.append(embedding.vector)
            self.vector_ids.append(embedding_id)
        
        self.vector_matrix = np.vstack(vectors)
        print(f"📊 Built vector matrix: {self.vector_matrix.shape}")
        
        return self.vector_matrix
    
    def compute_similarity_matrix(self, query_vector: np.ndarray = None) -> np.ndarray:
        """Compute cosine similarity matrix using NumPy"""
        
        if self.vector_matrix is None:
            self.build_vector_matrix()
        
        if query_vector is not None:
            # Similarity between query and all vectors
            query_vector = query_vector.reshape(1, -1)
            similarities = cosine_similarity(query_vector, self.vector_matrix)
            return similarities.flatten()
        else:
            # Pairwise similarities between all vectors
            return cosine_similarity(self.vector_matrix)
    
    async def find_similar_embeddings(self, query_code: str, top_k: int = 5, 
                                    similarity_threshold: float = 0.7) -> List[Tuple[str, float, Dict]]:
        """Find similar code embeddings using NumPy operations"""
        
        # Generate query embedding
        query_metadata = {'id': 'query', 'content': query_code}
        query_embedding = await self.generate_code_embedding(query_code, query_metadata)
        
        if self.vector_matrix is None:
            self.build_vector_matrix()
        
        if self.vector_matrix.size == 0:
            return []
        
        # Compute similarities
        similarities = self.compute_similarity_matrix(query_embedding.vector)
        
        # Get top-k similar embeddings
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if similarities[idx] >= similarity_threshold:
                embedding_id = self.vector_ids[idx]
                embedding = self.embeddings_cache[embedding_id]
                results.append((embedding_id, similarities[idx], embedding.metadata))
        
        return results
    
    def perform_clustering(self, n_clusters: int = 5) -> Dict[str, Any]:
        """Perform K-means clustering on code embeddings"""
        
        if self.vector_matrix is None:
            self.build_vector_matrix()
        
        if self.vector_matrix.size == 0:
            return {"error": "No vectors available for clustering"}
        
        # Apply K-means clustering
        self.kmeans_model = KMeans(n_clusters=n_clusters, random_state=42)
        cluster_labels = self.kmeans_model.fit_predict(self.vector_matrix)
        
        # Organize results by cluster
        clusters = {}
        for i, label in enumerate(cluster_labels):
            if label not in clusters:
                clusters[label] = []
            
            embedding_id = self.vector_ids[i]
            embedding = self.embeddings_cache[embedding_id]
            clusters[label].append({
                'id': embedding_id,
                'metadata': embedding.metadata
            })
        
        # Compute cluster statistics
        cluster_stats = {}
        for cluster_id, items in clusters.items():
            cluster_vectors = self.vector_matrix[cluster_labels == cluster_id]
            centroid = np.mean(cluster_vectors, axis=0)
            inertia = np.sum(np.linalg.norm(cluster_vectors - centroid, axis=1) ** 2)
            
            cluster_stats[cluster_id] = {
                'size': len(items),
                'inertia': float(inertia),
                'centroid_norm': float(np.linalg.norm(centroid))
            }
        
        return {
            'clusters': clusters,
            'cluster_stats': cluster_stats,
            'total_inertia': float(self.kmeans_model.inertia_),
            'n_clusters': n_clusters
        }
    
    def reduce_dimensions(self, method: str = 'pca', n_components: int = 50) -> np.ndarray:
        """Reduce vector dimensions using PCA or SVD"""
        
        if self.vector_matrix is None:
            self.build_vector_matrix()
        
        if method.lower() == 'pca':
            self.pca_model = PCA(n_components=n_components)
            reduced_vectors = self.pca_model.fit_transform(self.vector_matrix)
            print(f"📉 PCA: Reduced from {self.vector_matrix.shape[1]} to {n_components} dimensions")
            print(f"   Explained variance ratio: {self.pca_model.explained_variance_ratio_.sum():.3f}")
            
        elif method.lower() == 'svd':
            self.svd_model = TruncatedSVD(n_components=n_components)
            reduced_vectors = self.svd_model.fit_transform(self.vector_matrix)
            print(f"📉 SVD: Reduced from {self.vector_matrix.shape[1]} to {n_components} dimensions")
            print(f"   Explained variance ratio: {self.svd_model.explained_variance_ratio_.sum():.3f}")
        
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return reduced_vectors
    
    def compute_vector_statistics(self) -> Dict[str, Any]:
        """Compute comprehensive statistics about vectors"""
        
        if self.vector_matrix is None:
            self.build_vector_matrix()
        
        if self.vector_matrix.size == 0:
            return {"error": "No vectors available"}
        
        stats = {
            'total_vectors': self.vector_matrix.shape[0],
            'vector_dimensions': self.vector_matrix.shape[1],
            'mean_vector_norm': float(np.mean(np.linalg.norm(self.vector_matrix, axis=1))),
            'std_vector_norm': float(np.std(np.linalg.norm(self.vector_matrix, axis=1))),
            'min_vector_norm': float(np.min(np.linalg.norm(self.vector_matrix, axis=1))),
            'max_vector_norm': float(np.max(np.linalg.norm(self.vector_matrix, axis=1))),
            'memory_usage_mb': float(self.vector_matrix.nbytes / (1024 * 1024))
        }
        
        # Compute pairwise similarity statistics
        if self.vector_matrix.shape[0] > 1:
            similarity_matrix = cosine_similarity(self.vector_matrix)
            # Remove diagonal (self-similarities)
            similarity_values = similarity_matrix[np.triu_indices_from(similarity_matrix, k=1)]
            
            stats.update({
                'mean_similarity': float(np.mean(similarity_values)),
                'std_similarity': float(np.std(similarity_values)),
                'min_similarity': float(np.min(similarity_values)),
                'max_similarity': float(np.max(similarity_values))
            })
        
        return stats
    
    def save_embeddings(self, filepath: str) -> bool:
        """Save embeddings to disk using joblib"""
        try:
            # Convert embeddings to serializable format
            embeddings_data = {
                'embeddings': {eid: emb.to_dict() for eid, emb in self.embeddings_cache.items()},
                'vector_matrix': self.vector_matrix,
                'vector_ids': self.vector_ids,
                'metrics': asdict(self.metrics)
            }
            
            joblib.dump(embeddings_data, filepath)
            print(f"💾 Embeddings saved to {filepath}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to save embeddings: {str(e)}")
            return False
    
    def load_embeddings(self, filepath: str) -> bool:
        """Load embeddings from disk"""
        try:
            embeddings_data = joblib.load(filepath)
            
            # Restore embeddings
            self.embeddings_cache = {
                eid: CodeEmbedding.from_dict(emb_data) 
                for eid, emb_data in embeddings_data['embeddings'].items()
            }
            
            self.vector_matrix = embeddings_data.get('vector_matrix')
            self.vector_ids = embeddings_data.get('vector_ids', [])
            
            if 'metrics' in embeddings_data:
                self.metrics = VectorMetrics(**embeddings_data['metrics'])
            
            print(f"📂 Embeddings loaded from {filepath}")
            print(f"   Loaded {len(self.embeddings_cache)} embeddings")
            return True
            
        except Exception as e:
            print(f"❌ Failed to load embeddings: {str(e)}")
            return False

class AdvancedCodeAnalyzer:
    """Advanced code analysis using ML techniques"""
    
    def __init__(self):
        self.vector_processor = EnhancedVectorProcessor()
        self.code_patterns = {}
        self.analysis_cache = {}
    
    async def analyze_code_quality(self, code: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze code quality using ML approaches"""
        
        # Generate embedding
        embedding = await self.vector_processor.generate_code_embedding(code, metadata)
        
        # Extract features
        features = self._extract_ml_features(code)
        
        # Complexity analysis
        complexity_score = self._calculate_complexity_score(code)
        
        # Pattern matching
        patterns = self._detect_code_patterns(code)
        
        # Quality metrics
        quality_metrics = {
            'readability_score': self._calculate_readability_score(code),
            'maintainability_index': self._calculate_maintainability_index(code),
            'cyclomatic_complexity': complexity_score,
            'code_length': len(code),
            'comment_ratio': self._calculate_comment_ratio(code)
        }
        
        return {
            'embedding_id': embedding.id,
            'features': features,
            'patterns': patterns,
            'quality_metrics': quality_metrics,
            'overall_score': np.mean(list(quality_metrics.values()))
        }
    
    def _extract_ml_features(self, code: str) -> Dict[str, float]:
        """Extract numerical features for ML analysis"""
        
        lines = code.split('\n')
        
        features = {
            'line_count': len(lines),
            'avg_line_length': np.mean([len(line) for line in lines]) if lines else 0,
            'max_line_length': max([len(line) for line in lines]) if lines else 0,
            'blank_line_ratio': sum(1 for line in lines if not line.strip()) / len(lines) if lines else 0,
            'indentation_consistency': self._calculate_indentation_consistency(lines),
            'keyword_density': self._calculate_keyword_density(code),
            'operator_density': self._calculate_operator_density(code),
            'nesting_depth': self._calculate_max_nesting_depth(code)
        }
        
        return features
    
    def _calculate_complexity_score(self, code: str) -> float:
        """Calculate cyclomatic complexity"""
        
        # Simple approximation of cyclomatic complexity
        decision_keywords = ['if', 'elif', 'else', 'for', 'while', 'try', 'except', 'case', 'switch']
        
        complexity = 1  # Base complexity
        for keyword in decision_keywords:
            complexity += len(re.findall(rf'\b{keyword}\b', code, re.IGNORECASE))
        
        return float(complexity)
    
    def _calculate_readability_score(self, code: str) -> float:
        """Calculate code readability score"""
        
        lines = [line.strip() for line in code.split('\n') if line.strip()]
        if not lines:
            return 0.0
        
        # Factors affecting readability
        avg_line_length = np.mean([len(line) for line in lines])
        long_line_penalty = sum(1 for line in lines if len(line) > 80) / len(lines)
        comment_bonus = self._calculate_comment_ratio(code) * 0.2
        
        # Normalize to 0-1 scale
        readability = max(0, 1 - (avg_line_length / 100) - long_line_penalty + comment_bonus)
        
        return float(min(1.0, readability))
    
    def _calculate_maintainability_index(self, code: str) -> float:
        """Calculate maintainability index"""
        
        lines_of_code = len([line for line in code.split('\n') if line.strip()])
        complexity = self._calculate_complexity_score(code)
        comment_ratio = self._calculate_comment_ratio(code)
        
        # Simplified maintainability index
        if lines_of_code == 0:
            return 0.0
        
        mi = 171 - 5.2 * np.log(lines_of_code) - 0.23 * complexity + 16.2 * np.log(lines_of_code) * comment_ratio
        
        # Normalize to 0-1 scale
        return float(max(0, min(1, mi / 100)))
    
    def _calculate_comment_ratio(self, code: str) -> float:
        """Calculate ratio of comment lines to total lines"""
        
        lines = code.split('\n')
        if not lines:
            return 0.0
        
        comment_lines = 0
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith('#') or 
                stripped.startswith('//') or 
                stripped.startswith('/*') or 
                stripped.startswith('*')):
                comment_lines += 1
        
        return comment_lines / len(lines)
    
    def _calculate_indentation_consistency(self, lines: List[str]) -> float:
        """Calculate indentation consistency score"""
        
        indentations = []
        for line in lines:
            if line.strip():  # Skip empty lines
                leading_spaces = len(line) - len(line.lstrip())
                indentations.append(leading_spaces)
        
        if not indentations:
            return 1.0
        
        # Check for consistent indentation (typically 2, 4, or 8 spaces)
        common_indents = [2, 4, 8]
        consistency_scores = []
        
        for indent_size in common_indents:
            if indent_size > 0:
                consistent = sum(1 for ind in indentations if ind % indent_size == 0)
                consistency_scores.append(consistent / len(indentations))
        
        return float(max(consistency_scores) if consistency_scores else 0.0)
    
    def _calculate_keyword_density(self, code: str) -> float:
        """Calculate programming keyword density"""
        
        keywords = ['def', 'class', 'if', 'else', 'for', 'while', 'try', 'except', 'import', 'return']
        
        words = re.findall(r'\b\w+\b', code.lower())
        if not words:
            return 0.0
        
        keyword_count = sum(1 for word in words if word in keywords)
        return keyword_count / len(words)
    
    def _calculate_operator_density(self, code: str) -> float:
        """Calculate operator density"""
        
        operators = ['+', '-', '*', '/', '=', '==', '!=', '<', '>', '<=', '>=', '&&', '||']
        
        total_chars = len(code)
        if total_chars == 0:
            return 0.0
        
        operator_count = sum(code.count(op) for op in operators)
        return operator_count / total_chars
    
    def _calculate_max_nesting_depth(self, code: str) -> int:
        """Calculate maximum nesting depth"""
        
        max_depth = 0
        current_depth = 0
        
        for line in code.split('\n'):
            stripped = line.strip()
            if any(keyword in stripped for keyword in ['if', 'for', 'while', 'try', 'def', 'class']):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif stripped in ['end', '}'] or (stripped.startswith('except') or stripped.startswith('finally')):
                current_depth = max(0, current_depth - 1)
        
        return max_depth
    
    def _detect_code_patterns(self, code: str) -> List[str]:
        """Detect common code patterns"""
        
        patterns = []
        
        # Design patterns
        if re.search(r'class.*Factory', code, re.IGNORECASE):
            patterns.append('factory_pattern')
        
        if re.search(r'class.*Singleton', code, re.IGNORECASE):
            patterns.append('singleton_pattern')
        
        if re.search(r'class.*Observer', code, re.IGNORECASE):
            patterns.append('observer_pattern')
        
        # Anti-patterns
        if re.search(r'def.*\(.*,.*,.*,.*,.*,.*\)', code):
            patterns.append('long_parameter_list')
        
        if len(code.split('\n')) > 50 and 'def ' in code:
            patterns.append('long_method')
        
        if code.count('if') > 5:
            patterns.append('complex_conditional')
        
        return patterns

# Integration with original YMERA system
class YMERAEnhancedPineconeEngine:
    """Enhanced YMERA Pinecone engine with NumPy and ML capabilities"""
    
    def __init__(self, api_key: str = None, environment: str = "us-west1-gcp"):
        # Initialize original engine components
        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        self.environment = environment
        self.pc = None
        self.index_name = "ymera-enterprise-enhanced-v1"
        self.index = None
        
        # Initialize enhanced components
        self.vector_processor = EnhancedVectorProcessor()
        self.code_analyzer = AdvancedCodeAnalyzer()
        
        # Performance tracking
        self.query_count = 0
        self.total_query_time = 0.0
        self.cache = {}
    
    async def initialize_enhanced(self) -> bool:
        """Initialize enhanced vector processing capabilities"""
        
        # Initialize ML models
        models_ready = await self.vector_processor.initialize_models()
        
        if models_ready:
            print("🚀 Enhanced YMERA Pinecone Engine initialized successfully")
            print(f"   Vector dimensions: {self.vector_processor.metrics.vector_dimensions}")
            print(f"   Embedding model: {self.vector_processor.embedding_model_name}")
            return True
        else:
            print("❌ Failed to initialize enhanced capabilities")
            return False
    
    async def enhanced_code_indexing(self, repository_path: str) -> Dict[str, Any]:
        """Enhanced code indexing with ML analysis"""
        
        start_time = time.time()
        results = {
            'processed_files': 0,
            'total_embeddings': 0,
            'quality_analysis': {},
            'clustering_results': {},
            'processing_time': 0.0
        }
        
        # Process code files
        code_files = list(Path(repository_path).rglob("*.py"))  # Focus on Python for demo
        
        for file_path in code_files[:10]:  # Limit for demo
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                if len(content.strip()) < 50:
                    continue
                
                # Enhanced analysis
                metadata = {
                    'id': hashlib.md5(f"{file_path}:{content}".encode()).hexdigest(),
                    'file_path': str(file_path),
                    'content': content[:1000]  # Truncated for metadata
                }
                
                # Generate embedding with quality analysis
                embedding = await self.vector_processor.generate_code_embedding(content, metadata)
                quality_analysis = await self.code_analyzer.analyze_code_quality(content, metadata)
                
                results['total_embeddings'] += 1
                results['quality_analysis'][str(file_path)] = quality_analysis
                
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
                continue
            
            results['processed_files'] += 1
        
        # Perform clustering analysis
        if results['total_embeddings'] > 3:
            clustering_results = self.vector_processor.perform_clustering(n_clusters=min(3, results['total_embeddings']))
            results['clustering_results'] = clustering_results
        
        results['processing_time'] = time.time() - start_time
        
        return results
    
    async def enhanced_similarity_search(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Enhanced similarity search with detailed analysis"""
        
        start_time = time.time()
        
        # Find similar embeddings
        similar_embeddings = await self.vector_processor.find_similar_embeddings(
            query, top_k=top_k
        )
        
        # Compute vector statistics
        vector_stats = self.vector_processor.compute_vector_statistics()
        
        results = {
            'query': query,
            'matches': [],
            'vector_statistics': vector_stats,
            'processing_time': time.time() - start_time
        }
        
        for embedding_id, similarity, metadata in similar_embeddings:
            results['matches'].append({
                'id': embedding_id,
                'similarity_score': float(similarity),
                'metadata': metadata,
                'match_type': 'semantic' if similarity > 0.8 else 'structural'
            })
        
        return results
    
    def save_enhanced_model(self, filepath: str) -> bool:
        """Save enhanced model state"""
        return self.vector_processor.save_embeddings(filepath)
    
    def load_enhanced_model(self, filepath: str) -> bool:
        """Load enhanced model state"""
        return self.vector_processor.load_embeddings(filepath)

# Demo function
async def enhanced_ymera_demo():
    """Demonstration of enhanced YMERA capabilities"""
    
    print("🚀 Enhanced YMERA Vector Database Demo")
    print("=" * 60)
    
    # Initialize enhanced engine
    engine = YMERAEnhancedPineconeEngine()
    
    # Initialize ML models
    print("1. Initializing ML models...")
    await engine.initialize_enhanced()
    
    # Create sample code for testing
    sample_codes = [
        """
def calculate_fibonacci(n):
    '''Calculate Fibonacci number recursively'''
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
        """,
        """
class DatabaseConnection:
    def __init__(self, host, username, password):
        # Security risk: hardcoded credentials
        self.connection_string = f"mysql://{username}:{password}@{host}/db"
        
    def execute_query(self, query, user_input):
        # SQL injection vulnerability
        sql = f"SELECT * FROM users WHERE name = '{user_input}'"
        return self.connection.execute(sql)
        """,
        """
async def process_large_dataset(data):
    '''Process large dataset efficiently'''
    results = []
    
    # Batch processing for better performance
    batch_size = 1000
    for i in range(0, len(data), batch_size):
        batch = data[i:i+batch_size]
        
        # Parallel processing
        tasks = [process_item(item) for item in batch]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)
        
    return results
        """,
        """
def validate_user_input(user_data):
    '''Validate and sanitize user input'''
    import re
    
    # Input validation
    if not user_data or len(user_data) > 1000:
        raise ValueError("Invalid input length")
    
    # Sanitization
    sanitized = re.sub(r'[<>"\']', '', user_data)
    
    # XSS prevention
    dangerous_patterns = ['<script', 'javascript:', 'onload=']
    for pattern in dangerous_patterns:
        if pattern in sanitized.lower():
            raise ValueError("Potentially dangerous input detected")
    
    return sanitized
        """
    ]
    
    # Process sample codes
    print("\n2. Processing sample code snippets...")
    for i, code in enumerate(sample_codes):
        metadata = {
            'id': f'sample_{i}',
            'file_path': f'samples/code_{i}.py',
            'content': code
        }
        
        # Generate embedding and analyze
        embedding = await engine.vector_processor.generate_code_embedding(code, metadata)
        analysis = await engine.code_analyzer.analyze_code_quality(code, metadata)
        
        print(f"   Sample {i+1}: Quality Score = {analysis['overall_score']:.3f}")
    
    # Build vector matrix for batch operations
    print("\n3. Building vector matrix...")
    engine.vector_processor.build_vector_matrix()
    
    # Compute vector statistics
    print("\n4. Computing vector statistics...")
    stats = engine.vector_processor.compute_vector_statistics()
    print(f"   Total vectors: {stats['total_vectors']}")
    print(f"   Vector dimensions: {stats['vector_dimensions']}")
    print(f"   Memory usage: {stats['memory_usage_mb']:.2f} MB")
    print(f"   Mean similarity: {stats.get('mean_similarity', 0):.3f}")
    
    # Perform clustering
    print("\n5. Performing code clustering...")
    clustering_results = engine.vector_processor.perform_clustering(n_clusters=2)
    print(f"   Found {len(clustering_results['clusters'])} clusters")
    print(f"   Total inertia: {clustering_results['total_inertia']:.3f}")
    
    # Test similarity search
    print("\n6. Testing similarity search...")
    search_query = "database security vulnerability SQL injection"
    search_results = await engine.enhanced_similarity_search(search_query, top_k=3)
    
    print(f"   Query: '{search_query}'")
    print(f"   Found {len(search_results['matches'])} matches:")
    for match in search_results['matches']:
        print(f"     - Similarity: {match['similarity_score']:.3f} ({match['match_type']})")
    
    # Dimensionality reduction
    print("\n7. Testing dimensionality reduction...")
    reduced_vectors_pca = engine.vector_processor.reduce_dimensions('pca', n_components=10)
    reduced_vectors_svd = engine.vector_processor.reduce_dimensions('svd', n_components=10)
    
    print(f"   PCA reduced shape: {reduced_vectors_pca.shape}")
    print(f"   SVD reduced shape: {reduced_vectors_svd.shape}")
    
    # Save model
    print("\n8. Saving enhanced model...")
    model_path = "ymera_enhanced_model.joblib"
    engine.save_enhanced_model(model_path)
    
    print("\n✅ Enhanced YMERA demo completed successfully!")
    
    return {
        'vector_stats': stats,
        'clustering_results': clustering_results,
        'search_results': search_results,
        'model_saved': model_path
    }

# Additional utility functions for YMERA integration

class VectorDatabaseBenchmark:
    """Benchmark vector database operations"""
    
    def __init__(self):
        self.results = {}
    
    async def benchmark_embedding_generation(self, processor: EnhancedVectorProcessor, 
                                           code_samples: List[str], iterations: int = 3) -> Dict[str, float]:
        """Benchmark embedding generation performance"""
        
        times = []
        
        for iteration in range(iterations):
            start_time = time.time()
            
            for i, code in enumerate(code_samples):
                metadata = {'id': f'bench_{i}', 'content': code}
                await processor.generate_code_embedding(code, metadata)
            
            iteration_time = time.time() - start_time
            times.append(iteration_time)
        
        return {
            'avg_time': np.mean(times),
            'std_time': np.std(times),
            'min_time': np.min(times),
            'max_time': np.max(times),
            'samples_processed': len(code_samples),
            'avg_time_per_sample': np.mean(times) / len(code_samples)
        }
    
    async def benchmark_similarity_search(self, processor: EnhancedVectorProcessor,
                                        queries: List[str], iterations: int = 3) -> Dict[str, float]:
        """Benchmark similarity search performance"""
        
        times = []
        
        for iteration in range(iterations):
            start_time = time.time()
            
            for query in queries:
                await processor.find_similar_embeddings(query, top_k=5)
            
            iteration_time = time.time() - start_time
            times.append(iteration_time)
        
        return {
            'avg_time': np.mean(times),
            'std_time': np.std(times),
            'queries_processed': len(queries),
            'avg_time_per_query': np.mean(times) / len(queries)
        }

class CodePatternLibrary:
    """Library of code patterns for analysis"""
    
    def __init__(self):
        self.security_patterns = {
            'sql_injection': [
                r'execute\s*\(\s*["\'].*\+.*["\']',
                r'query\s*=\s*["\'].*%.*["\']',
                r'SELECT.*\+.*FROM'
            ],
            'xss_vulnerability': [
                r'innerHTML\s*=\s*.*\+',
                r'document\.write\s*\(',
                r'eval\s*\(',
                r'dangerouslySetInnerHTML'
            ],
            'hardcoded_secrets': [
                r'password\s*=\s*["\'][^"\']+["\']',
                r'api_key\s*=\s*["\'][^"\']+["\']',
                r'secret\s*=\s*["\'][^"\']+["\']',
                r'token\s*=\s*["\'][^"\']+["\']'
            ]
        }
        
        self.performance_patterns = {
            'nested_loops': [
                r'for.*:\s*\n.*for.*:',
                r'while.*:\s*\n.*while.*:'
            ],
            'inefficient_operations': [
                r'\.append\s*\(.*\)\s*\n.*\.append',
                r'string.*\+.*string',
                r'list\(.*\)\s*\+\s*list\('
            ]
        }
        
        self.quality_patterns = {
            'long_methods': [
                r'def\s+\w+.*:\s*\n(?:.*\n){50,}'
            ],
            'complex_conditions': [
                r'if.*and.*and.*and',
                r'if.*or.*or.*or'
            ]
        }
    
    def analyze_code_patterns(self, code: str) -> Dict[str, List[str]]:
        """Analyze code for various patterns"""
        
        results = {
            'security_issues': [],
            'performance_issues': [],
            'quality_issues': []
        }
        
        # Check security patterns
        for pattern_type, patterns in self.security_patterns.items():
            for pattern in patterns:
                if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
                    results['security_issues'].append(pattern_type)
        
        # Check performance patterns
        for pattern_type, patterns in self.performance_patterns.items():
            for pattern in patterns:
                if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
                    results['performance_issues'].append(pattern_type)
        
        # Check quality patterns
        for pattern_type, patterns in self.quality_patterns.items():
            for pattern in patterns:
                if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
                    results['quality_issues'].append(pattern_type)
        
        return results

# FastAPI integration for enhanced capabilities
def create_enhanced_ymera_api():
    """Create FastAPI application with enhanced vector capabilities"""
    
    from fastapi import FastAPI, HTTPException, BackgroundTasks
    from pydantic import BaseModel
    from typing import Optional, List
    
    app = FastAPI(title="Enhanced YMERA Vector Database API", version="2.0.0")
    
    # Global engine instance
    engine = YMERAEnhancedPineconeEngine()
    benchmark = VectorDatabaseBenchmark()
    pattern_library = CodePatternLibrary()
    
    class CodeAnalysisRequest(BaseModel):
        code: str
        metadata: Optional[Dict[str, Any]] = {}
    
    class SimilaritySearchRequest(BaseModel):
        query: str
        top_k: Optional[int] = 5
        similarity_threshold: Optional[float] = 0.7
    
    class ClusteringRequest(BaseModel):
        n_clusters: Optional[int] = 5
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize enhanced capabilities on startup"""
        await engine.initialize_enhanced()
    
    @app.post("/api/enhanced/analyze-code")
    async def analyze_code_endpoint(request: CodeAnalysisRequest):
        """Analyze code quality and generate embeddings"""
        try:
            # Generate embedding
            embedding = await engine.vector_processor.generate_code_embedding(
                request.code, request.metadata
            )
            
            # Perform quality analysis
            quality_analysis = await engine.code_analyzer.analyze_code_quality(
                request.code, request.metadata
            )
            
            # Pattern analysis
            pattern_analysis = pattern_library.analyze_code_patterns(request.code)
            
            return {
                "status": "success",
                "embedding_id": embedding.id,
                "quality_analysis": quality_analysis,
                "pattern_analysis": pattern_analysis,
                "vector_dimensions": len(embedding.vector)
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/enhanced/similarity-search")
    async def enhanced_similarity_search_endpoint(request: SimilaritySearchRequest):
        """Perform enhanced similarity search"""
        try:
            results = await engine.enhanced_similarity_search(
                request.query, top_k=request.top_k
            )
            return results
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/enhanced/clustering")
    async def clustering_endpoint(request: ClusteringRequest):
        """Perform clustering analysis on embeddings"""
        try:
            clustering_results = engine.vector_processor.perform_clustering(
                n_clusters=request.n_clusters
            )
            return {
                "status": "success",
                "clustering_results": clustering_results
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/enhanced/vector-stats")
    async def vector_statistics_endpoint():
        """Get comprehensive vector statistics"""
        try:
            stats = engine.vector_processor.compute_vector_statistics()
            return {
                "status": "success",
                "statistics": stats
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/enhanced/dimensionality-reduction")
    async def dimensionality_reduction_endpoint(method: str = "pca", n_components: int = 50):
        """Perform dimensionality reduction"""
        try:
            reduced_vectors = engine.vector_processor.reduce_dimensions(method, n_components)
            
            return {
                "status": "success",
                "method": method,
                "original_dimensions": engine.vector_processor.vector_matrix.shape[1],
                "reduced_dimensions": reduced_vectors.shape[1],
                "reduced_shape": reduced_vectors.shape
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/enhanced/benchmark")
    async def benchmark_endpoint(background_tasks: BackgroundTasks):
        """Run performance benchmarks"""
        
        async def run_benchmarks():
            # Sample codes for benchmarking
            sample_codes = [
                "def hello(): return 'world'",
                "class Example: pass",
                "for i in range(10): print(i)"
            ]
            
            # Benchmark embedding generation
            embedding_benchmark = await benchmark.benchmark_embedding_generation(
                engine.vector_processor, sample_codes
            )
            
            # Benchmark similarity search
            queries = ["function definition", "class declaration", "loop iteration"]
            search_benchmark = await benchmark.benchmark_similarity_search(
                engine.vector_processor, queries
            )
            
            return {
                "embedding_performance": embedding_benchmark,
                "search_performance": search_benchmark
            }
        
        # Run benchmarks in background
        background_tasks.add_task(run_benchmarks)
        
        return {"status": "Benchmarks started in background"}
    
    @app.post("/api/enhanced/save-model")
    async def save_model_endpoint(filepath: str = "ymera_model.joblib"):
        """Save the enhanced model to disk"""
        try:
            success = engine.save_enhanced_model(filepath)
            
            if success:
                return {
                    "status": "success",
                    "message": f"Model saved to {filepath}",
                    "embeddings_count": len(engine.vector_processor.embeddings_cache)
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to save model")
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/enhanced/load-model")
    async def load_model_endpoint(filepath: str = "ymera_model.joblib"):
        """Load an enhanced model from disk"""
        try:
            success = engine.load_enhanced_model(filepath)
            
            if success:
                return {
                    "status": "success",
                    "message": f"Model loaded from {filepath}",
                    "embeddings_count": len(engine.vector_processor.embeddings_cache)
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to load model")
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return app

# Main execution
if __name__ == "__main__":
    import asyncio
    
    # Run the enhanced demo
    asyncio.run(enhanced_ymera_demo())