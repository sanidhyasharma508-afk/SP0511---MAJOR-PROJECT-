// ============================================================================
// Gemini AI Chatbot - Frontend Component
// ============================================================================
// Pure JavaScript implementation (No external frameworks)
// Handles UI, API communication, and state management
// ============================================================================

class GeminiChatbot {
  constructor(config = {}) {
    // Configuration
    this.apiBaseUrl = config.apiBaseUrl || 'http://localhost:3000/api';
    this.enabled = false;
    this.isOpen = false;
    this.isLoading = false;

    // DOM Elements (will be initialized)
    this.container = null;
    this.chatButton = null;
    this.chatWindow = null;
    this.messagesContainer = null;
    this.inputField = null;
    this.sendButton = null;

    // Chat state
    this.messages = [];
    this.sessionId = this._generateSessionId();
    this.userType = config.userType || 'student';
    this.userContext = config.context || {};

    // Initialize
    this.init();
  }

  /**
   * Initialize the chatbot component
   */
  init() {
    this.checkStatus();
    this.createDOM();
    this.attachEventListeners();
    this.loadMessages();
  }

  /**
   * Check chatbot status from backend
   */
  async checkStatus() {
    try {
      const response = await fetch(`${this.apiBaseUrl}/gemini/status`);
      const data = await response.json();

      this.enabled = data.enabled && data.api_connected;

      if (!this.enabled) {
        console.warn('Gemini Chatbot is disabled or not configured');
      }
    } catch (error) {
      console.error('Error checking chatbot status:', error);
      this.enabled = false;
    }
  }

