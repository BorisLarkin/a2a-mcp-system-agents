import os
import json
import logging
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RuBERT Classifier", version="1.0.0")

class ClassificationRequest(BaseModel):
    text: str
    categories: List[str] = None

class ClassificationResponse(BaseModel):
    predicted_class: str
    confidence: float
    scores: Dict[str, float]
    metadata: Dict[str, Any]

# Загружаем модель при старте
model = None
tokenizer = None

@app.on_event("startup")
async def load_model():
    global model, tokenizer
    try:
        model_name = os.getenv("MODEL_NAME", "cointegrated/rubert-tiny2")
        logger.info(f"Loading model: {model_name}")
        
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=5
        )
        model.eval()
        
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {str(e)}")
        raise

@app.get("/health")
async def health():
    return {
        "status": "healthy" if model is not None else "loading",
        "model": os.getenv("MODEL_NAME", "rubert-tiny2"),
        "capabilities": ["text_classification", "sentiment_analysis"]
    }

@app.post("/v1/classify")
async def classify(request: ClassificationRequest):
    """Классификация текста"""
    try:
        if model is None or tokenizer is None:
            raise HTTPException(status_code=503, detail="Model not loaded")
        
        # Токенизация
        inputs = tokenizer(
            request.text,
            truncation=True,
            padding=True,
            max_length=512,
            return_tensors="pt"
        )
        
        # Предсказание
        with torch.no_grad():
            outputs = model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
        
        scores = predictions[0].tolist()
        
        # Категории по умолчанию
        categories = request.categories or [
            "техническая", 
            "финансовая", 
            "HR", 
            "общая", 
            "другое"
        ]
        
        # Находим лучший результат
        predicted_idx = np.argmax(scores)
        predicted_class = categories[predicted_idx]
        confidence = float(scores[predicted_idx])
        
        # Формируем scores dict
        scores_dict = {
            categories[i]: float(score) 
            for i, score in enumerate(scores[:len(categories)])
        }
        
        return ClassificationResponse(
            predicted_class=predicted_class,
            confidence=confidence,
            scores=scores_dict,
            metadata={
                "model": os.getenv("MODEL_NAME"),
                "processing_time": "test"
            }
        )
        
    except Exception as e:
        logger.error(f"Classification error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/capabilities")
async def capabilities():
    """Возвращает возможности инструмента"""
    return {
        "name": "rubert-classifier",
        "version": "1.0.0",
        "supports": ["classification"],
        "model": os.getenv("MODEL_NAME"),
        "max_text_length": 512
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)