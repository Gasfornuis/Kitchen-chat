// Simple Kitchen Chat JavaScript - Minimal but fully functional
class SimpleKitchenChat {
    constructor() {
        this.currentSubjectId = null;
        this.subjects = [];
        this.messages = [];
        this.userName = localStorage.getItem('simpleKitchenChatUserName') || '';
        this.pollInterval = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadSubjects();
        this.updateConnectionStatus(navigator.onLine);
    }

    bindEvents() {
        // Modal events
        document.getElementById('newSubjectBtn').onclick = () => this.openModal();
        document.getElementById('closeModalBtn').onclick = () => this.closeModal();
        document.getElementById('cancelBtn').onclick = () => this.closeModal();
        document.getElementById('createSubjectBtn').onclick = () => this.createSubject();
        
        // Click outside modal to close
        document.getElementById('modalOverlay').onclick = (e) => {
            if (e.target === document.getElementById('modalOverlay')) {
                this.closeModal();
            }
        };

        // Form validation
        document.getElementById('subjectTitle').oninput = () => this.validateSubjectForm();
        document.getElementById('messageInput').oninput = () => this.validateMessageInput();
        
        // Character counters
        document.getElementById('subjectTitle').oninput = (e) => {
            document.getElementById('titleCharCount').textContent = `${e.target.value.length}/100`;
        };
        
        document.getElementById('messageInput').oninput = (e) => {
            document.getElementById('charCount').textContent = `${e.target.value.length}/500`;
        };

        // Message sending
        document.getElementById('sendBtn').onclick = () => this.sendMessage();
        document.getElementById('messageInput').onkeypress = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        };

        // Refresh button
        document.getElementById('refreshBtn').onclick = () => this.refreshMessages();

        // Search
        document.getElementById('searchInput').oninput = (e) => {
            this.filterSubjects(e.target.value);
        };

        // Connection status
        window.addEventListener('online', () => {
            this.updateConnectionStatus(true);
            this.showToast('Connection restored', 'success');
            this.loadSubjects();
        });

