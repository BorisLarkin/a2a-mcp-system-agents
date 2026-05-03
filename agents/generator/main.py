import os
import json
import logging
import asyncio
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import httpx
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем уровень логирования как строку
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
# Преобразуем строку в константу logging
level = getattr(logging, log_level, logging.INFO)

# Настройка логирования
logging.basicConfig(
    level=level,  # число (20 для INFO)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Generator Agent", version="1.0.0")

# Конфигурация из переменных окружения
MODEL_NAME = os.getenv('GENERATOR_MODEL', 'ilyagusev/saiga_llama3')
TEMPERATURE = float(os.getenv('GENERATOR_TEMPERATURE', '0.7'))
MAX_TOKENS = int(os.getenv('GENERATOR_MAX_TOKENS', '500'))
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://ollama:11434')
AGENT_NAME = os.getenv('AGENT_NAME', 'generator-v1')
AGENT_TYPE = os.getenv('AGENT_TYPE', 'generator')

class GenerationRequest(BaseModel):
    query: str
    category: str
    solutions: List[Dict[str, Any]]
    style: str = "friendly"
    context: str = ""
    language: str = "ru"

class GenerationResponse(BaseModel):
    response: str
    style: str
    metadata: Dict[str, Any]

class OllamaRequest(BaseModel):
    model: str
    prompt: str
    stream: bool = False
    options: Optional[Dict[str, Any]] = {
        "temperature": TEMPERATURE,
        "num_predict": MAX_TOKENS
    }

class OllamaResponse(BaseModel):
    response: str

class A2ATaskRequest(BaseModel):
    skill_id: str
    input: Dict[str, Any]

class A2ATaskResponse(BaseModel):
    task_id: Optional[str] = None
    status: str  # "completed" | "failed"
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent": AGENT_NAME,
        "type": AGENT_TYPE,
        "model": MODEL_NAME,
        "timestamp": asyncio.get_event_loop().time()
    }

@app.get("/.well-known/agent.json")
async def discovery():
    """A2A Discovery endpoint"""
    return {
        "name": AGENT_NAME,
        "type": AGENT_TYPE,
        "description": "Text generation and response formatting agent",
        "version": "1.0.0",
        "endpoint": f"http://{AGENT_TYPE}:9003",
        "capabilities": ["generation"],
        "skills": [
            {
                "id": "generate_response",
                "description": "Generate final answer based on classification and solutions",
                "input_schema": {
                    "query": "string (user text)",
                    "category": "string (problem category)",
                    "solutions": "array of {title, content, confidence}",
                    "style": "string (formal|friendly|technical|balanced)",
                    "context": "string (additional context)",
                    "language": "string (ru|en)"
                },
                "output_schema": {
                    "response": "string (generated text)",
                    "style": "string",
                    "metadata": "object"
                }
            },
            {
                "id": "format_response",
                "description": "Format and adjust tone of existing answer",
                "input_schema": {
                    "query": "string",
                    "solutions": "array",
                    "style": "string"
                },
                "output_schema": {
                    "formatted_response": "string",
                    "tone": "string"
                }
            }
        ],
        "llm_model": MODEL_NAME,
        "supports": ["a2a/v1", "tasks/send"],
        "a2a_protocol": {
            "task_endpoint": "/tasks/send",
            "status_endpoint": "/tasks/{task_id}/status",
            "async_support": False,
            "note": "Currently synchronous – tasks return completed immediately"
        },
        "configuration": {
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS
        }
    }

