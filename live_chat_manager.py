"""
YMERA Enterprise Chat System - Core Chat Manager
Real-time AI-powered conversations with multi-agent integration
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, AsyncGenerator
from enum import Enum
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

import aiohttp
import asyncio
from urllib.parse import quote
from bs4 import BeautifulSoup
import re
import logging

from ymera_core.database.manager import DatabaseManager
from ymera_core.cache.redis_cache import RedisCacheManager
from ymera_services.ai.multi_llm_manager import MultiLLMManager
from ymera_agents.learning.learning_engine import LearningEngine
from ymera_agents.orchestrator import AgentOrchestrator


class MessageType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    AGENT = "agent"
    SEARCH_RESULT = "search_result"
    ERROR = "error"


class ChatMode(str, Enum):
    GENERAL = "general"
    AGENT_SPECIFIC = "agent_specific"
    COLLABORATIVE = "collaborative"
    LEARNING = "learning"
    RESEARCH = "research"


class SearchProvider(str, Enum):
    SERPER = "serper"
    DUCKDUCKGO = "duckduckgo"
    BING = "bing"


@dataclass
class ChatMessage:
    id: str
    session_id: str
    user_id: str
    content: str
    message_type: MessageType
    timestamp: datetime
    metadata: Dict[str, Any] = None
    agent_id: Optional[str] = None
    search_queries: List[str] = None
    sources: List[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    processing_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class ChatSession:
    id: str
    user_id: str
    title: str
    mode: ChatMode
    created_at: datetime
    updated_at: datetime
    active_agents: List[str] = None
    context_summary: str = ""
    message_count: int = 0
    total_tokens: int = 0
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data


class WebSearchEngine:
    """Enhanced web search with multiple providers and smart result processing"""
    
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.session = None
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self):
        """Initialize HTTP session"""
        connector = aiohttp.TCPConnector(limit=50, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'YMERA Enterprise Chat System/2.0.0 (Enterprise Multi-Agent System)'
            }
        )
    
    async def search(
        self, 
        query: str, 
        num_results: int = 10,
        provider: SearchProvider = SearchProvider.SERPER
    ) -> List[Dict[str, Any]]:
        """Perform web search with fallback providers"""
        if not self.session:
            await self.initialize()
        
        try:
            if provider == SearchProvider.SERPER and self.config.get('serper_api_key'):
                return await self._search_serper(query, num_results)
            elif provider == SearchProvider.BING and self.config.get('bing_api_key'):
                return await self._search_bing(query, num_results)
            else:
                return await self._search_duckduckgo(query, num_results)
        except Exception as e:
            self.logger.error(f"Search failed with {provider}: {e}")
            # Try fallback
            if provider != SearchProvider.DUCKDUCKGO:
                return await self._search_duckduckgo(query, num_results)
            return []
    
    async def _search_serper(self, query: str, num_results: int) -> List[Dict[str, Any]]:
        """Search using Serper API"""
        url = "https://google.serper.dev/search"
        payload = {
            'q': query,
            'num': num_results,
            'gl': 'us',
            'hl': 'en'
        }
        headers = {
            'X-API-KEY': self.config['serper_api_key'],
            'Content-Type': 'application/json'
        }
        
        async with self.session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return self._format_serper_results(data)
        return []
    
    async def _search_bing(self, query: str, num_results: int) -> List[Dict[str, Any]]:
        """Search using Bing API"""
        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {
            'Ocp-Apim-Subscription-Key': self.config['bing_api_key']
        }
        params = {
            'q': query,
            'count': num_results,
            'responseFilter': 'Webpages',
            'textFormat': 'HTML'
        }
        
        async with self.session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return self._format_bing_results(data)
        return []
    
    async def _search_duckduckgo(self, query: str, num_results: int) -> List[Dict[str, Any]]:
        """Search using DuckDuckGo (fallback)"""
        url = f"https://duckduckgo.com/html/?q={quote(query)}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    return self._parse_duckduckgo_results(html, num_results)
        except Exception as e:
            self.logger.error(f"DuckDuckGo search failed: {e}")
        return []
    
    def _format_serper_results(self, data: Dict) -> List[Dict[str, Any]]:
        """Format Serper API results"""
        results = []
        for item in data.get('organic', []):
            results.append({
                'title': item.get('title', ''),
                'url': item.get('link', ''),
                'snippet': item.get('snippet', ''),
                'provider': 'serper'
            })
        return results
    
    def _format_bing_results(self, data: Dict) -> List[Dict[str, Any]]:
        """Format Bing API results"""
        results = []
        for item in data.get('webPages', {}).get('value', []):
            results.append({
                'title': item.get('name', ''),
                'url': item.get('url', ''),
                'snippet': item.get('snippet', ''),
                'provider': 'bing'
            })
        return results
    
    def _parse_duckduckgo_results(self, html: str, num_results: int) -> List[Dict[str, Any]]:
        """Parse DuckDuckGo HTML results"""
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        for result in soup.find_all('div', class_='result', limit=num_results):
            title_elem = result.find('a', class_='result__a')
            snippet_elem = result.find('a', class_='result__snippet')
            
            if title_elem:
                results.append({
                    'title': title_elem.get_text(strip=True),
                    'url': title_elem.get('href', ''),
                    'snippet': snippet_elem.get_text(strip=True) if snippet_elem else '',
                    'provider': 'duckduckgo'
                })
        
        return results
    
    async def get_page_content(self, url: str, max_chars: int = 5000) -> str:
        """Extract content from a web page"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200 and 'text/html' in response.headers.get('content-type', ''):
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # Get text content
                    text = soup.get_text()
                    
                    # Clean up whitespace
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    text = ' '.join(chunk for chunk in chunks if chunk)
                    
                    return text[:max_chars]
        except Exception as e:
            self.logger.error(f"Failed to get page content from {url}: {e}")
        return ""
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()


