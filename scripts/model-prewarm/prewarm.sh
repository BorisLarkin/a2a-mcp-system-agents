#!/bin/sh

# Устанавливаем значения по умолчанию, если переменные не заданы
echo 'Getting environment variables...'

OLLAMA_MODEL=${OLLAMA_MODEL:-llama3.2}
OLLAMA_MODEL_TAG=${OLLAMA_MODEL_TAG:-${OLLAMA_MODEL}:latest}
OLLAMA_HOST=${OLLAMA_HOST:-ollama:11434}

echo 'Waiting for Ollama to be ready...'
sleep 30

# Функция для проверки доступности Ollama
check_ollama() {
    curl -s http://${OLLAMA_HOST}/api/tags > /dev/null
    return $?
}

# Ждем полной готовности Ollama
echo 'Checking Ollama connection with ${OLLAMA_HOST}...'
until check_ollama; do
    echo 'Ollama not ready yet, waiting...'
    sleep 5
done

echo 'Ollama is ready!'

# Проверяем наличие модели
echo "Checking if model ${OLLAMA_MODEL_TAG} exists..."
# Экранируем специальные символы для grep
MODEL_EXISTS=$(curl -s http://${OLLAMA_HOST}/api/tags | grep -c "\"name\":\"${OLLAMA_MODEL_TAG}\"")

if [ "$MODEL_EXISTS" -eq "0" ]; then
    echo "Model ${OLLAMA_MODEL_TAG} not found. Pulling model..."
    
    # Загружаем модель
    curl -X POST http://${OLLAMA_HOST}/api/pull \
        -H 'Content-Type: application/json' \
        -d "{\"name\": \"${OLLAMA_MODEL_TAG}\"}"
    
    # Проверяем успешность загрузки
    if [ $? -eq 0 ]; then
        echo "Model ${OLLAMA_MODEL_TAG} pulled successfully!"
    else
        echo "Failed to pull model ${OLLAMA_MODEL_TAG}!"
        exit 1
    fi
else
    echo "Model ${OLLAMA_MODEL_TAG} already exists!"
fi

# Пре-варминг модели
echo "Pre-warming ${OLLAMA_MODEL} model..."
curl -X POST http://${OLLAMA_HOST}/api/generate \
    -H 'Content-Type: application/json' \
    -d "{\"model\": \"${OLLAMA_MODEL}\", \"prompt\": \"Hello\", \"keep_alive\": -1}"

if [ $? -eq 0 ]; then
    echo 'Model pre-warmed successfully!'
else
    echo 'Failed to pre-warm model!'
    exit 1
fi

# Keep container running
tail -f /dev/null