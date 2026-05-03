import os
import logging
import numpy as np
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sentence Encoder MCP Server", version="1.0.0")

class EncodeRequest(BaseModel):
    texts: List[str]
    normalize: bool = True

class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[int] = 1

model = None

@app.on_event("startup")
async def load_model():
    global model
    model_name = os.getenv("MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    logger.info(f"Loading encoder model: {model_name}")
    model = SentenceTransformer(model_name)
    logger.info(f"Model loaded, dimension: {model.get_sentence_embedding_dimension()}")

@app.get("/health")
async def health():
    return {"status": "healthy" if model else "loading"}

@app.get("/.well-known/mcp.json")
async def mcp_discovery():
    return {
        "name": "sentence-encoder",
        "version": "1.0.0",
        "tools": [
            {
                "name": "embed",
                "description": "Преобразование текста в векторное представление",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "texts": {"type": "array", "items": {"type": "string"}},
                        "normalize": {"type": "boolean", "default": True}
                    },
                    "required": ["texts"]
                }
            }
        ]
    }

@app.post("/embed")
async def encode(request: EncodeRequest):
    if not model:
        raise HTTPException(status_code=503, detail="Model not loaded")
    embeddings = model.encode(request.texts, normalize_embeddings=request.normalize, show_progress_bar=False)
    return {"embeddings": embeddings.tolist(), "dimensions": model.get_sentence_embedding_dimension()}

@app.post("/mcp")
async def mcp_handler(req: Request):
    body = await req.json()
    try:
        rpc_req = JsonRpcRequest(**body)
    except:
        return {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": None}
    
    if rpc_req.method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": rpc_req.id,
            "result": {
                "tools": [
                    {
                        "name": "embed",
                        "description": "Векторизация текстов",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "texts": {"type": "array", "items": {"type": "string"}},
                                "normalize": {"type": "boolean"}
                            },
                            "required": ["texts"]
                        }
                    }
                ]
            }
        }
    elif rpc_req.method == "tools/call":
        params = rpc_req.params or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if tool_name != "embed":
            return {"jsonrpc": "2.0", "id": rpc_req.id, "error": {"code": -32601, "message": "Tool not found"}}
        try:
            texts = arguments["texts"]
            normalize = arguments.get("normalize", True)
            embeddings = model.encode(texts, normalize_embeddings=normalize, show_progress_bar=False)
            return {"jsonrpc": "2.0", "id": rpc_req.id, "result": {"embeddings": embeddings.tolist(), "dimensions": model.get_sentence_embedding_dimension()}}
        except KeyError as e:
            return {"jsonrpc": "2.0", "id": rpc_req.id, "error": {"code": -32602, "message": f"Missing argument: {e}"}}
    else:
        return {"jsonrpc": "2.0", "id": rpc_req.id, "error": {"code": -32601, "message": "Method not found"}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)