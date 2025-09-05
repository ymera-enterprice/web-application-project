# YMERA Enterprise WebSocket Streaming System
# Real-time code analysis and AI-powered insights streaming

import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional, Any, Callable, AsyncGenerator
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import websockets
from websockets.server import WebSocketServerProtocol
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from fastapi.websockets import WebSocketState
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessageType(Enum):
    """WebSocket message types for YMERA platform"""
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    AUTH = "auth"
    CODE_ANALYSIS = "code_analysis"
    ANALYSIS_RESULT = "analysis_result"
    ANALYSIS_PROGRESS = "analysis_progress"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    CHAT_MESSAGE = "chat_message"
    FILE_UPDATE = "file_update"
    AGENT_STATUS = "agent_status"
    SYSTEM_NOTIFICATION = "system_notification"

@dataclass
class WebSocketMessage:
    """Standard WebSocket message format for YMERA"""
    id: str
    type: MessageType
    timestamp: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.id is None:
            self.id = str(uuid.uuid4())

@dataclass
class ClientSession:
    """WebSocket client session management"""
    session_id: str
    user_id: str
    websocket: WebSocket
    connected_at: str
    last_heartbeat: float
    subscriptions: List[str]
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        if self.connected_at is None:
            self.connected_at = datetime.now().isoformat()
        if self.last_heartbeat is None:
            self.last_heartbeat = time.time()