async def call_ollama(prompt: str) -> str:
    """Вызов Ollama для генерации текста"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            request = OllamaRequest(
                model=MODEL_NAME,
                prompt=prompt,
                options={
                    "temperature": TEMPERATURE,
                    "num_predict": MAX_TOKENS
                }
            )
            
            response = await client.post(
                f"http://{OLLAMA_HOST}/api/generate",
                json=request.model_dump()
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            else:
                logger.error(f"Ollama error: {response.status_code} - {response.text}")
                return ""
                
    except Exception as e:
        logger.error(f"Error calling Ollama: {str(e)}")
        return ""

def build_prompt(request: GenerationRequest) -> str:
    """Формирование промпта для LLM"""
    
    style_mapping = {
        "formal": "Формальный деловой стиль",
        "friendly": "Дружелюбный и поддерживающий тон",
        "technical": "Технический стиль с деталями",
        "balanced": "Сбалансированный профессиональный тон"
    }
    
    style_instruction = style_mapping.get(request.style, "Дружелюбный тон")
    
    # Формируем решения для контекста
    solutions_text = ""
    if request.solutions:
        solutions_text = "\nНайденные решения:\n"
        for i, sol in enumerate(request.solutions[:3], 1):  # Берем топ-3 решения
            title = sol.get('title', 'Решение')
            content = sol.get('content', '')
            confidence = sol.get('confidence', 1.0)
            solutions_text += f"{i}. {title} (уверенность: {confidence:.2f})\n   {content[:200]}...\n"
    
    system_prompt = f"""Ты — AI-ассистент технической поддержки.
    Стиль ответа: {style_instruction}
    Категория вопроса: {request.category}
    Контекст: {request.context}

    Сгенерируй ответ на русском языке. Ответ должен быть вежливым, полезным, не более 3-4 предложений."""

    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

    {system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>

    Запрос пользователя: {request.query}

    Найденные решения: {solutions_text}

    Ответ:<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

    return prompt

@app.post("/v1/generate")
async def generate_response(request: GenerationRequest):
    """Генерация ответа с использованием Ollama"""
    try:
        logger.info(f"Generating response for: {request.query[:50]}...")
        
        # Пробуем использовать Ollama
        prompt = build_prompt(request)
        response_text = await call_ollama(prompt)
        
        # Если Ollama не ответила, используем заглушку
        if not response_text:
            logger.warning("Ollama unavailable, using mock response")
            response_text = generate_mock_response(request)
        
        metadata = {
            "solutions_used": len(request.solutions),
            "category": request.category,
            "model": MODEL_NAME,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "ollama_used": bool(response_text and response_text != generate_mock_response(request))
        }
        
        return GenerationResponse(
            response=response_text,
            style=request.style,
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def generate_mock_response(request: GenerationRequest) -> str:
    """Заглушка для генерации ответа"""
    
    # Безопасное получение первого решения
    first_solution_title = "Проверьте оборудование"
    first_solution_content = "Проверьте соединение"
    if request.solutions:
        sol = request.solutions[0]
        first_solution_title = sol.get('title', 'Рекомендация')
        first_solution_content = sol.get('content', 'Проверьте соединение')[:100]
    
    mock_responses = {
        "technical": f"Техническое решение: {request.query}. "
                    f"Рекомендуем: {first_solution_title}.",
        
        "friendly": f"Здравствуйте! Похоже, у вас проблема: {request.query}. "
                   f"Попробуйте: {first_solution_content}. "
                   f"Обращайтесь, если нужна помощь!",
        
        "formal": f"Уважаемый пользователь, по вашему обращению '{request.query}' "
                 f"предлагаем следующее решение: {first_solution_title}.",
        
        "balanced": f"По вашему запросу '{request.query}'. "
                   f"Рекомендуем: {first_solution_content}."
    }
    
    return mock_responses.get(
        request.style, 
        f"По вопросу '{request.query}' - "
        f"{first_solution_content}"
    )

@app.post("/v1/format-response")
async def format_response(request: GenerationRequest):
    """Форматирование существующего ответа"""
    try:
        formatted = f"[{request.style.upper()}] {request.query}"
        
        if request.solutions:
            formatted += f"\n\nРешение: {request.solutions[0]['title']}"
        
        return {
            "formatted_response": formatted,
            "tone": request.style,
            "metadata": {
                "solutions_available": len(request.solutions),
                "format_version": "1.0"
            }
        }
        
    except Exception as e:
        logger.error(f"Formatting error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ A2A Protocol Endpoint ============

@app.post("/tasks/send", response_model=A2ATaskResponse)
async def tasks_send(request: A2ATaskRequest):
    """
    A2A endpoint: receive a task, execute skill, return result
    
    Synchronous implementation for now – returns completed result immediately.
    """
    logger.info(f"A2A Task received: skill={request.skill_id}, input_keys={list(request.input.keys())}")
    
    try:
        if request.skill_id == "generate_response":
            # Преобразуем input в GenerationRequest
            gen_req = GenerationRequest(**request.input)
            
            # Выполняем генерацию (та же логика, что в /v1/generate)
            prompt = build_prompt(gen_req)
            response_text = await call_ollama(prompt)
            
            if not response_text:
                logger.warning("Ollama unavailable, using mock response")
                response_text = generate_mock_response(gen_req)
            
            metadata = {
                "solutions_used": len(gen_req.solutions),
                "category": gen_req.category,
                "model": MODEL_NAME,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
                "ollama_used": bool(response_text and response_text != generate_mock_response(gen_req))
            }
            
            output = {
                "response": response_text,
                "style": gen_req.style,
                "metadata": metadata
            }
            
            return A2ATaskResponse(
                task_id=str(uuid.uuid4()),
                status="completed",
                output=output
            )
        
        elif request.skill_id == "format_response":
            # Форматирование ответа
            gen_req = GenerationRequest(**request.input)
            formatted = f"[{gen_req.style.upper()}] {gen_req.query}"
            if gen_req.solutions:
                formatted += f"\n\nРешение: {gen_req.solutions[0].get('title', '')}"
            
            output = {
                "formatted_response": formatted,
                "tone": gen_req.style,
                "metadata": {
                    "solutions_available": len(gen_req.solutions),
                    "format_version": "1.0"
                }
            }
            
            return A2ATaskResponse(
                task_id=str(uuid.uuid4()),
                status="completed",
                output=output
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

# ============ End A2A Endpoint ============

@app.on_event("startup")
async def startup_event():
    """Проверка подключения к Ollama при старте"""
    logger.info(f"Starting Generator Agent with model: {MODEL_NAME}")
    logger.info(f"Ollama host: {OLLAMA_HOST}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://{OLLAMA_HOST}/api/tags")
            if response.status_code == 200:
                models = response.json().get('models', [])
                logger.info(f"Connected to Ollama. Available models: {[m['name'] for m in models]}")
            else:
                logger.warning("Could not connect to Ollama")
    except Exception as e:
        logger.warning(f"Ollama not available: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('AGENT_PORT', 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)