        window.addEventListener('offline', () => {
            this.updateConnectionStatus(false);
            this.showToast('Connection lost', 'error');
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
            if (e.ctrlKey && e.key === 'n') {
                e.preventDefault();
                this.openModal();
            }
        });
    }

    // API Methods
    async apiCall(endpoint, method = 'GET', data = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(endpoint, options);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            this.showToast(`Error: ${error.message}`, 'error');
            throw error;
        }
    }

    // Load subjects from API
    async loadSubjects() {
        try {
            this.subjects = await this.apiCall('/api/subjects');
            this.renderSubjects();
        } catch (error) {
            this.renderSubjectsError();
        }
    }

    // Load messages for a subject
    async loadMessages(subjectId) {
        try {
            const container = document.getElementById('messagesContainer');
            container.innerHTML = '<p class="loading">Loading messages...</p>';
            
            this.messages = await this.apiCall(`/api/posts?SubjectId=${subjectId}`);
            this.renderMessages();
            
            // Start polling for new messages
            this.startPolling(subjectId);
            
        } catch (error) {
            this.renderMessagesError();
        }
    }

    // Start polling for new messages
    startPolling(subjectId) {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
        }
        
        this.pollInterval = setInterval(async () => {
            if (this.currentSubjectId === subjectId && navigator.onLine) {
                try {
                    const newMessages = await this.apiCall(`/api/posts?SubjectId=${subjectId}`);
                    if (newMessages.length !== this.messages.length) {
                        const oldLength = this.messages.length;
                        this.messages = newMessages;
                        this.renderMessages();
                        
                        // Show notification for new messages
                        const newCount = newMessages.length - oldLength;
                        if (newCount > 0) {
                            this.showToast(`${newCount} new message(s)`, 'success');
                        }
                    }
                } catch (error) {
                    console.warn('Polling error:', error);
                }
            }
        }, 5000); // Poll every 5 seconds
    }

    // Stop polling
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }

    // Create new subject
    async createSubject() {
        const title = document.getElementById('subjectTitle').value.trim();
        
        if (!title) {
            this.showToast('Please enter a conversation title', 'error');
            return;
        }

        let createdBy = this.userName;
        if (!createdBy) {
            createdBy = prompt('What is your name?');
            if (!createdBy) return;
            localStorage.setItem('simpleKitchenChatUserName', createdBy);
            this.userName = createdBy;
        }

        try {
            await this.apiCall('/api/subjects', 'POST', {
                Title: title,
                CreatedBy: createdBy
            });

            this.showToast('Conversation created!', 'success');
            this.closeModal();
            this.clearForm();
            
            // Reload subjects
            setTimeout(() => this.loadSubjects(), 1000);
        } catch (error) {
            console.error('Failed to create subject:', error);
        }
    }

    // Send message
    async sendMessage() {
        const content = document.getElementById('messageInput').value.trim();
        if (!content || !this.currentSubjectId) {
            return;
        }

        let postedBy = this.userName;
        if (!postedBy) {
            postedBy = prompt('What is your name?');
            if (!postedBy) return;
            localStorage.setItem('simpleKitchenChatUserName', postedBy);
            this.userName = postedBy;
        }

        try {
            // Clear input immediately for better UX
            document.getElementById('messageInput').value = '';
            document.getElementById('charCount').textContent = '0/500';
            this.validateMessageInput();

            await this.apiCall('/api/posts', 'POST', {
                Content: content,
                SubjectId: this.currentSubjectId,
                PostedBy: postedBy
            });
            
            this.showToast('Message sent!', 'success');
            
            // Reload messages immediately
            this.loadMessages(this.currentSubjectId);
            
        } catch (error) {
            console.error('Failed to send message:', error);
        }
    }

    // Subject selection
    selectSubject(subjectId, subjectTitle) {
        this.stopPolling();
        
        // Update UI
        document.querySelectorAll('.subject-item').forEach(item => {
            item.classList.remove('active');
        });
        
        const selectedItem = document.querySelector(`[data-id="${subjectId}"]`);
        if (selectedItem) {
            selectedItem.classList.add('active');
        }
        
        // Show chat area
        document.getElementById('welcomeScreen').style.display = 'none';
        document.getElementById('chatArea').style.display = 'block';
        
        // Update header
        document.getElementById('currentSubjectTitle').textContent = subjectTitle;
        
        // Load messages
        this.currentSubjectId = subjectId;
        this.loadMessages(subjectId);
    }

    // Render Methods
    renderSubjects() {
        const container = document.getElementById('subjectsList');
        
        if (this.subjects.length === 0) {
            container.innerHTML = '<p class="loading">No conversations found. Create one to get started!</p>';
            return;
        }

        container.innerHTML = this.subjects.map(subject => `
            <div class="subject-item" data-id="${subject.id}" onclick="simpleChat.selectSubject('${subject.id}', '${this.escapeHtml(subject.Title)}'">
                <h3>${this.escapeHtml(subject.Title)}</h3>
                <div class="subject-meta">
                    by ${this.escapeHtml(subject.CreatedBy)} • ${this.formatDate(subject.CreatedAt)}
                </div>
            </div>
        `).join('');
    }

    renderSubjectsError() {
        document.getElementById('subjectsList').innerHTML = '<p class="loading">Error loading conversations</p>';
    }

    renderMessages() {
        const container = document.getElementById('messagesContainer');
        
        if (this.messages.length === 0) {
            container.innerHTML = '<p class="loading">No messages yet. Start the conversation!</p>';
            return;
        }

        const scrollAtBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 10;

        container.innerHTML = this.messages.map(message => {
            const isOwn = message.PostedBy === this.userName;
            return `
                <div class="message ${isOwn ? 'own' : ''}">
                    <div class="message-header">
                        <span class="message-author">${this.escapeHtml(message.PostedBy)}</span>
                        <span class="message-time">${this.formatTime(message.CreatedAt)}</span>
                    </div>
                    <div class="message-content">${this.escapeHtml(message.Content)}</div>
                </div>
            `;
        }).join('');

        // Auto-scroll if user was at bottom
        if (scrollAtBottom || this.messages.length <= 1) {
            container.scrollTop = container.scrollHeight;
        }
    }

    renderMessagesError() {
        document.getElementById('messagesContainer').innerHTML = '<p class="loading">Error loading messages</p>';
    }

    // Modal Methods
    openModal() {
        const modal = document.getElementById('modalOverlay');
        modal.style.display = 'flex';
        
        setTimeout(() => {
            document.getElementById('subjectTitle').focus();
        }, 100);
        
        this.validateSubjectForm();
    }

    closeModal() {
        document.getElementById('modalOverlay').style.display = 'none';
    }

    clearForm() {
        document.getElementById('subjectTitle').value = '';
        document.getElementById('titleCharCount').textContent = '0/100';
        this.validateSubjectForm();
    }

    // Validation
    validateSubjectForm() {
        const title = document.getElementById('subjectTitle').value.trim();
        document.getElementById('createSubjectBtn').disabled = !title;
    }

    validateMessageInput() {
        const input = document.getElementById('messageInput');
        const sendBtn = document.getElementById('sendBtn');
        sendBtn.disabled = !input.value.trim() || !this.currentSubjectId;
    }

    // Filter subjects
    filterSubjects(searchTerm) {
        const items = document.querySelectorAll('.subject-item');
        const term = searchTerm.toLowerCase();
        
        items.forEach(item => {
            const title = item.querySelector('h3').textContent.toLowerCase();
            const meta = item.querySelector('.subject-meta').textContent.toLowerCase();
            
            if (title.includes(term) || meta.includes(term)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    }

    // Refresh messages
    refreshMessages() {
        if (this.currentSubjectId) {
            this.loadMessages(this.currentSubjectId);
            this.showToast('Messages refreshed', 'success');
        }
    }

    // Connection status
    updateConnectionStatus(isOnline) {
        const status = document.getElementById('connectionStatus');
        if (status) {
            if (isOnline) {
                status.className = 'connection-status';
                status.innerHTML = '<span>Status: Connected</span>';
            } else {
                status.className = 'connection-status disconnected';
                status.innerHTML = '<span>Status: Disconnected</span>';
            }
        }
    }

    // Toast notifications
    showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        
        container.appendChild(toast);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (container.contains(toast)) {
                container.removeChild(toast);
            }
        }, 3000);
    }

    // Utility methods
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatDate(dateString) {
        try {
            const date = new Date(dateString);
            const now = new Date();
            const diffTime = Math.abs(now - date);
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            
            if (diffDays === 1) {
                return 'Today';
            } else if (diffDays === 2) {
                return 'Yesterday';
            } else if (diffDays <= 7) {
                return `${diffDays - 1} days ago`;
            } else {
                return date.toLocaleDateString();
            }
        } catch (e) {
            return 'Unknown';
        }
    }

    formatTime(dateString) {
        try {
            const date = new Date(dateString);
            const now = new Date();
            const diffTime = Math.abs(now - date);
            const diffMinutes = Math.floor(diffTime / (1000 * 60));
            const diffHours = Math.floor(diffTime / (1000 * 60 * 60));
            
            if (diffMinutes < 1) {
                return 'Now';
            } else if (diffMinutes < 60) {
                return `${diffMinutes}m ago`;
            } else if (diffHours < 24) {
                return `${diffHours}h ago`;
            } else {
                return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            }
        } catch (e) {
            return 'Unknown';
        }
    }
}

// Initialize when page loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.simpleChat = new SimpleKitchenChat();
    });
} else {
    window.simpleChat = new SimpleKitchenChat();
}