// DOM Elements
const messagesContainer = document.getElementById('messagesContainer');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');
const voiceButton = document.getElementById('voiceButton');
const closeButton = document.getElementById('closeButton');
const quickActionBtns = document.querySelectorAll('.quick-action-btn');
const productCardTemplate = document.getElementById('productCardTemplate');

// State
let isWaitingForConfirmation = false;
let pendingProducts = [];
let recognition = null;
let isRecording = false;

// SVG Icons
const AGENT_ICON = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="2"/>
  <path d="M6 20C6 17 8 15 12 15C16 15 18 17 18 20" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
  <path d="M9 8L10 6M15 8L14 6M12 4V2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
</svg>`;

const USER_ICON = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="2"/>
  <path d="M6 20C6 17 8 15 12 15C16 15 18 17 18 20" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
</svg>`;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  loadChatHistory();
  initSpeechRecognition();
});

function setupEventListeners() {
  sendButton.addEventListener('click', handleSendMessage);
  closeButton.addEventListener('click', () => window.close());
  userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      handleSendMessage();
    }
  });

  voiceButton.addEventListener('click', toggleVoiceRecognition);

  quickActionBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const mealType = btn.textContent.trim();
      showMealHint(mealType);
    });
  });
}

// Speech Recognition
function initSpeechRecognition() {
  if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.lang = 'ru-RU';
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      console.log('Speech recognition started');
      isRecording = true;
      voiceButton.classList.add('recording');
      voiceButton.title = 'Запись...';
    };

    recognition.onend = () => {
      console.log('Speech recognition ended');
      isRecording = false;
      voiceButton.classList.remove('recording');
      voiceButton.title = 'Голосовой ввод';
    };

    recognition.onresult = (event) => {
      console.log('Speech recognition result:', event);
      const transcript = event.results[0][0].transcript;
      userInput.value = transcript;
      handleSendMessage();
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      isRecording = false;
      voiceButton.classList.remove('recording');
      voiceButton.title = 'Голосовой ввод';

      if (event.error === 'not-allowed') {
        showToast('Доступ к микрофону запрещён', 'error');
      } else if (event.error === 'no-speech') {
        showToast('Речь не обнаружена', 'error');
      } else if (event.error === 'audio-capture') {
        showToast('Микрофон не найден', 'error');
      } else if (event.error === 'aborted') {
        // User cancelled, do nothing
        return;
      } else {
        showToast('Ошибка распознавания: ' + event.error, 'error');
      }
    };
  } else {
    voiceButton.style.display = 'none';
    console.warn('Speech Recognition API not supported');
  }
}

function toggleVoiceRecognition() {
  console.log('toggleVoiceRecognition called, isRecording:', isRecording, 'recognition:', recognition);
  
  if (!recognition) {
    showToast('Голосовой ввод не поддерживается', 'error');
    return;
  }

  if (isRecording) {
    recognition.stop();
  } else {
    try {
      // Create new recognition instance each time to avoid state issues
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognition = new SpeechRecognition();
      recognition.lang = 'ru-RU';
      recognition.interimResults = false;
      recognition.continuous = false;
      recognition.maxAlternatives = 1;
      
      recognition.onstart = () => {
        console.log('Speech recognition started');
        isRecording = true;
        voiceButton.classList.add('recording');
        voiceButton.title = 'Запись...';
      };

      recognition.onend = () => {
        console.log('Speech recognition ended');
        isRecording = false;
        voiceButton.classList.remove('recording');
        voiceButton.title = 'Голосовой ввод';
      };

      recognition.onresult = (event) => {
        console.log('Speech recognition result:', event);
        const transcript = event.results[0][0].transcript;
        userInput.value = transcript;
        handleSendMessage();
      };

      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        isRecording = false;
        voiceButton.classList.remove('recording');
        voiceButton.title = 'Голосовой ввод';

        if (event.error === 'not-allowed') {
          showToast('Доступ к микрофону запрещён', 'error');
        } else if (event.error === 'no-speech') {
          showToast('Речь не обнаружена', 'error');
        } else if (event.error === 'audio-capture') {
          showToast('Микрофон не найден', 'error');
        } else if (event.error === 'aborted') {
          return;
        } else {
          showToast('Ошибка распознавания: ' + event.error, 'error');
        }
      };
      
      recognition.start();
    } catch (error) {
      console.error('Failed to start recognition:', error);
      showToast('Ошибка запуска микрофона', 'error');
    }
  }
}

