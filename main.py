"""
YMERA Enterprise Platform - Unified Backend
Main FastAPI application for YMERA with enhanced learning engine
"""

import os
import uuid
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import structlog
from typing import List, Dict, Optional
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import json
from datetime import datetime
import openai
import pinecone
from openai import OpenAI
import requests

# Initialize LLM Clients
openai_client = OpenAI(api_key=config.get_api_key('openai_api_key'), base_url=config.get_endpoint('openai_base_url')) if config.get_api_key('openai_api_key') else None
xai_client = OpenAI(api_key=config.get_api_key('xai_api_key'), base_url=config.get_endpoint('xai_base_url')) if config.get_api_key('xai_api_key') else None

# Initialize Pinecone
pc = pinecone.Pinecone(api_key=config.get_api_key('pinecone_api_key'), environment=config.get_endpoint('pinecone_env')) if config.get_api_key('pinecone_api_key') else None
index_name = config.api_endpoints['pinecone_index']
if pc and index_name not in pc.list_indexes().names():
    pc.create_index(index_name, dimension=1536, metric='cosine')
    time.sleep(1)


# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Configuration
class ConfigManager:
    def __init__(self):
        self.security = {
            'secret_key': os.getenv("SECRET_KEY", "your-secret-key"),
            'algorithm': "HS256",
        }
        self.system = {
            'host': os.getenv("HOST", "0.0.0.0"),
            'port': int(os.getenv("PORT", "8000")),
            'db_url': os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/ymera_db"),
            'openai_api_key': os.getenv("OPENAI_API_KEY", ""),
            'xai_api_key': os.getenv("XAI_API_KEY", ""),
            'pinecone_api_key': os.getenv("PINECONE_API_KEY", ""),
            'pinecone_env': os.getenv("PINECONE_ENV", "us-east-1"),
        }

config = ConfigManager()

# Database Setup
Base = declarative_base()
engine = create_engine(config.system['db_url'])
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Agent(Base):
    __tablename__ = 'agents'
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    status = Column(String, default='idle')
    chat_history = Column(JSON, nullable=True)
    learning_data = Column(JSON, nullable=True)
    embeddings = Column(JSON, nullable=True)  # Store vector embeddings

class Project(Base):
    __tablename__ = 'projects'
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    edited_by = Column(String, nullable=True)
    data = Column(JSON, nullable=True)

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(String, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey('agents.id'))
    description = Column(String, nullable=False)
    status = Column(String, default='pending')
    created_at = Column(String, default=str(datetime.utcnow()))

# FastAPI application
app = FastAPI(
    title="YMERA Enterprise Platform",
    description="Unified backend for YMERA with enhanced learning engine",
    version="3.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "agents", "description": "Agent management endpoints"},
        {"name": "projects", "description": "Project management endpoints"},
        {"name": "tasks", "description": "Task execution endpoints"},
        {"name": "learning", "description": "Learning engine endpoints"}
    ]
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-frontend-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(credentials.credentials, config.security['secret_key'], algorithms=[config.security['algorithm']])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Pydantic models
class AgentCreate(BaseModel):
    name: str
    type: str

class AgentResponse(AgentCreate):
    id: str
    status: str
    chat_history: Dict = {}
    learning_data: Dict = {}
    embeddings: Dict = {}

class ProjectCreate(BaseModel):
    name: str

class ProjectResponse(ProjectCreate):
    id: str
    edited_by: str | None
    data: Dict | None

class TaskCreate(BaseModel):
    agent_id: str
    description: str

class TaskResponse(TaskCreate):
    id: str
    status: str
    created_at: str

class LearningRequest(BaseModel):
    agent_id: str
    data: Dict
    model: Optional[str] = "openai"  # Default to OpenAI, extensible to others

class LearningUpdate(BaseModel):
    agent_id: str
    chat_history: List[Dict]
    feedback: Optional[Dict] = None

# Initialize LLM Clients
openai_client = OpenAI(api_key=config.system['openai_api_key'], base_url="https://api.openai.com/v1") if config.system['openai_api_key'] else None
xai_client = OpenAI(api_key=config.system['xai_api_key'], base_url="https://api.x.ai/v1") if config.system['xai_api_key'] else None

# Initialize Pinecone
pc = pinecone.Pinecone(api_key=config.system['pinecone_api_key'], environment=config.system['pinecone_env']) if config.system['pinecone_api_key'] else None
index_name = 'ymera-learning'
if pc and index_name not in pc.list_indexes().names():
    pc.create_index(index_name, dimension=1536, metric='cosine')
    time.sleep(1)

# Learning Engine Functions
def generate_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    if not openai_client:
        raise HTTPException(status_code=500, detail="OpenAI client not initialized")
    response = openai_client.embeddings.create(input=text, model=model)
    return response.data[0].embedding

