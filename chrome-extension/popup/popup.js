// DOM Elements
const messagesContainer = document.getElementById('messagesContainer');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');
const voiceButton = document.getElementById('voiceButton');
const quickActionBtns = document.querySelectorAll('.quick-action-btn');
const productCardTemplate = document.getElementById('productCardTemplate');

// State
let isWaitingForConfirmation = false;
let pendingProducts = [];
let recognition = null;
let isRecording = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  loadChatHistory();
  initSpeechRecognition();
});

function setupEventListeners() {
  sendButton.addEventListener('click', handleSendMessage);
  userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      handleSendMessage();
    }
  });

  voiceButton.addEventListener('click', toggleVoiceRecognition);

  quickActionBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const query = btn.dataset.query;
      userInput.value = query;
      handleSendMessage();
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
  if (!message || !message) return;

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
      addMessage(response.error || 'Произошла ошибка. Попробуйте позже.', 'agent');
    }
  } catch (error) {
    hideTypingIndicator();
    console.error('Error sending message:', error);
    addMessage('Не удалось соединиться с сервером. Проверьте подключение.', 'agent');
  }
}

function processAIResponse(data) {
  switch (data.type) {
    case 'text':
      addMessage(data.text, 'agent');
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
      addMessage(data.text || 'Понял ваш запрос.', 'agent');
  }
}

// UI Functions
function addMessage(content, type) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message message-${type}`;

  const avatar = type === 'agent' ? '🤖' : '👤';

  messageDiv.innerHTML = `
    <div class="message-avatar">${avatar}</div>
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

  const avatar = type === 'agent' ? '🤖' : '👤';

  messageDiv.innerHTML = `
    <div class="message-avatar">${avatar}</div>
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
  
  try {
    const response = await chrome.runtime.sendMessage({
      type: 'ADD_TO_CART',
      products: pendingProducts
    });

    if (response.success) {
      addMessage(`✅ Добавлено ${pendingProducts.length} товар(а) в корзину!`, 'agent');
      showToast('Товары добавлены в корзину', 'success');
    } else {
      addMessage('Не удалось добавить товары. Попробуйте вручную.', 'agent');
      showToast('Ошибка добавления в корзину', 'error');
    }
  } catch (error) {
    console.error('Error adding to cart:', error);
    addMessage('Ошибка при добавлении в корзину.', 'agent');
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
  try {
    const response = await chrome.runtime.sendMessage({
      type: 'ADD_SINGLE_TO_CART',
      product: product
    });

    if (response.success) {
      showToast('Товар добавлен в корзину', 'success');
    } else {
      showToast('Не удалось добавить товар', 'error');
    }
  } catch (error) {
    console.error('Error adding to cart:', error);
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
    <div class="message-avatar">🤖</div>
    <div class="message-content">
      <div class="typing-indicator">
        <span></span>
        <span></span>
        <span></span>
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
