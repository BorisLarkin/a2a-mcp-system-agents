import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from sentence_transformers import SentenceTransformer
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sentence Encoder", version="1.0.0")

class EncodeRequest(BaseModel):
    texts: List[str]
    normalize: bool = True

class EncodeResponse(BaseModel):
    embeddings: List[List[float]]
    model: str
    dimensions: int

# Загружаем модель
model = None

@app.on_event("startup")
async def load_model():
    global model
    try:
        model_name = os.getenv("MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        logger.info(f"Loading sentence encoder: {model_name}")
        
        model = SentenceTransformer(model_name)
        
        logger.info(f"Model loaded. Dimensions: {model.get_sentence_embedding_dimension()}")
    except Exception as e:
        logger.error(f"Failed to load model: {str(e)}")
        raise

@app.get("/health")
async def health():
    return {
        "status": "healthy" if model is not None else "loading",
        "model": os.getenv("MODEL_NAME", "multilingual-MiniLM"),
        "dimensions": model.get_sentence_embedding_dimension() if model else 0
    }

@app.post("/embed")
async def encode(request: EncodeRequest):
    """Векторизация текста"""
    try:
        if model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")
        
        # Кодируем тексты
        embeddings = model.encode(
            request.texts,
            normalize_embeddings=request.normalize,
            show_progress_bar=False
        )
        
        # Конвертируем numpy в список
        embeddings_list = embeddings.tolist() if hasattr(embeddings, 'tolist') else embeddings
        
        return EncodeResponse(
            embeddings=embeddings_list,
            model=os.getenv("MODEL_NAME"),
            dimensions=model.get_sentence_embedding_dimension()
        )
        
    except Exception as e:
        logger.error(f"Encoding error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/info")
async def model_info():
    """Информация о модели"""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    return {
        "model_name": os.getenv("MODEL_NAME"),
        "dimensions": model.get_sentence_embedding_dimension(),
        "max_seq_length": model.max_seq_length,
        "languages": ["multilingual", "russian", "english"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)