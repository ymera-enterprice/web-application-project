# ============================================================================
# COMPLETE AGENT SYSTEM WITH API, CHAT, AND FILE MANAGEMENT
# ============================================================================

import asyncio
import json
import os
import uuid
import mimetypes
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import aiofiles
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# API MODELS
# ============================================================================

class TaskRequest(BaseModel):
    task_id: Optional[str] = None
    type: str
    description: Optional[str] = None
    data: Optional[Dict] = None
    required_capabilities: Optional[List[str]] = None
    session_id: Optional[str] = None
    priority: Optional[str] = "normal"

class ChatMessage(BaseModel):
    message_id: Optional[str] = None
    session_id: str
    content: str
    message_type: str = "user"
    attachments: Optional[List[str]] = None
    timestamp: Optional[str] = None

class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    size: int
    content_type: str
    upload_timestamp: str
    session_id: str

class AgentResponse(BaseModel):
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None
    agent_id: Optional[str] = None
    processing_time: Optional[float] = None

# ============================================================================
# FILE MANAGER
# ============================================================================

class FileManager:
    """Handles file upload, download, and management for agent system"""
    
    def __init__(self, upload_directory: str = "uploads", max_file_size: int = 100 * 1024 * 1024):
        self.upload_directory = Path(upload_directory)
        self.upload_directory.mkdir(exist_ok=True)
        self.max_file_size = max_file_size
        self.file_metadata: Dict[str, Dict] = {}
        
        # Create subdirectories
        (self.upload_directory / "temp").mkdir(exist_ok=True)
        (self.upload_directory / "permanent").mkdir(exist_ok=True)
        (self.upload_directory / "processed").mkdir(exist_ok=True)
    
    async def upload_file(self, file: UploadFile, session_id: str, temporary: bool = False) -> Dict:
        """Upload and store file"""
        try:
            # Validate file size
            file_content = await file.read()
            if len(file_content) > self.max_file_size:
                raise HTTPException(status_code=413, detail="File too large")
            
            # Generate unique file ID
            file_id = f"{uuid.uuid4().hex}_{file.filename}"
            
            # Determine storage location
            storage_dir = "temp" if temporary else "permanent"
            file_path = self.upload_directory / storage_dir / file_id
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
            
            # Store metadata
            metadata = {
                "file_id": file_id,
                "original_filename": file.filename,
                "size": len(file_content),
                "content_type": file.content_type or mimetypes.guess_type(file.filename)[0],
                "session_id": session_id,
                "upload_timestamp": datetime.utcnow().isoformat(),
                "file_path": str(file_path),
                "temporary": temporary,
                "processed": False
            }
            
            self.file_metadata[file_id] = metadata
            
            logger.info(f"File uploaded: {file.filename} -> {file_id}")
            
            return {
                "file_id": file_id,
                "filename": file.filename,
                "size": len(file_content),
                "content_type": metadata["content_type"],
                "upload_timestamp": metadata["upload_timestamp"],
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    async def download_file(self, file_id: str, session_id: str = None) -> FileResponse:
        """Download file by ID"""
        try:
            metadata = self.file_metadata.get(file_id)
            if not metadata:
                raise HTTPException(status_code=404, detail="File not found")
            
            # Session validation (optional)
            if session_id and metadata["session_id"] != session_id:
                raise HTTPException(status_code=403, detail="Access denied")
            
            file_path = Path(metadata["file_path"])
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="File not found on disk")
            
            return FileResponse(
                path=file_path,
                filename=metadata["original_filename"],
                media_type=metadata["content_type"]
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"File download failed: {e}")
            raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
    
    async def process_file_with_agent(self, file_id: str, agent_manager, processing_type: str = "auto") -> Dict:
        """Process uploaded file using appropriate agent"""
        try:
            metadata = self.file_metadata.get(file_id)
            if not metadata:
                raise ValueError("File not found")
            
            # Read file content
            async with aiofiles.open(metadata["file_path"], 'rb') as f:
                file_content = await f.read()
            
            # Determine processing task based on file type
            content_type = metadata["content_type"]
            task = {
                "task_id": f"file_process_{file_id}",
                "type": self._determine_task_type(content_type, processing_type),
                "file_id": file_id,
                "file_metadata": metadata,
                "data": {
                    "content": file_content.decode('utf-8') if content_type.startswith('text/') else None,
                    "binary_content": file_content if not content_type.startswith('text/') else None,
                    "processing_type": processing_type
                }
            }
            
            # Assign to agent
            result = await agent_manager.assign_task(task, metadata["session_id"])
            
            # Mark as processed
            self.file_metadata[file_id]["processed"] = True
            self.file_metadata[file_id]["processing_result"] = result
            
            return result
            
        except Exception as e:
            logger.error(f"File processing failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _determine_task_type(self, content_type: str, processing_type: str) -> str:
        """Determine appropriate task type based on file content type"""
        if processing_type != "auto":
            return processing_type
        
        type_mapping = {
            "text/plain": "natural_language",
            "text/csv": "data_processing",
            "application/json": "data_processing",
            "text/html": "web_scraping",
            "text/javascript": "code_analysis",
            "text/python": "code_analysis",
            "application/pdf": "natural_language",
            "image/": "data_processing"
        }
        
        for file_type, task_type in type_mapping.items():
            if content_type.startswith(file_type):
                return task_type
        
        return "general"
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict]:
        """Get file metadata"""
        return self.file_metadata.get(file_id)
    
    def list_files(self, session_id: str = None) -> List[Dict]:
        """List files, optionally filtered by session"""
        files = []
        for file_id, metadata in self.file_metadata.items():
            if session_id is None or metadata["session_id"] == session_id:
                files.append({
                    "file_id": file_id,
                    "filename": metadata["original_filename"],
                    "size": metadata["size"],
                    "upload_timestamp": metadata["upload_timestamp"],
                    "processed": metadata["processed"]
                })
        return files
    
    async def cleanup_temporary_files(self, max_age_hours: int = 24):
        """Clean up temporary files older than specified age"""
        try:
            cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)
            
            files_to_remove = []
            for file_id, metadata in self.file_metadata.items():
                if metadata["temporary"]:
                    upload_time = datetime.fromisoformat(metadata["upload_timestamp"]).timestamp()
                    if upload_time < cutoff_time:
                        files_to_remove.append(file_id)
            
            for file_id in files_to_remove:
                await self._delete_file(file_id)
                
            logger.info(f"Cleaned up {len(files_to_remove)} temporary files")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
    
    async def _delete_file(self, file_id: str):
        """Delete file and metadata"""
        try:
            metadata = self.file_metadata.get(file_id)
            if metadata:
                file_path = Path(metadata["file_path"])
                if file_path.exists():
                    file_path.unlink()
                del self.file_metadata[file_id]
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")


