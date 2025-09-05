
"""
Enhanced Tavily Search Service for YMERA Enterprise Platform
Multi-key load balancing with agent-specific search strategies
"""

import asyncio
import random
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    TavilyClient = None

logger = logging.getLogger(__name__)

class EnhancedTavilyManager:
    """Enhanced Tavily search manager with load balancing and agent-specific strategies"""
    
    def __init__(self):
        self.api_keys = [
            "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",  # Primary key from config
            # Add additional keys from environment variables
        ]
        # Filter out None/empty keys
        self.api_keys = [key for key in self.api_keys if key and key.strip()]
        
        self.mcp_endpoints = [
            "https://tavily.api.tadata.com/mcp/tavily/grouchy-prevent-cucumber-t2vksr",
            "https://tavily.api.tadata.com/mcp/tavily/power-go-kart-sitar-idkvam", 
            "https://tavily.api.tadata.com/mcp/tavily/obsolete-merciful-earrings-tphbxw"
        ]
        
        self.current_key_index = 0
        self.agent_search_strategies = self._initialize_search_strategies()
        
    def _initialize_search_strategies(self) -> Dict[str, Dict[str, Any]]:
        """Initialize agent-specific search strategies"""
        return {
            "code_editing": {
                "domains": [
                    "stackoverflow.com", "github.com", "docs.python.org",
                    "developer.mozilla.org", "reactjs.org", "fastapi.tiangolo.com"
                ],
                "search_depth": "basic",
                "max_results": 8
            },
            "examination": {
                "domains": [
                    "security.org", "owasp.org", "nvd.nist.gov",
                    "snyk.io", "sonarqube.org", "cwe.mitre.org"
                ],
                "search_depth": "advanced",
                "max_results": 10
            },
            "enhancement": {
                "domains": [
                    "refactoring.guru", "clean-code-developer.com",
                    "martinfowler.com", "patterns.dev", "google.github.io"
                ],
                "search_depth": "advanced",
                "max_results": 12
            },
            "general": {
                "search_depth": "basic",
                "max_results": 6
            }
        }
    
    def get_client_with_failover(self) -> Optional[TavilyClient]:
        """Get Tavily client with automatic failover"""
        if not TAVILY_AVAILABLE:
            logger.warning("Tavily package not available")
            return None
            
        if not self.api_keys:
            logger.warning("No Tavily API keys configured")
            return None
            
        for attempt in range(len(self.api_keys)):
            try:
                key_index = (self.current_key_index + attempt) % len(self.api_keys)
                client = TavilyClient(self.api_keys[key_index])
                self.current_key_index = key_index
                return client
            except Exception as e:
                logger.warning(f"Tavily API key {key_index} failed: {e}")
                continue
                
        logger.error("All Tavily API keys failed")
        return None
    
    async def agent_research(self, query: str, agent_type: str = "general") -> Dict[str, Any]:
        """Specialized research for different YMERA agents"""
        try:
            client = self.get_client_with_failover()
            if not client:
                return {
                    "success": False,
                    "error": "Tavily client not available",
                    "agent_type": agent_type,
                    "query": query,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Get agent-specific search parameters
            strategy = self.agent_search_strategies.get(agent_type, self.agent_search_strategies["general"])
            
            search_params = {
                "query": query,
                "max_results": strategy.get("max_results", 6)
            }
            
            if "domains" in strategy:
                search_params["include_domains"] = strategy["domains"]
            
            if "search_depth" in strategy:
                search_params["search_depth"] = strategy["search_depth"]
            
            # Execute search
            response = client.search(**search_params)
            
            return {
                "success": True,
                "results": response,
                "agent_type": agent_type,
                "query": query,
                "strategy_used": strategy,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Tavily search failed for {agent_type}: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_type": agent_type,
                "query": query,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def multi_agent_research(self, queries: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Execute multiple research queries concurrently"""
        tasks = []
        for query_info in queries:
            query = query_info.get("query", "")
            agent_type = query_info.get("agent_type", "general")
            task = self.agent_research(query, agent_type)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "error": str(result),
                    "query_index": i,
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    def extract_research_context(self, results: Dict[str, Any], max_length: int = 2000) -> str:
        """Extract relevant context from search results"""
        if not results.get("success") or not results.get("results"):
            return ""
        
        context_snippets = []
        total_length = 0
        
        for result in results["results"].get("results", []):
            if "content" in result and total_length < max_length:
                snippet = result["content"][:500]
                if total_length + len(snippet) <= max_length:
                    context_snippets.append(snippet)
                    total_length += len(snippet)
                else:
                    remaining = max_length - total_length
                    if remaining > 100:  # Only add if meaningful length remains
                        context_snippets.append(snippet[:remaining])
                    break
        
        return "\n\n---\n\n".join(context_snippets)

# Global instance for use across the platform
tavily_manager = EnhancedTavilyManager()
"""
YMERA Enterprise Tavily Search Service
Enhanced web search capabilities with intelligent API key management
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ymera.services.tavily")

class TavilySearchManager:
    """Enhanced Tavily search manager with intelligent key rotation"""
    
    def __init__(self):
        self.api_keys = [
            "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",
            "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", 
            "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"
        ]
        self.current_key_index = 0
        
    async def agent_research(self, query: str, agent_type: str = "general") -> Dict[str, Any]:
        """Perform agent-specific research with web search"""
        try:
            # Mock implementation for now
            results = {
                "success": True,
                "query": query,
                "agent_type": agent_type,
                "results": [
                    {
                        "title": f"Research result for: {query}",
                        "url": "https://example.com",
                        "content": f"Mock research content for {query} from {agent_type} agent perspective",
                        "relevance_score": 0.95
                    }
                ],
                "timestamp": datetime.utcnow().isoformat(),
                "processing_time": 0.5
            }
            
            return results
            
        except Exception as e:
            logger.error(f"Tavily search failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def extract_research_context(self, research_result: Dict[str, Any]) -> str:
        """Extract context from research results"""
        if not research_result.get("success"):
            return "No research context available"
            
        results = research_result.get("results", [])
        if not results:
            return "No research results found"
            
        context_parts = []
        for result in results[:3]:  # Use top 3 results
            context_parts.append(f"- {result.get('title', 'Unknown')}: {result.get('content', 'No content')}")
            
        return "\n".join(context_parts)

# Global instance
tavily_manager = TavilySearchManager()
