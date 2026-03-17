import os
import json
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Researcher Agent", version="1.0.0")

class ResearchRequest(BaseModel):
    query: str
    category: str = None
    use_internet: bool = False
    max_results: int = 3

class ResearchResult(BaseModel):
    title: str
    content: str
    relevance: float
    source: str

class ResearchResponse(BaseModel):
    results: List[ResearchResult]
    source: str
    metadata: Dict[str, Any]

@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "researcher"}

@app.get("/.well-known/agent.json")
async def discovery():
    """A2A Discovery endpoint"""
    return {
        "name": "researcher-v1",
        "type": "researcher",
        "description": "Information retrieval and research agent",
        "version": "1.0.0",
        "endpoint": "http://researcher:8080",
        "capabilities": ["rag_search", "information_retrieval", "knowledge_base_search"],
        "llm_model": "Phi-3-mini-4k-instruct",
        "supports": ["a2a/v1"]
    }

@app.post("/v1/research")
async def research(request: ResearchRequest):
    """Поиск информации"""
    try:
        logger.info(f"Research query: {request.query}")
        
        # Имитация поиска в RAG базе
        # В реальности здесь будет запрос к Qdrant
        mock_results = [
            {
                "title": "Решение: проблемы с интернетом",
                "content": "Проверьте подключение кабелей, перезагрузите роутер.",
                "relevance": 0.89,
                "source": "knowledge_base"
            },
            {
                "title": "Частые проблемы после грозы",
                "content": "После грозы часто сгорает сетевое оборудование.",
                "relevance": 0.76,
                "source": "knowledge_base"
            }
        ]
        
        # Если включен интернет-поиск
        if request.use_internet:
            # Имитация интернет-поиска
            mock_results.append({
                "title": "Что делать если не работает интернет",
                "content": "Проверьте индикаторы на роутере, позвоните провайдеру.",
                "relevance": 0.82,
                "source": "internet"
            })
        
        results = [ResearchResult(**result) for result in mock_results]
        
        return ResearchResponse(
            results=results[:request.max_results],
            source="rag_and_internet" if request.use_internet else "rag",
            metadata={
                "query": request.query,
                "results_count": len(results),
                "processing_time": 0.2
            }
        )
        
    except Exception as e:
        logger.error(f"Research error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/search-knowledge-base")
async def search_knowledge_base(request: ResearchRequest):
    """Поиск в базе знаний"""
    # Заглушка
    return {
        "results": [
            {
                "id": "doc_001",
                "content": "Техническая поддержка работает 24/7",
                "relevance": 0.91
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)