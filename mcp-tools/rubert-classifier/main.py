import os
import json
import logging
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RuBERT Classifier MCP Server", version="1.0.0")

# --- Pydantic models ---
class ClassificationRequest(BaseModel):
    text: str
    categories: Optional[List[str]] = None

class ClassificationResponse(BaseModel):
    predicted_class: str
    confidence: float
    scores: Dict[str, float]
    metadata: Dict[str, Any]

class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[int] = 1

class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

# --- Global model objects ---
model = None
tokenizer = None
DEFAULT_CATEGORIES = ["техническая", "биллинг", "жалоба", "общий вопрос", "другое"]

@app.on_event("startup")
async def load_model():
    global model, tokenizer
    model_name = os.getenv("MODEL_NAME", "cointegrated/rubert-tiny2")
    logger.info(f"Loading model: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=len(DEFAULT_CATEGORIES)
    )
    model.eval()
    logger.info("Model loaded successfully")

@app.get("/health")
async def health():
    return {"status": "healthy" if model else "loading"}

# --- MCP discovery ---
@app.get("/.well-known/mcp.json")
async def mcp_discovery():
    return {
        "name": "rubert-classifier",
        "version": "1.0.0",
        "tools": [
            {
                "name": "classify",
                "description": "Классификация текста обращения на русском языке",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Текст для классификации"},
                        "categories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Пользовательские категории (опционально)"
                        }
                    },
                    "required": ["text"]
                }
            }
        ]
    }

# --- Direct REST endpoint (legacy) ---
@app.post("/v1/classify", response_model=ClassificationResponse)
async def classify(request: ClassificationRequest):
    if not model or not tokenizer:
        raise HTTPException(status_code=503, detail="Model not loaded")
    inputs = tokenizer(request.text, truncation=True, padding=True, max_length=512, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
        predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
    scores = predictions[0].tolist()
    categories = request.categories or DEFAULT_CATEGORIES
    predicted_idx = np.argmax(scores)
    return ClassificationResponse(
        predicted_class=categories[predicted_idx],
        confidence=float(scores[predicted_idx]),
        scores={cat: float(s) for cat, s in zip(categories, scores)},
        metadata={"model": os.getenv("MODEL_NAME")}
    )

# --- Core classification logic (used by MCP) ---
def classify_text(text: str, categories: Optional[List[str]] = None) -> dict:
    if not model or not tokenizer:
        raise RuntimeError("Model not loaded")
    inputs = tokenizer(text, truncation=True, padding=True, max_length=512, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
        predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
    scores = predictions[0].tolist()
    cats = categories or DEFAULT_CATEGORIES
    idx = np.argmax(scores)
    return {
        "predicted_class": cats[idx],
        "confidence": float(scores[idx]),
        "scores": {cat: float(s) for cat, s in zip(cats, scores)}
    }

# --- MCP JSON-RPC endpoint ---
@app.post("/mcp")
async def mcp_handler(req: Request):
    body = await req.json()
    try:
        rpc_req = JsonRpcRequest(**body)
    except Exception as e:
        return {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": None}
    
    if rpc_req.method == "tools/list":
        tools = [
            {
                "name": "classify",
                "description": "Классификация текста на русском языке",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "categories": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["text"]
                }
            }
        ]
        return {"jsonrpc": "2.0", "id": rpc_req.id, "result": {"tools": tools}}
    
    elif rpc_req.method == "tools/call":
        params = rpc_req.params or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if tool_name != "classify":
            return {"jsonrpc": "2.0", "id": rpc_req.id, "error": {"code": -32601, "message": "Tool not found"}}
        try:
            text = arguments["text"]
            categories = arguments.get("categories")
            result = classify_text(text, categories)
            return {"jsonrpc": "2.0", "id": rpc_req.id, "result": result}
        except KeyError as e:
            return {"jsonrpc": "2.0", "id": rpc_req.id, "error": {"code": -32602, "message": f"Missing required argument: {e}"}}
        except Exception as e:
            logger.error(f"Tool call error: {e}")
            return {"jsonrpc": "2.0", "id": rpc_req.id, "error": {"code": -32603, "message": str(e)}}
    
    else:
        return {"jsonrpc": "2.0", "id": rpc_req.id, "error": {"code": -32601, "message": "Method not found"}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)