// Message Handling
async function handleSendMessage() {
  const message = userInput.value.trim();
  if (!message) return;

  if (isWaitingForConfirmation) {
    handleConfirmationResponse(message);
    return;
  }

  // Add user message
  addMessage(message, 'user');
  userInput.value = '';

  // Show typing indicator
  showTypingIndicator();

  try {
    // Send to background script for AI processing
    const response = await chrome.runtime.sendMessage({
      type: 'USER_MESSAGE',
      message: message
    });

    hideTypingIndicator();

    if (response.success) {
      processAIResponse(response.data);
    } else {
      // Fallback response when backend is unavailable
      const fallbackResponse = getFallbackResponse(message);
      if (fallbackResponse) {
        addMessage(fallbackResponse, 'agent');
      }
    }
  } catch (error) {
    hideTypingIndicator();
    console.error('Error sending message:', error);
    // Show helpful fallback response instead of error
    const fallbackResponse = getFallbackResponse(message);
    if (fallbackResponse) {
      addMessage(fallbackResponse, 'agent');
    }
  }
}

/**
 * Show hint message for meal plan buttons
 */
function showMealHint(mealType) {
  const mealMap = {
    '🌅 Завтрак': 'завтрак',
    '🍲 Обед': 'обед',
    '🌙 Ужин': 'ужин',
    '🍿 Перекус': 'перекус'
  };
  
  const meal = mealMap[mealType] || 'питание';
  
  const hintHtml = `
    <p>Например, опишите что вы хотите купить, на сколько дней и для какого количества человек.</p>
    <p class="hint-text">"Чем подробнее запрос, тем точнее будет результат.<br>
    Собери продукты на 5 дней для семьи из 4 человек, на ${meal}, сбалансированное питание по БЖУ".</p>
  `;
  addMessageWithHtml(hintHtml, 'agent');
}

/**
 * Generate fallback response when backend API is unavailable
 */
function getFallbackResponse(message) {
  const lowerMessage = message.toLowerCase();
  
  // Check for common shopping requests
  if (lowerMessage.includes('завтрак')) {
    return 'Для завтрака рекомендую: молоко, хлопья, яйца, хлеб, сыр. Перейдите в раздел "Молочные продукты" или "Хлеб" чтобы добавить товары в корзину.';
  }
  
  if (lowerMessage.includes('обед')) {
    return 'Для обеда можно приготовить: пасту, суп, салат. Перейдите в соответствующий раздел каталога для выбора продуктов.';
  }
  
  if (lowerMessage.includes('ужин')) {
    return 'Для ужина подойдут: рыба, мясо, овощи, гарнир. Перейдите в каталог для выбора продуктов.';
  }
  
  if (lowerMessage.includes('перекус')) {
    return 'Для перекуса рекомендую: орехи, фрукты, йогурт, печенье, чипсы. Перейдите в раздел "Снеки" или "Фрукты" для выбора.';
  }
  
  if (lowerMessage.includes('молок')) {
    return 'Молоко можно найти в разделе "Молочные продукты". Перейдите в каталог и я помогу найти нужные товары.';
  }
  
  if (lowerMessage.includes('хлеб')) {
    return 'Хлеб и выпечка доступны в разделе "Хлеб". Перейдите в каталог для выбора.';
  }
  
  if (lowerMessage.includes('яиц')) {
    return 'Яйца находятся в разделе "Молочные продукты". Перейдите в каталог для выбора.';
  }

  // Default response - no auto-reply
  return '';
}

function processAIResponse(data) {
  switch (data.type) {
    case 'text':
      if (data.text) {
        addMessage(data.text, 'agent');
      }
      break;

    case 'products':
      displayProducts(data.products, data.text);
      break;

    case 'confirmation':
      displayConfirmation(data.text, data.products);
      break;

    case 'cart_action':
      handleCartActionResponse(data);
      break;

    default:
      if (data.text) {
        addMessage(data.text, 'agent');
      }
  }
}

