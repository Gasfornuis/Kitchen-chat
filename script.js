// Kitchen Chat Frontend JavaScript
class KitchenChat {
    constructor() {
        this.currentSubjectId = null;
        this.subjects = [];
        this.messages = [];
        this.userName = localStorage.getItem('kitchenChatUserName') || '';
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadSubjects();
        this.setupAutoRefresh();
    }

    bindEvents() {
        // Modal events
        document.getElementById('newSubjectBtn').addEventListener('click', () => this.openModal());
        document.getElementById('closeModalBtn').addEventListener('click', () => this.closeModal());
        document.getElementById('cancelBtn').addEventListener('click', () => this.closeModal());
        document.getElementById('createSubjectBtn').addEventListener('click', () => this.createSubject());
        
        // Modal overlay click to close
        document.getElementById('modalOverlay').addEventListener('click', (e) => {
            if (e.target === document.getElementById('modalOverlay')) {
                this.closeModal();
            }
        });

        // Form inputs
        document.getElementById('subjectTitle').addEventListener('input', () => this.validateSubjectForm());
        document.getElementById('createdBy').addEventListener('input', () => this.validateSubjectForm());
        
        // Character counters
        document.getElementById('subjectTitle').addEventListener('input', (e) => {
            document.getElementById('titleCharCount').textContent = `${e.target.value.length}/100`;
        });
        
        document.getElementById('messageInput').addEventListener('input', (e) => {
            document.getElementById('charCount').textContent = `${e.target.value.length}/500`;
            this.validateMessageInput();
        });

        // Message sending
        document.getElementById('sendBtn').addEventListener('click', () => this.sendMessage());
        document.getElementById('messageInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', () => this.refreshMessages());

        // Search functionality
        document.getElementById('searchInput').addEventListener('input', (e) => {
            this.filterSubjects(e.target.value);
        });

        // ESC key to close modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });
    }