# ============================================================================
# LIVE CHAT MANAGER
# ============================================================================

class LiveChatManager:
    """Manages real-time chat connections and message routing"""
    
    def __init__(self, agent_manager):
        self.agent_manager = agent_manager
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_agents: Dict[str, str] = {}  # session_id -> agent_id
        self.message_history: Dict[str, List[Dict]] = {}  # session_id -> messages
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Connect new client"""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        
        if session_id not in self.message_history:
            self.message_history[session_id] = []
        
        logger.info(f"Client connected: {session_id}")
        
        # Send connection confirmation
        await self.send_message(session_id, {
            "type": "system",
            "content": "Connected to AI Agent System",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def disconnect(self, session_id: str):
        """Disconnect client"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        
        if session_id in self.session_agents:
            del self.session_agents[session_id]
        
        logger.info(f"Client disconnected: {session_id}")
    
    async def send_message(self, session_id: str, message: Dict):
        """Send message to specific client"""
        try:
            connection = self.active_connections.get(session_id)
            if connection:
                await connection.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send message to {session_id}: {e}")
            await self.disconnect(session_id)
    
    async def broadcast_message(self, message: Dict, exclude_session: str = None):
        """Broadcast message to all connected clients"""
        for session_id, connection in self.active_connections.items():
            if session_id != exclude_session:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Broadcast failed for {session_id}: {e}")
    
    async def process_user_message(self, session_id: str, message: Dict):
        """Process incoming user message"""
        try:
            # Store user message
            user_msg = {
                "message_id": str(uuid.uuid4()),
                "session_id": session_id,
                "type": "user",
                "content": message.get("content", ""),
                "timestamp": datetime.utcnow().isoformat(),
                "attachments": message.get("attachments", [])
            }
            
            self.message_history[session_id].append(user_msg)
            
            # Determine task type from message
            task_type = self._determine_task_from_message(message.get("content", ""))
            
            # Create task for agent processing
            task = {
                "task_id": f"chat_{user_msg['message_id']}",
                "type": task_type,
                "description": message.get("content", ""),
                "data": {
                    "message": user_msg,
                    "conversation_history": self.message_history[session_id][-10:],  # Last 10 messages
                    "attachments": message.get("attachments", [])
                },
                "session_id": session_id
            }
            
            # Send typing indicator
            await self.send_message(session_id, {
                "type": "typing",
                "content": "Agent is processing...",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Process with agent
            result = await self.agent_manager.assign_task(task, session_id)
            
            # Create agent response message
            agent_msg = {
                "message_id": str(uuid.uuid4()),
                "session_id": session_id,
                "type": "agent",
                "content": result.get("response", result.get("data", "I'm sorry, I couldn't process that request.")),
                "timestamp": datetime.utcnow().isoformat(),
                "agent_id": result.get("agent_id"),
                "processing_time": result.get("processing_time"),
                "success": result.get("success", False)
            }
            
            self.message_history[session_id].append(agent_msg)
            
            # Send response to user
            await self.send_message(session_id, agent_msg)
            
        except Exception as e:
            logger.error(f"Message processing failed: {e}")
            await self.send_message(session_id, {
                "type": "error",
                "content": f"Sorry, an error occurred: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            })
    
    def _determine_task_from_message(self, content: str) -> str:
        """Determine task type based on message content"""
        content_lower = content.lower()
        
        if any(word in content_lower for word in ["analyze code", "review code", "code quality"]):
            return "code_analysis"
        elif any(word in content_lower for word in ["scrape", "web data", "website"]):
            return "web_scraping"
        elif any(word in content_lower for word in ["process data", "analyze data", "statistics"]):
            return "data_processing"
        elif any(word in content_lower for word in ["api", "integrate", "endpoint"]):
            return "api_integration"
        elif any(word in content_lower for word in ["security", "audit", "vulnerability"]):
            return "security_audit"
        else:
            return "natural_language"
    
    def get_conversation_history(self, session_id: str) -> List[Dict]:
        """Get conversation history for session"""
        return self.message_history.get(session_id, [])
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        return list(self.active_connections.keys())


# ============================================================================
# MAIN API APPLICATION
# ============================================================================

class AgentAPI:
    """Main API application integrating all components"""
    
    def __init__(self, agent_manager, file_manager: FileManager, chat_manager: LiveChatManager):
        self.agent_manager = agent_manager
        self.file_manager = file_manager
        self.chat_manager = chat_manager
        
        # Create FastAPI app
        self.app = FastAPI(title="Intelligent Agent System API", version="1.0.0")
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Mount static files
        self.app.mount("/static", StaticFiles(directory="static"), name="static")
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup API routes"""
        
        # ============================================================================
        # AGENT MANAGEMENT ROUTES
        # ============================================================================
        
        @self.app.post("/api/agents/create", response_model=AgentResponse)
        async def create_agent(
            name: str,
            agent_type: str,
            capabilities: List[str],
            configuration: Optional[Dict] = None
        ):
            """Create new agent"""
            try:
                from enum import Enum
                # Convert string capabilities to enum (assuming AgentCapability enum exists)
                cap_enums = []
                for cap in capabilities:
                    try:
                        # This would need to be adjusted based on actual AgentCapability enum
                        cap_enums.append(cap)  # Placeholder
                    except ValueError:
                        continue
                
                agent_id = await self.agent_manager.create_agent(
                    name=name,
                    agent_type=agent_type,
                    capabilities=cap_enums,
                    configuration=configuration or {}
                )
                
                return AgentResponse(
                    success=True,
                    data={"agent_id": agent_id, "name": name, "type": agent_type}
                )
                
            except Exception as e:
                return AgentResponse(success=False, error=str(e))
        
        @self.app.get("/api/agents/status")
        async def get_agents_status():
            """Get status of all agents"""
            try:
                status = await self.agent_manager.get_all_agents_status()
                return AgentResponse(success=True, data=status)
            except Exception as e:
                return AgentResponse(success=False, error=str(e))
        
        @self.app.get("/api/agents/{agent_id}/status")
        async def get_agent_status(agent_id: str):
            """Get status of specific agent"""
            try:
                status = await self.agent_manager.get_agent_status(agent_id)
                return AgentResponse(success=True, data=status)
            except Exception as e:
                return AgentResponse(success=False, error=str(e))
        
        @self.app.post("/api/agents/task", response_model=AgentResponse)
        async def assign_task(task_request: TaskRequest):
            """Assign task to appropriate agent"""
            try:
                task = {
                    "task_id": task_request.task_id or f"task_{uuid.uuid4().hex[:8]}",
                    "type": task_request.type,
                    "description": task_request.description,
                    "data": task_request.data or {},
                    "required_capabilities": task_request.required_capabilities or [],
                    "priority": task_request.priority
                }
                
                result = await self.agent_manager.assign_task(task, task_request.session_id)
                return AgentResponse(
                    success=result.get("success", True),
                    data=result,
                    agent_id=result.get("agent_id"),
                    processing_time=result.get("processing_time")
                )
                
            except Exception as e:
                return AgentResponse(success=False, error=str(e))
        
        @self.app.get("/api/agents/performance")
        async def get_performance_report():
            """Get system performance report"""
            try:
                report = await self.agent_manager.get_performance_report()
                return AgentResponse(success=True, data=report)
            except Exception as e:
                return AgentResponse(success=False, error=str(e))
        
        # ============================================================================
        # FILE MANAGEMENT ROUTES  
        # ============================================================================
        
        @self.app.post("/api/files/upload", response_model=FileUploadResponse)
        async def upload_file(
            file: UploadFile = File(...),
            session_id: str = "default",
            temporary: bool = False
        ):
            """Upload file"""
            try:
                result = await self.file_manager.upload_file(file, session_id, temporary)
                return FileUploadResponse(**result)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/files/{file_id}/download")
        async def download_file(file_id: str, session_id: Optional[str] = None):
            """Download file"""
            return await self.file_manager.download_file(file_id, session_id)
        
        @self.app.post("/api/files/{file_id}/process")
        async def process_file(file_id: str, processing_type: str = "auto"):
            """Process file with agent"""
            try:
                result = await self.file_manager.process_file_with_agent(
                    file_id, self.agent_manager, processing_type
                )
                return AgentResponse(
                    success=result.get("success", True),
                    data=result
                )
            except Exception as e:
                return AgentResponse(success=False, error=str(e))
        
        @self.app.get("/api/files/list")
        async def list_files(session_id: Optional[str] = None):
            """List files"""
            try:
                files = self.file_manager.list_files(session_id)
                return AgentResponse(success=True, data={"files": files})
            except Exception as e:
                return AgentResponse(success=False, error=str(e))
        
        @self.app.get("/api/files/{file_id}/metadata")
        async def get_file_metadata(file_id: str):
            """Get file metadata"""
            try:
                metadata = self.file_manager.get_file_metadata(file_id)
                if not metadata:
                    raise HTTPException(status_code=404, detail="File not found")
                return AgentResponse(success=True, data=metadata)
            except HTTPException:
                raise
            except Exception as e:
                return AgentResponse(success=False, error=str(e))
        
        # ============================================================================
        # LIVE CHAT WEBSOCKET
        # ============================================================================
        
        @self.app.websocket("/ws/chat/{session_id}")
        async def chat_websocket(websocket: WebSocket, session_id: str):
            """WebSocket endpoint for live chat"""
            await self.chat_manager.connect(websocket, session_id)
            
            try:
                while True:
                    # Receive message from client
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    # Process message
                    await self.chat_manager.process_user_message(session_id, message)
                    
            except WebSocketDisconnect:
                await self.chat_manager.disconnect(session_id)
            except Exception as e:
                logger.error(f"WebSocket error for {session_id}: {e}")
                await self.chat_manager.disconnect(session_id)
        
        # ============================================================================
        # CHAT MANAGEMENT ROUTES
        # ============================================================================
        
        @self.app.get("/api/chat/{session_id}/history")
        async def get_chat_history(session_id: str):
            """Get chat history for session"""
            try:
                history = self.chat_manager.get_conversation_history(session_id)
                return AgentResponse(success=True, data={"history": history})
            except Exception as e:
                return AgentResponse(success=False, error=str(e))
        
        @self.app.get("/api/chat/sessions")
        async def get_active_sessions():
            """Get active chat sessions"""
            try:
                sessions = self.chat_manager.get_active_sessions()
                return AgentResponse(success=True, data={"sessions": sessions})
            except Exception as e:
                return AgentResponse(success=False, error=str(e))
        
        @self.app.post("/api/chat/message")
        async def send_chat_message(message: ChatMessage):
            """Send chat message (alternative to WebSocket)"""
            try:
                message_dict = {
                    "content": message.content,
                    "attachments": message.attachments or []
                }
                
                await self.chat_manager.process_user_message(
                    message.session_id, 
                    message_dict
                )
                
                return AgentResponse(success=True, data={"message_sent": True})
                
            except Exception as e:
                return AgentResponse(success=False, error=str(e))
        
        # ============================================================================
        # SYSTEM ROUTES
        # ============================================================================
        
        @self.app.get("/api/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "agents": len(self.agent_manager.agents),
                "active_sessions": len(self.chat_manager.active_connections)
            }
        
        @self.app.get("/api/system/info")
        async def system_info():
            """Get system information"""
            try:
                return AgentResponse(success=True, data={
                    "total_agents": len(self.agent_manager.agents),
                    "active_chat_sessions": len(self.chat_manager.active_connections),
                    "uploaded_files": len(self.file_manager.file_metadata),
                    "capabilities": list(self.agent_manager.agent_pools.keys()),
                    "uptime": datetime.utcnow().isoformat()
                })
            except Exception as e:
                return AgentResponse(success=False, error=str(e))
        
        # ============================================================================
        # BROWSER ACCESS ROUTES
        # ============================================================================
        
        @self.app.post("/api/browser/access")
        async def browser_access(
            url: str,
            session_id: str,
            safety_level: str = "high",
            agent_id: Optional[str] = None
        ):
            """Access URL through secure browser"""
            try:
                # If no specific agent, create a browser access task
                if not agent_id:
                    task = {
                        "task_id": f"browser_{uuid.uuid4().hex[:8]}",
                        "type": "web_scraping",
                        "url": url,
                        "safety_level": safety_level,
                        "rules": {"content": True, "links": True}
                    }
                    
                    result = await self.agent_manager.assign_task(task, session_id)
                    return AgentResponse(success=True, data=result)
                else:
                    # Direct browser access through specific agent
                    agent = self.agent_manager.agents.get(agent_id)
                    if not agent:
                        return AgentResponse(success=False, error="Agent not found")
                    
                    result = await agent.browser.access_url(agent_id, session_id, url, safety_level)
                    return AgentResponse(success=True, data=result)
                    
            except Exception as e:
                return AgentResponse(success=False, error=str(e))


# ============================================================================
# INITIALIZATION AND STARTUP
# ============================================================================

async def create_complete_system():
    """Create complete system with all components"""
    try:
        # Initialize core components (these would be properly initialized)
        # db_manager = DatabaseManager(...)
        # redis_manager = RedisManager(...)
        # ai_manager = MultiLLMManager(...)
        # learning_engine = LearningEngine(...)
        # browser_manager = SecureBrowserManager(...)
        
        # agent_manager = AgentManager(db_manager, redis_manager, ai_manager, learning_engine, browser_manager)
        # await agent_manager.initialize()
        
        # Initialize file manager
        file_manager = FileManager(upload_directory="uploads", max_file_size=100 * 1024 * 1024)
        
        # Initialize chat manager
        # chat_manager = LiveChatManager(agent_manager)
        
        # Create API application
        # api = AgentAPI(agent_manager, file_manager, chat_manager)
        
        # Setup cleanup tasks
        # asyncio.create_task(file_manager.cleanup_temporary_files())
        
        logger.info("Complete Agent System initialized successfully")
        # return api.app
        
    except Exception as e:
        logger.error(f"System initialization failed: {e}")
        raise


# Example client-side HTML for testing
HTML_CLIENT = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Agent System</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .chat-container { border: 1px solid #ccc; height: 400px; overflow-y: auto; padding: 10px; margin-bottom: 10px; }
        .message { margin-bottom: 10px; padding: 5px; border-radius: 5px; }
        .user-message { background-color: #e3f2fd; text-align: right; }
        .agent-message { background-color