  /**
   * Create DOM elements for chatbot
   */
  createDOM() {
    // Main container
    this.container = document.createElement('div');
    this.container.className = 'gemini-chatbot-container';
    this.container.innerHTML = `
      <!-- Chat Button -->
      <button class="gemini-chat-button" id="gemini-chat-btn" title="Chat with Campus Bot">
        💬
      </button>

      <!-- Chat Window -->
      <div class="gemini-chat-window" id="gemini-chat-window">
        <!-- Header -->
        <div class="gemini-chat-header">
          <h3 class="gemini-chat-header-title">Campus Automation Bot</h3>
          <button class="gemini-chat-close" id="gemini-close-btn">✕</button>
        </div>

        <!-- Messages Area -->
        <div class="gemini-chat-messages" id="gemini-messages">
          <div class="gemini-empty-state">
            <div class="gemini-empty-state-icon">🤖</div>
            <div class="gemini-empty-state-text">
              Hello! I'm your Campus Bot. Ask me about schedules, attendance, events, and more.
            </div>
          </div>
        </div>

        <!-- Input Area -->
        <div class="gemini-chat-input-area">
          <textarea
            id="gemini-input"
            class="gemini-chat-input"
            placeholder="Ask me anything about campus..."
            rows="1"
          ></textarea>
          <button class="gemini-chat-send-btn" id="gemini-send-btn" title="Send message">
            →
          </button>
        </div>

        <!-- Action Buttons -->
        <div class="gemini-chat-actions">
          <button class="gemini-action-btn" id="gemini-clear-btn">Clear Chat</button>
          <button class="gemini-action-btn" id="gemini-settings-btn">⚙️ Settings</button>
        </div>
      </div>

      <!-- Settings Modal -->
      <div class="gemini-settings-modal" id="gemini-settings-modal">
        <div class="gemini-settings-content">
          <h2 class="gemini-settings-title">🔑 API Settings</h2>
          
          <div class="gemini-settings-form" id="gemini-settings-form">
            <div class="gemini-form-group">
              <label class="gemini-form-label">Gemini API Key</label>
              <input
                type="password"
                id="gemini-api-key-input"
                class="gemini-form-input"
                placeholder="Enter your Gemini API Key"
              />
              <small style="color: rgba(229, 231, 235, 0.5); font-size: 12px;">
                Get API key from <a href="https://makersuite.google.com" target="_blank" style="color: #1E3A8A;">Google AI Studio</a>
              </small>
            </div>

            <div class="gemini-form-group">
              <label class="gemini-form-label">Admin Password</label>
              <input
                type="password"
                id="gemini-admin-pwd"
                class="gemini-form-input"
                placeholder="Enter admin password"
              />
            </div>

            <div id="gemini-settings-status" class="gemini-status-message" style="display: none;"></div>

            <div class="gemini-settings-buttons">
              <button class="gemini-btn-save" id="gemini-save-key-btn">Save & Validate</button>
              <button class="gemini-btn-cancel" id="gemini-cancel-settings-btn">Cancel</button>
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(this.container);

    // Get references to key elements
    this.chatButton = document.getElementById('gemini-chat-btn');
    this.chatWindow = document.getElementById('gemini-chat-window');
    this.messagesContainer = document.getElementById('gemini-messages');
    this.inputField = document.getElementById('gemini-input');
    this.sendButton = document.getElementById('gemini-send-btn');
    this.closeButton = document.getElementById('gemini-close-btn');
    this.clearButton = document.getElementById('gemini-clear-btn');
    this.settingsButton = document.getElementById('gemini-settings-btn');
    this.settingsModal = document.getElementById('gemini-settings-modal');
    this.settingsForm = document.getElementById('gemini-settings-form');
    this.saveKeyButton = document.getElementById('gemini-save-key-btn');
    this.cancelSettingsButton = document.getElementById('gemini-cancel-settings-btn');
    this.apiKeyInput = document.getElementById('gemini-api-key-input');
    this.adminPwdInput = document.getElementById('gemini-admin-pwd');
    this.settingsStatus = document.getElementById('gemini-settings-status');
  }

  /**
   * Attach event listeners
   */
  attachEventListeners() {
    // Toggle chat window
    this.chatButton.addEventListener('click', () => this.toggleChat());

    // Close chat
    this.closeButton.addEventListener('click', () => this.closeChat());

    // Send message on button click
    this.sendButton.addEventListener('click', () => this.sendMessage());

    // Send message on Enter (not on Shift+Enter)
    this.inputField.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    // Auto-resize textarea
    this.inputField.addEventListener('input', () => {
      this.inputField.style.height = 'auto';
      this.inputField.style.height = Math.min(this.inputField.scrollHeight, 100) + 'px';
    });

    // Clear chat
    this.clearButton.addEventListener('click', () => this.clearChat());

    // Settings
    this.settingsButton.addEventListener('click', () => this.openSettings());
    this.cancelSettingsButton.addEventListener('click', () => this.closeSettings());
    this.saveKeyButton.addEventListener('click', () => this.saveAPIKey());

    // Close settings on modal background
    this.settingsModal.addEventListener('click', (e) => {
      if (e.target === this.settingsModal) {
        this.closeSettings();
      }
    });
  }

  /**
   * Toggle chat window open/closed
   */
  toggleChat() {
    if (this.isOpen) {
      this.closeChat();
    } else {
      this.openChat();
    }
  }

  /**
   * Open chat window
   */
  openChat() {
    this.isOpen = true;
    this.chatButton.classList.add('open');
    this.chatWindow.classList.add('open');
    this.inputField.focus();
  }

  /**
   * Close chat window
   */
  closeChat() {
    this.isOpen = false;
    this.chatButton.classList.remove('open');
    this.chatWindow.classList.remove('open');
  }

  /**
   * Send message to chatbot
   */
  async sendMessage() {
    const message = this.inputField.value.trim();

    if (!message || this.isLoading) {
      return;
    }

    if (!this.enabled) {
      this.showNotification('Chatbot is not configured. Please add API key in settings.', 'error');
      return;
    }

    // Add user message to UI
    this.addMessage('user', message);

    // Clear input
    this.inputField.value = '';
    this.inputField.style.height = 'auto';

    // Show loading indicator
    this.showTypingIndicator();
    this.isLoading = true;
    this.sendButton.disabled = true;

    try {
      // Make API request
      const response = await fetch(`${this.apiBaseUrl}/gemini/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          user_type: this.userType,
          context: this.userContext,
        }),
      });

      const data = await response.json();

      // Remove loading indicator
      this.removeTypingIndicator();

      if (response.ok && data.success) {
        this.addMessage('bot', data.response || 'No response');
      } else {
        this.addMessage('bot', `❌ Error: ${data.message || 'Unable to process request'}`);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      this.removeTypingIndicator();
      this.addMessage('bot', '❌ Network error. Please check your connection.');
    } finally {
      this.isLoading = false;
      this.sendButton.disabled = false;
      this.inputField.focus();
    }
  }

  /**
   * Add message to chat
   */
  addMessage(role, content) {
    // Remove empty state if this is the first message
    if (this.messages.length === 0) {
      this.messagesContainer.innerHTML = '';
    }

    this.messages.push({ role, content, timestamp: new Date() });

    const messageEl = document.createElement('div');
    messageEl.className = `gemini-message ${role}`;

    const timestamp = new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });

    messageEl.innerHTML = `
      <div class="gemini-message-bubble">${this._escapeHtml(content)}</div>
      <div class="gemini-message-time">${timestamp}</div>
    `;

    this.messagesContainer.appendChild(messageEl);
    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;

    // Save messages
    this.saveMessages();
  }

  /**
   * Show typing indicator
   */
  showTypingIndicator() {
    const typingEl = document.createElement('div');
    typingEl.className = 'gemini-message bot';
    typingEl.id = 'gemini-typing-indicator';
    typingEl.innerHTML = `
      <div class="gemini-typing">
        <div class="gemini-typing-dot"></div>
        <div class="gemini-typing-dot"></div>
        <div class="gemini-typing-dot"></div>
      </div>
    `;

    this.messagesContainer.appendChild(typingEl);
    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
  }

  /**
   * Remove typing indicator
   */
  removeTypingIndicator() {
    const typingEl = document.getElementById('gemini-typing-indicator');
    if (typingEl) {
      typingEl.remove();
    }
  }

  /**
   * Clear chat history
   */
  clearChat() {
    if (confirm('Are you sure you want to clear the chat history?')) {
      this.messages = [];
      this.messagesContainer.innerHTML = `
        <div class="gemini-empty-state">
          <div class="gemini-empty-state-icon">🤖</div>
          <div class="gemini-empty-state-text">
            Hello! I'm your Campus Bot. Ask me about schedules, attendance, events, and more.
          </div>
        </div>
      `;
      this.saveMessages();
      this.showNotification('Chat cleared', 'success');
    }
  }

  /**
   * Open settings modal
   */
  openSettings() {
    this.settingsModal.classList.add('open');
    this.apiKeyInput.focus();
  }

  /**
   * Close settings modal
   */
  closeSettings() {
    this.settingsModal.classList.remove('open');
    this.apiKeyInput.value = '';
    this.adminPwdInput.value = '';
    this.settingsStatus.style.display = 'none';
  }

  /**
   * Save and validate API key
   */
  async saveAPIKey() {
    const apiKey = this.apiKeyInput.value.trim();
    const adminPwd = this.adminPwdInput.value.trim();

    if (!apiKey || !adminPwd) {
      this.showSettingsStatus('Please fill in all fields', 'error');
      return;
    }

    this.saveKeyButton.disabled = true;
    this.showSettingsStatus('Validating API key...', 'loading');

    try {
      const response = await fetch(`${this.apiBaseUrl}/gemini/validate-key`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          api_key: apiKey,
          admin_password: adminPwd,
        }),
      });

      const data = await response.json();

      if (response.ok && data.valid) {
        // API key is valid, now update it
        const updateResponse = await fetch(`${this.apiBaseUrl}/gemini/update-key`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            api_key: apiKey,
            admin_password: adminPwd,
          }),
        });

        const updateData = await updateResponse.json();

        if (updateResponse.ok && updateData.success) {
          this.enabled = true;
          this.showSettingsStatus('✅ API Key saved and validated successfully!', 'success');
          setTimeout(() => this.closeSettings(), 1500);
        } else {
          this.showSettingsStatus('❌ Failed to save API key', 'error');
        }
      } else {
        this.showSettingsStatus(`❌ ${data.message || 'Invalid API key'}`, 'error');
      }
    } catch (error) {
      console.error('Error saving API key:', error);
      this.showSettingsStatus('❌ Network error. Please try again.', 'error');
    } finally {
      this.saveKeyButton.disabled = false;
    }
  }

  /**
   * Show settings status message
   */
  showSettingsStatus(message, type) {
    this.settingsStatus.textContent = message;
    this.settingsStatus.className = `gemini-status-message gemini-status-${type}`;
    this.settingsStatus.style.display = 'block';
  }

  /**
   * Show notification toast
   */
  showNotification(message, type = 'info') {
    // Create temporary notification
    const notification = document.createElement('div');
    notification.className = `gemini-status-message gemini-status-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      bottom: 100px;
      right: 20px;
      max-width: 300px;
      z-index: 9998;
      animation: slideIn 0.3s ease;
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
      notification.remove();
    }, 3000);
  }

  /**
   * Save messages to localStorage
   */
  saveMessages() {
    try {
      const serialized = this.messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));
      localStorage.setItem(`gemini-messages-${this.sessionId}`, JSON.stringify(serialized));
    } catch (error) {
      console.warn('Could not save messages:', error);
    }
  }

  /**
   * Load messages from localStorage
   */
  loadMessages() {
    try {
      const stored = localStorage.getItem(`gemini-messages-${this.sessionId}`);
      if (stored) {
        const loaded = JSON.parse(stored);
        loaded.forEach((m) => this.addMessage(m.role, m.content));
      }
    } catch (error) {
      console.warn('Could not load messages:', error);
    }
  }

  /**
   * Generate session ID
   */
  _generateSessionId() {
    return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Escape HTML to prevent XSS
   */
  _escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// ============================================================================
// Auto-Initialize on DOM Ready
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  // Create global instance
  window.geminiChatbot = new GeminiChatbot({
    apiBaseUrl: 'http://localhost:3000/api',
    userType: 'student',
  });

  console.log('✅ Gemini Chatbot initialized');
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = GeminiChatbot;
}

// ============================================================================
// END OF GEMINI CHATBOT
// ============================================================================
