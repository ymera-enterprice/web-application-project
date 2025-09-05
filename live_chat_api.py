"""
YMERA Enterprise Chat System - FastAPI Routes and WebSocket Handler
Real-time chat API with streaming responses and agent integration
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query, Path
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union, AsyncGenerator
from datetime import datetime
import json
import asyncio
import logging
from contextlib import asynccontextmanager

from ymera_core.security.auth_manager import AuthManager
from ymera_core.database.manager import DatabaseManager
from ymera_core.cache.redis_cache import RedisCacheManager
from ymera_services.ai.multi_llm_manager import MultiLLMManager
from ymera_agents.learning.learning_engine import LearningEngine
from ymera_agents.orchestrator import AgentOrchestrator

from .enhanced_chat_manager import EnhancedChatManager, ChatSession, ChatMessage, ChatMode, MessageType

# Pydantic models for API
class CreateSessionRequest(BaseModel):
    title: Optional[str] = None
    mode: ChatMode = ChatMode.GENERAL
    active_agents: Optional[List[str]] = Field(default_factory=list)

class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    agent_id: Optional[str] = None

class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    active_agents: Optional[List[str]] = None

class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: str
    mode: str
    created_at: str
    updated_at: str
    active_agents: List[str]
    message_count: int
    total_tokens: int

class MessageResponse(BaseModel):
    id: str
    session_id: str
    content: str
    message_type: str
    timestamp: str
    agent_id: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = None
    confidence_score: Optional[float] = None

class ChatAnalyticsResponse(BaseModel):
    total_sessions: int
    total_messages: int
    avg_messages_per_session: float
    total_tokens: int
    last_activity: Optional[str] = None
    agent_usage: List[Dict[str, Any]]

class StreamMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    agent_id: Optional[str] = None
    stream: bool = True

class WebSocketMessage(BaseModel):
    type: str  # message, typing, connected, disconnected, error, agent_status
    data: Dict[str, Any]
    timestamp: Optional[str] = None

# WebSocket connection manager
class ChatConnectionManager:
    """Manages WebSocket connections for real-time chat"""
    
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        self.user_sessions: Dict[str, List[str]] = {}
        self.typing_status: Dict[str, Dict[str, bool]] = {}
        self.logger = logging.getLogger(__name__)
    
    async def connect(self, websocket: WebSocket, user_id: str, session_id: str):
        """Connect user to chat session"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
            self.user_sessions[user_id] = []
            self.typing_status[user_id] = {}
        
        self.active_connections[user_id][session_id] = websocket
        if session_id not in self.user_sessions[user_id]:
            self.user_sessions[user_id].append(session_id)
        
        self.typing_status[user_id][session_id] = False
        
        self.logger.info(f"User {user_id} connected to session {session_id}")
        
        # Send connection confirmation
        await self.send_to_session(user_id, session_id, {
            "type": "connected",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def disconnect(self, user_id: str, session_id: str):
        """Disconnect user from session"""
        if user_id in self.active_connections:
            if session_id in self.active_connections[user_id]:
                del self.active_connections[user_id][session_id]
            
            if session_id in self.user_sessions.get(user_id, []):
                self.user_sessions[user_id].remove(session_id)
            
            if user_id in self.typing_status and session_id in self.typing_status[user_id]:
                del self.typing_status[user_id][session_id]
            
            # Clean up empty user entries
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                if user_id in self.user_sessions:
                    del self.user_sessions[user_id]
                if user_id in self.typing_status:
                    del self.typing_status[user_id]
        
        self.logger.info(f"User {user_id} disconnected from session {session_id}")
    
    async def send_to_session(self, user_id: str, session_id: str, message: dict):
        """Send message to specific session"""
        if (user_id in self.active_connections and 
            session_id in self.active_connections[user_id]):
            try:
                websocket = self.active_connections[user_id][session_id]
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                self.logger.error(f"Error sending message to {user_id}/{session_id}: {e}")
                self.disconnect(user_id, session_id)
    
    async def send_to_user(self, user_id: str, message: dict):
        """Send message to all user's sessions"""
        if user_id in self.user_sessions:
            for session_id in self.user_sessions[user_id]:
                await self.send_to_session(user_id, session_id, message)
    
    async def set_typing_status(self, user_id: str, session_id: str, is_typing: bool):
        """Set typing status for user in session"""
        if user_id in self.typing_status and session_id in self.typing_status[user_id]:
            self.typing_status[user_id][session_id] = is_typing
            await self.send_to_session(user_id, session_id, {
                "type": "typing",
                "is_typing": is_typing,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    def get_active_users(self) -> List[str]:
        """Get list of active users"""
        return list(self.active_connections.keys())
    
    def get_user_sessions(self, user_id: str) -> List[str]:
        """Get active sessions for user"""
        return self.user_sessions.get(user_id, [])


# Global connection manager
connection_manager = ChatConnectionManager()

# Router setup
router = APIRouter(prefix="/chat", tags=["Enhanced Chat System"])

# Dependency injection
async def get_current_user(token: str = Depends(AuthManager.get_current_user)) -> dict:
    return token

async def get_chat_manager(
    db_manager: DatabaseManager = Depends(),
    cache_manager: RedisCacheManager = Depends(),
    ai_manager: MultiLLMManager = Depends(),
    learning_engine: LearningEngine = Depends(),
    agent_orchestrator: AgentOrchestrator = Depends()
) -> EnhancedChatManager:
    """Get initialized chat manager"""
    return EnhancedChatManager(
        db_manager=db_manager,
        cache_manager=cache_manager,
        ai_manager=ai_manager,
        learning_engine=learning_engine,
        agent_orchestrator=agent_orchestrator,
        config={}
    )


# REST API Endpoints

@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest,
    current_user: dict = Depends(get_current_user),
    chat_manager: EnhancedChatManager = Depends(get_chat_manager)
):
    """Create a new chat session"""
    try:
        session = await chat_manager.create_session(
            user_id=current_user["user_id"],
            title=request.title,
            mode=request.mode,
            active_agents=request.active_agents
        )
        
        return SessionResponse(
            id=session.id,
            user_id=session.user_id,
            title=session.title,
            mode=session.mode.value,
            created_at=session.created_at.isoformat(),
            updated_at=session.updated_at.isoformat(),
            active_agents=session.active_agents,
            message_count=session.message_count,
            total_tokens=session.total_tokens
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


@router.get("/sessions", response_model=List[SessionResponse])
async def get_user_sessions(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    chat_manager: EnhancedChatManager = Depends(get_chat_manager)
):
    """Get user's chat sessions"""
    try:
        sessions = await chat_manager.get_user_sessions(
            user_id=current_user["user_id"],
            limit=limit
        )
        
        return [
            SessionResponse(
                id=session.id,
                user_id=session.user_id,
                title=session.title,
                mode=session.mode.value,
                created_at=session.created_at.isoformat(),
                updated_at=session.updated_at.isoformat(),
                active_agents=session.active_agents,
                message_count=session.message_count,
                total_tokens=session.total_tokens
            ) for session in sessions
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve sessions: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str = Path(...),
    current_user: dict = Depends(get_current_user),
    chat_manager: EnhancedChatManager = Depends(get_chat_manager)
):
    """Get specific chat session"""
    try:
        session = await chat_manager.get_session(session_id)
        if not session or session.user_id != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        return SessionResponse(
            id=session.id,
            user_id=session.user_id,
            title=session.title,
            mode=session.mode.value,
            created_at=session.created_at.isoformat(),
            updated_at=session.updated_at.isoformat(),
            active_agents=session.active_agents,
            message_count=session.message_count,
            total_tokens=session.total_tokens
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve session: {str(e)}"
        )


@router.put("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    request: UpdateSessionRequest,
    session_id: str = Path(...),
    current_user: dict = Depends(get_current_user),
    chat_manager: EnhancedChatManager = Depends(get_chat_manager)
):
    """Update chat session"""
    try:
        session = await chat_manager.get_session(session_id)
        if not session or session.user_id != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        if request.title:
            await chat_manager.update_session_title(session_id, request.title)
            session.title = request.title
        
        if request.active_agents is not None:
            await chat_manager.update_active_agents(session_id, request.active_agents)
            session.active_agents = request.active_agents
        
        session.updated_at = datetime.utcnow()
        
        return SessionResponse(
            id=session.id,
            user_id=session.user_id,
            title=session.title,
            mode=session.mode.value,
            created_at=session.created_at.isoformat(),
            updated_at=session.updated_at.isoformat(),
            active_agents=session.active_agents,
            message_count=session.message_count,
            total_tokens=session.total_tokens
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session: {str(e)}"
        )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str = Path(...),
    current_user: dict = Depends(get_current_user),
    chat_manager: EnhancedChatManager = Depends(get_chat_manager)
):
    """Delete chat session"""
    try:
        session = await chat_manager.get_session(session_id)
        if not session or session.user_id != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        await chat_manager.delete_session(session_id)
        
        # Notify WebSocket connections if any
        await connection_manager.send_to_user(current_user["user_id"], {
            "type": "session_deleted",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(
    session_id: str = Path(...),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    chat_manager: EnhancedChatManager = Depends(get_chat_manager)
):
    """Get messages for a chat session"""
    try:
        session = await chat_manager.get_session(session_id)
        if not session or session.user_id != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        messages = await chat_manager.get_session_messages(
            session_id=session_id,
            limit=limit,
            offset=offset
        )
        
        return [
            MessageResponse(
                id=msg.id,
                session_id=msg.session_id,
                content=msg.content,
                message_type=msg.message_type.value,
                timestamp=msg.timestamp.isoformat(),
                agent_id=msg.agent_id,
                sources=msg.sources,
                confidence_score=msg.confidence_score
            ) for msg in messages
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve messages: {str(e)}"
        )


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(
    request: SendMessageRequest,
    session_id: str = Path(...),
    current_user: dict = Depends(get_current_user),
    chat_manager: EnhancedChatManager = Depends(get_chat_manager)
):
    """Send a message to a chat session (non-streaming)"""
    try:
        session = await chat_manager.get_session(session_id)
        if not session or session.user_id != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Send user message
        user_message = await chat_manager.add_message(
            session_id=session_id,
            content=request.content,
            message_type=MessageType.USER
        )
        
        # Get AI response
        ai_response = await chat_manager.process_message(
            session_id=session_id,
            message=request.content,
            agent_id=request.agent_id
        )
        
        # Add AI response to session
        ai_message = await chat_manager.add_message(
            session_id=session_id,
            content=ai_response.content,
            message_type=MessageType.AI,
            agent_id=ai_response.agent_id,
            sources=ai_response.sources,
            confidence_score=ai_response.confidence_score
        )
        
        # Notify WebSocket connections
        await connection_manager.send_to_user(current_user["user_id"], {
            "type": "new_message",
            "message": {
                "id": ai_message.id,
                "session_id": ai_message.session_id,
                "content": ai_message.content,
                "message_type": ai_message.message_type.value,
                "timestamp": ai_message.timestamp.isoformat(),
                "agent_id": ai_message.agent_id,
                "sources": ai_message.sources,
                "confidence_score": ai_message.confidence_score
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return MessageResponse(
            id=ai_message.id,
            session_id=ai_message.session_id,
            content=ai_message.content,
            message_type=ai_message.message_type.value,
            timestamp=ai_message.timestamp.isoformat(),
            agent_id=ai_message.agent_id,
            sources=ai_message.sources,
            confidence_score=ai_message.confidence_score
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )


@router.post("/sessions/{session_id}/stream")
async def stream_message(
    request: StreamMessageRequest,
    session_id: str = Path(...),
    current_user: dict = Depends(get_current_user),
    chat_manager: EnhancedChatManager = Depends(get_chat_manager)
):
    """Send a message with streaming response"""
    try:
        session = await chat_manager.get_session(session_id)
        if not session or session.user_id != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        async def generate_response():
            try:
                # Send user message
                user_message = await chat_manager.add_message(
                    session_id=session_id,
                    content=request.content,
                    message_type=MessageType.USER
                )
                
                # Send initial response with user message
                yield f"data: {json.dumps({'type': 'user_message', 'message': request.content, 'timestamp': datetime.utcnow().isoformat()})}\n\n"
                
                # Stream AI response
                response_content = ""
                async for chunk in chat_manager.stream_response(
                    session_id=session_id,
                    message=request.content,
                    agent_id=request.agent_id
                ):
                    response_content += chunk.content
                    chunk_data = {
                        "type": "chunk",
                        "content": chunk.content,
                        "agent_id": chunk.agent_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                    
                    # Also send to WebSocket connections
                    await connection_manager.send_to_user(current_user["user_id"], {
                        "type": "stream_chunk",
                        "session_id": session_id,
                        "chunk": chunk_data
                    })
                
                # Save complete AI response
                ai_message = await chat_manager.add_message(
                    session_id=session_id,
                    content=response_content,
                    message_type=MessageType.AI,
                    agent_id=request.agent_id
                )
                
                # Send completion signal
                completion_data = {
                    "type": "complete",
                    "message_id": ai_message.id,
                    "total_tokens": ai_message.token_count if hasattr(ai_message, 'token_count') else 0,
                    "timestamp": datetime.utcnow().isoformat()
                }
                yield f"data: {json.dumps(completion_data)}\n\n"
                
                # Notify WebSocket connections of completion
                await connection_manager.send_to_user(current_user["user_id"], {
                    "type": "stream_complete",
                    "session_id": session_id,
                    "completion": completion_data
                })
                
            except Exception as e:
                error_data = {
                    "type": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
                yield f"data: {json.dumps(error_data)}\n\n"
        
        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stream message: {str(e)}"
        )


@router.get("/analytics", response_model=ChatAnalyticsResponse)
async def get_chat_analytics(
    current_user: dict = Depends(get_current_user),
    chat_manager: EnhancedChatManager = Depends(get_chat_manager)
):
    """Get chat analytics for the user"""
    try:
        analytics = await chat_manager.get_user_analytics(current_user["user_id"])
        
        return ChatAnalyticsResponse(
            total_sessions=analytics["total_sessions"],
            total_messages=analytics["total_messages"],
            avg_messages_per_session=analytics["avg_messages_per_session"],
            total_tokens=analytics["total_tokens"],
            last_activity=analytics["last_activity"].isoformat() if analytics["last_activity"] else None,
            agent_usage=analytics["agent_usage"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve analytics: {str(e)}"
        )


@router.get("/agents", response_model=List[Dict[str, Any]])
async def get_available_agents(
    current_user: dict = Depends(get_current_user),
    chat_manager: EnhancedChatManager = Depends(get_chat_manager)
):
    """Get list of available agents"""
    try:
        agents = await chat_manager.get_available_agents()
        return agents
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve agents: {str(e)}"
        )


# WebSocket Endpoints

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
    chat_manager: EnhancedChatManager = Depends(get_chat_manager)
):
    """WebSocket endpoint for real-time chat"""
    try:
        # Authenticate user
        current_user = await AuthManager.get_current_user(token)
        user_id = current_user["user_id"]
        
        # Verify session ownership
        session = await chat_manager.get_session(session_id)
        if not session or session.user_id != user_id:
            await websocket.close(code=4004, reason="Session not found")
            return
        
        # Connect to chat
        await connection_manager.connect(websocket, user_id, session_id)
        
        try:
            while True:
                # Receive message from WebSocket
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                message_type = message_data.get("type")
                
                if message_type == "message":
                    # Handle chat message
                    content = message_data.get("content")
                    agent_id = message_data.get("agent_id")
                    
                    if content and content.strip():
                        # Add user message
                        user_message = await chat_manager.add_message(
                            session_id=session_id,
                            content=content,
                            message_type=MessageType.USER
                        )
                        
                        # Send typing indicator
                        await connection_manager.set_typing_status(user_id, session_id, True)
                        
                        # Process and stream AI response
                        response_content = ""
                        async for chunk in chat_manager.stream_response(
                            session_id=session_id,
                            message=content,
                            agent_id=agent_id
                        ):
                            response_content += chunk.content
                            await connection_manager.send_to_session(user_id, session_id, {
                                "type": "stream_chunk",
                                "content": chunk.content,
                                "agent_id": chunk.agent_id,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                        
                        # Stop typing indicator
                        await connection_manager.set_typing_status(user_id, session_id, False)
                        
                        # Save AI response
                        ai_message = await chat_manager.add_message(
                            session_id=session_id,
                            content=response_content,
                            message_type=MessageType.AI,
                            agent_id=agent_id
                        )
                        
                        # Send completion
                        await connection_manager.send_to_session(user_id, session_id, {
                            "type": "message_complete",
                            "message_id": ai_message.id,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                
                elif message_type == "typing":
                    # Handle typing indicator
                    is_typing = message_data.get("is_typing", False)
                    await connection_manager.set_typing_status(user_id, session_id, is_typing)
                
                elif message_type == "ping":
                    # Handle ping/pong for connection keep-alive
                    await connection_manager.send_to_session(user_id, session_id, {
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logging.error(f"WebSocket error for user {user_id}, session {session_id}: {e}")
            await connection_manager.send_to_session(user_id, session_id, {
                "type": "error",
                "error": "Internal server error",
                "timestamp": datetime.utcnow().isoformat()
            })
        finally:
            connection_manager.disconnect(user_id, session_id)
            
    except Exception as e:
        logging.error(f"WebSocket connection error: {e}")
        await websocket.close(code=4000, reason="Authentication failed")


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    active_users = len(connection_manager.get_active_users())
    total_connections = sum(
        len(sessions) for sessions in connection_manager.active_connections.values()
    )
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_users": active_users,
        "total_connections": total_connections,
        "websocket_manager": "operational"
    }


# Connection status endpoint
@router.get("/connections")
async def get_connection_status(current_user: dict = Depends(get_current_user)):
    """Get current user's connection status"""
    user_id = current_user["user_id"]
    active_sessions = connection_manager.get_user_sessions(user_id)
    
    return {
        "user_id": user_id,
        "active_sessions": active_sessions,
        "total_connections": len(active_sessions),
        "timestamp": datetime.utcnow().isoformat()
    }