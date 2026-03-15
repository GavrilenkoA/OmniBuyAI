# Perekrestok AI Assistant - Chrome Extension

AI-powered shopping assistant for Perekrestok.ru online grocery store.

## Features

- 💬 **Chat Interface** - Natural language interaction with AI assistant
- 🛒 **Smart Shopping** - Build carts from text requests like "Собери мне завтрак"
- 🔍 **Product Search** - Find products by name, category, or fuzzy matching
- ⚡ **Quick Actions** - One-click suggestions for breakfast, lunch, dinner
- 🎨 **Material Design** - Clean, modern UI with Perekrestok brand colors

## Installation

### Development Mode

1. **Clone or download** this repository

2. **Open Chrome Extensions**
   - Navigate to `chrome://extensions/` in Chrome
   - Or go to Menu → More Tools → Extensions

3. **Enable Developer Mode**
   - Toggle the "Developer mode" switch in the top right

4. **Load Unpacked Extension**
   - Click "Load unpacked"
   - Select the `chrome-extension` folder

5. **Navigate to Perekrestok**
   - Go to `https://perekrestok.ru`
   - The extension will activate on the domain

### Usage

1. Click the extension icon in the Chrome toolbar
2. Type your request in natural language (e.g., "Добавь молоко и яйца")
3. Review suggested products
4. Click "В корзину" to add items
5. Proceed to checkout on the website

## Project Structure

```
chrome-extension/
├── manifest.json          # Extension configuration (Manifest V3)
├── icons/
│   ├── icon16.png         # 16x16 icon
│   ├── icon48.png         # 48x48 icon
│   └── icon128.png        # 128x128 icon
├── popup/
│   ├── popup.html         # Chat UI structure
│   ├── popup.css          # Material Design styles
│   └── popup.js           # Chat logic and message handling
├── content/
│   └── content.js         # Page interaction, DOM parsing
├── background/
│   └── background.js      # Service worker, message routing
└── services/
    └── api.js             # Backend API client
```

## Configuration

### Backend API

Edit `services/api.js` to configure the backend URL:

```javascript
export const API_CONFIG = {
  BASE_URL: 'http://localhost:8000/api/v1', // Change for production
  TIMEOUT: 30000,
  RETRIES: 3
};
```

## Development

### Testing the Extension

1. Open `chrome://extensions/`
2. Find "Perekrestok AI Assistant"
3. Click "Inspect views: popup" to debug the popup
4. Click "Inspect views: service worker" to debug background script
5. Right-click on Perekrestok page → Inspect → Console for content script logs

### Reloading Changes

After making code changes:
1. Go to `chrome://extensions/`
2. Click the refresh icon 🔄 on the extension card
3. Re-open the popup to see changes

### Debugging Tips

- **Popup**: Right-click popup → Inspect
- **Content Script**: Page DevTools → Console (filter by content script)
- **Background**: `chrome://extensions/` → Service Worker → Inspect

## Permissions

| Permission | Purpose |
|------------|---------|
| `activeTab` | Access current tab for product parsing |
| `scripting` | Inject content scripts |
| `storage` | Save chat history locally |
| `host_permissions` | Access Perekrestok.ru pages |

## Backend Requirements

The extension expects a FastAPI backend with these endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat` | POST | Send message, get AI response |
| `/api/v1/search` | POST | Search products |
| `/api/v1/products` | GET | Get all products |
| `/api/v1/cart/add` | POST | Add product to cart |
| `/api/v1/health` | GET | Health check |

See the backend specification in `../perekrestok_ai_agent_spec.md` for details.

## Troubleshooting

### Extension not working on Perekrestok

- Ensure you're on `https://perekrestok.ru` or `https://www.perekrestok.ru`
- Check if the extension is enabled in `chrome://extensions/`
- Reload the extension

### Products not parsing

- Navigate to a catalog page with products
- Wait for the page to fully load
- Check console for parsing errors

### Backend connection errors

- Verify backend is running at the configured URL
- Check CORS settings on the backend
- Ensure network connectivity

## Browser Support

- ✅ Google Chrome (tested)
- ✅ Microsoft Edge (Chromium-based)
- ⚠️ Other Chromium browsers (untested)

## Security Notes

- Extension works **only** on Perekrestok.ru domain
- No personal data is stored or transmitted
- No access to payment information
- Chat history stored locally in Chrome storage

## License

Internal project for HAC HSE.

## Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly on Perekrestok.ru
4. Submit a pull request

---

**Note**: This is a prototype/development version. For production deployment, additional security reviews and optimizations are required.
