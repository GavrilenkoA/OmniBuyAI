/**
 * API Client for Backend Communication
 * Handles HTTP requests to the FastAPI backend
 */

// Import configuration from central config file
import { API_CONFIG, API_ENDPOINTS } from '../config.js';

/**
 * API Client Class
 */
class ApiClient {
  constructor(config) {
    this.baseUrl = config.BASE_URL;
    this.timeout = config.TIMEOUT;
    this.retries = config.RETRIES;
  }

  /**
   * Generic request method
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    
    const config = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    };

    // Add timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);
    config.signal = controller.signal;

    try {
      const response = await fetch(url, config);
      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      clearTimeout(timeoutId);
      
      if (error.name === 'AbortError') {
        throw new Error('Request timeout');
      }
      
      console.error('[API Client] Request failed:', error);
      throw error;
    }
  }

  /**
   * GET request
   */
  async get(endpoint, params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${endpoint}?${queryString}` : endpoint;
    
    return this.request(url, {
      method: 'GET'
    });
  }

  /**
   * POST request
   */
  async post(endpoint, data) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  /**
   * PUT request
   */
  async put(endpoint, data) {
    return this.request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data)
    });
  }

  /**
   * DELETE request
   */
  async delete(endpoint) {
    return this.request(endpoint, {
      method: 'DELETE'
    });
  }

  /**
   * Request with retry logic
   */
  async requestWithRetry(endpoint, options = {}) {
    let lastError;
    
    for (let i = 0; i < this.retries; i++) {
      try {
        return await this.request(endpoint, options);
      } catch (error) {
        lastError = error;
        console.log(`[API Client] Retry ${i + 1}/${this.retries} failed`);
        
        if (i < this.retries - 1) {
          await this.sleep(1000 * (i + 1)); // Exponential backoff
        }
      }
    }
    
    throw lastError;
  }

  /**
   * Sleep utility
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Set base URL
   */
  setBaseUrl(url) {
    this.baseUrl = url;
  }

  /**
   * Get current base URL
   */
  getBaseUrl() {
    return this.baseUrl;
  }
}

// Create singleton instance
export const apiClient = new ApiClient(API_CONFIG);

/**
 * Helper functions for specific API operations
 */

/**
 * Send chat message to AI
 */
export async function sendChatMessage(message, products = [], context = {}) {
  return apiClient.post(API_ENDPOINTS.CHAT, {
    message,
    products,
    context
  });
}

/**
 * Search products
 */
export async function searchProducts(query, filters = {}) {
  return apiClient.post(API_ENDPOINTS.SEARCH, {
    query,
    ...filters
  });
}

/**
 * Get all products
 */
export async function getProducts() {
  return apiClient.get(API_ENDPOINTS.PRODUCTS);
}

/**
 * Add product to cart
 */
export async function addToCart(productId, quantity = 1) {
  return apiClient.post(API_ENDPOINTS.CART_ADD, {
    product_id: productId,
    quantity
  });
}

/**
 * Remove product from cart
 */
export async function removeFromCart(productId) {
  return apiClient.post(API_ENDPOINTS.CART_REMOVE, {
    product_id: productId
  });
}

/**
 * Get cart contents
 */
export async function getCart() {
  return apiClient.get(API_ENDPOINTS.CART_GET);
}

/**
 * Check backend health
 */
export async function checkHealth() {
  return apiClient.get(API_ENDPOINTS.HEALTH);
}

export default apiClient;