// UI Functions
function addMessage(content, type) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message message-${type}`;

  const avatar = type === 'agent' ? AGENT_ICON : USER_ICON;

  messageDiv.innerHTML = `
    <div class="message-avatar ${type === 'agent' ? 'agent-avatar' : 'user-avatar'}">
      ${avatar}
    </div>
    <div class="message-content">
      <div class="message-bubble">
        ${typeof content === 'string' ? `<p>${escapeHtml(content)}</p>` : content}
      </div>
    </div>
  `;

  messagesContainer.appendChild(messageDiv);
  scrollToBottom();
  saveMessageToHistory(content, type);
}

function addMessageWithHtml(htmlContent, type) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message message-${type}`;

  const avatar = type === 'agent' ? AGENT_ICON : USER_ICON;

  messageDiv.innerHTML = `
    <div class="message-avatar ${type === 'agent' ? 'agent-avatar' : 'user-avatar'}">
      ${avatar}
    </div>
    <div class="message-content">
      <div class="message-bubble">
        ${htmlContent}
      </div>
    </div>
  `;

  messagesContainer.appendChild(messageDiv);
  scrollToBottom();
}

function displayProducts(products, introductoryText) {
  const container = document.createElement('div');
  
  if (introductoryText) {
    const intro = document.createElement('p');
    intro.textContent = introductoryText;
    container.appendChild(intro);
  }

  const cardsContainer = document.createElement('div');
  cardsContainer.className = 'product-cards-container';

  products.forEach(product => {
    const card = createProductCard(product);
    cardsContainer.appendChild(card);
  });

  container.appendChild(cardsContainer);
  addMessageWithHtml(container.innerHTML, 'agent');
}

function createProductCard(product) {
  const template = productCardTemplate.content.cloneNode(true);
  
  const card = template.querySelector('.product-card');
  const img = template.querySelector('.product-image');
  const name = template.querySelector('.product-name');
  const price = template.querySelector('.product-price');
  const addBtn = template.querySelector('.add-to-cart-btn');

  img.src = product.image || 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%23e0e0e0"><rect width="24" height="24"/></svg>';
  img.alt = product.name;
  name.textContent = product.name;
  price.textContent = `${product.price} ₽`;

  addBtn.addEventListener('click', () => {
    addToCart(product);
  });

  return template;
}

function displayConfirmation(text, products) {
  pendingProducts = products;
  isWaitingForConfirmation = true;

  const html = `
    <p>${escapeHtml(text)}</p>
    <div class="confirmation-buttons">
      <button class="confirm-btn">Да, добавить</button>
      <button class="cancel-btn">Отмена</button>
    </div>
  `;

  addMessageWithHtml(html, 'agent');

  // Attach event listeners to buttons
  const buttons = messagesContainer.querySelectorAll('.confirmation-buttons:last-child');
  const lastButtons = buttons[buttons.length - 1];
  
  lastButtons.querySelector('.confirm-btn').addEventListener('click', () => {
    confirmAddToCart();
  });
  
  lastButtons.querySelector('.cancel-btn').addEventListener('click', () => {
    cancelAddToCart();
  });
}

function handleConfirmationResponse(message) {
  const lowerMessage = message.toLowerCase();
  
  if (lowerMessage.includes('да') || lowerMessage.includes('yes') || lowerMessage.includes('конечно')) {
    confirmAddToCart();
  } else {
    cancelAddToCart();
  }
}

async function confirmAddToCart() {
  isWaitingForConfirmation = false;

  // Create progress message
  const progressMessageId = 'cartProgress_' + Date.now();
  showCartProgress(progressMessageId, pendingProducts);

  try {
    const response = await chrome.runtime.sendMessage({
      type: 'ADD_TO_CART',
      products: pendingProducts
    });

    if (response.success) {
      // Update UI for successful items
      updateCartProgressSuccess(progressMessageId, pendingProducts.slice(0, response.added));
      
      // Show errors for failed items
      if (response.failed > 0 && response.errors) {
        response.errors.forEach((err, index) => {
          setTimeout(() => {
            updateCartProgressItem(progressMessageId, response.added + index, 'error', `❌ ${err.product}: ${err.error || 'Недоступен'}`);
          }, (response.added + index) * 200);
        });
      }
      
      showToast(`Добавлено ${response.added} товар(а) в корзину`, 'success');
    } else {
      updateCartProgressError(progressMessageId, response.error || 'Не удалось добавить товары');
      showToast('Ошибка добавления в корзину', 'error');
    }
  } catch (error) {
    console.error('Error adding to cart:', error);
    updateCartProgressError(progressMessageId, error.message);
    showToast('Ошибка', 'error');
  }

  pendingProducts = [];
}