def store_in_pinecone(agent_id: str, embedding: List[float], metadata: Dict):
    if not pc:
        raise HTTPException(status_code=500, detail="Pinecone client not initialized")
    index = pc.Index(index_name)
    index.upsert(vectors=[(f"{agent_id}_{uuid.uuid4()}", embedding, metadata)])

def train_model(agent_id: str, data: Dict, model: str):
    if model == "openai" and openai_client:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "You are a trainer for the learning engine."}, {"role": "user", "content": json.dumps(data)}],
            max_tokens=500
        )
        return response.choices[0].message.content
    elif model == "xai" and xai_client:
        response = xai_client.chat.completions.create(
            model="grok-4",
            messages=[{"role": "system", "content": "You are a trainer for the learning engine."}, {"role": "user", "content": json.dumps(data)}],
            max_tokens=500
        )
        return response.choices[0].message.content
    else:
        raise HTTPException(status_code=400, detail=f"Model {model} not supported or API key missing")

# Routes
@app.post("/agents", response_model=AgentResponse, tags=["agents"])
async def create_agent(agent: AgentCreate, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    db_agent = Agent(id=str(uuid.uuid4()), name=agent.name, type=agent.type, status='idle')
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.get("/agents", response_model=List[AgentResponse], tags=["agents"])
async def get_agents(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Agent).all()

@app.post("/agents/{agent_id}/upload", tags=["agents"])
async def upload_agent(agent_id: str, file: UploadFile = File(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    content = await file.read()
    agent.data = json.loads(content.decode()) if content else {}
    db.commit()
    return {"status": "Upload successful"}

@app.get("/agents/{agent_id}/download", tags=["agents"])
async def download_agent(agent_id: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.post("/agents/{agent_id}/chat", tags=["agents"])
async def chat_agent(agent_id: str, message: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    chat_history = agent.chat_history or []
    chat_history.append({"user": message, "agent": "Mock response to " + message})
    agent.chat_history = chat_history
    # Generate and store embedding
    embedding = generate_embedding(message)
    store_in_pinecone(agent_id, embedding, {"text": message, "timestamp": str(datetime.utcnow())})
    agent.embeddings = agent.embeddings or {}
    agent.embeddings[message] = embedding
    db.commit()
    return {"chat_history": chat_history}

@app.post("/agents/{agent_id}/start", tags=["agents"])
async def start_agent(agent_id: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.status = "active"
    db.commit()
    return {"status": "Agent started"}

@app.post("/agents/{agent_id}/stop", tags=["agents"])
async def stop_agent(agent_id: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.status = "idle"
    db.commit()
    return {"status": "Agent stopped"}

@app.post("/projects", response_model=ProjectResponse, tags=["projects"])
async def create_project(project: ProjectCreate, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    db_project = Project(id=str(uuid.uuid4()), name=project.name, edited_by=user_id)
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

@app.get("/projects", response_model=List[ProjectResponse], tags=["projects"])
async def get_projects(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Project).all()

@app.post("/projects/{project_id}/upload", tags=["projects"])
async def upload_project(project_id: str, file: UploadFile = File(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    content = await file.read()
    project.data = json.loads(content.decode()) if content else {}
    project.edited_by = user_id
    db.commit()
    return {"status": "Upload successful"}

@app.get("/projects/{project_id}/download", tags=["projects"])
async def download_project(project_id: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@app.post("/tasks/submit", response_model=TaskResponse, tags=["tasks"])
async def submit_task(task: TaskCreate, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    db_task = Task(id=str(uuid.uuid4()), agent_id=task.agent_id, description=task.description)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.post("/learning/train", tags=["learning"])
async def train_learning_engine(request: LearningRequest, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == request.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    learning_data = agent.learning_data or {}
    training_result = train_model(request.agent_id, request.data, request.model)
    learning_data.update({"training_result": training_result, "data": request.data})
    agent.learning_data = learning_data
    # Update embeddings
    embedding = generate_embedding(json.dumps(request.data))
    store_in_pinecone(request.agent_id, embedding, {"type": "training", "data": request.data})
    agent.embeddings = agent.embeddings or {}
    agent.embeddings[json.dumps(request.data)] = embedding
    db.commit()
    return {"status": "Training completed", "result": training_result}

@app.post("/learning/update", tags=["learning"])
async def update_learning_engine(request: LearningUpdate, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == request.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.chat_history = request.chat_history
    if request.feedback:
        learning_data = agent.learning_data or {}
        learning_data.update({"feedback": request.feedback})
        agent.learning_data = learning_data
        # Retrain with feedback
        train_result = train_model(request.agent_id, request.feedback, "openai")
        learning_data.update({"feedback_training": train_result})
        agent.learning_data = learning_data
    db.commit()
    return {"status": "Learning updated"}

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    import uvicorn
    uvicorn.run(app, host=config.system['host'], port=config.system['port'], loop="uvloop")
from app.api.als_router import router as als_router
app.include_router(als_router)