    // API calls
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
            console.error('API call failed:', error);
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
            console.error('Failed to load subjects:', error);
            this.renderSubjectsError();
        }
    }

    // Load messages for a subject
    async loadMessages(subjectId) {
        try {
            const messagesContainer = document.getElementById('messagesContainer');
            messagesContainer.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i><span>Berichten laden...</span></div>';
            
            this.messages = await this.apiCall(`/api/posts?SubjectId=${subjectId}`);
            this.renderMessages();
        } catch (error) {
            console.error('Failed to load messages:', error);
            this.renderMessagesError();
        }
    }

    // Create new subject
    async createSubject() {
        const title = document.getElementById('subjectTitle').value.trim();
        const createdBy = document.getElementById('createdBy').value.trim();

        if (!title || !createdBy) {
            this.showToast('Vul alle velden in', 'error');
            return;
        }

        try {
            // Save user name for future use
            localStorage.setItem('kitchenChatUserName', createdBy);
            this.userName = createdBy;

            await this.apiCall('/api/subjects', 'POST', {
                Title: title,
                CreatedBy: createdBy
            });

            this.showToast('Onderwerp succesvol aangemaakt!', 'success');
            this.closeModal();
            this.clearModalForm();
            
            // Reload subjects to show the new one
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

        // Get or ask for username
        let postedBy = this.userName;
        if (!postedBy) {
            postedBy = prompt('Wat is je naam?');
            if (!postedBy) return;
            
            localStorage.setItem('kitchenChatUserName', postedBy);
            this.userName = postedBy;
        }

        try {
            // Temporarily add message to UI for instant feedback
            this.addTemporaryMessage(content, postedBy);
            document.getElementById('messageInput').value = '';
            document.getElementById('charCount').textContent = '0/500';
            this.validateMessageInput();

            await this.apiCall('/api/posts', 'POST', {
                Content: content,
                SubjectId: this.currentSubjectId,
                PostedBy: postedBy
            });

            // Refresh messages to get the actual message from server
            setTimeout(() => this.loadMessages(this.currentSubjectId), 500);
            
        } catch (error) {
            console.error('Failed to send message:', error);
            this.removeTemporaryMessage();
        }
    }

    // UI Rendering Methods
    renderSubjects() {
        const subjectsList = document.getElementById('subjectsList');
        
        if (this.subjects.length === 0) {
            subjectsList.innerHTML = `
                <div class="loading">
                    <i class="fas fa-comments"></i>
                    <span>Geen onderwerpen gevonden. Maak er een aan!</span>
                </div>
            `;
            return;
        }

        subjectsList.innerHTML = this.subjects.map(subject => `
            <div class="subject-item" data-id="${subject.id}" onclick="kitchenChat.selectSubject('${subject.id}', '${subject.Title}')">
                <h3>${this.escapeHtml(subject.Title)}</h3>
                <div class="meta">
                    <span class="creator">door ${this.escapeHtml(subject.CreatedBy)}</span>
                    <span class="date">${this.formatDate(subject.CreatedAt)}</span>
                </div>
            </div>
        `).join('');
    }

    renderSubjectsError() {
        document.getElementById('subjectsList').innerHTML = `
            <div class="loading">
                <i class="fas fa-exclamation-triangle"></i>
                <span>Fout bij laden onderwerpen</span>
            </div>
        `;
    }

    renderMessages() {
        const messagesContainer = document.getElementById('messagesContainer');
        
        if (this.messages.length === 0) {
            messagesContainer.innerHTML = `
                <div class="loading">
                    <i class="fas fa-comments"></i>
                    <span>Nog geen berichten. Stuur het eerste bericht!</span>
                </div>
            `;
            return;
        }

        // Sort messages by creation date
        const sortedMessages = this.messages.sort((a, b) => 
            new Date(a.CreatedAt) - new Date(b.CreatedAt)
        );

        messagesContainer.innerHTML = sortedMessages.map(message => {
            const isOwn = message.PostedBy === this.userName;
            return `
                <div class="message ${isOwn ? 'own' : 'other'}">
                    <div class="message-header">
                        <span class="message-author">${this.escapeHtml(message.PostedBy)}</span>
                        <span class="message-time">${this.formatTime(message.CreatedAt)}</span>
                    </div>
                    <div class="message-content">${this.escapeHtml(message.Content)}</div>
                </div>
            `;
        }).join('');

        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    renderMessagesError() {
        document.getElementById('messagesContainer').innerHTML = `
            <div class="loading">
                <i class="fas fa-exclamation-triangle"></i>
                <span>Fout bij laden berichten</span>
            </div>
        `;
    }

    addTemporaryMessage(content, author) {
        const messagesContainer = document.getElementById('messagesContainer');
        const tempMessage = document.createElement('div');
        tempMessage.className = 'message own temp-message';
        tempMessage.innerHTML = `
            <div class="message-header">
                <span class="message-author">${this.escapeHtml(author)}</span>
                <span class="message-time">Verzenden...</span>
            </div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `;
        
        messagesContainer.appendChild(tempMessage);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    removeTemporaryMessage() {
        const tempMessage = document.querySelector('.temp-message');
        if (tempMessage) {
            tempMessage.remove();
        }
    }

    // Subject selection
    selectSubject(subjectId, subjectTitle) {
        // Update UI
        document.querySelectorAll('.subject-item').forEach(item => {
            item.classList.remove('active');
        });
        
        document.querySelector(`[data-id="${subjectId}"]`).classList.add('active');
        
        // Show chat area
        document.getElementById('welcomeScreen').style.display = 'none';
        document.getElementById('chatArea').style.display = 'flex';
        
        // Update header
        document.getElementById('currentSubjectTitle').textContent = subjectTitle;
        
        // Load messages
        this.currentSubjectId = subjectId;
        this.loadMessages(subjectId);
    }

    // Modal methods
    openModal() {
        const modal = document.getElementById('modalOverlay');
        modal.classList.add('active');
        
        // Pre-fill username if available
        if (this.userName) {
            document.getElementById('createdBy').value = this.userName;
        }
        
        // Focus title input
        setTimeout(() => {
            document.getElementById('subjectTitle').focus();
        }, 100);
        
        this.validateSubjectForm();
    }

    closeModal() {
        document.getElementById('modalOverlay').classList.remove('active');
    }

    clearModalForm() {
        document.getElementById('subjectTitle').value = '';
        document.getElementById('createdBy').value = '';
        document.getElementById('titleCharCount').textContent = '0/100';
        this.validateSubjectForm();
    }

    // Validation methods
    validateSubjectForm() {
        const title = document.getElementById('subjectTitle').value.trim();
        const createdBy = document.getElementById('createdBy').value.trim();
        const createBtn = document.getElementById('createSubjectBtn');
        
        createBtn.disabled = !title || !createdBy;
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
            const creator = item.querySelector('.creator').textContent.toLowerCase();
            
            if (title.includes(term) || creator.includes(term)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    }

    // Refresh messages
    refreshMessages() {
        if (this.currentSubjectId) {
            const refreshBtn = document.getElementById('refreshBtn');
            const icon = refreshBtn.querySelector('i');
            
            icon.classList.add('fa-spin');
            
            this.loadMessages(this.currentSubjectId).finally(() => {
                setTimeout(() => {
                    icon.classList.remove('fa-spin');
                }, 500);
            });
        }
    }

    // Auto refresh setup
    setupAutoRefresh() {
        // Refresh messages every 30 seconds if a subject is selected
        setInterval(() => {
            if (this.currentSubjectId) {
                this.loadMessages(this.currentSubjectId);
            }
        }, 30000);

        // Refresh subjects every 2 minutes
        setInterval(() => {
            this.loadSubjects();
        }, 120000);
    }

    // Toast notifications
    showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        
        container.appendChild(toast);
        
        // Show toast
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Remove toast after 4 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                if (container.contains(toast)) {
                    container.removeChild(toast);
                }
            }, 300);
        }, 4000);
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
                return 'Vandaag';
            } else if (diffDays === 2) {
                return 'Gisteren';
            } else if (diffDays <= 7) {
                return `${diffDays - 1} dagen geleden`;
            } else {
                return date.toLocaleDateString('nl-NL', {
                    day: 'numeric',
                    month: 'short'
                });
            }
        } catch (e) {
            return 'Onbekend';
        }
    }

    formatTime(dateString) {
        try {
            const date = new Date(dateString);
            const now = new Date();
            const diffTime = Math.abs(now - date);
            const diffMinutes = Math.floor(diffTime / (1000 * 60));
            const diffHours = Math.floor(diffTime / (1000 * 60 * 60));
            const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
            
            if (diffMinutes < 1) {
                return 'Nu';
            } else if (diffMinutes < 60) {
                return `${diffMinutes}m geleden`;
            } else if (diffHours < 24) {
                return `${diffHours}u geleden`;
            } else if (diffDays === 1) {
                return 'Gisteren ' + date.toLocaleTimeString('nl-NL', {
                    hour: '2-digit',
                    minute: '2-digit'
                });
            } else {
                return date.toLocaleDateString('nl-NL', {
                    day: 'numeric',
                    month: 'short'
                }) + ' ' + date.toLocaleTimeString('nl-NL', {
                    hour: '2-digit',
                    minute: '2-digit'
                });
            }
        } catch (e) {
            return 'Onbekend';
        }
    }
}

// Initialize the application
const kitchenChat = new KitchenChat();

// Service Worker registration for PWA capabilities
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch(() => {
            console.log('Service Worker registration failed');
        });
    });
}

// Handle online/offline status
window.addEventListener('online', () => {
    kitchenChat.showToast('Verbinding hersteld', 'success');
    kitchenChat.loadSubjects();
    if (kitchenChat.currentSubjectId) {
        kitchenChat.loadMessages(kitchenChat.currentSubjectId);
    }
});

window.addEventListener('offline', () => {
    kitchenChat.showToast('Geen internetverbinding', 'error');
});