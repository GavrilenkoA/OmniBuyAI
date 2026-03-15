/**
 * Background Service Worker for Perekrestok AI Assistant
 * Handles communication between popup, content scripts, and backend API
 */

import { apiClient, API_ENDPOINTS } from './services/api.js';

// State
let activeTabId = null;
let isBackendConnected = false;

// Initialize
console.log('[Perekrestok AI] Background service worker started');

// Listen for extension installation
chrome.runtime.onInstalled.addListener((details) => {
  console.log('[Perekrestok AI] Extension installed:', details.reason);
  
  if (details.reason === 'install') {
    // Open welcome page on first install
    chrome.tabs.create({
      url: 'https://perekrestok.ru'
    });
  }
});

// Listen for messages from popup or content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  handleMessage(request, sender, sendResponse);
  return true; // Keep channel open for async response
});

// Track active tab
chrome.tabs.onActivated.addListener((activeInfo) => {
  activeTabId = activeInfo.tabId;
  checkIfPerekrestokTab(activeTabId);
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (tabId === activeTabId && changeInfo.url) {
    checkIfPerekrestokTab(tabId);
  }
});

/**
 * Handle messages from popup or content scripts
 */
async function handleMessage(request, sender, sendResponse) {
  try {
    console.log('[Perekrestok AI] Received message:', request.type);

    switch (request.type) {
      case 'USER_MESSAGE':
        const aiResponse = await processUserMessage(request.message);
        sendResponse(aiResponse);
        break;

      case 'ADD_TO_CART':
        const cartResult = await handleAddToCart(request.products);
        sendResponse(cartResult);
        break;

      case 'ADD_SINGLE_TO_CART':
        const singleResult = await handleAddSingleToCart(request.product);
        sendResponse(singleResult);
        break;

      case 'GET_PRODUCTS':
        const products = await getProductsFromTab();
        sendResponse({ success: true, products });
        break;

      case 'CHECK_BACKEND':
        const backendStatus = await checkBackendConnection();
        sendResponse({ success: true, connected: backendStatus });
        break;

      default:
        sendResponse({ success: false, error: 'Unknown message type' });
    }
  } catch (error) {
    console.error('[Perekrestok AI] Error handling message:', error);
    sendResponse({ 
      success: false, 
      error: error.message || 'An error occurred' 
    });
  }
}

/**
 * Process user message through AI backend
 */
async function processUserMessage(message) {
  try {
    // First, get products from the current page
    const products = await getProductsFromTab();

    // Send to AI backend
    const response = await apiClient.post(API_ENDPOINTS.CHAT, {
      message: message,
      products: products,
      context: {
        tabId: activeTabId,
        url: await getCurrentTabUrl()
      }
    });

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    console.error('[Perekrestok AI] AI processing error:', error);
    
    // Fallback: simple keyword-based response
    const fallbackResponse = generateFallbackResponse(message);
    return {
      success: true,
      data: fallbackResponse
    };
  }
}

/**
 * Generate fallback response when backend is unavailable
 */
function generateFallbackResponse(message) {
  const lowerMessage = message.toLowerCase();
  
  // Simple keyword matching
  if (lowerMessage.includes('завтрак') || lowerMessage.includes('утро')) {
    return {
      type: 'text',
      text: 'Для завтрака я рекомендую: хлеб, молоко, яйца, сыр, масло. К сожалению, сейчас я не могу получить доступ к каталогу товаров. Попробуйте перейти на страницу каталога.'
    };
  }
  
  if (lowerMessage.includes('обед') || lowerMessage.includes('ужин')) {
    return {
      type: 'text',
      text: 'Я могу помочь подобрать продукты для обеда или ужина. Пожалуйста, перейдите на страницу каталога товаров.'
    };
  }
  
  if (lowerMessage.includes('молоко')) {
    return {
      type: 'text',
      text: 'Чтобы найти молоко, пожалуйста, перейдите в раздел "Молочные продукты" или воспользуйтесь поиском на сайте.'
    };
  }

  // Default response
  return {
    type: 'text',
    text: 'Я понимаю ваш запрос. Для поиска товаров пожалуйста перейдите на страницу каталога Перекрёстка.'
  };
}

/**
 * Handle adding multiple products to cart
 */
async function handleAddToCart(products) {
  try {
    if (!activeTabId) {
      return { success: false, error: 'No active tab' };
    }

    // Send message to content script
    const response = await chrome.tabs.sendMessage(activeTabId, {
      type: 'ADD_MULTIPLE_TO_CART',
      products: products
    });

    return response;
  } catch (error) {
    console.error('[Perekrestok AI] Error adding to cart:', error);
    return { success: false, error: error.message };
  }
}

/**
 * Handle adding a single product to cart
 */
async function handleAddSingleToCart(product) {
  try {
    if (!activeTabId) {
      return { success: false, error: 'No active tab' };
    }

    const response = await chrome.tabs.sendMessage(activeTabId, {
      type: 'ADD_TO_CART',
      product: product
    });

    return response;
  } catch (error) {
    console.error('[Perekrestok AI] Error adding single product to cart:', error);
    return { success: false, error: error.message };
  }
}

/**
 * Get products from current tab
 */
async function getProductsFromTab() {
  try {
    if (!activeTabId) {
      return [];
    }

    const response = await chrome.tabs.sendMessage(activeTabId, {
      type: 'PARSE_PRODUCTS'
    });

    return response.products || [];
  } catch (error) {
    console.log('[Perekrestok AI] Could not parse products:', error.message);
    return [];
  }
}

/**
 * Check if current tab is Perekrestok
 */
async function checkIfPerekrestokTab(tabId) {
  try {
    const tab = await chrome.tabs.get(tabId);
    const isPerekrestok = tab.url?.includes('perekrestok.ru') || false;
    
    chrome.storage.local.set({ isPerekrestokTab: isPerekrestok });
    
    if (isPerekrestok) {
      console.log('[Perekrestok AI] On Perekrestok site');
    }
  } catch (error) {
    console.error('[Perekrestok AI] Error checking tab:', error);
  }
}

/**
 * Get current tab URL
 */
async function getCurrentTabUrl() {
  try {
    if (!activeTabId) return '';
    const tab = await chrome.tabs.get(activeTabId);
    return tab.url || '';
  } catch (error) {
    return '';
  }
}

/**
 * Check backend API connection
 */
async function checkBackendConnection() {
  try {
    const response = await apiClient.get(API_ENDPOINTS.HEALTH);
    isBackendConnected = response.success;
    return isBackendConnected;
  } catch (error) {
    isBackendConnected = false;
    return false;
  }
}

// Periodic backend health check
setInterval(() => {
  checkBackendConnection();
}, 60000); // Check every minute

// Initial backend check
checkBackendConnection();

console.log('[Perekrestok AI] Background service worker initialized');