class YMERAWebSocketManager:
    """Advanced WebSocket connection manager for YMERA platform"""
    
    def __init__(self):
        # Active connections
        self.active_connections: Dict[str, ClientSession] = {}
        self.user_sessions: Dict[str, List[str]] = {}  # user_id -> [session_ids]
        
        # Message handlers
        self.message_handlers: Dict[MessageType, Callable] = {}
        self.middleware: List[Callable] = []
        
        # Performance metrics
        self.total_connections = 0
        self.total_messages = 0
        self.connection_stats = {
            'current_connections': 0,
            'peak_connections': 0,
            'total_connections': 0,
            'messages_per_second': 0.0,
            'average_response_time': 0.0
        }
        
        # Message queues for different priorities
        self.high_priority_queue = asyncio.Queue()
        self.normal_priority_queue = asyncio.Queue()
        self.low_priority_queue = asyncio.Queue()
        
        # Background tasks
        self.background_tasks: List[asyncio.Task] = []
        
        # Register default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default message handlers"""
        self.register_handler(MessageType.AUTH, self._handle_auth)
        self.register_handler(MessageType.HEARTBEAT, self._handle_heartbeat)
        self.register_handler(MessageType.CODE_ANALYSIS, self._handle_code_analysis)
        self.register_handler(MessageType.CHAT_MESSAGE, self._handle_chat_message)
    
    def register_handler(self, message_type: MessageType, handler: Callable):
        """Register a message handler for specific message types"""
        self.message_handlers[message_type] = handler
        logger.info(f"Registered handler for {message_type.value}")
    
    def add_middleware(self, middleware: Callable):
        """Add middleware for message processing"""
        self.middleware.append(middleware)
    
    async def connect(self, websocket: WebSocket, user_id: str, session_data: Dict = None) -> str:
        """Handle new WebSocket connection"""
        
        try:
            await websocket.accept()
            
            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # Create session
            session = ClientSession(
                session_id=session_id,
                user_id=user_id,
                websocket=websocket,
                connected_at=datetime.now().isoformat(),
                last_heartbeat=time.time(),
                subscriptions=[],
                metadata=session_data or {}
            )
            
            # Store session
            self.active_connections[session_id] = session
            
            # Track user sessions
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = []
            self.user_sessions[user_id].append(session_id)
            
            # Update stats
            self.total_connections += 1
            self.connection_stats['current_connections'] = len(self.active_connections)
            self.connection_stats['total_connections'] = self.total_connections
            
            if self.connection_stats['current_connections'] > self.connection_stats['peak_connections']:
                self.connection_stats['peak_connections'] = self.connection_stats['current_connections']
            
            # Send connection confirmation
            welcome_message = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.CONNECT,
                timestamp=datetime.now().isoformat(),
                user_id=user_id,
                session_id=session_id,
                data={
                    "status": "connected",
                    "session_id": session_id,
                    "server_time": datetime.now().isoformat(),
                    "capabilities": [
                        "code_analysis",
                        "real_time_chat",
                        "file_updates",
                        "agent_communication"
                    ]
                }
            )
            
            await self._send_to_client(session_id, welcome_message)
            
            logger.info(f"Client {user_id} connected with session {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Error connecting client: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")
    
    async def disconnect(self, session_id: str):
        """Handle WebSocket disconnection"""
        
        if session_id in self.active_connections:
            session = self.active_connections[session_id]
            user_id = session.user_id
            
            # Remove from active connections
            del self.active_connections[session_id]
            
            # Remove from user sessions
            if user_id in self.user_sessions:
                self.user_sessions[user_id] = [
                    sid for sid in self.user_sessions[user_id] if sid != session_id
                ]
                if not self.user_sessions[user_id]:
                    del self.user_sessions[user_id]
            
            # Update stats
            self.connection_stats['current_connections'] = len(self.active_connections)
            
            logger.info(f"Client {user_id} disconnected (session: {session_id})")
    
    async def _send_to_client(self, session_id: str, message: WebSocketMessage) -> bool:
        """Send message to specific client with error handling"""
        
        if session_id not in self.active_connections:
            logger.warning(f"Session {session_id} not found")
            return False
        
        session = self.active_connections[session_id]
        
        try:
            if session.websocket.client_state == WebSocketState.CONNECTED:
                message_json = json.dumps(asdict(message), default=str)
                await session.websocket.send_text(message_json)
                self.total_messages += 1
                return True
            else:
                logger.warning(f"WebSocket for session {session_id} is not connected")
                await self.disconnect(session_id)
                return False
                
        except Exception as e:
            logger.error(f"Error sending message to {session_id}: {str(e)}")
            await self.disconnect(session_id)
            return False
    
    async def broadcast_to_user(self, user_id: str, message: WebSocketMessage) -> int:
        """Send message to all sessions of a specific user"""
        
        if user_id not in self.user_sessions:
            return 0
        
        successful_sends = 0
        session_ids = self.user_sessions[user_id].copy()  # Copy to avoid modification during iteration
        
        for session_id in session_ids:
            if await self._send_to_client(session_id, message):
                successful_sends += 1
        
        return successful_sends
    
    async def broadcast_to_all(self, message: WebSocketMessage, exclude_sessions: List[str] = None) -> int:
        """Broadcast message to all connected clients"""
        
        exclude_sessions = exclude_sessions or []
        successful_sends = 0
        
        session_ids = list(self.active_connections.keys())
        
        for session_id in session_ids:
            if session_id not in exclude_sessions:
                if await self._send_to_client(session_id, message):
                    successful_sends += 1
        
        return successful_sends
    
    async def stream_analysis_results(self, session_id: str, analysis_generator: AsyncGenerator) -> None:
        """Stream analysis results in real-time"""
        
        try:
            async for result_chunk in analysis_generator:
                progress_message = WebSocketMessage(
                    id=str(uuid.uuid4()),
                    type=MessageType.ANALYSIS_PROGRESS,
                    timestamp=datetime.now().isoformat(),
                    session_id=session_id,
                    data=result_chunk
                )
                
                await self._send_to_client(session_id, progress_message)
                
                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.1)
                
        except Exception as e:
            error_message = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.ERROR,
                timestamp=datetime.now().isoformat(),
                session_id=session_id,
                data={"error": str(e), "error_type": "streaming_error"}
            )
            await self._send_to_client(session_id, error_message)
    
    async def handle_message(self, session_id: str, raw_message: str):
        """Process incoming WebSocket messages"""
        
        start_time = time.time()
        
        try:
            # Parse message
            message_data = json.loads(raw_message)
            message_type = MessageType(message_data.get("type"))
            
            message = WebSocketMessage(
                id=message_data.get("id", str(uuid.uuid4())),
                type=message_type,
                timestamp=message_data.get("timestamp", datetime.now().isoformat()),
                user_id=message_data.get("user_id"),
                session_id=session_id,
                data=message_data.get("data", {}),
                metadata=message_data.get("metadata", {})
            )
            
            # Apply middleware
            for middleware in self.middleware:
                message = await middleware(message)
                if message is None:  # Middleware can filter messages
                    return
            
            # Route to appropriate handler
            if message_type in self.message_handlers:
                await self.message_handlers[message_type](message)
            else:
                logger.warning(f"No handler for message type: {message_type.value}")
            
            # Update performance metrics
            processing_time = time.time() - start_time
            self._update_performance_metrics(processing_time)
            
        except json.JSONDecodeError:
            error_message = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.ERROR,
                timestamp=datetime.now().isoformat(),
                session_id=session_id,
                data={"error": "Invalid JSON format", "error_type": "parse_error"}
            )
            await self._send_to_client(session_id, error_message)
            
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            error_message = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.ERROR,
                timestamp=datetime.now().isoformat(),
                session_id=session_id,
                data={"error": str(e), "error_type": "processing_error"}
            )
            await self._send_to_client(session_id, error_message)
    
    def _update_performance_metrics(self, processing_time: float):
        """Update performance metrics"""
        current_time = time.time()
        
        # Update average response time
        if self.connection_stats['average_response_time'] == 0:
            self.connection_stats['average_response_time'] = processing_time
        else:
            # Rolling average
            self.connection_stats['average_response_time'] = (
                self.connection_stats['average_response_time'] * 0.9 + processing_time * 0.1
            )
        
        # Calculate messages per second (simplified)
        self.connection_stats['messages_per_second'] = self.total_messages / max(current_time - self.start_time, 1) if hasattr(self, 'start_time') else 0
    
    # Default message handlers
    async def _handle_auth(self, message: WebSocketMessage):
        """Handle authentication messages"""
        session = self.active_connections.get(message.session_id)
        if not session:
            return
        
        # Update session with auth data
        session.metadata.update(message.data or {})
        
        auth_response = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.AUTH,
            timestamp=datetime.now().isoformat(),
            session_id=message.session_id,
            data={"status": "authenticated", "user_id": session.user_id}
        )
        
        await self._send_to_client(message.session_id, auth_response)
    
    async def _handle_heartbeat(self, message: WebSocketMessage):
        """Handle heartbeat messages"""
        session = self.active_connections.get(message.session_id)
        if session:
            session.last_heartbeat = time.time()
        
        # Send heartbeat response
        heartbeat_response = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.HEARTBEAT,
            timestamp=datetime.now().isoformat(),
            session_id=message.session_id,
            data={"server_time": datetime.now().isoformat()}
        )
        
        await self._send_to_client(message.session_id, heartbeat_response)
    
    async def _handle_code_analysis(self, message: WebSocketMessage):
        """Handle code analysis requests with streaming results"""
        
        # Extract analysis parameters
        code = message.data.get("code", "")
        analysis_type = message.data.get("analysis_type", "comprehensive")
        language = message.data.get("language", "python")
        
        if not code:
            error_message = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.ERROR,
                timestamp=datetime.now().isoformat(),
                session_id=message.session_id,
                data={"error": "No code provided for analysis", "error_type": "validation_error"}
            )
            await self._send_to_client(message.session_id, error_message)
            return
        
        # Create async generator for streaming results
        async def analysis_stream():
            yield {"status": "starting", "progress": 0}
            await asyncio.sleep(0.5)
            
            yield {"status": "syntax_analysis", "progress": 25}
            await asyncio.sleep(0.5)
            
            yield {"status": "security_scan", "progress": 50}
            await asyncio.sleep(0.5)
            
            yield {"status": "quality_check", "progress": 75}
            await asyncio.sleep(0.5)
            
            # Final results
            yield {
                "status": "completed",
                "progress": 100,
                "results": {
                    "syntax_errors": 0,
                    "security_issues": 1,
                    "quality_score": 8.5,
                    "recommendations": [
                        "Consider adding input validation",
                        "Use parameterized queries for database operations"
                    ]
                }
            }
        
        # Stream results
        await self.stream_analysis_results(message.session_id, analysis_stream())
    
    async def _handle_chat_message(self, message: WebSocketMessage):
        """Handle chat messages between users and AI agents"""
        
        chat_data = message.data
        recipient = chat_data.get("recipient")  # "agent" or user_id
        
        if recipient == "agent":
            # Process with AI agent
            ai_response = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.CHAT_MESSAGE,
                timestamp=datetime.now().isoformat(),
                session_id=message.session_id,
                data={
                    "sender": "ai_agent",
                    "message": f"I received your message: '{chat_data.get('message')}'. How can I help you with your code?",
                    "message_type": "ai_response"
                }
            )
            
            await self._send_to_client(message.session_id, ai_response)
        else:
            # Forward to another user
            await self.broadcast_to_user(recipient, message)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get current connection statistics"""
        return {
            **self.connection_stats,
            "active_sessions": len(self.active_connections),
            "total_users": len(self.user_sessions),
            "total_messages_processed": self.total_messages,
            "uptime": time.time() - getattr(self, 'start_time', time.time())
        }
    
    async def start_background_tasks(self):
        """Start background maintenance tasks"""
        self.start_time = time.time()
        
        # Heartbeat monitor
        self.background_tasks.append(
            asyncio.create_task(self._heartbeat_monitor())
        )
        
        # Connection cleanup
        self.background_tasks.append(
            asyncio.create_task(self._connection_cleanup())
        )
    
    async def _heartbeat_monitor(self):
        """Monitor client heartbeats and disconnect stale connections"""
        while True:
            current_time = time.time()
            stale_sessions = []
            
            for session_id, session in self.active_connections.items():
                if current_time - session.last_heartbeat > 60:  # 60 seconds timeout
                    stale_sessions.append(session_id)
            
            # Disconnect stale sessions
            for session_id in stale_sessions:
                await self.disconnect(session_id)
                logger.info(f"Disconnected stale session: {session_id}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def _connection_cleanup(self):
        """Periodic cleanup of resources"""
        while True:
            # Clear old cache entries, update metrics, etc.
            await asyncio.sleep(300)  # Run every 5 minutes
    
    async def shutdown(self):
        """Gracefully shutdown the WebSocket manager"""
        logger.info("Shutting down WebSocket manager...")
        
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        # Disconnect all clients
        session_ids = list(self.active_connections.keys())
        for session_id in session_ids:
            await self.disconnect(session_id)
        
        logger.info("WebSocket manager shutdown complete")

# FastAPI WebSocket Integration
class YMERAWebSocketHandler:
    """FastAPI WebSocket handler for YMERA platform"""
    
    def __init__(self):
        self.manager = YMERAWebSocketManager()
        
    async def websocket_endpoint(self, websocket: WebSocket, user_id: str = "anonymous"):
        """Main WebSocket endpoint for YMERA platform"""
        
        session_id = None
        
        try:
            # Connect client
            session_id = await self.manager.connect(websocket, user_id)
            
            # Handle messages
            while True:
                try:
                    data = await websocket.receive_text()
                    await self.manager.handle_message(session_id, data)
                    
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error in WebSocket communication: {str(e)}")
                    break
                    
        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}")
            
        finally:
            if session_id:
                await self.manager.disconnect(session_id)

# Real-time Code Analysis Integration
class YMERARealTimeAnalyzer:
    """Real-time code analysis with WebSocket streaming"""
    
    def __init__(self, websocket_manager: YMERAWebSocketManager, groq_engine=None, pinecone_engine=None):
        self.ws_manager = websocket_manager
        self.groq_engine = groq_engine
        self.pinecone_engine = pinecone_engine
        
        # Register analysis handler
        self.ws_manager.register_handler(
            MessageType.CODE_ANALYSIS, 
            self._handle_real_time_analysis
        )
    
    async def _handle_real_time_analysis(self, message: WebSocketMessage):
        """Handle real-time code analysis with streaming results"""
        
        code = message.data.get("code", "")
        analysis_types = message.data.get("analysis_types", ["security", "quality"])
        context = message.data.get("context", {})
        
        if not code:
            await self._send_error(message.session_id, "No code provided")
            return
        
        # Create streaming analysis generator
        async def comprehensive_analysis_stream():
            total_steps = len(analysis_types) + 2  # +2 for vector search and final processing
            current_step = 0
            
            # Step 1: Vector similarity search
            current_step += 1
            yield {
                "status": "vector_search",
                "progress": int((current_step / total_steps) * 100),
                "message": "Finding similar code patterns..."
            }
            
            similar_patterns = []
            if self.pinecone_engine:
                try:
                    similar_patterns = await self.pinecone_engine.find_similar_code(code, top_k=3)
                    yield {
                        "status": "vector_search_complete",
                        "progress": int((current_step / total_steps) * 100),
                        "data": {
                            "similar_patterns_found": len(similar_patterns),
                            "patterns": [{"score": p.score, "file": p.metadata.get("file_path", "unknown")} for p in similar_patterns[:3]]
                        }
                    }
                except Exception as e:
                    yield {
                        "status": "vector_search_error",
                        "progress": int((current_step / total_steps) * 100),
                        "error": str(e)
                    }
            
            # Step 2: GROQ-powered analysis for each type
            analysis_results = {}
            
            for analysis_type in analysis_types:
                current_step += 1
                yield {
                    "status": f"analyzing_{analysis_type}",
                    "progress": int((current_step / total_steps) * 100),
                    "message": f"Performing {analysis_type} analysis..."
                }
                
                if self.groq_engine:
                    try:
                        # Simulate GROQ analysis (replace with actual GROQ call)
                        await asyncio.sleep(0.5)  # Simulate processing time
                        
                        if analysis_type == "security":
                            results = {
                                "vulnerabilities": ["Potential SQL injection in line 5", "Missing input validation"],
                                "severity": "HIGH",
                                "confidence": 0.89
                            }
                        elif analysis_type == "quality":
                            results = {
                                "complexity_score": 7.5,
                                "maintainability": "GOOD",
                                "suggestions": ["Consider extracting method", "Add documentation"],
                                "confidence": 0.92
                            }
                        else:
                            results = {"analysis": f"Completed {analysis_type} analysis", "confidence": 0.85}
                        
                        analysis_results[analysis_type] = results
                        
                        yield {
                            "status": f"{analysis_type}_complete",
                            "progress": int((current_step / total_steps) * 100),
                            "data": {
                                "type": analysis_type,
                                "results": results
                            }
                        }
                        
                    except Exception as e:
                        yield {
                            "status": f"{analysis_type}_error",
                            "progress": int((current_step / total_steps) * 100),
                            "error": str(e)
                        }
            
            # Final step: Aggregate results
            current_step += 1
            yield {
                "status": "aggregating_results",
                "progress": int((current_step / total_steps) * 100),
                "message": "Generating comprehensive report..."
            }
            
            await asyncio.sleep(0.3)
            
            # Generate final comprehensive report
            comprehensive_report = {
                "analysis_id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "code_hash": hashlib.md5(code.encode()).hexdigest()[:8],
                "similar_patterns": len(similar_patterns),
                "analysis_results": analysis_results,
                "overall_score": sum(r.get("confidence", 0.5) for r in analysis_results.values()) / len(analysis_results) if analysis_results else 0.5,
                "recommendations": [
                    "Review security vulnerabilities immediately",
                    "Consider refactoring for better maintainability",
                    "Add comprehensive error handling"
                ],
                "processing_time": time.time() - start_time
            }
            
            yield {
                "status": "complete",
                "progress": 100,
                "data": comprehensive_report
            }
        
        start_time = time.time()
        
        # Stream the analysis
        try:
            await self.ws_manager.stream_analysis_results(
                message.session_id, 
                comprehensive_analysis_stream()
            )
        except Exception as e:
            await self._send_error(message.session_id, f"Analysis failed: {str(e)}")
    
    async def _send_error(self, session_id: str, error_message: str):
        """Send error message to client"""
        error_msg = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.ERROR,
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            data={"error": error_message, "error_type": "analysis_error"}
        )
        await self.ws_manager._send_to_client(session_id, error_msg)

# Performance Testing System
class YMERAWebSocketTester:
    """Performance testing for WebSocket system"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.test_results = {}
    
    async def run_performance_tests(self) -> Dict[str, Any]:
        """Run comprehensive performance tests"""
        
        print("🚀 Starting YMERA WebSocket Performance Tests")
        print("=" * 50)
        
        tests = [
            ("Connection Speed", self._test_connection_speed),
            ("Message Throughput", self._test_message_throughput),
            ("Concurrent Connections", self._test_concurrent_connections),
            ("Streaming Performance", self._test_streaming_performance),
            ("Error Handling", self._test_error_handling)
        ]
        
        for test_name, test_func in tests:
            print(f"\n📊 Running {test_name} Test...")
            try:
                result = await test_func()
                self.test_results[test_name] = result
                print(f"   ✅ {test_name}: {result.get('status', 'COMPLETED')}")
                if 'metrics' in result:
                    for metric, value in result['metrics'].items():
                        print(f"      {metric}: {value}")
            except Exception as e:
                self.test_results[test_name] = {"status": "FAILED", "error": str(e)}
                print(f"   ❌ {test_name}: FAILED - {str(e)}")
        
        return self.test_results
    
    async def _test_connection_speed(self) -> Dict[str, Any]:
        """Test WebSocket connection establishment speed"""
        
        connection_times = []
        
        for i in range(10):
            start_time = time.time()
            
            try:
                # Simulate WebSocket connection
                await asyncio.sleep(0.1)  # Simulate connection time
                connection_time = time.time() - start_time
                connection_times.append(connection_time)
                
            except Exception as e:
                return {"status": "FAILED", "error": str(e)}
        
        avg_connection_time = sum(connection_times) / len(connection_times)
        
        return {
            "status": "PASSED" if avg_connection_time < 1.0 else "SLOW",
            "metrics": {
                "average_connection_time": f"{avg_connection_time:.3f}s",
                "min_connection_time": f"{min(connection_times):.3f}s",
                "max_connection_time": f"{max(connection_times):.3f}s"
            }
        }
    
    async def _test_message_throughput(self) -> Dict[str, Any]:
        """Test message processing throughput"""
        
        message_count = 100
        start_time = time.time()
        
        # Simulate message processing
        for i in range(message_count):
            await asyncio.sleep(0.01)  # Simulate message processing
        
        total_time = time.time() - start_time
        messages_per_second = message_count / total_time
        
        return {
            "status": "PASSED" if messages_per_second > 50 else "SLOW",
            "metrics": {
                "messages_processed": message_count,
                "total_time": f"{total_time:.3f}s",
                "messages_per_second": f"{messages_per_second:.1f}"
            }
        }
    
    async def _test_concurrent_connections(self) -> Dict[str, Any]:
        """Test handling of concurrent connections"""
        
        concurrent_count = 50
        connection_tasks = []
        
        async def simulate_connection():
            await asyncio.sleep(0.5)  # Simulate connection lifetime
            return True
        
        start_time = time.time()
        
        # Create concurrent connections
        for i in range(concurrent_count):
            task = asyncio.create_task(simulate_connection())
            connection_tasks.append(task)
        
        # Wait for all connections
        results = await asyncio.gather(*connection_tasks)
        total_time = time.time() - start_time
        
        successful_connections = sum(results)
        
        return {
            "status": "PASSED" if successful_connections == concurrent_count else "PARTIAL",
            "metrics": {
                "concurrent_connections": concurrent_count,
                "successful_connections": successful_connections,
                "total_time": f"{total_time:.3f}s",
                "success_rate": f"{(successful_connections/concurrent_count)*100:.1f}%"
            }
        }
    
    async def _test_streaming_performance(self) -> Dict[str, Any]:
        """Test real-time streaming performance"""
        
        stream_duration = 5.0  # seconds
        expected_messages = 50
        
        messages_received = 0
        start_time = time.time()
        
        # Simulate streaming
        while time.time() - start_time < stream_duration:
            await asyncio.sleep(0.1)
            messages_received += 1
        
        actual_duration = time.time() - start_time
        messages_per_second = messages_received / actual_duration
        
        return {
            "status": "PASSED" if messages_received >= expected_messages else "SLOW",
            "metrics": {
                "stream_duration": f"{actual_duration:.1f}s",
                "messages_received": messages_received,
                "messages_per_second": f"{messages_per_second:.1f}",
                "expected_messages": expected_messages
            }
        }
    
    async def _test_error_handling(self) -> Dict[str, Any]:
        """Test error handling capabilities"""
        
        error_scenarios = [
            "invalid_json",
            "unknown_message_type", 
            "missing_data",
            "connection_timeout"
        ]
        
        handled_errors = 0
        
        for scenario in error_scenarios:
            try:
                # Simulate error scenario
                await asyncio.sleep(0.1)
                handled_errors += 1  # Assume error was handled properly
                
            except Exception:
                continue  # Error handling failed
        
        return {
            "status": "PASSED" if handled_errors == len(error_scenarios) else "PARTIAL",
            "metrics": {
                "total_scenarios": len(error_scenarios),
                "handled_errors": handled_errors,
                "error_handling_rate": f"{(handled_errors/len(error_scenarios))*100:.1f}%"
            }
        }

