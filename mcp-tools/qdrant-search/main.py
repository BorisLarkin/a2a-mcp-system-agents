import os
import json
import logging
import uuid
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Qdrant Search MCP Server", version="1.0.0")

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "knowledge_base")
VECTOR_SIZE = int(os.getenv("VECTOR_SIZE", "384"))

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[int] = 1

@app.on_event("startup")
async def init_collection():
    """Создаёт коллекцию, если её нет"""
    try:
        collections = client.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)
        if not exists:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
            )
            logger.info(f"Created collection '{COLLECTION_NAME}' with vector size {VECTOR_SIZE}")
        else:
            logger.info(f"Collection '{COLLECTION_NAME}' already exists")
    except Exception as e:
        logger.error(f"Failed to init collection: {e}")

@app.get("/health")
async def health():
    try:
        client.get_collections()
        return {"status": "healthy", "qdrant": f"{QDRANT_HOST}:{QDRANT_PORT}"}
    except:
        return {"status": "unhealthy"}

@app.get("/.well-known/mcp.json")
async def mcp_discovery():
    return {
        "name": "qdrant-search",
        "version": "1.0.0",
        "tools": [
            {
                "name": "search",
                "description": "Поиск документов в векторной базе знаний",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "vector": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "Вектор запроса (384 измерения)"
                        },
                        "category": {
                            "type": "string",
                            "description": "Фильтр по категории (опционально)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Максимальное количество результатов (по умолчанию 5)"
                        },
                        "score_threshold": {
                            "type": "number",
                            "description": "Минимальный порог релевантности (0-1, по умолчанию 0.5)"
                        }
                    },
                    "required": ["vector"]
                }
            },
            {
                "name": "upsert",
                "description": "Добавление или обновление документов в базе знаний",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "documents": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "title": {"type": "string"},
                                    "content": {"type": "string"},
                                    "category": {"type": "string"},
                                    "source": {"type": "string"},
                                    "vector": {"type": "array", "items": {"type": "number"}}
                                },
                                "required": ["title", "content", "vector"]
                            }
                        }
                    },
                    "required": ["documents"]
                }
            },
            {
                "name": "delete",
                "description": "Удаление документа из базы знаний",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string"}
                    },
                    "required": ["document_id"]
                }
            }
        ]
    }

@app.post("/mcp")
async def mcp_handler(req: Request):
    body = await req.json()
    try:
        rpc_req = JsonRpcRequest(**body)
    except:
        return {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": None}
    
    if rpc_req.method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": rpc_req.id,
            "result": {
                "tools": [
                    {
                        "name": "search",
                        "description": "Поиск документов в векторной базе знаний",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "vector": {"type": "array", "items": {"type": "number"}},
                                "category": {"type": "string"},
                                "limit": {"type": "integer", "default": 5},
                                "score_threshold": {"type": "number", "default": 0.5}
                            },
                            "required": ["vector"]
                        }
                    },
                    {
                        "name": "upsert",
                        "description": "Добавление или обновление документов в базе знаний",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "documents": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "title": {"type": "string"},
                                            "content": {"type": "string"},
                                            "category": {"type": "string"},
                                            "source": {"type": "string"},
                                            "vector": {"type": "array", "items": {"type": "number"}}
                                        },
                                        "required": ["title", "content", "vector"]
                                    }
                                }
                            },
                            "required": ["documents"]
                        }
                    }
                ]
            }
        }
    
    elif rpc_req.method == "tools/call":
        params = rpc_req.params or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        try:
            if tool_name == "search":
                vector = arguments["vector"]
                category = arguments.get("category")
                limit = arguments.get("limit", 5)
                score_threshold = arguments.get("score_threshold", 0.5)
            
                # Строим фильтр по категории если указана
                query_filter = None
                if category:
                    query_filter = Filter(
                        must=[FieldCondition(key="category", match=MatchValue(value=category))]
                    )
            
                # Используем query_points (актуальный метод для qdrant-client ^1.7)
                results = client.query_points(
                    collection_name=COLLECTION_NAME,
                    query=vector,
                    limit=limit,
                    score_threshold=score_threshold,
                    query_filter=query_filter
                )
                
                documents = []
                for r in results.points:
                    documents.append({
                        "id": r.id,
                        "title": r.payload.get("title", ""),
                        "content": r.payload.get("content", ""),
                        "category": r.payload.get("category", "общее"),
                        "source": r.payload.get("source", "knowledge_base"),
                        "relevance": round(r.score, 4)
                    })
                
                return {"jsonrpc": "2.0", "id": rpc_req.id, "result": {"results": documents}}
            
            elif tool_name == "upsert":
                documents = arguments["documents"]
                points = []
                for doc in documents:
                    doc_id = doc.get("id", str(uuid.uuid4()))
                    points.append(PointStruct(
                        id=doc_id,
                        vector=doc["vector"],
                        payload={
                            "title": doc.get("title", ""),
                            "content": doc.get("content", ""),
                            "category": doc.get("category", "общее"),
                            "source": doc.get("source", "knowledge_base"),
                            "created_at": doc.get("created_at", "")
                        }
                    ))
                
                client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=points,
                    wait=True
                )
                
                return {"jsonrpc": "2.0", "id": rpc_req.id, "result": {"inserted": len(points)}}
            
            elif tool_name == "delete":
                doc_id = arguments["document_id"]
                client.delete(
                    collection_name=COLLECTION_NAME,
                    points_selector=[doc_id],
                    wait=True
                )
                return {"jsonrpc": "2.0", "id": rpc_req.id, "result": {"deleted": doc_id}}
            
            else:
                return {"jsonrpc": "2.0", "id": rpc_req.id, "error": {"code": -32601, "message": "Tool not found"}}
        
        except KeyError as e:
            return {"jsonrpc": "2.0", "id": rpc_req.id, "error": {"code": -32602, "message": f"Missing argument: {e}"}}
        except Exception as e:
            logger.error(f"Tool call error: {e}")
            return {"jsonrpc": "2.0", "id": rpc_req.id, "error": {"code": -32603, "message": str(e)}}
    
    return {"jsonrpc": "2.0", "id": rpc_req.id, "error": {"code": -32601, "message": "Method not found"}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)