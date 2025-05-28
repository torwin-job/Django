# Payments System — Django Interview

## Описание
Проект представляет собой backend-сервис для обработки webhook-ов от банка. Сервис принимает платежи, начисляет баланс организациям по ИНН и предоставляет API для получения текущего баланса.

## Технологии
- Python 3.9
- Django 4.2.17
- MySQL (в продакшене) / SQLite (для разработки)

## API Endpoints

### 1. Вебхук от банка (POST)
**URL:** `/api/webhook/bank/`  
**Метод:** POST  
**Content-Type:** application/json  
**Тело запроса:**
```json
{
  "operation_id": "ccf0a86d-041b-4991-bcf7-e2352f7b8a4a",
  "amount": 145000,
  "payer_inn": "1234567890",
  "document_number": "PAY-328",
  "document_date": "2024-04-27T21:00:00Z"
}
```
**Ответ:**
- 200 OK: `{"status": "success"}` или `{"status": "already processed"}`
- 400 Bad Request: `{"error": "..."}`

### 2. Получение баланса организации (GET)
**URL:** `/api/organizations/<inn>/balance/`  
**Метод:** GET  
**Ответ:**
- 200 OK: `{"inn": "1234567890", "balance": 145000}`
- 404 Not Found: `{"error": "Organization not found"}`

## Примеры для Postman

### 1. Вебхук от банка
- **Метод:** POST
- **URL:** `http://127.0.0.1:8000/api/webhook/bank/`
- **Headers:** `Content-Type: application/json`
- **Body (raw JSON):**
```json
{
  "operation_id": "ccf0a86d-041b-4991-bcf7-e2352f7b8a4a",
  "amount": 145000,
  "payer_inn": "1234567890",
  "document_number": "PAY-328",
  "document_date": "2024-04-27T21:00:00Z"
}
```

### 2. Получение баланса
- **Метод:** GET
- **URL:** `http://127.0.0.1:8000/api/organizations/1234567890/balance/`

## Структура проекта
```
payments/
    admin.py         # регистрация моделей в админке
    models.py        # модели
    services/        # слой сервисов
        services.py  # бизнес-логика
    views.py         # вьюхи
    urls.py          # маршруты
    ...
```

## Дополнительно
- **Админка:** Доступна по адресу `http://127.0.0.1:8000/admin/`
- **Логирование:** Изменения баланса логируются в консоль и в таблицу `BalanceLog` 