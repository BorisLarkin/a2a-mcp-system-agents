# Билдер для зависимостей
FROM python:3.11-slim as builder

WORKDIR /app

# Аргументы сборки
ARG MODEL_NAME=ilyagusev/saiga_llama3

# Системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements отдельно для кэширования
COPY requirements.txt .

# Создаем кэш pip
RUN pip install --user --no-cache-dir --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# Основной образ
FROM python:3.11-slim

WORKDIR /app

# Копируем установленные пакеты
COPY --from=builder /root/.local /root/.local

# Добавляем в PATH
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Копируем код
COPY . .

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Порт
EXPOSE 8080

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Запуск
CMD ["python", "main.py"]