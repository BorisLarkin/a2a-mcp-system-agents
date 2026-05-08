"""
Скрипт для наполнения Qdrant тестовыми документами.
Запускать после старта всех контейнеров:
  docker exec -it mcp-researcher python /app/seed_qdrant.py
или
  python scripts/seed_qdrant.py
"""
import os
import sys
import httpx
import asyncio
import uuid

QDRANT_MCP_URL = os.getenv("QDRANT_MCP_URL", "http://mcp-qdrant-search:8080/mcp")
ENCODER_MCP_URL = os.getenv("ENCODER_MCP_URL", "http://mcp-encoder:8080/mcp")

FAQ_DOCUMENTS = [
    # Технические проблемы
    {
        "title": "Не работает интернет",
        "content": "Проверьте подключение кабелей к роутеру. Перезагрузите роутер, выключив его на 30 секунд. Проверьте индикаторы на устройстве.",
        "category": "техническая"
    },
    {
        "title": "Медленный интернет",
        "content": "Проверьте скорость через Speedtest. Отключите другие устройства от сети. Перезагрузите роутер. Если проблема сохраняется, обратитесь к провайдеру.",
        "category": "техническая"
    },
    {
        "title": "Ошибка 500 на сайте",
        "content": "Очистите кэш браузера и cookies. Попробуйте открыть сайт в режиме инкогнито. Обновите браузер до последней версии.",
        "category": "техническая"
    },
    {
        "title": "Не включается устройство",
        "content": "Проверьте подключение к электросети. Убедитесь, что кабель питания не повреждён. Попробуйте другую розетку. Если устройство не реагирует, обратитесь в сервисный центр.",
        "category": "техническая"
    },
    {
        "title": "Проблемы с Wi-Fi подключением",
        "content": "Проверьте, включён ли Wi-Fi на устройстве. Забудьте сеть и подключитесь заново, введя пароль. Перезагрузите роутер. Проверьте настройки безопасности сети.",
        "category": "техническая"
    },
    # Биллинг и платежи
    {
        "title": "Не прошёл платёж",
        "content": "Проверьте баланс карты. Убедитесь, что карта не заблокирована. Попробуйте другой способ оплаты. Обратитесь в банк, выпустивший карту.",
        "category": "биллинг"
    },
    {
        "title": "Двойное списание средств",
        "content": "Проверьте историю платежей в личном кабинете. Сохраните чеки. Напишите в поддержку, приложив скриншоты обеих транзакций. Возврат производится в течение 5 рабочих дней.",
        "category": "биллинг"
    },
    {
        "title": "Проверить баланс лицевого счёта",
        "content": "Баланс можно проверить в личном кабинете на сайте, в мобильном приложении или отправив USSD-запрос *100# с номера телефона.",
        "category": "биллинг"
    },
    {
        "title": "Смена тарифного плана",
        "content": "Зайдите в личный кабинет, раздел «Тарифы». Выберите новый тариф и нажмите «Подключить». Новый тариф вступит в силу с начала следующего расчётного периода.",
        "category": "биллинг"
    },
    # Жалобы
    {
        "title": "Недовольство качеством обслуживания",
        "content": "Примите извинения за доставленные неудобства. Опишите ситуацию подробно: дата, время, с кем общались. Мы проведём проверку и свяжемся с вами в течение 24 часов.",
        "category": "жалоба"
    },
    {
        "title": "Задержка выполнения заявки",
        "content": "Проверьте статус заявки в личном кабинете. Среднее время выполнения — 3 рабочих дня. Если срок прошёл, напишите в поддержку, указав номер заявки.",
        "category": "жалоба"
    },
    # Общие вопросы
    {
        "title": "Как зарегистрироваться",
        "content": "Нажмите кнопку «Регистрация» на главной странице. Заполните поля: email, пароль, имя. Подтвердите email по ссылке из письма. После этого можете войти в личный кабинет.",
        "category": "общий_вопрос"
    },
    {
        "title": "Как восстановить пароль",
        "content": "Нажмите «Забыли пароль?» на странице входа. Введите email, указанный при регистрации. Перейдите по ссылке из письма и задайте новый пароль.",
        "category": "общий_вопрос"
    },
    {
        "title": "График работы поддержки",
        "content": "Техническая поддержка работает ежедневно с 8:00 до 22:00 по московскому времени. В праздничные дни — с 10:00 до 18:00. Экстренные заявки принимаются круглосуточно.",
        "category": "общий_вопрос"
    },
    {
        "title": "Установка мобильного приложения",
        "content": "Скачайте приложение из App Store (iOS) или Google Play (Android). Введите номер телефона, подтвердите вход по SMS. Предоставьте необходимые разрешения.",
        "category": "общий_вопрос"
    },
    # Другое
    {
        "title": "Проблемы после грозы",
        "content": "После грозы часто сгорает сетевое оборудование. Отключите все устройства от сети. Проверьте целостность кабелей. Если есть запах гари, не включайте устройства, вызовите специалиста.",
        "category": "техническая"
    },
    {
        "title": "Вирус или вредоносное ПО",
        "content": "Запустите полное сканирование антивирусом. Удалите подозрительные программы. Обновите антивирусные базы. Если проблема сохраняется, обратитесь в техподдержку.",
        "category": "техническая"
    },
    {
        "title": "Блокировка аккаунта",
        "content": "Аккаунт может быть заблокирован из-за подозрительной активности. Напишите в поддержку с почты, привязанной к аккаунту. Приложите фото документа для верификации.",
        "category": "общий_вопрос"
    },
]


