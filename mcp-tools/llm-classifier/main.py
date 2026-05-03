import os
import json
import logging
import httpx
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="LLM Classifier MCP Server", version="1.0.0")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
MODEL_NAME = os.getenv("CLASSIFIER_MODEL", "ilyagusev/saiga_llama3")
DEFAULT_CATEGORIES = ["техническая", "биллинг", "жалоба", "общий_вопрос", "другое"]

class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[int] = 1

@app.get("/health")
async def health():
    return {"status": "healthy", "model": MODEL_NAME}

@app.get("/.well-known/mcp.json")
async def mcp_discovery():
    return {
        "name": "llm-classifier",
        "version": "1.0.0",
        "tools": [
            {
                "name": "classify",
                "description": "Классификация обращения техподдержки на русском языке через LLM",
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
    }

async def classify_with_llm(text: str, categories: list = None) -> dict:
    if categories is None:
        categories = DEFAULT_CATEGORIES
    cats_str = ", ".join(categories)
    
    system_prompt = f"""Ты — классификатор обращений в техподдержку. 
Определи категорию обращения. Ответь ТОЛЬКО валидным JSON с полями category и confidence.
Доступные категории: {cats_str}
Пример ответа: {{"category": "техническая", "confidence": 0.92}}"""
    
    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>

Обращение: "{text}"

Категория:<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"http://{OLLAMA_HOST}/api/generate",
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 100}
                }
            )
            if resp.status_code != 200:
                raise Exception(f"Ollama status {resp.status_code}")
            
            response_text = resp.json().get("response", "").strip()
            logger.info(f"LLM classification raw: {response_text}")
            
            # Парсим JSON (может быть в markdown-блоке)
            cleaned = response_text
            for marker in ["```json", "```"]:
                if marker in cleaned:
                    start = cleaned.find(marker) + len(marker)
                    end = cleaned.find("```", start)
                    cleaned = cleaned[start:end].strip() if end != -1 else cleaned[start:].strip()
                    break
            
            parsed = json.loads(cleaned)
            
            return {
                "category": parsed.get("category", categories[0]),
                "confidence": float(parsed.get("confidence", 0.7))
            }
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return {"category": categories[0] if categories else "другое", "confidence": 0.3}

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
                "tools": [{
                    "name": "classify",
                    "description": "Классификация текста через LLM",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "categories": {"type": "array"}
                        },
                        "required": ["text"]
                    }
                }]
            }
        }
    
    elif rpc_req.method == "tools/call":
        params = rpc_req.params or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name != "classify":
            return {"jsonrpc": "2.0", "id": rpc_req.id, "error": {"code": -32601, "message": "Tool not found"}}
        
        try:
            result = await classify_with_llm(arguments["text"], arguments.get("categories"))
            return {"jsonrpc": "2.0", "id": rpc_req.id, "result": result}
        except KeyError as e:
            return {"jsonrpc": "2.0", "id": rpc_req.id, "error": {"code": -32602, "message": f"Missing argument: {e}"}}
    
    return {"jsonrpc": "2.0", "id": rpc_req.id, "error": {"code": -32601, "message": "Method not found"}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)