function cancelAddToCart() {
  isWaitingForConfirmation = false;
  pendingProducts = [];
  addMessage('Хорошо, отменил добавление в корзину.', 'agent');
}

async function addToCart(product) {
  const progressMessageId = 'cartProgress_' + Date.now();
  
  // Show single item progress
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message message-agent';
  messageDiv.id = progressMessageId;
  messageDiv.innerHTML = `
    <div class="message-avatar agent-avatar">
      ${AGENT_ICON}
    </div>
    <div class="message-content">
      <div class="message-bubble">
        <div class="cart-progress">
          <div class="progress-item pending">
            <div class="progress-icon">
              <div class="spinner"></div>
            </div>
            <span class="progress-text">Добавляю "${escapeHtml(product.name)}"...</span>
          </div>
        </div>
      </div>
    </div>
  `;
  
  messagesContainer.appendChild(messageDiv);
  scrollToBottom();

  try {
    const response = await chrome.runtime.sendMessage({
      type: 'ADD_SINGLE_TO_CART',
      product: product
    });

    if (response.success) {
      updateCartProgressItem(progressMessageId, 0, 'success');
      setTimeout(() => {
        addProgressSummary(progressMessageId, 1, 0);
      }, 300);
      showToast('Товар добавлен в корзину', 'success');
    } else {
      updateCartProgressItem(progressMessageId, 0, 'error', response.error || 'Не удалось добавить товар');
      showToast('Не удалось добавить товар', 'error');
    }
  } catch (error) {
    console.error('Error adding to cart:', error);
    updateCartProgressItem(progressMessageId, 0, 'error', error.message);
    showToast('Ошибка', 'error');
  }
}

async function handleCartActionResponse(data) {
  if (data.action === 'added') {
    addMessage(`✅ Товар "${data.productName}" добавлен в корзину!`, 'agent');
    showToast('Добавлено в корзину', 'success');
  } else if (data.action === 'error') {
    addMessage('Не удалось добавить товар в корзину.', 'agent');
    showToast('Ошибка', 'error');
  }
}

// Typing Indicator
function showTypingIndicator() {
  const indicator = document.createElement('div');
  indicator.className = 'message message-agent';
  indicator.id = 'typingIndicator';
  indicator.innerHTML = `
    <div class="message-avatar agent-avatar">
      ${AGENT_ICON}
    </div>
    <div class="message-content">
      <div class="typing-indicator">
        <span class="typing-text">Думаю</span>
        <div class="typing-dots">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </div>
  `;
  messagesContainer.appendChild(indicator);
  scrollToBottom();
}

function hideTypingIndicator() {
  const indicator = document.getElementById('typingIndicator');
  if (indicator) {
    indicator.remove();
  }
}

// Toast Notifications
function showToast(message, type = 'info') {
  let toast = document.querySelector('.toast');
  
  if (!toast) {
    toast = document.createElement('div');
    toast.className = 'toast';
    document.body.appendChild(toast);
  }

  toast.textContent = message;
  toast.className = `toast ${type}`;
  toast.classList.add('show');

  setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
}

