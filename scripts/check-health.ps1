# check-health.ps1
$services = @{
    "Classifier" = "http://localhost:9001/health"
    "Researcher" = "http://localhost:9002/health"
    "Generator" = "http://localhost:9003/health"
    "RuBERT" = "http://localhost:9100/health"
    "Encoder" = "http://localhost:9102/health"
    "Redis" = "http://localhost:6379"  # Redis не имеет HTTP, проверим через docker
}

Write-Host "🔍 Проверка здоровья сервисов..." -ForegroundColor Cyan

foreach ($service in $services.Keys) {
    try {
        $response = Invoke-WebRequest -Uri $services[$service] -Method GET -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ $service : OK" -ForegroundColor Green
        } else {
            Write-Host "❌ $service : Статус $($response.StatusCode)" -ForegroundColor Red
        }
    } catch {
        Write-Host "❌ $service : Недоступен" -ForegroundColor Red
    }
}

# Проверка Redis через docker
$redisCheck = docker exec mcp-redis redis-cli ping 2>$null
if ($redisCheck -eq "PONG") {
    Write-Host "✅ Redis : OK" -ForegroundColor Green
} else {
    Write-Host "❌ Redis : Недоступен" -ForegroundColor Red
}