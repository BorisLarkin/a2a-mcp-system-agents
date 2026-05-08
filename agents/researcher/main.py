import os
import json
import logging
import uuid
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Researcher Agent", version="2.0.0")

# MCP-инструменты
ENCODER_MCP_URL = os.getenv("ENCODER_MCP_URL", "http://sentence-encoder:8080/mcp")
QDRANT_MCP_URL = os.getenv("QDRANT_MCP_URL", "http://qdrant-search:8080/mcp")

# --- A2A Models ---
class A2ATaskRequest(BaseModel):
    skill_id: str
    input: Dict[str, Any]

class A2ATaskResponse(BaseModel):
    task_id: Optional[str] = None
    status: str
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# --- MCP Helpers ---

async def call_mcp_tool(mcp_url: str, tool_name: str, arguments: dict) -> dict:
    """Универсальный вызов MCP-инструмента"""
    rpc_request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        },
        "id": 1
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(mcp_url, json=rpc_request)
        resp.raise_for_status()
        result = resp.json()
        if "error" in result:
            raise Exception(result["error"]["message"])
        return result["result"]


async def get_embedding(text: str) -> list:
    """Получает эмбеддинг текста через sentence-encoder"""
    result = await call_mcp_tool(ENCODER_MCP_URL, "embed", {"texts": [text]})
    embeddings = result.get("embeddings", [])
    return embeddings[0] if embeddings else []


async def search_qdrant(vector: list, category: str = None, limit: int = 5) -> list:
    """Поиск в Qdrant по вектору"""
    arguments = {
        "vector": vector,
        "limit": limit,
        "score_threshold": 0.3
    }
    if category:
        arguments["category"] = category
    
    result = await call_mcp_tool(QDRANT_MCP_URL, "search", arguments)
    return result.get("results", [])


async def do_research(query: str, category: str = None, max_results: int = 3) -> dict:
    """
    Основная логика исследования:
    1. Векторизовать запрос
    2. Найти релевантные документы в Qdrant
    3. Отранжировать и вернуть
    """
    # Шаг 1: получаем эмбеддинг
    vector = await get_embedding(query)
    if not vector:
        return {
            "results": [],
            "source": "none",
            "metadata": {"error": "Failed to get embedding"}
        }
    
    # Шаг 2: ищем в Qdrant
    results = await search_qdrant(vector, category=category, limit=max_results + 2)
    
    # Шаг 3: отбираем лучшие
    top_results = results[:max_results]
    
    return {
        "results": top_results,
        "source": "rag",
        "metadata": {
            "query": query,
            "results_count": len(top_results),
            "total_found": len(results)
        }
    }


# --- REST Endpoints ---

@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "researcher"}

@app.get("/.well-known/agent.json")
async def discovery():
    """A2A Discovery endpoint с JSON Schema"""
    return {
        "name": "researcher-v2",
        "type": "researcher",
        "description": "Information retrieval agent using vector search (Qdrant) and embeddings",
        "version": "2.0.0",
        "endpoint": "http://researcher:9002",
        "capabilities": ["search"],
        "skills": [
            {
                "id": "search",
                "description": "Поиск релевантных решений в базе знаний через векторный поиск",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Текст обращения"},
                        "category": {"type": "string", "description": "Категория для фильтрации (опционально)"},
                        "max_results": {"type": "integer", "default": 3, "description": "Максимальное количество результатов"}
                    },
                    "required": ["query"]
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "title": {"type": "string"},
                                    "content": {"type": "string"},
                                    "category": {"type": "string"},
                                    "source": {"type": "string"},
                                    "relevance": {"type": "number", "minimum": 0, "maximum": 1}
                                }
                            }
                        },
                        "source": {"type": "string"},
                        "metadata": {"type": "object"}
                    },
                    "required": ["results", "source"]
                }
            },
            {
                "id": "search_knowledge_base",
                "description": "Поиск только в локальной базе знаний (без интернета)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_results": {"type": "integer", "default": 3}
                    },
                    "required": ["query"]
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "results": {"type": "array"},
                        "source": {"type": "string"}
                    }
                }
            }
        ],
        "supports": ["a2a/v1", "tasks/send"],
        "a2a_protocol": {
            "task_endpoint": "/tasks/send",
            "async_support": False
        }
    }

# --- A2A Endpoint ---

@app.post("/tasks/send", response_model=A2ATaskResponse)
async def tasks_send(request: A2ATaskRequest):
    """
    A2A endpoint: выполняет поиск решений через Qdrant.
    """
    logger.info(f"A2A Task received: skill={request.skill_id}")
    
    try:
        if request.skill_id in ("search", "search_knowledge_base"):
            query = request.input.get("query", "")
            category = request.input.get("category")
            max_results = request.input.get("max_results", 3)
            
            result = await do_research(
                query=query,
                category=category,
                max_results=max_results
            )
            
            return A2ATaskResponse(
                task_id=str(uuid.uuid4()),
                status="completed",
                output=result
            )
        
        else:
            return A2ATaskResponse(
                task_id=str(uuid.uuid4()),
                status="failed",
                error=f"Unknown skill: {request.skill_id}"
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