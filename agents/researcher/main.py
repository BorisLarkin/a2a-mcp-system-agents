import os
import json
import logging
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Researcher Agent", version="1.0.0")

# --- Pydantic Models ---

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

# --- A2A Protocol Models ---

class A2ATaskRequest(BaseModel):
    skill_id: str
    input: Dict[str, Any]

class A2ATaskResponse(BaseModel):
    task_id: Optional[str] = None
    status: str
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# --- Core research logic ---

def do_research(query: str, category: str = None, use_internet: bool = False, max_results: int = 3) -> dict:
    """
    Заглушка поиска. В будущем — запрос к Qdrant / SearXNG.
    """
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
    
    if use_internet:
        mock_results.append({
            "title": "Что делать если не работает интернет",
            "content": "Проверьте индикаторы на роутере, позвоните провайдеру.",
            "relevance": 0.82,
            "source": "internet"
        })
    
    return {
        "results": mock_results[:max_results],
        "source": "rag_and_internet" if use_internet else "rag",
        "metadata": {
            "query": query,
            "results_count": len(mock_results[:max_results]),
            "processing_time": 0.2
        }
    }

# --- REST Endpoints ---

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
        "endpoint": "http://researcher:9002",
        "capabilities": ["search"],
        "skills": [
            {
                "id": "search",
                "description": "Search knowledge base and optionally internet for solutions",
                "input_schema": {
                    "query": "string (search query)",
                    "category": "string (optional, problem category)",
                    "use_internet": "bool (default false)",
                    "max_results": "int (default 3)"
                },
                "output_schema": {
                    "results": "array of {title, content, relevance, source}",
                    "source": "string",
                    "metadata": "object"
                }
            },
            {
                "id": "search_knowledge_base",
                "description": "Search only local knowledge base",
                "input_schema": {
                    "query": "string",
                    "max_results": "int"
                },
                "output_schema": {
                    "results": "array of {id, content, relevance}"
                }
            }
        ],
        "supports": ["a2a/v1", "tasks/send"],
        "a2a_protocol": {
            "task_endpoint": "/tasks/send",
            "async_support": False
        }
    }

@app.post("/v1/research")
async def research(request: ResearchRequest):
    """Поиск информации (прямой вызов)"""
    try:
        logger.info(f"Research query: {request.query}")
        result = do_research(
            query=request.query,
            category=request.category,
            use_internet=request.use_internet,
            max_results=request.max_results
        )
        
        results = [ResearchResult(**r) for r in result["results"]]
        return ResearchResponse(
            results=results,
            source=result["source"],
            metadata=result["metadata"]
        )
    except Exception as e:
        logger.error(f"Research error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/search-knowledge-base")
async def search_knowledge_base(request: ResearchRequest):
    """Поиск в базе знаний (прямой вызов)"""
    return {
        "results": [
            {
                "id": "doc_001",
                "content": "Техническая поддержка работает 24/7",
                "relevance": 0.91
            }
        ]
    }

# --- A2A Protocol Endpoint ---

@app.post("/tasks/send", response_model=A2ATaskResponse)
async def tasks_send(request: A2ATaskRequest):
    """
    A2A endpoint: receive a task, execute skill, return result.
    Synchronous implementation.
    """
    logger.info(f"A2A Task received: skill={request.skill_id}")
    
    try:
        if request.skill_id == "search":
            query = request.input.get("query", "")
            category = request.input.get("category")
            use_internet = request.input.get("use_internet", False)
            max_results = request.input.get("max_results", 3)
            
            result = do_research(
                query=query,
                category=category,
                use_internet=use_internet,
                max_results=max_results
            )
            
            return A2ATaskResponse(
                task_id=str(uuid.uuid4()),
                status="completed",
                output=result
            )
        
        elif request.skill_id == "search_knowledge_base":
            query = request.input.get("query", "")
            max_results = request.input.get("max_results", 3)
            
            output = {
                "results": [
                    {"id": "doc_001", "content": f"Результат по запросу: {query}", "relevance": 0.91}
                ]
            }
            
            return A2ATaskResponse(
                task_id=str(uuid.uuid4()),
                status="completed",
                output=output
            )
        
        else:
            return A2ATaskResponse(
                task_id=str(uuid.uuid4()),
                status="failed",
                error=f"Unknown skill_id: {request.skill_id}"
            )
    
    except Exception as e:
        logger.error(f"A2A Task failed: {str(e)}", exc_info=True)
        return A2ATaskResponse(
            task_id=str(uuid.uuid4()),
            status="failed",
            error=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)