// Utility Functions
function scrollToBottom() {
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Chat History (Storage)
function saveMessageToHistory(content, type) {
  chrome.storage.local.get(['chatHistory'], (result) => {
    const history = result.chatHistory || [];
    history.push({
      content: typeof content === 'string' ? content : '[complex content]',
      type: type,
      timestamp: Date.now()
    });

    // Keep last 50 messages
    if (history.length > 50) {
      history.shift();
    }

    chrome.storage.local.set({ chatHistory: history });
  });
}

function loadChatHistory() {
  chrome.storage.local.get(['chatHistory'], (result) => {
    const history = result.chatHistory || [];
    
    // Clear existing messages except welcome message
    const welcomeMessage = messagesContainer.querySelector('.message:first-child');
    messagesContainer.innerHTML = '';
    if (welcomeMessage) {
      messagesContainer.appendChild(welcomeMessage);
    }

    // Load history
    history.forEach(msg => {
      addMessage(msg.content, msg.type);
    });
  });
}

// Clear chat option (can be triggered from menu)
function clearChatHistory() {
  chrome.storage.local.remove(['chatHistory']);
  messagesContainer.innerHTML = '';
  location.reload();
}

// Cart Progress Functions
function showCartProgress(messageId, products) {
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message message-agent';
  messageDiv.id = messageId;

  const itemsHtml = products.map((product, index) => `
    <div class="progress-item pending" data-product-index="${index}">
      <div class="progress-icon">
        <div class="spinner"></div>
      </div>
      <span class="progress-text">Добавляю "${escapeHtml(product.name)}"...</span>
    </div>
  `).join('');

  messageDiv.innerHTML = `
    <div class="message-avatar agent-avatar">
      ${AGENT_ICON}
    </div>
    <div class="message-content">
      <div class="message-bubble">
        <div class="cart-progress">
          ${itemsHtml}
        </div>
      </div>
    </div>
  `;

  messagesContainer.appendChild(messageDiv);
  scrollToBottom();
}

function updateCartProgressItem(messageId, productIndex, status, errorMessage = null) {
  const messageElement = document.getElementById(messageId);
  if (!messageElement) return;

  const progressItem = messageElement.querySelector(`.progress-item[data-product-index="${productIndex}"]`);
  if (!progressItem) return;

  const iconContainer = progressItem.querySelector('.progress-icon');
  const progressText = progressItem.querySelector('.progress-text');

  progressItem.classList.remove('pending', 'success', 'error');
  progressItem.classList.add(status);

  if (status === 'success') {
    iconContainer.innerHTML = `
      <svg class="success-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M20 6L9 17L4 12" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    `;
    progressText.textContent = progressText.textContent.replace('Добавляю', 'Добавлено').replace('...', '');
  } else if (status === 'error') {
    iconContainer.innerHTML = `
      <svg class="error-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    `;
    if (errorMessage) {
      progressText.textContent = errorMessage;
    }
  }
}

function updateCartProgressSuccess(messageId, products) {
  products.forEach((_, index) => {
    setTimeout(() => {
      updateCartProgressItem(messageId, index, 'success');
    }, index * 200);
  });

  // Add summary after all items are processed
  setTimeout(() => {
    addProgressSummary(messageId, products.length, 0);
  }, products.length * 200 + 300);
}

function updateCartProgressError(messageId, error) {
  const messageElement = document.getElementById(messageId);
  if (!messageElement) return;

  // Mark all pending items as error
  const pendingItems = messageElement.querySelectorAll('.progress-item.pending');
  pendingItems.forEach((item, index) => {
    setTimeout(() => {
      updateCartProgressItem(messageId, index, 'error', error);
    }, index * 100);
  });
}

function addProgressSummary(messageId, successCount, errorCount) {
  const messageElement = document.getElementById(messageId);
  if (!messageElement) return;

  const cartProgress = messageElement.querySelector('.cart-progress');
  if (!cartProgress) return;

  const summaryDiv = document.createElement('div');
  summaryDiv.className = 'progress-summary';
  summaryDiv.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M9 20C9.55228 20 10 20.4477 10 21C10 21.5523 9.55228 22 9 22C8.44772 22 8 21.5523 8 21C8 20.4477 8.44772 20 9 20Z" fill="currentColor"/>
      <path d="M20 20C20.5523 20 21 20.4477 21 21C21 21.5523 20.5523 22 20 22C19.4477 22 19 21.5523 19 21C19 20.4477 19.4477 20 20 20Z" fill="currentColor"/>
      <path d="M1 1H5L7.68 14.39C7.84676 15.2233 8.27386 15.9874 8.90667 16.5839C9.53948 17.1804 10.3493 17.5817 11.22 17.73H19.41C20.2233 17.5973 20.9691 17.1903 21.5466 16.5642C22.1241 15.9381 22.5051 15.1234 22.64 14.23L23 12H6L5 7H2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <span>Готово! Добавлено ${successCount} товар(а) в корзину</span>
  `;

  cartProgress.appendChild(summaryDiv);
  scrollToBottom();
}
