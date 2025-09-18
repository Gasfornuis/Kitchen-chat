// Kitchen Chat Frontend JavaScript
class KitchenChat {
    constructor() {
        this.currentSubjectId = null;
        this.subjects = [];
        this.messages = [];
        this.userName = localStorage.getItem('kitchenChatUserName') || '';
        this.emojiPicker = new EmojiPicker();
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadSubjects();
        this.setupAutoRefresh();
        this.emojiPicker.init();
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

        // Emoji button - IMPROVED
        document.getElementById('emojiBtn').addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('Emoji button clicked'); // Debug log
            this.emojiPicker.toggle();
        });

        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', () => this.refreshMessages());

        // Search functionality
        document.getElementById('searchInput').addEventListener('input', (e) => {
            this.filterSubjects(e.target.value);
        });

        // ESC key to close modal and emoji picker
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
                this.emojiPicker.hide();
            }
        });

        // Click outside to close emoji picker - IMPROVED
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.emoji-picker') && !e.target.closest('.emoji-btn')) {
                this.emojiPicker.hide();
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
            messagesContainer.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i><span>Loading messages...</span></div>';
            
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
            this.showToast('Please fill in all fields', 'error');
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

            this.showToast('Topic created successfully!', 'success');
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
            postedBy = prompt('What is your name?');
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
                    <span>No topics found. Create one to get started!</span>
                </div>
            `;
            return;
        }

        subjectsList.innerHTML = this.subjects.map(subject => `
            <div class="subject-item" data-id="${subject.id}" onclick="kitchenChat.selectSubject('${subject.id}', '${subject.Title}')">
                <h3>${this.escapeHtml(subject.Title)}</h3>
                <div class="meta">
                    <span class="creator">by ${this.escapeHtml(subject.CreatedBy)}</span>
                    <span class="date">${this.formatDate(subject.CreatedAt)}</span>
                </div>
            </div>
        `).join('');
    }

    renderSubjectsError() {
        document.getElementById('subjectsList').innerHTML = `
            <div class="loading">
                <i class="fas fa-exclamation-triangle"></i>
                <span>Error loading topics</span>
            </div>
        `;
    }

    renderMessages() {
        const messagesContainer = document.getElementById('messagesContainer');
        
        if (this.messages.length === 0) {
            messagesContainer.innerHTML = `
                <div class="loading">
                    <i class="fas fa-comments"></i>
                    <span>No messages yet. Send the first message!</span>
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
                    <div class="message-content">${this.processEmojis(this.escapeHtml(message.Content))}</div>
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
                <span>Error loading messages</span>
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
                <span class="message-time">Sending...</span>
            </div>
            <div class="message-content">${this.processEmojis(this.escapeHtml(content))}</div>
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

    // Process emojis in messages
    processEmojis(text) {
        // This function can be extended to handle custom emoji codes if needed
        // For now, it just returns the text as-is since browsers handle Unicode emojis natively
        return text;
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
                return 'Today';
            } else if (diffDays === 2) {
                return 'Yesterday';
            } else if (diffDays <= 7) {
                return `${diffDays - 1} days ago`;
            } else {
                return date.toLocaleDateString('en-US', {
                    day: 'numeric',
                    month: 'short'
                });
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
            const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
            
            if (diffMinutes < 1) {
                return 'Now';
            } else if (diffMinutes < 60) {
                return `${diffMinutes}m ago`;
            } else if (diffHours < 24) {
                return `${diffHours}h ago`;
            } else if (diffDays === 1) {
                return 'Yesterday ' + date.toLocaleTimeString('en-US', {
                    hour: '2-digit',
                    minute: '2-digit'
                });
            } else {
                return date.toLocaleDateString('en-US', {
                    day: 'numeric',
                    month: 'short'
                }) + ' ' + date.toLocaleTimeString('en-US', {
                    hour: '2-digit',
                    minute: '2-digit'
                });
            }
        } catch (e) {
            return 'Unknown';
        }
    }
}

