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

app = FastAPI(title="Classifier Agent", version="1.0.0")

MCP_CLASSIFIER_URL = os.getenv("MCP_CLASSIFIER_URL", "http://llm-classifier:8080/mcp")

# --- A2A Models ---
class A2ATaskRequest(BaseModel):
    skill_id: str
    input: Dict[str, Any]

class A2ATaskResponse(BaseModel):
    task_id: Optional[str] = None
    status: str
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# --- Core: вызов MCP-инструмента ---
async def classify_via_mcp(text: str, categories: List[str] = None) -> dict:
    rpc_request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "classify",
            "arguments": {"text": text}
        },
        "id": 1
    }
    if categories:
        rpc_request["params"]["arguments"]["categories"] = categories
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(MCP_CLASSIFIER_URL, json=rpc_request)
        resp.raise_for_status()
        result = resp.json()
        if "error" in result:
            raise Exception(result["error"]["message"])
        return result["result"]

# --- REST Endpoints ---
@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "classifier"}

@app.get("/.well-known/agent.json")
async def discovery():
    return {
        "name": "classifier-v1",
        "type": "classifier",
        "description": "Text classification agent (uses LLM via MCP)",
        "version": "1.0.0",
        "endpoint": "http://classifier:9001",
        "capabilities": ["classification"],
        "skills": [
            {
                "id": "classify",
                "description": "Classify user request into problem category with confidence score",
                "input_schema": {"text": "string"},
                "output_schema": {"category": "string", "confidence": "float"}
            }
        ],
        "supports": ["a2a/v1", "tasks/send"]
    }

# --- A2A Endpoint ---
@app.post("/tasks/send", response_model=A2ATaskResponse)
async def tasks_send(request: A2ATaskRequest):
    logger.info(f"A2A Task: skill={request.skill_id}")
    
    try:
        if request.skill_id == "classify":
            text = request.input.get("text", "")
            categories = request.input.get("categories")
            
            result = await classify_via_mcp(text, categories)
            
            return A2ATaskResponse(
                task_id=str(uuid.uuid4()),
                status="completed",
                output={
                    "category": result["category"],
                    "confidence": result["confidence"],
                    "predicted_class": result["category"],
                    "entities": [],
                    "metadata": {"source": "llm-classifier"}
                }
            )
        else:
            return A2ATaskResponse(
                task_id=str(uuid.uuid4()),
                status="failed",
                error=f"Unknown skill: {request.skill_id}"
            )
    except Exception as e:
        logger.error(f"A2A Task failed: {e}")
        return A2ATaskResponse(
            task_id=str(uuid.uuid4()),
            status="failed",
            error=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)