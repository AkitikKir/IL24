const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

// DOM Elements
const messagesList = document.getElementById('messages-list');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const closeBtn = document.getElementById('close-btn');
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const saveSettingsBtn = document.getElementById('save-settings-btn');
const modelSelect = document.getElementById('model-select');
const systemPromptInput = document.getElementById('system-prompt');

// State
let selectedModel = localStorage.getItem('selectedModel') || 'yandexgpt/rc';
let systemPrompt = localStorage.getItem('systemPrompt') || 'You are a helpful assistant specialized in PC and Mobile troubleshooting.';
const userId = tg.initDataUnsafe?.user?.id || 12345; // Default for testing

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Set theme colors
    document.documentElement.style.setProperty('--bg-color', tg.themeParams.bg_color || '#ffffff');
    document.documentElement.style.setProperty('--text-color', tg.themeParams.text_color || '#000000');

    // Load initial settings
    systemPromptInput.value = systemPrompt;
    fetchModels();
    loadHistory();

    // Auto-focus input
    messageInput.focus();

    // Event Listeners
    messageInput.addEventListener('input', handleInput);
    sendBtn.addEventListener('click', sendMessage);
    closeBtn.addEventListener('click', () => tg.close());
    settingsBtn.addEventListener('click', () => settingsModal.classList.remove('hidden'));

    // Clear history button
    const clearBtn = document.getElementById('clear-btn');
    if (clearBtn) {
        clearBtn.addEventListener('click', clearHistory);
    }
    
    saveSettingsBtn.addEventListener('click', () => {
        selectedModel = modelSelect.value;
        systemPrompt = systemPromptInput.value;
        localStorage.setItem('selectedModel', selectedModel);
        localStorage.setItem('systemPrompt', systemPrompt);
        settingsModal.classList.add('hidden');
    });

    // Close modal on outside click
    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) settingsModal.classList.add('hidden');
    });

    // Handle Enter key (Shift+Enter for newline)
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Initial scroll to bottom
    scrollToBottom();
});

async function fetchModels() {
    try {
        const response = await fetch('/api/models');
        const models = await response.json();
        
        modelSelect.innerHTML = models.map(m => 
            `<option value="${m.id}" ${m.id === selectedModel ? 'selected' : ''}>${m.label}</option>`
        ).join('');
    } catch (error) {
        console.error('Failed to fetch models:', error);
        modelSelect.innerHTML = '<option value="yandexgpt/rc">YandexGPT 5.1 Pro (Default)</option>';
    }
}

async function loadHistory() {
    try {
        const response = await fetch(`/api/history?user_id=${userId}`);
        const history = await response.json();
        
        messagesList.innerHTML = '';
        history.forEach(h => {
            appendMessage(h.role === 'assistant' ? 'bot' : 'user', h.content);
        });
        scrollToBottom();
    } catch (error) {
        console.error('Failed to load history:', error);
    }
}

async function clearHistory() {
    tg.showConfirm('Are you sure you want to clear chat history?', async (ok) => {
        if (!ok) return;
        
        try {
            const response = await fetch(`/api/history/clear?user_id=${userId}`, { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                messagesList.innerHTML = '';
                if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
            }
        } catch (error) {
            console.error('Failed to clear history:', error);
        }
    });
}

function handleInput() {
    // Auto-resize textarea
    messageInput.style.height = 'auto';
    messageInput.style.height = (messageInput.scrollHeight) + 'px';

    // Toggle send button state
    if (messageInput.value.trim().length > 0) {
        sendBtn.classList.remove('disabled');
    } else {
        sendBtn.classList.add('disabled');
    }
}

async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text) return;

    // Add user message to UI
    appendMessage('user', text);

    // Clear input
    messageInput.value = '';
    handleInput();
    scrollToBottom();

    // Show typing indicator or just wait
    const typingId = showTypingIndicator();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: userId,
                prompt: text,
                model_id: selectedModel,
                system_prompt: systemPrompt
            }),
        });

        const data = await response.json();
        removeTypingIndicator(typingId);

        if (data.success) {
            appendMessage('bot', data.response);
        } else {
            appendMessage('bot', "Sorry, I'm having trouble connecting to the AI service. " + (data.response || ""));
        }
        
        scrollToBottom();
        
        // Use Telegram Haptic Feedback
        if (tg.HapticFeedback) {
            tg.HapticFeedback.notificationOccurred('success');
        }
    } catch (error) {
        removeTypingIndicator(typingId);
        console.error('Chat error:', error);
        appendMessage('bot', "An error occurred. Please try again later.");
        scrollToBottom();
    }
}

function showTypingIndicator() {
    const id = 'typing-' + Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message bot typing`;
    messageDiv.id = id;
    messageDiv.innerHTML = `<div class="message-content">...</div>`;
    messagesList.appendChild(messageDiv);
    return id;
}

function removeTypingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function appendMessage(sender, text) {
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    messageDiv.innerHTML = `
        <div class="message-content">${formatText(text)}</div>
        <div class="message-time">${time}</div>
    `;
    messagesList.appendChild(messageDiv);
}

function formatText(text) {
    // Simple markdown-like formatting for newlines and code blocks
    return text
        .replace(/\n/g, '<br>')
        .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
        .replace(/`([^`]+)`/g, '<code>$1</code>');
}

function scrollToBottom() {
    messagesList.scrollTop = messagesList.scrollHeight;
}
