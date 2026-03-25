# OmniBuyAI — Инструкция по развёртыванию и настройке

## 📋 Содержание

1. [Обзор проекта](#обзор-проекта)
2. [Быстрый старт](#быстрый-старт)
3. [Конфигурация](#конфигурация)
4. [Backend (FastAPI)](#backend-fastapi)
5. [Chrome Extension](#chrome-extension)
6. [Scraper (сбор данных)](#scraper-сбор-данных)
7. [Production развёртывание](#production-развёртывание)
8. [Troubleshooting](#troubleshooting)

---

## 📖 Обзор проекта

**OmniBuyAI** — AI-агент для планирования покупок в магазине «Перекрёсток».

### Архитектура

```
┌─────────────────────┐
│  Chrome Extension   │  ← UI для пользователя
│  (Popup + Content)  │
└──────────┬──────────┘
           │ HTTP/WebSocket
           ▼
┌─────────────────────┐
│   Backend (FastAPI) │  ← LLM + бизнес-логика
│   basket_service.py │
└──────────┬──────────┘
           │
           ├──→ GROQ API (LLM)
           │
           └──→ Perekrestok API (корзина)
```

### Компоненты

| Компонент | Описание | Порт |
|-----------|----------|------|
| **Backend** | FastAPI сервер, LLM агент, интеграция с API Перекрёстка | 8000 |
| **Chrome Extension** | Расширение для браузера, UI чата, парсинг товаров | - |
| **Scraper** | Скрипт для сбора каталога товаров из Перекрёстка | - |
| **CLI** | Консольный интерфейс для тестирования | - |

---

## 🚀 Быстрый старт

### 1. Требования

- **Python 3.12+**
- **uv** (менеджер пакетов)
- **GROQ API ключ** (получить: https://console.groq.com/keys)
- **Chrome/Edge браузер** (для расширения)

### 2. Установка

```bash
# Клонирование репозитория
git clone <repository-url>
cd OmniBuyAI

# Установка uv (если не установлен)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Установка Python 3.12 и зависимостей
uv python install 3.12
uv sync
```

### 3. Настройка конфигурации

```bash
# Создать файл конфигурации
cp .env.example .env

# Отредактировать .env (см. раздел Конфигурация)
nano .env  # или ваш редактор
```

### 4. Запуск Backend

**Для работы с Chrome Extension используйте api_service.py:**

```bash
# Запуск сервера разработки
uv run uvicorn api_service:app --reload --port 8000

# Запуск production сервера
uv run uvicorn api_service:app --host 0.0.0.0 --port 8000 --workers 4
```

**Альтернатива: basket_service.py** (только /basket/build endpoint):

```bash
uv run uvicorn basket_service:app --reload --port 8000
```

### 5. Установка Chrome Extension

1. Откройте `chrome://extensions/`
2. Включите **«Режим разработчика»**
3. Нажмите **«Загрузить распакованное»**
4. Выберите папку `chrome-extension/`
5. Расширение появится в панели

---

## ⚙️ Конфигурация

### Файл `.env` (Backend)

Все настройки backend находятся в файле `.env`.

#### 1. LLM API (GROQ)

```env
# 🔑 Обязательно для работы
GROQ_API_KEY=gsk_your_api_key_here

# Модель LLM (доступные: https://console.groq.com/docs/models)
LLM_MODEL=llama-3.3-70b-versatile

# Base URL (не менять для Groq)
LLM_BASE_URL=https://api.groq.com/openai/v1
```

**Где взять API ключ:**
1. Перейдите на https://console.groq.com/keys
2. Зарегистрируйтесь/войдите
3. Создайте новый API ключ
4. Скопируйте в `.env`

#### 2. Backend Server

```env
# Хост и порт для запуска
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000

# URL backend для Chrome extension
# Для локальной разработки:
BACKEND_URL=http://localhost:8000

# Для production:
# BACKEND_URL=https://your-domain.com
```

#### 3. Perekrestok API

```env
# Не менять (официальный API Перекрёстка)
PEREKRESTOK_API_BASE_URL=https://www.perekrestok.ru/api/customer/1.4.1.0
PEREKRESTOK_SITE_URL=https://www.perekrestok.ru

# Задержка между запросами (секунды)
# Увеличьте при проблемах с rate limiting
PEREKRESTOK_REQUEST_DELAY=0.3
```

#### 4. Chrome Extension

```env
# Должен совпадать с BACKEND_URL
EXTENSION_BACKEND_URL=http://localhost:8000/api/v1

# Таймаут запросов (мс)
EXTENSION_API_TIMEOUT=30000

# Количество попыток
EXTENSION_API_RETRIES=3
```

#### 5. Данные и логирование

```env
# Путь к данным (товары, категории)
DATA_DIR=data

# Уровень логирования: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
```

#### 6. CORS

```env
# Разрешённые источники
# Для production укажите ваш домен
CORS_ALLOW_ORIGINS=*

# Пример для production:
# CORS_ALLOW_ORIGINS=https://your-frontend.com
```

---

### Файл `chrome-extension/config.js` (Extension)

Настройки Chrome расширения.

#### Быстрая настройка

```javascript
// 🔧 LOKALNO (разработка)
export const API_CONFIG = {
  BASE_URL: 'http://localhost:8000/api/v1',
  TIMEOUT: 30000,
  RETRIES: 3
};

// 🔧 PRODUCTION (замените your-domain.com)
export const API_CONFIG = {
  BASE_URL: 'https://your-domain.com/api/v1',
  TIMEOUT: 30000,
  RETRIES: 3
};
```

#### Обновление расширения после изменений

1. Откройте `chrome://extensions/`
2. Найдите «Perekrestok AI Assistant»
3. Нажмите иконку обновления 🔄
4. Переоткройте popup

---

## 🖥️ Backend (FastAPI)

### Запуск сервера

#### Разработка

```bash
# Автперезагрузка при изменениях
uv run uvicorn basket_service:app --reload --port 8000
```

#### Production

```bash
# Несколько workers для продакшена
uv run uvicorn basket_service:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --loop uvloop \
  --http httptools
```

### API Endpoints

**api_service.py** (рекомендуется):

| Endpoint | Method | Описание |
|----------|--------|----------|
| `/api/v1/chat` | POST | Отправить сообщение AI, получить ответ |
| `/api/v1/search` | POST | Поиск товаров по запросу |
| `/api/v1/products` | GET | Получить все товары из CSV |
| `/api/v1/cart/add` | POST | Добавить товар в корзину Перекрёстка |
| `/api/v1/cart/remove` | POST | Удалить товар из корзины |
| `/api/v1/cart` | GET | Получить содержимое корзины |
| `/api/v1/health` | GET | Проверка доступности |
| `/api/v1/basket/build` | POST | Построить корзину по промту (полный цикл) |

**basket_service.py** (устаревший):

| Endpoint | Method | Описание |
|----------|--------|----------|
| `/basket/build` | POST | Построить корзину по промту |
| `/health` | GET | Проверка доступности |

### Пример запроса

**Chat endpoint:**

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Собери ужин на двоих",
    "products": [],
    "context": {}
  }'
```

**Basket build endpoint:**

```bash
curl -X POST http://localhost:8000/api/v1/basket/build \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Собери ужин на двоих за 3000 рублей",
    "session": {
      "auth_token": "Bearer eyJ...",
      "cookies": {"session": "...", "spid": "..."}
    }
  }'
```

### Тестирование

```bash
# Проверка здоровья
curl http://localhost:8000/health

# Swagger UI
open http://localhost:8000/docs
```

---

## 🧩 Chrome Extension

### Установка (разработка)

1. Откройте Chrome
2. Перейдите на `chrome://extensions/`
3. Включите **«Режим разработчика»** (переключатель справа сверху)
4. Нажмите **«Загрузить распакованное»**
5. Выберите папку `chrome-extension/`
6. Расширение появится в списке

### Настройка для production

1. Откройте `chrome-extension/config.js`
2. Измените `BASE_URL`:
   ```javascript
   BASE_URL: 'https://your-domain.com/api/v1'
   ```
3. Обновите `manifest.json`:
   ```json
   "host_permissions": [
     "https://perekrestok.ru/*",
     "https://www.perekrestok.ru/*",
     "https://your-domain.com/*"
   ]
   ```
4. Сохраните файлы
5. Перезагрузите расширение в `chrome://extensions/`

### Использование

1. Перейдите на `https://perekrestok.ru`
2. Нажмите на иконку расширения
3. Введите запрос (например, «Собери завтрак на 2 дня»)
4. Или используйте голосовой ввод 🎤
5. Просмотрите товары и нажмите «В корзину»

### Отладка

```
Popup:         ПКМ по popup → Inspect
Content Script: DevTools страницы → Console
Background:    chrome://extensions/ → Service Worker → Inspect
```

---

## 🕷️ Scraper (сбор данных)

Скрипт для сбора каталога товаров из Перекрёстка.

### Установка зависимостей

```bash
uv add perekrestok-api tqdm
```

### Использование

```bash
# Полный обход каталога
uv run python scraper.py

# Быстрый тест (50 товаров на категорию)
uv run python scraper.py --max-per-category 50

# Продолжить прерванный обход
uv run python scraper.py --resume

# Поиск товаров
uv run python scraper.py --search "молоко" --pages 3

# Показать категории
uv run python scraper.py --list-categories
```

### Выходные файлы

| Файл | Описание |
|------|----------|
| `data/products.csv` | Основной CSV (2500+ товаров) |
| `data/products.jsonl` | JSONL (по строке на товар) |
| `data/products_full.json` | Полный JSON |
| `data/categories.json` | Дерево категорий |
| `data/catalog_summary.json` | Саммари сбора |

### Конфигурация scraper

Настройки в `scraper.py`:

```python
BASE_URL = "https://www.perekrestok.ru/api/customer/1.4.1.0"
SITE_URL = "https://www.perekrestok.ru"
ITEMS_PER_PAGE = 48
DELAY_BETWEEN_REQUESTS = 1.0  # Задержка между запросами
```

---

## 🌐 Production развёртывание

### 1. Подготовка сервера

#### Требования

- **CPU**: 2+ cores
- **RAM**: 4GB+
- **Storage**: 10GB+
- **OS**: Ubuntu 20.04+ / Debian 11+

#### Установка

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Python и зависимостей
sudo apt install -y python3.12 python3.12-venv python3-pip git curl

# Установка uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Клонирование репозитория
git clone <repository-url> /opt/omnibuyai
cd /opt/omnibuyai

# Установка зависимостей
uv python install 3.12
uv sync
```

### 2. Настройка конфигурации

```bash
cd /opt/omnibuyai

# Создание .env
cp .env.example .env
nano .env
```

**Обязательные изменения для production:**

```env
# GROQ API
GROQ_API_KEY=gsk_your_production_key

# Backend
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
BACKEND_URL=https://your-domain.com

# CORS
CORS_ALLOW_ORIGINS=https://your-domain.com

# Logging
LOG_LEVEL=WARNING
```

### 3. Chrome Extension для production

1. Откройте `chrome-extension/config.js`
2. Измените:
   ```javascript
   BASE_URL: 'https://your-domain.com/api/v1'
   ```
3. Обновите `manifest.json`:
   ```json
   "host_permissions": [
     "https://perekrestok.ru/*",
     "https://www.perekrestok.ru/*",
     "https://your-domain.com/*"
   ]
   ```

### 4. Запуск через systemd

Создайте файл службы:

```bash
sudo nano /etc/systemd/system/omnibuyai.service
```

```ini
[Unit]
Description=OmniBuyAI Backend Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/omnibuyai
Environment=PATH=/home/username/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/home/username/.local/bin/uv run uvicorn api_service:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение автозапуска
sudo systemctl enable omnibuyai

# Запуск службы
sudo systemctl start omnibuyai

# Проверка статуса
sudo systemctl status omnibuyai
```

### 5. Настройка Nginx (reverse proxy)

```bash
sudo nano /etc/nginx/sites-available/omnibuyai
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # WebSocket support (если понадобится)
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Активация:

```bash
# Создание симлинка
sudo ln -s /etc/nginx/sites-available/omnibuyai /etc/nginx/sites-enabled/

# Проверка конфигурации
sudo nginx -t

# Перезагрузка Nginx
sudo systemctl reload nginx
```

### 6. SSL сертификат (Let's Encrypt)

```bash
# Установка Certbot
sudo apt install -y certbot python3-certbot-nginx

# Получение сертификата
sudo certbot --nginx -d your-domain.com

# Автообновление
sudo certbot renew --dry-run
```

### 7. Мониторинг и логи

```bash
# Логи systemd
sudo journalctl -u omnibuyai -f

# Логи Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Использование ресурсов
htop
```

---

## 🔧 Troubleshooting

### Backend не запускается

**Ошибка: GROQ_API_KEY не задан**

```bash
# Проверьте .env файл
cat .env | grep GROQ_API_KEY

# Убедитесь, что ключ действителен
# Проверьте на https://console.groq.com/keys
```

**Ошибка: Port already in use**

```bash
# Найти процесс на порту 8000
lsof -i :8000

# Убить процесс
kill -9 <PID>

# Или измените порт в .env
BACKEND_PORT=8001
```

**Ошибка: Module not found**

```bash
# Убедитесь, что используете правильный файл
# Для Chrome Extension: api_service.py
uv run uvicorn api_service:app --reload --port 8000

# Для простого /basket/build: basket_service.py
uv run uvicorn basket_service:app --reload --port 8000
```

### Chrome Extension не подключается

**Ошибка: Network error**

1. Проверьте, запущен ли backend:
   ```bash
   curl http://localhost:8000/health
   ```
2. Проверьте `config.js` в расширении
3. Убедитесь, что `host_permissions` в `manifest.json` включает backend URL
4. Перезагрузите расширение

**Ошибка: CORS**

```env
# В .env backend установите:
CORS_ALLOW_ORIGINS=*

# Для production укажите конкретный домен:
CORS_ALLOW_ORIGINS=https://your-domain.com
```

### Scraper не собирает товары

**Ошибка: Too many requests**

```python
# Увеличьте задержку в scraper.py
DELAY_BETWEEN_REQUESTS = 2.0  # было 1.0
```

**Ошибка: No products found**

- Убедитесь, что вы на странице каталога
- Проверьте селекторы в `scraper.py`
- Структура сайта могла измениться

### LLM возвращает некорректные ответы

**Проверьте:**

1. Действителен ли API ключ GROQ
2. Правильно ли указана модель:
   ```env
   LLM_MODEL=llama-3.3-70b-versatile
   ```
3. Квоты API: https://console.groq.com/usage

### Товары не добавляются в корзину

**Проблемы с авторизацией:**

1. Истёк токен — перелогиньтесь на perekrestok.ru
2. Проверьте cookies в DevTools → Application → Cookies
3. Убедитесь, что вы авторизованы на сайте

**Rate limiting:**

```env
# Увеличьте задержку
PEREKRESTOK_REQUEST_DELAY=0.5
```

---

## 📞 Поддержка

### Логи

```bash
# Backend логи
uv run uvicorn api_service:app --log-level DEBUG

# Systemd логи
sudo journalctl -u omnibuyai --since "1 hour ago"

# Chrome Extension логи
# Откройте DevTools → Console для каждого компонента
```

### Контакты

- GitHub Issues: <repository-url>/issues
- Email: <your-email>

---

## 📚 Дополнительные ресурсы

- [GROQ API Docs](https://console.groq.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Chrome Extensions](https://developer.chrome.com/docs/extensions/)
- [Perekrestok API (неофициальный)](https://github.com/anvilkov/perekrestok-api)

---

**Версия инструкции:** 1.0  
**Последнее обновление:** 2026-03-25