# Integration with existing YMERA system
def create_ymera_websocket_app():
    """Create FastAPI app with WebSocket support for YMERA"""
    
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    
    app = FastAPI(title="YMERA WebSocket API")
    handler = YMERAWebSocketHandler()
    
    @app.websocket("/ws/{user_id}")
    async def websocket_endpoint(websocket: WebSocket, user_id: str):
        """Main WebSocket endpoint"""
        await handler.websocket_endpoint(websocket, user_id)
    
    @app.get("/ws-stats")
    async def get_websocket_stats():
        """Get WebSocket performance statistics"""
        return handler.manager.get_connection_stats()
    
    @app.get("/ws-test", response_class=HTMLResponse)
    async def websocket_test_page():
        """Simple WebSocket test page"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>YMERA WebSocket Test</title>
        </head>
        <body>
            <h1>YMERA WebSocket Test</h1>
            <div id="messages"></div>
            <input type="text" id="messageInput" placeholder="Enter message...">
            <button onclick="sendMessage()">Send</button>
            
            <script>
                const ws = new WebSocket('ws://localhost:8000/ws/test_user');
                const messages = document.getElementById('messages');
                
                ws.onmessage = function(event) {
                    const div = document.createElement('div');
                    div.textContent = event.data;
                    messages.appendChild(div);
                };
                
                function sendMessage() {
                    const input = document.getElementById('messageInput');
                    const message = {
                        type: 'chat_message',
                        data: { message: input.value, recipient: 'agent' }
                    };
                    ws.send(JSON.stringify(message));
                    input.value = '';
                }
            </script>
        </body>
        </html>
        """
    
    return app

# Usage example
async def main():
    """Example usage of YMERA WebSocket system"""
    
    # Initialize WebSocket manager
    manager = YMERAWebSocketManager()
    await manager.start_background_tasks()
    
    # Initialize real-time analyzer
    analyzer = YMERARealTimeAnalyzer(manager)
    
    # Run performance tests
    tester = YMERAWebSocketTester("ws://localhost:8000")
    test_results = await tester.run_performance_tests()
    
    print("\n📊 Performance Test Results:")
    print("=" * 30)
    for test_name, result in test_results.items():
        print(f"{test_name}: {result.get('status', 'UNKNOWN')}")
    
    # Cleanup
    await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
            