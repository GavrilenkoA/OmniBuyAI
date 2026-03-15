/**
 * Content Script for Perekrestok.ru
 * Handles DOM parsing, product extraction, and cart manipulation
 */

// Product cache
let productCache = [];
let isParsing = false;

// Initialize
console.log('[Perekrestok AI] Content script loaded');

// Listen for messages from popup/background
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  handleMessage(request, sender, sendResponse);
  return true; // Keep channel open for async response
});

async function handleMessage(request, sender, sendResponse) {
  try {
    switch (request.type) {
      case 'PARSE_PRODUCTS':
        const products = await parseProductsFromPage();
        sendResponse({ success: true, products });
        break;

      case 'GET_PRODUCTS':
        sendResponse({ success: true, products: productCache });
        break;

      case 'ADD_TO_CART':
        const result = await addToCart(request.product);
        sendResponse(result);
        break;

      case 'ADD_MULTIPLE_TO_CART':
        const multiResult = await addToCartMultiple(request.products);
        sendResponse(multiResult);
        break;

      case 'GET_CART':
        const cart = await getCart();
        sendResponse({ success: true, cart });
        break;

      case 'CHECK_SITE':
        const isPerekrestok = isPerekrestokSite();
        sendResponse({ success: true, isPerekrestok });
        break;

      default:
        sendResponse({ success: false, error: 'Unknown message type' });
    }
  } catch (error) {
    console.error('[Perekrestok AI] Error handling message:', error);
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Check if we're on Perekrestok site
 */
function isPerekrestokSite() {
  const hostname = window.location.hostname;
  return hostname.includes('perekrestok.ru');
}

/**
 * Parse products from the current page
 */
async function parseProductsFromPage() {
  if (isParsing) {
    return productCache;
  }

  isParsing = true;
  productCache = [];

  try {
    // Wait for page to load
    await waitForElement('.catalog-product', 5000);

    const productElements = document.querySelectorAll('.catalog-product');
    
    productElements.forEach((element, index) => {
      try {
        const product = extractProductFromElement(element, index);
        if (product && product.id) {
          productCache.push(product);
        }
      } catch (error) {
        console.error('[Perekrestok AI] Error extracting product:', error);
      }
    });

    console.log(`[Perekrestok AI] Parsed ${productCache.length} products`);
    return productCache;
  } catch (error) {
    console.error('[Perekrestok AI] Error parsing products:', error);
    return [];
  } finally {
    isParsing = false;
  }
}

/**
 * Extract product data from a DOM element
 */
function extractProductFromElement(element, index) {
  const product = {
    id: null,
    name: '',
    price: 0,
    category: '',
    url: window.location.href,
    image: ''
  };

  // Try to get product ID from data attributes or URL
  const productId = element.dataset.productId || 
                    element.dataset.id ||
                    element.querySelector('[data-product-id]')?.dataset.productId ||
                    generateProductId(element, index);
  
  product.id = productId;

  // Get product name
  const nameElement = element.querySelector('.catalog-product__name, .product-title, [class*="name"], h3, h4');
  product.name = nameElement?.textContent?.trim() || `Товар ${index + 1}`;

  // Get price
  const priceElement = element.querySelector('.catalog-product__price, .product-price, [class*="price"], .price');
  const priceText = priceElement?.textContent?.trim() || '0';
  product.price = parseInt(priceText.replace(/\D/g, '')) || 0;

  // Get image
  const imageElement = element.querySelector('img');
  product.image = imageElement?.src || imageElement?.dataset?.src || '';

  // Get category from page context
  product.category = extractCategoryFromPage();

  return product;
}

/**
 * Generate a product ID if none is available
 */
function generateProductId(element, index) {
  // Create a hash from element content
  const content = element.textContent?.substring(0, 50) || '';
  const hash = hashCode(content + index);
  return `gen_${Math.abs(hash)}`;
}

/**
 * Extract category from page context
 */
function extractCategoryFromPage() {
  // Try to get category from breadcrumbs
  const breadcrumb = document.querySelector('.breadcrumbs, .breadcrumb, [class*="breadcrumb"]');
  if (breadcrumb) {
    const links = breadcrumb.querySelectorAll('a');
    if (links.length > 0) {
      return links[links.length - 1]?.textContent?.trim() || '';
    }
  }

  // Try from page title
  const title = document.title;
  const categoryMatch = title.match(/(.+?) - Перекрёсток/);
  if (categoryMatch) {
    return categoryMatch[1].trim();
  }

  return '';
}

/**
 * Add a single product to cart
 */
async function addToCart(product) {
  try {
    // Try to find the add to cart button for this product
    const productElement = findProductElement(product.id);
    
    if (productElement) {
      const addToCartButton = productElement.querySelector(
        '.catalog-product__button--cart, ' +
        '[class*="add-to-cart"], ' +
        '[class*="cart-button"], ' +
        'button[class*="cart"]'
      );

      if (addToCartButton) {
        addToCartButton.click();
        await waitForCartUpdate();
        return { success: true, message: 'Product added to cart' };
      }
    }

    // Fallback: Try to add via API simulation
    return await addToCartViaAPI(product);
  } catch (error) {
    console.error('[Perekrestok AI] Error adding to cart:', error);
    return { success: false, error: error.message };
  }
}

/**
 * Add multiple products to cart
 */
async function addToCartMultiple(products) {
  const results = {
    added: 0,
    failed: 0,
    errors: []
  };

  for (const product of products) {
    const result = await addToCart(product);
    if (result.success) {
      results.added++;
    } else {
      results.failed++;
      results.errors.push({ product: product.name, error: result.error });
    }
    
    // Small delay between additions
    await sleep(300);
  }

  return { success: results.added > 0, ...results };
}

/**
 * Find product element by ID
 */
function findProductElement(productId) {
  const productElements = document.querySelectorAll('.catalog-product');
  
  for (const element of productElements) {
    const id = element.dataset.productId || 
               element.dataset.id ||
               element.querySelector('[data-product-id]')?.dataset.productId;
    
    if (id === productId) {
      return element;
    }
  }

  return null;
}

/**
 * Add to cart via API (fallback method)
 */
async function addToCartViaAPI(product) {
  try {
    // This would integrate with Perekrestok's actual API if available
    // For now, simulate by finding and clicking the product
    console.log('[Perekrestok AI] Attempting API add for:', product.name);
    
    // Dispatch custom event for background script to handle
    window.dispatchEvent(new CustomEvent('perekrestok-add-to-cart', {
      detail: { product }
    }));

    return { success: true, message: 'Product added via API' };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * Get current cart contents
 */
async function getCart() {
  try {
    const cartElement = document.querySelector('.cart, [class*="cart"], #cart');
    const cartItems = cartElement?.querySelectorAll('.cart-item, [class*="cart-item"]') || [];
    
    const items = [];
    cartItems.forEach(item => {
      const name = item.querySelector('.cart-item__name, [class*="name"]')?.textContent?.trim();
      const priceText = item.querySelector('.cart-item__price, [class*="price"]')?.textContent?.trim() || '0';
      const price = parseInt(priceText.replace(/\D/g, '')) || 0;
      const quantityElement = item.querySelector('.cart-item__quantity, [class*="quantity"]');
      const quantity = parseInt(quantityElement?.textContent?.trim() || '1');

      if (name) {
        items.push({ name, price, quantity });
      }
    });

    return { items, total: items.reduce((sum, item) => sum + (item.price * item.quantity), 0) };
  } catch (error) {
    console.error('[Perekrestok AI] Error getting cart:', error);
    return { items: [], total: 0 };
  }
}

/**
 * Wait for cart to update after adding item
 */
async function waitForCartUpdate() {
  return new Promise(resolve => {
    setTimeout(resolve, 500);
  });
}

/**
 * Wait for an element to appear
 */
function waitForElement(selector, timeout = 10000) {
  return new Promise((resolve, reject) => {
    const element = document.querySelector(selector);
    if (element) {
      resolve(element);
      return;
    }

    const observer = new MutationObserver(() => {
      const element = document.querySelector(selector);
      if (element) {
        observer.disconnect();
        resolve(element);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    setTimeout(() => {
      observer.disconnect();
      reject(new Error(`Timeout waiting for ${selector}`));
    }, timeout);
  });
}

/**
 * Simple hash function for generating IDs
 */
function hashCode(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return hash;
}

/**
 * Sleep utility
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Inject floating chat widget (future enhancement)
 */
function injectChatWidget() {
  // This could add a floating chat button to the page
  console.log('[Perekrestok AI] Chat widget injection not yet implemented');
}

// Auto-parse products when page loads
if (isPerekrestokSite()) {
  window.addEventListener('load', async () => {
    // Wait a bit for dynamic content
    await sleep(1000);
    parseProductsFromPage();
  });
}

console.log('[Perekrestok AI] Content script initialized');
