# ⚡ Quick Configuration Guide

## 🎯 Быстрая настройка для разработки (5 минут)

### Шаг 1: Backend (.env)

```bash
cp .env.example .env
```

Отредактируйте **только эти 3 строки** в `.env`:

```env
GROQ_API_KEY=gsk_your_actual_key_here  # ← Вставьте ваш ключ Groq
LLM_MODEL=llama-3.3-70b-versatile
BACKEND_URL=http://localhost:8000
```

**Где взять ключ Groq:**
1. https://console.groq.com/keys
2. Sign up / Login
3. Create API Key
4. Copy → вставить в `.env`

### Шаг 2: Chrome Extension

Откройте `chrome-extension/config.js` и проверьте:

```javascript
export const API_CONFIG = {
  BASE_URL: 'http://localhost:8000/api/v1',  # ← Оставить как есть для локальной разработки
  TIMEOUT: 30000,
  RETRIES: 3
};
```

### Шаг 3: Запуск

```bash
# Терминал 1: Backend (api_service.py для extension)
uv run uvicorn api_service:app --reload --port 8000

# Терминал 2: Установка расширения
# 1. chrome://extensions/
# 2. Включить "Режим разработчика"
# 3. "Загрузить распакованное" → выбрать папку chrome-extension/
```

### Шаг 4: Проверка

```bash
# Проверка backend
curl http://localhost:8000/health

# Проверка расширения
# 1. Откройте https://perekrestok.ru
# 2. Нажмите на иконку расширения
# 3. Введите "Собери завтрак на 2 дня"
```

---

## 🚀 Production развёртывание

### 1. Backend (.env)

```env
# API Keys
GROQ_API_KEY=gsk_production_key_here

# Server
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
BACKEND_URL=https://your-domain.com

# CORS
CORS_ALLOW_ORIGINS=https://your-domain.com

# Logging
LOG_LEVEL=WARNING
```

### 2. Chrome Extension (config.js)

```javascript
export const API_CONFIG = {
  BASE_URL: 'https://your-domain.com/api/v1',  # ← Ваш production URL
  TIMEOUT: 30000,
  RETRIES: 3
};
```

### 3. manifest.json

```json
{
  "host_permissions": [
    "https://perekrestok.ru/*",
    "https://www.perekrestok.ru/*",
    "https://your-domain.com/*"  # ← Добавьте ваш домен
  ]
}
```

### 4. Deploy

```bash
# Server setup (api_service.py для работы с extension)
uv run uvicorn api_service:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4

# Systemd service (опционально)
sudo systemctl enable omnibuyai
sudo systemctl start omnibuyai

# Nginx reverse proxy (опционально)
# См. полную инструкцию в INSTRUCTION.md
```

---

## 📁 Файлы конфигурации

| Файл | Назначение | Критично |
|------|------------|----------|
| `.env` | Backend настройки | ✅ Да |
| `chrome-extension/config.js` | Extension настройки | ✅ Да |
| `chrome-extension/manifest.json` | Extension разрешения | ⚠️ Для production |
| `pyproject.toml` | Python зависимости | ❌ Нет |

---

## 🔑 Переменные окружения (.env)

### Обязательные

```env
GROQ_API_KEY=...              # Ключ Groq API
LLM_MODEL=llama-3.3-70b-versatile  # Модель LLM
BACKEND_URL=http://localhost:8000  # URL backend
```

### Опциональные (можно не менять)

```env
LLM_BASE_URL=https://api.groq.com/openai/v1
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
PEREKRESTOK_API_BASE_URL=https://www.perekrestok.ru/api/customer/1.4.1.0
PEREKRESTOK_REQUEST_DELAY=0.3
EXTENSION_BACKEND_URL=http://localhost:8000/api/v1
EXTENSION_API_TIMEOUT=30000
EXTENSION_API_RETRIES=3
DATA_DIR=data
LOG_LEVEL=INFO
CORS_ALLOW_ORIGINS=*
```

---

## 🧪 Тестирование

### Backend

```bash
# Health check
curl http://localhost:8000/api/v1/health

# API docs
open http://localhost:8000/docs

# Test chat endpoint
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Собери ужин на двоих", "products": [], "context": {}}'

# Test basket build
curl -X POST http://localhost:8000/api/v1/basket/build \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Собери ужин на двоих", "session": {"auth_token": "Bearer test", "cookies": {}}}'
```

### Extension

1. Откройте `chrome://extensions/`
2. Найдите "Perekrestok AI Assistant"
3. Нажмите "Inspect views: popup"
4. Проверьте консоль на ошибки

### CLI

```bash
uv run python main.py "Собери продукты на 3 дня для 2 человек"
```

---

## ❗ Частые проблемы

### "GROQ_API_KEY не задан"

```bash
# Проверьте .env
cat .env | grep GROQ_API_KEY

# Должно быть:
# GROQ_API_KEY=gsk_...
```

### Extension не подключается

1. Проверьте, запущен ли backend: `curl http://localhost:8000/health`
2. Проверьте `config.js`: `BASE_URL` должен совпадать
3. Перезагрузите расширение в `chrome://extensions/`

### CORS ошибки

```env
# В .env установите:
CORS_ALLOW_ORIGINS=*
```

---

## 📚 Полная документация

- **[INSTRUCTION.md](INSTRUCTION.md)** — Полная инструкция по развёртыванию
- **[README.md](README.md)** — Общая информация о проекте
- **[chrome-extension/README.md](chrome-extension/README.md)** — Документация расширения

---

**Время настройки:** 5-10 минут (локально), 30-60 минут (production)  
**Сложность:** ⭐⭐☆☆☆ (начинающий)