// Emoji Picker Class - COMPLETELY REWRITTEN FOR BETTER DEBUGGING
class EmojiPicker {
    constructor() {
        this.isVisible = false;
        this.currentCategory = 'smileys';
        this.recentEmojis = JSON.parse(localStorage.getItem('recentEmojis') || '[]');
        this.searchTimeout = null;
        
        // Emoji data - comprehensive list organized by categories
        this.emojiData = {
            smileys: [
                '😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂', '🙂', '🙃',
                '😉', '😊', '😇', '🥰', '😍', '🤩', '😘', '😗', '☺️', '😚',
                '😙', '🥲', '😋', '😛', '😜', '🤪', '😝', '🤑', '🤗', '🤭',
                '🤫', '🤔', '🤐', '🤨', '😐', '😑', '😶', '😏', '😒', '🙄',
                '😬', '🤥', '😔', '😪', '🤤', '😴', '😷', '🤒', '🤕', '🤢',
                '🤮', '🤧', '🥵', '🥶', '🥴', '😵', '🤯', '🤠', '🥳', '🥸'
            ],
            people: [
                '👶', '🧒', '👦', '👧', '🧑', '👱', '👨', '🧔', '👩', '🧓',
                '👴', '👵', '🙍', '🙎', '🙅', '🙆', '💁', '🙋', '🧏', '🙇',
                '🤦', '🤷', '👮', '🕵️', '💂', '🥷', '👷', '🤴', '👸', '👳',
                '👲', '🧕', '🤵', '👰', '🤰', '🤱', '👼', '🎅', '🤶', '🦸',
                '🦹', '🧙', '🧚', '🧛', '🧜', '🧝', '🧞', '🧟', '💆', '💇',
                '🚶', '🧍', '🏃', '🧎', '🧘', '🏋️', '🤸', '⛹️', '🤺', '🏌️'
            ],
            food: [
                '🍎', '🍐', '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '🫐', '🍈',
                '🍒', '🍑', '🥭', '🍍', '🥥', '🥝', '🍅', '🍆', '🥑', '🥦',
                '🥬', '🥒', '🌶️', '🫑', '🌽', '🥕', '🫒', '🧄', '🧅', '🥔',
                '🍠', '🥐', '🥖', '🍞', '🥨', '🥯', '🧀', '🥚', '🍳', '🧈',
                '🥞', '🧇', '🥓', '🥩', '🍗', '🍖', '🌭', '🍔', '🍟', '🍕',
                '🥪', '🥙', '🧆', '🌮', '🌯', '🫔', '🥗', '🥘', '🫕', '🍝',
                '🍜', '🍲', '🍛', '🍣', '🍱', '🥟', '🦪', '🍤', '🍙', '🍚',
                '🍘', '🍥', '🥠', '🥮', '🍢', '🍡', '🍧', '🍨', '🍦', '🥧',
                '🧁', '🍰', '🎂', '🍮', '🍭', '🍬', '🍫', '🍿', '🍩', '🍪'
            ],
            animals: [
                '🐶', '🐱', '🐭', '🐹', '🐰', '🦊', '🐻', '🐼', '🐻‍❄️', '🐨',
                '🐯', '🦁', '🐮', '🐷', '🐽', '🐸', '🐵', '🙈', '🙉', '🙊',
                '🐒', '🐔', '🐧', '🐦', '🐤', '🐣', '🐥', '🦆', '🦅', '🦉',
                '🦇', '🐺', '🐗', '🐴', '🦄', '🐝', '🪱', '🐛', '🦋', '🐌',
                '🐞', '🐜', '🪰', '🪲', '🪳', '🦟', '🦗', '🕷️', '🕸️', '🦂',
                '🐢', '🐍', '🦎', '🦖', '🦕', '🐙', '🦑', '🦐', '🦞', '🦀',
                '🐡', '🐠', '🐟', '🐬', '🐳', '🐋', '🦈', '🐊', '🐅', '🐆',
                '🦓', '🦍', '🦧', '🐘', '🦣', '🦏', '🦛', '🦌', '🐪', '🐫'
            ],
            activities: [
                '⚽', '🏀', '🏈', '⚾', '🥎', '🎾', '🏐', '🏉', '🥏', '🎱',
                '🪀', '🏓', '🏸', '🏒', '🏑', '🥍', '🏏', '🪃', '🥅', '⛳',
                '🪁', '🏹', '🎣', '🤿', '🥊', '🥋', '🎽', '🛹', '🛷', '⛸️',
                '🥌', '🎿', '⛷️', '🏂', '🪂', '🏋️‍♀️', '🏋️‍♂️', '🤸‍♀️', '🤸‍♂️', '⛹️‍♀️',
                '⛹️‍♂️', '🤺', '🤾‍♀️', '🤾‍♂️', '🏌️‍♀️', '🏌️‍♂️', '🏇', '🧘‍♀️', '🧘‍♂️', '🏄‍♀️',
                '🏄‍♂️', '🏊‍♀️', '🏊‍♂️', '🤽‍♀️', '🤽‍♂️', '🚣‍♀️', '🚣‍♂️', '🧗‍♀️', '🧗‍♂️', '🚵‍♀️'
            ],
            objects: [
                '⌚', '📱', '📲', '💻', '⌨️', '🖥️', '🖨️', '🖱️', '🖲️', '🕹️',
                '🗜️', '💽', '💾', '💿', '📀', '📼', '📷', '📸', '📹', '🎥',
                '📽️', '🎞️', '📞', '☎️', '📟', '📠', '📺', '📻', '🎙️', '🎚️',
                '🎛️', '🧭', '⏱️', '⏲️', '⏰', '🕰️', '⏳', '⌛', '📡', '🔋',
                '🔌', '💡', '🔦', '🕯️', '🪔', '🧯', '🛢️', '💸', '💵', '💴',
                '💶', '💷', '🪙', '💰', '💳', '💎', '⚖️', '🪜', '🧰', '🔧',
                '🔨', '⚒️', '🛠️', '⛏️', '🪚', '🔩', '⚙️', '🪤', '🧱', '⛓️'
            ],
            symbols: [
                '❤️', '🧡', '💛', '💚', '💙', '💜', '🖤', '🤍', '🤎', '💔',
                '❣️', '💕', '💞', '💓', '💗', '💖', '💘', '💝', '💟', '☮️',
                '✝️', '☪️', '🕉️', '☸️', '✡️', '🔯', '🕎', '☯️', '☦️', '🛐',
                '⛎', '♈', '♉', '♊', '♋', '♌', '♍', '♎', '♏', '♐',
                '♑', '♒', '♓', '🆔', '⚛️', '🉑', '☢️', '☣️', '📴', '📳',
                '🈶', '🈚', '🈸', '🈺', '🈷️', '✴️', '🆚', '💮', '🉐', '㊙️',
                '㊗️', '🈴', '🈵', '🈹', '🈲', '🅰️', '🅱️', '🆎', '🆑', '🅾️',
                '🆘', '❌', '⭕', '🛑', '⛔', '📛', '🚫', '💯', '💢', '♨️'
            ]
        };
    }

