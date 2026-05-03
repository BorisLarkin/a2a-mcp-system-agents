# A2A/MCP System Agents

Набор специализированных AI-агентов для интеллектуальной системы автоматизации обработки обращений. Каждый агент реализует определённую capability и взаимодействует с оркестратором по протоколу A2A.

## 📋 Состав репозитория

```
agents/
├── agents/
│ ├── classifier/ # Агент-классификатор (Python)
│ ├── encoder/ # Агент-энкодер (Python)
│ ├── generator/ # Агент-генератор (Python)
│ └── researcher/ # Агент-исследователь (RAG)
├── docker/
│ ├── classifier.Dockerfile
│ ├── encoder.Dockerfile
│ ├── generator.Dockerfile
│ └── researcher.Dockerfile
├── mcp-tools/
│ ├── rubert-classifier/ # MCP инструмент для классификации
│ ├── sentence-encoder/ # MCP инструмент для эмбеддингов
│ └── searxng/ # MCP инструмент для поиска
├── scripts/
│ └── run-ai.ps1 # PowerShell скрипт для запуска
└── README.md
```

## 🤖 Доступные агенты

| Агент | Порт | Capability | Описание |
|-------|------|------------|----------|
| **Classifier** | 9001 | `classification` | Классификация обращений и извлечение сущностей |
| **Encoder** | 9102 | `embedding` | Создание эмбеддингов для RAG поиска |
| **Generator** | 9003 | `generation` | Генерация ответов через LLM |
| **Researcher** | 9004 | `search` | Поиск решений в базе знаний |

## 🏗️ Архитектура агентов

Каждый агент реализует:
- **A2A протокол** — эндпоинты `/.well-known/agent.json`, `/tasks`
- **MCP клиент** — для вызова инструментов
- **Health checks** — для мониторинга доступности

## 🚀 Быстрый старт

### Предварительные требования
- Python 3.10+
- Docker
- Git
- NVIDIA GPU (для генератора, опционально)

### Установка и запуск

```bash
# Клонирование репозитория
git clone https://github.com/your-org/a2a-mcp-system-agents.git
cd a2a-mcp-system-agents

# Запуск всех агентов через PowerShell
.\scripts\run-ai.ps1 -All

# Или запуск конкретного агента
.\scripts\run-ai.ps1 -Agent generator
```

### Запуск через Docker

```bash
# Сборка образов
docker build -f docker/classifier.Dockerfile -t classifier-agent .
docker build -f docker/generator.Dockerfile -t generator-agent .

# Запуск контейнеров
docker run -d -p 9001:8080 --name classifier classifier-agent
docker run -d -p 9003:8080 --name generator generator-agent
```

## 🔧 Конфигурация агентов

Каждый агент настраивается через переменные окружения:

### Classifier Agent

```env 
MODEL_NAME=cointegrated/rubert-tiny2
DEVICE=cpu
PORT=9001
```

### Generator Agent

```env 
GENERATOR_MODEL=saiga_llama3
GENERATOR_TEMPERATURE=0.7
GENERATOR_MAX_TOKENS=500
OLLAMA_HOST=http://ollama:11434
PORT=9003
AGENT_NAME=llm-generator
```

### Encoder Agent

```env 
MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
PORT=9102
```

## 📡 A2A Эндпоинты

Каждый агент представляет:

### `GET /.well-known/agent.json`

Метаданные и capabilities агента:

```json
{
  "name": "llm-generator",
  "capabilities": ["generation"],
  "skills": [
    {
      "id": "generate_response",
      "input_schema": {},
      "output_schema": {}
    }
  ]
}
```

### `POST /tasks`

Создание новой задачи:

```json
{
  "input": {
    "query": "У меня не работает интернет",
    "category": "техническая",
    "solutions": []
  }
}
```

### `GET /tasks/{task_id}`

Получение статуса и результата.

## 🛠️ MCP Инструменты

### rubert-classifier (порт 9100)
Эндпоинт: /classify

Модель: RuBERT-tiny2

Возвращает: категорию, confidence, сущности

### sentence-encoder (порт 9102)
Эндпоинт: /embed

Модель: sentence-transformers

Возвращает: 384-мерные эмбеддинги

### searxng (порт 8080)
Поиск в интернете

Фильтрация по языку

Ранжирование результатов

## 📊 Мониторинг

Каждый агент предоставляет:

- Health check — /health

- Метрики — /metrics (если реализовано)

- Логи — в stdout в JSON формате

## 🧪 Тестирование

```bash
# Проверка классификатора
curl -X POST http://localhost:9001/classify \
  -H "Content-Type: application/json" \
  -d '{"text": "У меня не работает интернет"}'

# Проверка генератора
curl -X POST http://localhost:9003/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "У меня не работает интернет",
    "category": "техническая",
    "solutions": []
  }'
```

## 📄 Лицензия

Boris Larkin 2026

## 📞 Контакты

По вопросам: borislarkin18@mail.ru
