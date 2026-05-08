# Универсальный оптимизированный Dockerfile для всех Python сервисов
FROM python:3.11-slim as builder

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements отдельно для кэширования
COPY requirements.txt .

# Создаем кэш pip
RUN pip install --user --no-cache-dir --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# Финальный образ
FROM python:3.11-slim

WORKDIR /app

# Копируем установленные пакеты из builder
COPY --from=builder /root/.local /root/.local

# Добавляем .local/bin в PATH
ENV PATH=/root/.local/bin:$PATH

# Копируем код
COPY . .

EXPOSE 8080

CMD ["python", "main.py"]