async def get_embedding(text: str) -> list:
    """Получает эмбеддинг текста через MCP sentence-encoder"""
    rpc_request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "embed",
            "arguments": {"texts": [text]}
        },
        "id": 1
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(ENCODER_MCP_URL, json=rpc_request)
        resp.raise_for_status()
        result = resp.json()
        if "error" in result:
            raise Exception(result["error"]["message"])
        embeddings = result["result"]["embeddings"]
        return embeddings[0] if embeddings else []


async def upsert_document(doc_id: str, title: str, content: str, category: str, vector: list):
    """Добавляет документ в Qdrant через MCP"""
    rpc_request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "upsert",
            "arguments": {
                "documents": [{
                    "id": doc_id,
                    "title": title,
                    "content": content,
                    "category": category,
                    "source": "seed_script",
                    "vector": vector
                }]
            }
        },
        "id": 1
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(QDRANT_MCP_URL, json=rpc_request)
        resp.raise_for_status()
        result = resp.json()
        if "error" in result:
            raise Exception(result["error"]["message"])
        return result["result"]


async def main():
    print(f"Seeding {len(FAQ_DOCUMENTS)} documents to Qdrant...")
    print(f"Encoder: {ENCODER_MCP_URL}")
    print(f"Qdrant: {QDRANT_MCP_URL}")
    
    for i, doc in enumerate(FAQ_DOCUMENTS):
        try:
            # Получаем эмбеддинг
            vector = await get_embedding(doc["content"])
            if not vector:
                print(f"[{i+1}/{len(FAQ_DOCUMENTS)}] ❌ Empty vector for: {doc['title']}")
                continue
            
            # Сохраняем в Qdrant
            doc_id = str(uuid.uuid4())
            await upsert_document(
                doc_id=doc_id,
                title=doc["title"],
                content=doc["content"],
                category=doc["category"],
                vector=vector
            )
            print(f"[{i+1}/{len(FAQ_DOCUMENTS)}] ✅ {doc['title']} ({doc['category']})")
        
        except Exception as e:
            print(f"[{i+1}/{len(FAQ_DOCUMENTS)}] ❌ Failed: {doc['title']} — {e}")
    
    print("Seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())