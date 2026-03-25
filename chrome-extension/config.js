/**
 * ═══════════════════════════════════════════════════════════
 * Chrome Extension Configuration
 * ═══════════════════════════════════════════════════════════
 * 
 * НАСТРОЙКА ДЛЯ РАЗРАБОТКИ (LOCAL):
 * ----------------------------------
 * BASE_URL: 'http://localhost:8000/api/v1'
 * 
 * НАСТРОЙКА ДЛЯ PRODUCTION:
 * -------------------------
 * BASE_URL: 'https://your-domain.com/api/v1'
 * 
 * ИНСТРУКЦИЯ:
 * 1. Измените BASE_URL на ваш production URL
 * 2. При необходимости настройте TIMEOUT и RETRIES
 * 3. Сохраните файл
 * 4. Перезагрузите расширение в chrome://extensions/
 * 
 * API ENDPOINTS:
 * --------------
 * POST /chat    — Отправить сообщение AI
 * POST /search  — Поиск товаров
 * GET  /products— Получить все товары
 * POST /cart/add— Добавить товар в корзину
 * GET  /health  — Проверка доступности
 * ═══════════════════════════════════════════════════════════
 */

export const API_CONFIG = {
  // 🔧 BACKEND URL
  // Локально: 'http://localhost:8000/api/v1'
  // Production: 'https://your-domain.com/api/v1'
  // Важно: URL должен включать префикс /api/v1
  BASE_URL: 'http://localhost:8000/api/v1',
  
  // ⏱️ TIMEOUT (миллисекунды)
  // Максимальное время ожидания ответа от сервера
  TIMEOUT: 30000, // 30 секунд
  
  // 🔄 RETRIES
  // Количество попыток повторного запроса при ошибке
  RETRIES: 3
};

// ═══════════════════════════════════════════════════════════
// API ENDPOINTS (не менять)
// ═══════════════════════════════════════════════════════════
export const API_ENDPOINTS = {
  CHAT: '/chat',           // Отправка сообщения AI
  SEARCH: '/search',       // Поиск товаров
  PRODUCTS: '/products',   // Получить все товары
  CART_ADD: '/cart/add',   // Добавить товар в корзину
  CART_REMOVE: '/cart/remove', // Удалить товар из корзины
  CART_GET: '/cart',       // Получить содержимое корзины
  HEALTH: '/health',       // Проверка доступности сервера
  BASKET_BUILD: '/basket/build' // Построение корзины по промту
};

// ═══════════════════════════════════════════════════════════
// РАЗРЕШЕНИЯ (manifest.json)
// ═══════════════════════════════════════════════════════════
// Убедитесь, что в manifest.json указаны правильные разрешения:
//
// "host_permissions": [
//   "https://perekrestok.ru/*",
//   "https://www.perekrestok.ru/*",
//   "http://localhost:8000/*"  // Для локальной разработки
// ]
//
// Для production замените localhost на ваш домен:
// "host_permissions": [
//   "https://perekrestok.ru/*",
//   "https://www.perekrestok.ru/*",
//   "https://your-domain.com/*"  // Production backend
// ]
// ═══════════════════════════════════════════════════════════
