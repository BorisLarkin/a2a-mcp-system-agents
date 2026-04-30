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

app = FastAPI(title="Classifier Agent", version="1.0.0")

# --- Pydantic Models ---

class ClassificationRequest(BaseModel):
    text: str
    categories: List[str] = ["техническая", "финансовая", "HR", "общая", "другое"]

class ClassificationResponse(BaseModel):
    category: str
    confidence: float
    entities: List[str]
    metadata: Dict[str, Any]

# --- A2A Protocol Models ---

class A2ATaskRequest(BaseModel):
    skill_id: str
    input: Dict[str, Any]

class A2ATaskResponse(BaseModel):
    task_id: Optional[str] = None
    status: str  # "completed" | "failed"
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# --- Core classification logic ---

def classify_text(text: str, categories: List[str] = None) -> dict:
    """
    Заглушка классификации. В будущем здесь будет вызов реальной модели
    или MCP-инструмента rubert-classifier.
    """
    if categories is None:
        categories = ["техническая", "финансовая", "HR", "общая", "другое"]
    
    # Имитация работы модели
    result = {
        "category": "техническая",
        "confidence": 0.92,
        "entities": ["система", "ошибка", "работа"],
        "metadata": {
            "model": "test",
            "processing_time": 0.15
        }
    }
    return result

# --- REST Endpoints ---

@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "classifier"}

@app.get("/.well-known/agent.json")
async def discovery():
    """A2A Discovery endpoint"""
    return {
        "name": "classifier-v1",
        "type": "classifier",
        "description": "Text classification and entity extraction agent",
        "version": "1.0.0",
        "endpoint": "http://classifier:9001",
        "capabilities": ["classification"],
        "skills": [
            {
                "id": "classify",
                "description": "Classify user request into problem category with confidence score",
                "input_schema": {
                    "text": "string (user message)",
                    "categories": "array of strings (optional, default: тех, фин, HR, общая, другое)"
                },
                "output_schema": {
                    "category": "string (predicted class)",
                    "confidence": "float (0-1)",
                    "entities": "array of strings",
                    "metadata": "object"
                }
            },
            {
                "id": "extract_entities",
                "description": "Extract named entities from text",
                "input_schema": {
                    "text": "string"
                },
                "output_schema": {
                    "entities": "array of {text, type, confidence}"
                }
            }
        ],
        "supports": ["a2a/v1", "tasks/send"],
        "a2a_protocol": {
            "task_endpoint": "/tasks/send",
            "async_support": False
        }
    }

@app.post("/classify")
async def classify(request: ClassificationRequest):
    """Классификация текста (прямой вызов)"""
    try:
        logger.info(f"Classifying text: {request.text[:100]}...")
        result = classify_text(request.text, request.categories)
        return result
    except Exception as e:
        logger.error(f"Classification error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract-entities")
async def extract_entities(request: ClassificationRequest):
    """Извлечение сущностей (прямой вызов)"""
    return {
        "entities": [
            {"text": "система", "type": "system", "confidence": 0.95},
            {"text": "ошибка", "type": "problem", "confidence": 0.87}
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
        if request.skill_id == "classify":
            text = request.input.get("text", "")
            categories = request.input.get("categories", None)
            
            result = classify_text(text, categories)
            
            output = {
                "category": result["category"],
                "confidence": result["confidence"],
                "entities": result["entities"],
                "metadata": result["metadata"]
            }
            
            return A2ATaskResponse(
                task_id=str(uuid.uuid4()),
                status="completed",
                output=output
            )
        
        elif request.skill_id == "extract_entities":
            text = request.input.get("text", "")
            entities = [
                {"text": "система", "type": "system", "confidence": 0.95},
                {"text": "ошибка", "type": "problem", "confidence": 0.87}
            ]
            
            return A2ATaskResponse(
                task_id=str(uuid.uuid4()),
                status="completed",
                output={"entities": entities}
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