    init() {
        console.log('EmojiPicker init started'); // Debug log
        this.bindEvents();
        this.renderCategories();
        this.renderEmojis(this.currentCategory);
        this.renderRecentEmojis();
        console.log('EmojiPicker init completed'); // Debug log
    }

    bindEvents() {
        console.log('EmojiPicker bindEvents started'); // Debug log
        
        // Category buttons
        document.querySelectorAll('.emoji-category').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const category = e.currentTarget.dataset.category;
                console.log('Category selected:', category); // Debug log
                this.selectCategory(category);
            });
        });

        // Emoji search
        const emojiSearch = document.getElementById('emojiSearch');
        if (emojiSearch) {
            emojiSearch.addEventListener('input', (e) => {
                clearTimeout(this.searchTimeout);
                this.searchTimeout = setTimeout(() => {
                    console.log('Searching emojis:', e.target.value); // Debug log
                    this.searchEmojis(e.target.value);
                }, 300);
            });
        } else {
            console.warn('Emoji search input not found!'); // Debug log
        }
        
        console.log('EmojiPicker bindEvents completed'); // Debug log
    }

    toggle() {
        console.log('EmojiPicker toggle called, current state:', this.isVisible); // Debug log
        const picker = document.getElementById('emojiPicker');
        
        if (!picker) {
            console.error('Emoji picker element not found!'); // Debug log
            return;
        }
        
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }

    show() {
        console.log('EmojiPicker show called'); // Debug log
        const picker = document.getElementById('emojiPicker');
        const emojiBtn = document.getElementById('emojiBtn');
        
        if (!picker) {
            console.error('Emoji picker element not found in show()!'); // Debug log
            return;
        }
        
        // Force display and visibility
        picker.style.display = 'flex';
        picker.style.visibility = 'visible';
        picker.style.opacity = '1';
        picker.classList.add('show');
        
        if (emojiBtn) {
            emojiBtn.classList.add('active');
        }
        
        this.isVisible = true;
        
        console.log('EmojiPicker should now be visible'); // Debug log
        console.log('Picker element:', picker); // Debug log
        console.log('Picker computed style:', window.getComputedStyle(picker)); // Debug log
        
        // Make sure we have emojis rendered
        this.renderEmojis(this.currentCategory);
        
        // Focus search input
        setTimeout(() => {
            const searchInput = document.getElementById('emojiSearch');
            if (searchInput) {
                searchInput.focus();
            }
        }, 100);
    }

    hide() {
        console.log('EmojiPicker hide called'); // Debug log
        const picker = document.getElementById('emojiPicker');
        const emojiBtn = document.getElementById('emojiBtn');
        
        if (!picker) {
            console.error('Emoji picker element not found in hide()!'); // Debug log
            return;
        }
        
        picker.classList.remove('show');
        picker.style.display = 'none';
        
        if (emojiBtn) {
            emojiBtn.classList.remove('active');
        }
        
        this.isVisible = false;
        
        // Clear search
        const searchInput = document.getElementById('emojiSearch');
        if (searchInput) {
            searchInput.value = '';
            this.renderEmojis(this.currentCategory);
        }
        
        console.log('EmojiPicker hidden'); // Debug log
    }

    selectCategory(category) {
        console.log('Selecting category:', category); // Debug log
        
        // Update active category button
        document.querySelectorAll('.emoji-category').forEach(btn => {
            btn.classList.remove('active');
        });
        
        const activeBtn = document.querySelector(`[data-category="${category}"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
        }
        
        this.currentCategory = category;
        this.renderEmojis(category);
    }

    renderEmojis(category) {
        console.log('Rendering emojis for category:', category); // Debug log
        const grid = document.getElementById('emojiGrid');
        
        if (!grid) {
            console.error('Emoji grid element not found!'); // Debug log
            return;
        }
        
        const emojis = this.emojiData[category] || [];
        console.log('Emojis to render:', emojis.length); // Debug log
        
        grid.innerHTML = emojis.map(emoji => `
            <button class="emoji-item" data-emoji="${emoji}" onclick="kitchenChat.emojiPicker.selectEmoji('${emoji}')">
                ${emoji}
            </button>
        `).join('');
        
        console.log('Emojis rendered, grid innerHTML length:', grid.innerHTML.length); // Debug log
    }

    searchEmojis(query) {
        console.log('Searching emojis with query:', query); // Debug log
        
        if (!query.trim()) {
            this.renderEmojis(this.currentCategory);
            return;
        }

        const grid = document.getElementById('emojiGrid');
        if (!grid) {
            console.error('Emoji grid not found for search!'); // Debug log
            return;
        }
        
        const allEmojis = Object.values(this.emojiData).flat();
        
        // Simple search - you could enhance this with emoji names/keywords
        const filteredEmojis = allEmojis.filter(emoji => {
            // This is a basic implementation - in a real app you'd want emoji name matching
            return emoji.includes(query) || this.getEmojiKeywords(emoji).some(keyword => 
                keyword.toLowerCase().includes(query.toLowerCase())
            );
        });
        
        console.log('Filtered emojis:', filteredEmojis.length); // Debug log
        
        grid.innerHTML = filteredEmojis.slice(0, 64).map(emoji => `
            <button class="emoji-item" data-emoji="${emoji}" onclick="kitchenChat.emojiPicker.selectEmoji('${emoji}')">
                ${emoji}
            </button>
        `).join('');
    }

    getEmojiKeywords(emoji) {
        // Basic emoji keyword mapping - this could be much more comprehensive
        const keywords = {
            '😀': ['happy', 'smile', 'joy'],
            '😍': ['love', 'heart', 'eyes'],
            '🍕': ['pizza', 'food', 'slice'],
            '🎉': ['party', 'celebration', 'confetti'],
            '❤️': ['heart', 'love', 'red'],
            '🔥': ['fire', 'hot', 'flame'],
            '👍': ['thumbs', 'up', 'good', 'like'],
            '😂': ['laugh', 'cry', 'funny', 'lol'],
            '🤔': ['think', 'hmm', 'wondering'],
            '💯': ['hundred', 'perfect', 'score']
        };
        return keywords[emoji] || [];
    }

    selectEmoji(emoji) {
        console.log('Emoji selected:', emoji); // Debug log
        
        const messageInput = document.getElementById('messageInput');
        if (!messageInput) {
            console.error('Message input not found!'); // Debug log
            return;
        }
        
        const cursorPos = messageInput.selectionStart;
        const textBefore = messageInput.value.substring(0, cursorPos);
        const textAfter = messageInput.value.substring(messageInput.selectionEnd);
        
        // Insert emoji at cursor position
        messageInput.value = textBefore + emoji + textAfter;
        
        // Update cursor position
        const newCursorPos = cursorPos + emoji.length;
        messageInput.setSelectionRange(newCursorPos, newCursorPos);
        
        // Update character count
        const charCount = document.getElementById('charCount');
        if (charCount) {
            charCount.textContent = `${messageInput.value.length}/500`;
        }
        
        // Validate input
        kitchenChat.validateMessageInput();
        
        // Add to recent emojis
        this.addToRecent(emoji);
        
        // Focus back on input
        messageInput.focus();
        
        // Hide picker on mobile
        if (window.innerWidth <= 768) {
            this.hide();
        }
        
        console.log('Emoji inserted successfully'); // Debug log
    }

    addToRecent(emoji) {
        // Remove if already exists
        this.recentEmojis = this.recentEmojis.filter(e => e !== emoji);
        
        // Add to beginning
        this.recentEmojis.unshift(emoji);
        
        // Keep only last 10
        this.recentEmojis = this.recentEmojis.slice(0, 10);
        
        // Save to localStorage
        localStorage.setItem('recentEmojis', JSON.stringify(this.recentEmojis));
        
        // Re-render recent emojis
        this.renderRecentEmojis();
    }

    renderRecentEmojis() {
        const container = document.getElementById('recentEmojiList');
        
        if (!container) {
            console.warn('Recent emoji container not found!'); // Debug log
            return;
        }
        
        if (this.recentEmojis.length === 0) {
            container.innerHTML = '<span style="color: #a0aec0; font-size: 0.8rem;">None yet</span>';
            return;
        }
        
        container.innerHTML = this.recentEmojis.map(emoji => `
            <button class="recent-emoji" data-emoji="${emoji}" onclick="kitchenChat.emojiPicker.selectEmoji('${emoji}')">
                ${emoji}
            </button>
        `).join('');
    }

    renderCategories() {
        // This method could be used to dynamically render categories if needed
        // For now, categories are defined in HTML
        console.log('Categories rendered (using HTML structure)'); // Debug log
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
    kitchenChat.showToast('Connection restored', 'success');
    kitchenChat.loadSubjects();
    if (kitchenChat.currentSubjectId) {
        kitchenChat.loadMessages(kitchenChat.currentSubjectId);
    }
});

window.addEventListener('offline', () => {
    kitchenChat.showToast('No internet connection', 'error');
});

// Debug function to test emoji picker manually
window.debugEmojiPicker = () => {
    console.log('Manual emoji picker test');
    const picker = document.getElementById('emojiPicker');
    console.log('Picker element:', picker);
    if (picker) {
        picker.style.display = 'flex';
        picker.style.visibility = 'visible';
        picker.style.opacity = '1';
        picker.style.zIndex = '99999';
        picker.style.position = 'fixed';
        picker.style.top = '100px';
        picker.style.right = '100px';
        picker.style.background = 'white';
        picker.style.border = '2px solid red';
        console.log('Picker should be visible now');
    }
};