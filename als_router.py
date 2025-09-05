from fastapi import APIRouter
from app.learning.advanced.scheduler import (
    task_optimize_retriever, task_train_embedding, task_train_reranker, task_select_prompt, current_retriever_config
)

router = APIRouter(prefix="/als", tags=["AdvancedLearning"])

@router.post("/optimize")
def optimize():
    res = task_optimize_retriever.delay()
    return {"task_id": res.id}

@router.post("/train/embedding")
def train_embedding(limit: int = 1024):
    res = task_train_embedding.delay(limit)
    return {"task_id": res.id}

@router.post("/train/reranker")
def train_reranker(limit: int = 2048):
    res = task_train_reranker.delay(limit)
    return {"task_id": res.id}

@router.post("/policy/select")
def policy_select(metrics: dict):
    res = task_select_prompt.delay(metrics)
    return {"task_id": res.id}

@router.get("/retriever/config")
def retriever_config():
    return current_retriever_config()
