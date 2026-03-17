import os
import json
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Classifier Agent", version="1.0.0")

class ClassificationRequest(BaseModel):
    text: str
    categories: List[str] = ["техническая", "финансовая", "HR", "общая", "другое"]

class ClassificationResponse(BaseModel):
    category: str
    confidence: float
    entities: List[str]
    metadata: Dict[str, Any]

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
        "endpoint": "http://classifier-agent:8080",
        "capabilities": ["classification", "ner", "entity_extraction"],
        "llm_model": "llama3.2:1b",
        "supports": ["a2a/v1", "mcp/json-rpc"]
    }

@app.post("/classify")
async def classify(request: ClassificationRequest):
    """Классификация текста"""
    try:
        # Временная заглушка - в реальности будет вызов модели
        logger.info(f"Classifying text: {request.text[:100]}...")
        
        # Имитация работы модели
        response = {
            "category": "техническая",
            "confidence": 0.92,
            "entities": ["система", "ошибка", "работа"],
            "metadata": {
                "model": "test",
                "processing_time": 0.15
            }
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Classification error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract-entities")
async def extract_entities(request: ClassificationRequest):
    """Извлечение сущностей"""
    # Заглушка
    return {
        "entities": [
            {"text": "система", "type": "system", "confidence": 0.95},
            {"text": "ошибка", "type": "problem", "confidence": 0.87}
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)