class EnhancedChatManager:
    """
    Enterprise-grade chat manager with live AI responses, web search, and agent integration
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_manager: RedisCacheManager,
        ai_manager: MultiLLMManager,
        learning_engine: LearningEngine,
        agent_orchestrator: AgentOrchestrator,
        config: Dict[str, Any]
    ):
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        self.ai_manager = ai_manager
        self.learning_engine = learning_engine
        self.agent_orchestrator = agent_orchestrator
        self.config = config
        
        # Initialize web search
        self.search_engine = WebSearchEngine({
            'serper_api_key': config.get('serper_api_key'),
            'bing_api_key': config.get('bing_api_key')
        })
        
        self.logger = logging.getLogger(__name__)
        
        # Active sessions
        self.active_sessions: Dict[str, ChatSession] = {}
        
        # Response generation settings
        self.max_context_messages = 20
        self.search_threshold_keywords = [
            'latest', 'recent', 'current', 'today', 'news', 'update',
            'what is', 'how to', 'where is', 'when did', 'search for'
        ]
    
    async def initialize(self):
        """Initialize chat manager"""
        await self.search_engine.initialize()
        await self._create_tables()
        self.logger.info("Enhanced Chat Manager initialized")
    
    async def _create_tables(self):
        """Create database tables for chat system"""
        create_sessions_table = """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            title VARCHAR(500),
            mode VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active_agents JSON,
            context_summary TEXT,
            message_count INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            metadata JSON,
            INDEX idx_user_id (user_id),
            INDEX idx_created_at (created_at)
        )
        """
        
        create_messages_table = """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id VARCHAR(36) PRIMARY KEY,
            session_id VARCHAR(36) NOT NULL,
            user_id VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            message_type VARCHAR(50),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSON,
            agent_id VARCHAR(100),
            search_queries JSON,
            sources JSON,
            confidence_score FLOAT,
            processing_time FLOAT,
            INDEX idx_session_id (session_id),
            INDEX idx_timestamp (timestamp),
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        )
        """
        
        await self.db_manager.execute(create_sessions_table)
        await self.db_manager.execute(create_messages_table)
    
    async def create_session(
        self, 
        user_id: str, 
        title: str = None,
        mode: ChatMode = ChatMode.GENERAL,
        active_agents: List[str] = None
    ) -> ChatSession:
        """Create a new chat session"""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        if not title:
            title = f"Chat Session - {now.strftime('%Y-%m-%d %H:%M')}"
        
        session = ChatSession(
            id=session_id,
            user_id=user_id,
            title=title,
            mode=mode,
            created_at=now,
            updated_at=now,
            active_agents=active_agents or [],
            message_count=0,
            total_tokens=0
        )
        
        # Save to database
        query = """
        INSERT INTO chat_sessions 
        (id, user_id, title, mode, created_at, updated_at, active_agents, message_count, total_tokens)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        await self.db_manager.execute(query, (
            session.id, session.user_id, session.title, session.mode.value,
            session.created_at, session.updated_at, json.dumps(session.active_agents),
            session.message_count, session.total_tokens
        ))
        
        # Cache session
        self.active_sessions[session_id] = session
        await self.cache_manager.set(
            f"chat_session:{session_id}", 
            session.to_dict(), 
            ttl=3600
        )
        
        self.logger.info(f"Created chat session {session_id} for user {user_id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get chat session by ID"""
        # Try cache first
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]
        
        # Try Redis cache
        cached = await self.cache_manager.get(f"chat_session:{session_id}")
        if cached:
            session_data = cached
            session = ChatSession(**session_data)
            self.active_sessions[session_id] = session
            return session
        
        # Query database
        query = "SELECT * FROM chat_sessions WHERE id = %s"
        result = await self.db_manager.fetch_one(query, (session_id,))
        
        if result:
            session = ChatSession(
                id=result['id'],
                user_id=result['user_id'],
                title=result['title'],
                mode=ChatMode(result['mode']),
                created_at=result['created_at'],
                updated_at=result['updated_at'],
                active_agents=json.loads(result['active_agents'] or '[]'),
                context_summary=result.get('context_summary', ''),
                message_count=result.get('message_count', 0),
                total_tokens=result.get('total_tokens', 0),
                metadata=json.loads(result.get('metadata') or '{}')
            )
            
            self.active_sessions[session_id] = session
            await self.cache_manager.set(
                f"chat_session:{session_id}", 
                session.to_dict(), 
                ttl=3600
            )
            return session
        
        return None
    
    async def _should_search_web(self, message: str) -> bool:
        """Determine if message requires web search"""
        message_lower = message.lower()
        
        # Check for search trigger keywords
        for keyword in self.search_threshold_keywords:
            if keyword in message_lower:
                return True
        
        # Check for questions about current events
        current_indicators = ['2024', '2025', 'today', 'now', 'currently', 'recent']
        if any(indicator in message_lower for indicator in current_indicators):
            return True
        
        # Use AI to determine if search is needed
        search_prompt = f"""
        Analyze this user message and determine if it requires current/real-time information that would benefit from web search.
        
        Message: "{message}"
        
        Return only 'YES' if web search would be helpful, 'NO' if existing knowledge is sufficient.
        Consider: current events, recent developments, real-time data, latest news, current prices, recent updates.
        """
        
        try:
            response = await self.ai_manager.generate_response(
                messages=[{"role": "user", "content": search_prompt}],
                provider="openai",
                model="gpt-4",
                max_tokens=10,
                temperature=0.1
            )
            return response.content.strip().upper() == 'YES'
        except Exception as e:
            self.logger.error(f"Error determining search need: {e}")
            return False
    
    async def _perform_smart_search(self, query: str, context: str = "") -> List[Dict[str, Any]]:
        """Perform intelligent web search with context awareness"""
        # Generate optimized search queries
        search_optimization_prompt = f"""
        Based on this user query and conversation context, generate 2-3 optimal search queries that would find the most relevant and current information.
        
        User Query: "{query}"
        Context: "{context[:500]}"
        
        Return search queries as a JSON array of strings. Focus on:
        - Current, factual information
        - Specific, targeted searches
        - Professional/authoritative sources
        
        Example: ["specific term 2024", "latest updates specific term", "current status specific term"]
        """
        
        try:
            response = await self.ai_manager.generate_response(
                messages=[{"role": "user", "content": search_optimization_prompt}],
                provider="openai",
                model="gpt-4",
                max_tokens=150,
                temperature=0.3
            )
            
            # Parse search queries
            import re
            json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if json_match:
                search_queries = json.loads(json_match.group())
            else:
                search_queries = [query]
        except Exception as e:
            self.logger.error(f"Error generating search queries: {e}")
            search_queries = [query]
        
        # Perform searches
        all_results = []
        for search_query in search_queries[:2]:  # Limit to 2 searches
            results = await self.search_engine.search(search_query, num_results=5)
            for result in results:
                result['search_query'] = search_query
            all_results.extend(results)
        
        # Enhance results with content extraction for top results
        enhanced_results = []
        for result in all_results[:3]:  # Get content for top 3 results
            content = await self.search_engine.get_page_content(result['url'])
            if content:
                result['content'] = content
            enhanced_results.append(result)
        
        return enhanced_results
    
    async def _get_context_messages(self, session_id: str, limit: int = None) -> List[ChatMessage]:
        """Get recent messages for context"""
        limit = limit or self.max_context_messages
        
        query = """
        SELECT * FROM chat_messages 
        WHERE session_id = %s 
        ORDER BY timestamp DESC 
        LIMIT %s
        """
        
        results = await self.db_manager.fetch_all(query, (session_id, limit))
        
        messages = []
        for result in reversed(results):  # Reverse to get chronological order
            message = ChatMessage(
                id=result['id'],
                session_id=result['session_id'],
                user_id=result['user_id'],
                content=result['content'],
                message_type=MessageType(result['message_type']),
                timestamp=result['timestamp'],
                metadata=json.loads(result.get('metadata') or '{}'),
                agent_id=result.get('agent_id'),
                search_queries=json.loads(result.get('search_queries') or '[]'),
                sources=json.loads(result.get('sources') or '[]'),
                confidence_score=result.get('confidence_score'),
                processing_time=result.get('processing_time')
            )
            messages.append(message)
        
        return messages
    
    async def process_message(
        self, 
        session_id: str, 
        user_id: str, 
        content: str,
        agent_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process user message and generate streaming response
        """
        start_time = datetime.utcnow()
        
        # Get session
        session = await self.get_session(session_id)
        if not session:
            yield {
                "type": "error",
                "content": "Session not found",
                "timestamp": datetime.utcnow().isoformat()
            }
            return
        
        # Save user message
        user_message = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            content=content,
            message_type=MessageType.USER,
            timestamp=start_time
        )
        await self._save_message(user_message)
        
        yield {
            "type": "user_message_saved",
            "message": user_message.to_dict()
        }
        
        try:
            # Get conversation context
            context_messages = await self._get_context_messages(session_id)
            
            # Determine if web search is needed
            needs_search = await self._should_search_web(content)
            
            search_results = []
            if needs_search:
                yield {
                    "type": "search_initiated",
                    "content": "Searching for current information..."
                }
                
                context = " ".join([msg.content for msg in context_messages[-3:]])
                search_results = await self._perform_smart_search(content, context)
                
                yield {
                    "type": "search_completed",
                    "results_count": len(search_results),
                    "sources": [{"title": r["title"], "url": r["url"]} for r in search_results[:3]]
                }
            
            # Determine response strategy
            if agent_id and agent_id in session.active_agents:
                # Agent-specific response
                async for chunk in self._generate_agent_response(
                    session, user_message, context_messages, agent_id, search_results
                ):
                    yield chunk
            elif session.mode == ChatMode.COLLABORATIVE:
                # Multi-agent collaborative response
                async for chunk in self._generate_collaborative_response(
                    session, user_message, context_messages, search_results
                ):
                    yield chunk
            else:
                # General AI response
                async for chunk in self._generate_ai_response(
                    session, user_message, context_messages, search_results
                ):
                    yield chunk
            
            # Update session statistics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            await self._update_session_stats(session_id, processing_time)
            
            # Trigger learning
            asyncio.create_task(self._trigger_learning(session, user_message, search_results))
            
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            yield {
                "type": "error",
                "content": f"An error occurred while processing your message: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _generate_ai_response(
        self,
        session: ChatSession,
        user_message: ChatMessage,
        context_messages: List[ChatMessage],
        search_results: List[Dict[str, Any]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate AI response with streaming"""
        
        # Build conversation context
        messages = []
        
        # System prompt
        system_prompt = f"""
        You are YMERA, an advanced AI assistant integrated with a multi-agent enterprise system. 
        
        Current session mode: {session.mode.value}
        Available agents: {', '.join(session.active_agents) if session.active_agents else 'None'}
        
        Guidelines:
        - Provide accurate, helpful, and professional responses
        - Use search results when available for current information
        - Be concise but comprehensive
        - Cite sources when using search results
        - Maintain context from previous messages
        - Suggest relevant agents when appropriate
        
        If search results are provided, integrate them naturally into your response and cite sources.
        """
        
        messages.append({"role": "system", "content": system_prompt})
        
        # Add context messages
        for msg in context_messages[-10:]:  # Last 10 messages
            if msg.message_type in [MessageType.USER, MessageType.ASSISTANT]:
                role = "user" if msg.message_type == MessageType.USER else "assistant"
                messages.append({"role": role, "content": msg.content})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message.content})
        
        # Add search context if available
        if search_results:
            search_context = "\n\nCurrent Information from Web Search:\n"
            for i, result in enumerate(search_results[:3], 1):
                search_context += f"\n{i}. {result['title']}\n"
                search_context += f"   URL: {result['url']}\n"
                search_context += f"   Content: {result.get('content', result['snippet'])[:300]}...\n"
            
            messages[-1]["content"] += search_context
        
        # Generate streaming response
        response_content = ""
        message_id = str(uuid.uuid4())
        
        yield {
            "type": "response_started",
            "message_id": message_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            async for chunk in self.ai_manager.generate_streaming_response(
                messages=messages,
                provider="openai",  # Primary provider
                model="gpt-4",
                max_tokens=1500,
                temperature=0.7
            ):
                if chunk.content:
                    response_content += chunk.content
                    yield {
                        "type": "response_chunk",
                        "message_id": message_id,
                        "content": chunk.content,
                        "timestamp": datetime.utcnow().isoformat()
                    }
            
            # Save assistant message
            assistant_message = ChatMessage(
                id=message_id,
                session_id=session.id,
                user_id=user_message.user_id,
                content=response_content,
                message_type=MessageType.ASSISTANT,
                timestamp=datetime.utcnow(),
                search_queries=[r.get('search_query') for r in search_results if r.get('search_query')],
                sources=search_results,
                confidence_score=0.9  # High confidence for AI responses
            )
            
            await self._save_message(assistant_message)
            
            yield {
                "type": "response_completed",
                "message": assistant_message.to_dict()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating AI response: {e}")
            yield {
                "type": "error",
                "content": f"Error generating response: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _generate_agent_response(
        self,
        session: ChatSession,
        user_message: ChatMessage,
        context_messages: List[ChatMessage],
        agent_id: str,
        search_results: List[Dict[str, Any]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate response from specific agent"""
        
        yield {
            "type": "agent_processing",
            "agent_id": agent_id,
            "content": f"Processing with {agent_id} agent...",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # Get agent from orchestrator
            agent = await self.agent_orchestrator.get_agent(agent_id)
            if not agent:
                yield {
                    "type": "error",
                    "content": f"Agent {agent_id} not found",
                    "timestamp": datetime.utcnow().isoformat()
                }
                return
            
            # Prepare agent context
            context = {
                "session": session.to_dict(),
                "user_message": user_message.content,
                "context_messages": [msg.to_dict() for msg in context_messages[-5:]],
                "search_results": search_results,
                "mode": "chat_response"
            }
            
            # Get agent response
            agent_response = await agent.process_chat_message(context)
            
            # Save agent message
            agent_message = ChatMessage(
                id=str(uuid.uuid4()),
                session_id=session.id,
                user_id=user_message.user_id,
                content=agent_response.get("content", ""),
                message_type=MessageType.AGENT,
                timestamp=datetime.utcnow(),
                agent_id=agent_id,
                metadata=agent_response.get("metadata", {}),
                confidence_score=agent_response.get("confidence", 0.8)
            )
            
            await self._save_message(agent_message)
            
            yield {
                "type": "agent_response",
                "message": agent_message.to_dict()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating agent response: {e}")
            yield {
                "type": "error",
                "content": f"Error getting response from {agent_id}: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _generate_collaborative_response(
        self,
        session: ChatSession,
        user_message: ChatMessage,
        context_messages: List[ChatMessage],
        search_results: List[Dict[str, Any]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate collaborative response using multiple agents"""
        
        yield {
            "type": "collaborative_processing",
            "content": "Coordinating response from multiple agents...",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # Determine relevant agents based on message content
            relevant_agents = await self._identify_relevant_agents(user_message.content)
            
            # Limit to top 3 agents for efficiency
            selected_agents = relevant_agents[:3]
            
            yield {
                "type": "agents_selected",
                "agents": selected_agents,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Collect responses from agents
            agent_responses = []
            for agent_id in selected_agents:
                try:
                    agent = await self.agent_orchestrator.get_agent(agent_id)
                    if agent:
                        context = {
                            "session": session.to_dict(),
                            "user_message": user_message.content,
                            "context_messages": [msg.to_dict() for msg in context_messages[-3:]],
                            "search_results": search_results,
                            "mode": "collaborative_input"
                        }
                        
                        response = await agent.process_chat_message(context)
                        agent_responses.append({
                            "agent_id": agent_id,
                            "content": response.get("content", ""),
                            "confidence": response.get("confidence", 0.5),
                            "metadata": response.get("metadata", {})
                        })
                        
                        yield {
                            "type": "agent_contribution",
                            "agent_id": agent_id,
                            "preview": response.get("content", "")[:100] + "...",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
                except Exception as e:
                    self.logger.error(f"Error getting response from agent {agent_id}: {e}")
            
            # Synthesize collaborative response
            if agent_responses:
                synthesized_response = await self._synthesize_agent_responses(
                    user_message.content, agent_responses, search_results
                )
                
                # Save collaborative message
                collab_message = ChatMessage(
                    id=str(uuid.uuid4()),
                    session_id=session.id,
                    user_id=user_message.user_id,
                    content=synthesized_response["content"],
                    message_type=MessageType.AGENT,
                    timestamp=datetime.utcnow(),
                    agent_id="collaborative",
                    metadata={
                        "participating_agents": selected_agents,
                        "agent_responses": agent_responses
                    },
                    confidence_score=synthesized_response.get("confidence", 0.8)
                )
                
                await self._save_message(collab_message)
                
                yield {
                    "type": "collaborative_response",
                    "message": collab_message.to_dict()
                }
            else:
                # Fallback to AI response
                async for chunk in self._generate_ai_response(
                    session, user_message, context_messages, search_results
                ):
                    yield chunk
                    
        except Exception as e:
            self.logger.error(f"Error in collaborative response: {e}")
            yield {
                "type": "error",
                "content": f"Error in collaborative processing: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _identify_relevant_agents(self, message: str) -> List[str]:
        """Identify which agents are most relevant for the message"""
        agent_keywords = {
            "analysis": ["analyze", "review", "check", "examine", "assess", "evaluate"],
            "enhancement": ["improve", "optimize", "enhance", "upgrade", "refactor", "better"],
            "security": ["security", "vulnerability", "secure", "threat", "risk", "protection"],
            "documentation": ["document", "explain", "describe", "guide", "tutorial", "readme"],
            "deployment": ["deploy", "release", "publish", "build", "production", "launch"],
            "project_management": ["project", "manage", "plan", "schedule", "timeline", "milestone"],
            "monitoring": ["monitor", "track", "observe", "metrics", "performance", "health"],
            "learning": ["learn", "train", "knowledge", "insight", "pattern", "intelligence"]
        }
        
        message_lower = message.lower()
        agent_scores = {}
        
        for agent_id, keywords in agent_keywords.items():
            score = sum(1 for keyword in keywords if keyword in message_lower)
            if score > 0:
                agent_scores[agent_id] = score
        
        # Sort by relevance score
        return sorted(agent_scores.keys(), key=lambda x: agent_scores[x], reverse=True)
    
    async def _synthesize_agent_responses(
        self,
        original_query: str,
        agent_responses: List[Dict[str, Any]],
        search_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Synthesize multiple agent responses into coherent answer"""
        
        synthesis_prompt = f"""
        You are synthesizing responses from multiple specialized AI agents to answer a user query.
        
        Original Query: "{original_query}"
        
        Agent Responses:
        {chr(10).join([f"- {resp['agent_id']}: {resp['content'][:200]}..." for resp in agent_responses])}
        
        Search Results Available: {len(search_results) > 0}
        
        Create a comprehensive, coherent response that:
        1. Integrates the best insights from each agent
        2. Resolves any contradictions
        3. Provides a clear, actionable answer
        4. Cites agent expertise where relevant
        5. Maintains a professional, helpful tone
        
        Response:
        """
        
        try:
            response = await self.ai_manager.generate_response(
                messages=[{"role": "user", "content": synthesis_prompt}],
                provider="openai",
                model="gpt-4",
                max_tokens=1000,
                temperature=0.7
            )
            
            return {
                "content": response.content,
                "confidence": 0.85
            }
        except Exception as e:
            self.logger.error(f"Error synthesizing responses: {e}")
            # Fallback: combine responses simply
            combined_content = f"Based on analysis from {len(agent_responses)} specialized agents:\n\n"
            for resp in agent_responses:
                combined_content += f"**{resp['agent_id'].title()} Agent**: {resp['content'][:300]}...\n\n"
            
            return {
                "content": combined_content,
                "confidence": 0.6
            }
    
    async def _save_message(self, message: ChatMessage):
        """Save message to database"""
        query = """
        INSERT INTO chat_messages 
        (id, session_id, user_id, content, message_type, timestamp, metadata, 
         agent_id, search_queries, sources, confidence_score, processing_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        await self.db_manager.execute(query, (
            message.id, message.session_id, message.user_id, message.content,
            message.message_type.value, message.timestamp,
            json.dumps(message.metadata or {}), message.agent_id,
            json.dumps(message.search_queries or []),
            json.dumps(message.sources or []),
            message.confidence_score, message.processing_time
        ))
    
    async def _update_session_stats(self, session_id: str, processing_time: float):
        """Update session statistics"""
        query = """
        UPDATE chat_sessions 
        SET message_count = message_count + 1, 
            updated_at = %s,
            total_tokens = total_tokens + %s
        WHERE id = %s
        """
        
        # Estimate tokens (rough approximation)
        estimated_tokens = int(processing_time * 50)  # Rough estimate
        
        await self.db_manager.execute(query, (
            datetime.utcnow(), estimated_tokens, session_id
        ))
        
        # Update cached session
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.message_count += 1
            session.total_tokens += estimated_tokens
            session.updated_at = datetime.utcnow()
    
    async def _trigger_learning(
        self,
        session: ChatSession,
        user_message: ChatMessage,
        search_results: List[Dict[str, Any]]
    ):
        """Trigger learning engine with conversation data"""
        try:
            learning_data = {
                "type": "chat_interaction",
                "session_id": session.id,
                "user_query": user_message.content,
                "search_performed": len(search_results) > 0,
                "search_results": search_results,
                "session_mode": session.mode.value,
                "active_agents": session.active_agents,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.learning_engine.process_learning_data(learning_data)
            
        except Exception as e:
            self.logger.error(f"Error triggering learning: {e}")
    
    async def get_session_messages(
        self, 
        session_id: str, 
        limit: int = 50,
        offset: int = 0
    ) -> List[ChatMessage]:
        """Get messages for a session with pagination"""
        query = """
        SELECT * FROM chat_messages 
        WHERE session_id = %s 
        ORDER BY timestamp DESC 
        LIMIT %s OFFSET %s
        """
        
        results = await self.db_manager.fetch_all(query, (session_id, limit, offset))
        
        messages = []
        for result in reversed(results):
            message = ChatMessage(
                id=result['id'],
                session_id=result['session_id'],
                user_id=result['user_id'],
                content=result['content'],
                message_type=MessageType(result['message_type']),
                timestamp=result['timestamp'],
                metadata=json.loads(result.get('metadata') or '{}'),
                agent_id=result.get('agent_id'),
                search_queries=json.loads(result.get('search_queries') or '[]'),
                sources=json.loads(result.get('sources') or '[]'),
                confidence_score=result.get('confidence_score'),
                processing_time=result.get('processing_time')
            )
            messages.append(message)
        
        return messages
    
    async def get_user_sessions(
        self, 
        user_id: str, 
        limit: int = 20
    ) -> List[ChatSession]:
        """Get user's chat sessions"""
        query = """
        SELECT * FROM chat_sessions 
        WHERE user_id = %s 
        ORDER BY updated_at DESC 
        LIMIT %s
        """
        
        results = await self.db_manager.fetch_all(query, (user_id, limit))
        
        sessions = []
        for result in results:
            session = ChatSession(
                id=result['id'],
                user_id=result['user_id'],
                title=result['title'],
                mode=ChatMode(result['mode']),
                created_at=result['created_at'],
                updated_at=result['updated_at'],
                active_agents=json.loads(result['active_agents'] or '[]'),
                context_summary=result.get('context_summary', ''),
                message_count=result.get('message_count', 0),
                total_tokens=result.get('total_tokens', 0),
                metadata=json.loads(result.get('metadata') or '{}')
            )
            sessions.append(session)
        
        return sessions
    
    async def update_session_title(self, session_id: str, title: str):
        """Update session title"""
        query = "UPDATE chat_sessions SET title = %s, updated_at = %s WHERE id = %s"
        await self.db_manager.execute(query, (title, datetime.utcnow(), session_id))
        
        # Update cache
        if session_id in self.active_sessions:
            self.active_sessions[session_id].title = title
    
    async def delete_session(self, session_id: str, user_id: str):
        """Delete a chat session and all its messages"""
        # Verify ownership
        session = await self.get_session(session_id)
        if not session or session.user_id != user_id:
            raise ValueError("Session not found or access denied")
        
        # Delete messages first (foreign key constraint)
        await self.db_manager.execute(
            "DELETE FROM chat_messages WHERE session_id = %s", 
            (session_id,)
        )
        
        # Delete session
        await self.db_manager.execute(
            "DELETE FROM chat_sessions WHERE id = %s", 
            (session_id,)
        )
        
        # Remove from cache
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        await self.cache_manager.delete(f"chat_session:{session_id}")
    
    async def search_messages(
        self, 
        user_id: str, 
        query: str, 
        limit: int = 20
    ) -> List[ChatMessage]:
        """Search user's messages"""
        search_query = """
        SELECT cm.* FROM chat_messages cm
        JOIN chat_sessions cs ON cm.session_id = cs.id
        WHERE cs.user_id = %s AND cm.content LIKE %s
        ORDER BY cm.timestamp DESC
        LIMIT %s
        """
        
        results = await self.db_manager.fetch_all(
            search_query, 
            (user_id, f"%{query}%", limit)
        )
        
        messages = []
        for result in results:
            message = ChatMessage(
                id=result['id'],
                session_id=result['session_id'],
                user_id=result['user_id'],
                content=result['content'],
                message_type=MessageType(result['message_type']),
                timestamp=result['timestamp'],
                metadata=json.loads(result.get('metadata') or '{}'),
                agent_id=result.get('agent_id'),
                search_queries=json.loads(result.get('search_queries') or '[]'),
                sources=json.loads(result.get('sources') or '[]'),
                confidence_score=result.get('confidence_score'),
                processing_time=result.get('processing_time')
            )
            messages.append(message)
        
        return messages
    
    async def get_chat_analytics(self, user_id: str) -> Dict[str, Any]:
        """Get chat analytics for user"""
        analytics_query = """
        SELECT 
            COUNT(DISTINCT cs.id) as total_sessions,
            COUNT(cm.id) as total_messages,
            AVG(cs.message_count) as avg_messages_per_session,
            SUM(cs.total_tokens) as total_tokens,
            MAX(cs.updated_at) as last_activity
        FROM chat_sessions cs
        LEFT JOIN chat_messages cm ON cs.id = cm.session_id
        WHERE cs.user_id = %s
        """
        
        result = await self.db_manager.fetch_one(analytics_query, (user_id,))
        
        # Get agent usage stats
        agent_usage_query = """
        SELECT 
            agent_id, 
            COUNT(*) as usage_count
        FROM chat_messages cm
        JOIN chat_sessions cs ON cm.session_id = cs.id
        WHERE cs.user_id = %s AND cm.agent_id IS NOT NULL
        GROUP BY agent_id
        ORDER BY usage_count DESC
        """
        
        agent_stats = await self.db_manager.fetch_all(agent_usage_query, (user_id,))
        
        return {
            "total_sessions": result.get('total_sessions', 0),
            "total_messages": result.get('total_messages', 0),
            "avg_messages_per_session": float(result.get('avg_messages_per_session', 0) or 0),
            "total_tokens": result.get('total_tokens', 0),
            "last_activity": result.get('last_activity').isoformat() if result.get('last_activity') else None,
            "agent_usage": [
                {"agent_id": row['agent_id'], "usage_count": row['usage_count']}
                for row in agent_stats
            ]
        }
    
    async def export_session(self, session_id: str, user_id: str) -> Dict[str, Any]:
        """Export session data"""
        session = await self.get_session(session_id)
        if not session or session.user_id != user_id:
            raise ValueError("Session not found or access denied")
        
        messages = await self.get_session_messages(session_id, limit=1000)
        
        return {
            "session": session.to_dict(),
            "messages": [msg.to_dict() for msg in messages],
            "export_timestamp": datetime.utcnow().isoformat()
        }
    
    async def cleanup_old_sessions(self, days_old: int = 90):
        """Clean up old sessions"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Get sessions to delete
        old_sessions_query = """
        SELECT id FROM chat_sessions 
        WHERE updated_at < %s
        """
        
        old_sessions = await self.db_manager.fetch_all(old_sessions_query, (cutoff_date,))
        
        for session in old_sessions:
            session_id = session['id']
            
            # Delete messages
            await self.db_manager.execute(
                "DELETE FROM chat_messages WHERE session_id = %s", 
                (session_id,)
            )
            
            # Delete session
            await self.db_manager.execute(
                "DELETE FROM chat_sessions WHERE id = %s", 
                (session_id,)
            )
            
            # Remove from cache
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            await self.cache_manager.delete(f"chat_session:{session_id}")
        
        self.logger.info(f"Cleaned up {len(old_sessions)} old chat sessions")
        return len(old_sessions)
    
    async def shutdown(self):
        """Shutdown chat manager"""
        await self.search_engine.close()
        self.logger.info("Enhanced Chat Manager shutdown complete")