# run-ai.ps1
Write-Host "🚀 Запуск MCP AI системы" -ForegroundColor Green

# Загружаем переменные окружения
if (Test-Path .env.ai) {
    Write-Host "✅ Загружен .env.ai" -ForegroundColor Green
} else {
    Write-Host "❌ Файл .env.ai не найден!" -ForegroundColor Red
    exit 1
}

# Останавливаем старые контейнеры
Write-Host "🛑 Останавливаем старые контейнеры..." -ForegroundColor Yellow
docker-compose -f docker/docker-compose.ai.yml down

# Очищаем кэш (опционально)
#docker system prune -f

# Собираем и запускаем
Write-Host "🏗️  Сборка и запуск контейнеров..." -ForegroundColor Yellow
docker-compose -f docker/docker-compose.ai.yml up --build -d

# Проверяем статус
Write-Host "📊 Статус контейнеров:" -ForegroundColor Cyan
docker-compose -f docker/docker-compose.ai.yml ps

# Показываем логи
Write-Host "📝 Логи генератора:" -ForegroundColor Cyan
docker logs mcp-generator --tail 20

Write-Host "✅ Система запущена!" -ForegroundColor Green
Write-Host "📌 Generator: http://localhost:9003"
Write-Host "📌 Classifier: http://localhost:9001"
Write-Host "📌 Researcher: http://localhost:9002"
Write-Host "📌 RuBERT: http://localhost:9100"
Write-Host "📌 Encoder: http://localhost:9102"