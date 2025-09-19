// Kitchen Chat Frontend JavaScript with Real-time Synchronization
class KitchenChat {
    constructor() {
        this.currentSubjectId = null;
        this.subjects = [];
        this.messages = [];
        this.userName = localStorage.getItem('kitchenChatUserName') || '';
        this.emojiPicker = new EmojiPicker();
        this.isInitialized = false;
        this.authManager = null;
        this.authUI = null;
        this.messagePollingInterval = null;
        this.lastMessageTimestamp = null;
        this.init();
    }

    async init() {
        try {
            // Show loading screen initially
            this.showLoadingScreen();
            
            // Wait a bit for Firebase to load
            await this.delay(1000);
            
            // Initialize authentication system
            await this.initAuth();
            
            // Wait a bit more for a nice loading experience
            await this.delay(500);
            
            // Initialize components
            this.bindEvents();
            this.emojiPicker.init();
            
            // Mark as initialized
            this.isInitialized = true;
            
            // Hide loading screen and show app
            this.hideLoadingScreen();
            
            console.log('🚀 Kitchen Chat with Real-time Sync initialized successfully!');
        } catch (error) {
            console.error('Failed to initialize Kitchen Chat:', error);
            this.hideLoadingScreen();
            this.showToast('Failed to load Kitchen Chat. Please refresh the page.', 'error');
        }
    }

    async initAuth() {
        try {
            // Check if Firebase is loaded
            if (typeof firebase === 'undefined') {
                console.warn('Firebase not loaded, running in demo mode');
                await this.loadSubjects(); // Load subjects without auth
                return;
            }
            
            // Initialize Auth Manager
            this.authManager = new AuthManager();
            
            // Initialize Auth UI
            this.authUI = new AuthUI(this.authManager);
            
            // Listen for auth state changes
            this.authManager.addAuthStateListener((user) => {
                this.handleAuthStateChange(user);
            });
            
            // Start activity tracking if user is logged in
            if (this.authManager.isAuthenticated()) {
                this.authManager.startActivityTracking();
            }
            
        } catch (error) {
            console.error('Auth initialization failed:', error);
            // Continue without auth - fallback to old behavior
            await this.loadSubjects();
        }
    }

    handleAuthStateChange(user) {
        if (user) {
            // User is logged in
            console.log('User logged in:', user.displayName);
            this.userName = user.displayName || user.email || 'User';
            localStorage.setItem('kitchenChatUserName', this.userName);
            
            // Load subjects now that user is authenticated
            this.loadSubjects();
            
            // Start activity tracking
            if (this.authManager) {
                this.authManager.startActivityTracking();
            }
        } else {
            // User is logged out
            console.log('User logged out');
            this.userName = '';
            localStorage.removeItem('kitchenChatUserName');
            
            // Clear current chat
            this.currentSubjectId = null;
            this.subjects = [];
            this.messages = [];
            
            // Stop polling
            this.stopMessagePolling();
            
            // Show welcome screen
            document.getElementById('welcomeScreen').style.display = 'block';
            document.getElementById('chatArea').style.display = 'none';
            
            // Clear subjects list
            document.getElementById('subjectsList').innerHTML = `
                <div class="loading">
                    <i class="fas fa-sign-in-alt"></i>
                    <span>Please sign in to access conversations</span>
                </div>
            `;
            
            // Stop activity tracking
            if (this.authManager) {
                this.authManager.stopActivityTracking();
            }
        }
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    showLoadingScreen() {
        const loadingScreen = document.getElementById('loadingScreen');
        const appContainer = document.getElementById('appContainer');
        
        if (loadingScreen) {
            loadingScreen.classList.remove('hidden');
        }
        
        if (appContainer) {
            appContainer.classList.remove('loaded');
        }
    }

    hideLoadingScreen() {
        const loadingScreen = document.getElementById('loadingScreen');
        const appContainer = document.getElementById('appContainer');
        
        if (loadingScreen) {
            loadingScreen.classList.add('hidden');
            // Remove from DOM after animation
            setTimeout(() => {
                if (loadingScreen.parentNode) {
                    loadingScreen.style.display = 'none';
                }
            }, 800);
        }
        
        if (appContainer) {
            appContainer.classList.add('loaded');
        }
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

        // Emoji button
        document.getElementById('emojiBtn').addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.emojiPicker.toggle();
        });

        // Emoji picker close button
        const emojiCloseBtn = document.getElementById('emojiClose');
        if (emojiCloseBtn) {
            emojiCloseBtn.addEventListener('click', () => {
                this.emojiPicker.hide();
            });
        }

        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', () => this.refreshMessages());

        // Search functionality
        document.getElementById('searchInput').addEventListener('input', (e) => {
            this.filterSubjects(e.target.value);
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // ESC key to close modal and emoji picker
            if (e.key === 'Escape') {
                this.closeModal();
                this.emojiPicker.hide();
            }
            
            // Ctrl+K to focus search
            if (e.ctrlKey && e.key === 'k') {
                e.preventDefault();
                const searchInput = document.getElementById('searchInput');
                if (searchInput) {
                    searchInput.focus();
                }
            }
            
            // Ctrl+N to create new topic
            if (e.ctrlKey && e.key === 'n') {
                e.preventDefault();
                this.openModal();
            }
        });

        // Click outside to close emoji picker
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.emoji-picker') && !e.target.closest('.emoji-btn')) {
                this.emojiPicker.hide();
            }
        });

        // Handle connection status
        this.updateConnectionStatus(navigator.onLine);
        
        window.addEventListener('online', () => {
            this.updateConnectionStatus(true);
            this.showToast('Connection restored', 'success');
            if (this.isInitialized) {
                this.loadSubjects();
                if (this.currentSubjectId) {
                    this.loadMessages(this.currentSubjectId);
                }
            }
        });

        window.addEventListener('offline', () => {
            this.updateConnectionStatus(false);
            this.showToast('No internet connection', 'error');
        });
    }

    updateConnectionStatus(isOnline) {
        const connectionStatus = document.getElementById('connectionStatus');
        const statusText = connectionStatus?.querySelector('.status-text');
        
        if (connectionStatus) {
            if (isOnline) {
                connectionStatus.classList.remove('disconnected');
                if (statusText) statusText.textContent = 'Connected - Real-time';
            } else {
                connectionStatus.classList.add('disconnected');
                if (statusText) statusText.textContent = 'Disconnected';
            }
        }
    }

    // API calls with authentication
    async apiCall(endpoint, method = 'GET', data = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        // Add auth token if available
        if (this.authManager && this.authManager.isAuthenticated()) {
            try {
                const token = await this.authManager.getIdToken();
                if (token) {
                    options.headers['Authorization'] = `Bearer ${token}`;
                }
            } catch (error) {
                console.warn('Failed to get auth token:', error);
            }
        }

        if (data) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(endpoint, options);
            
            if (!response.ok) {
                if (response.status === 401) {
                    // Unauthorized - user needs to log in
                    if (this.authManager) {
                        await this.authManager.signOut();
                    }
                    throw new Error('Authentication required');
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API call failed:', error);
            if (this.isInitialized) {
                this.showToast(`Error: ${error.message}`, 'error');
            }
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

    // Load messages for a subject with real-time polling
    async loadMessages(subjectId) {
        try {
            const messagesContainer = document.getElementById('messagesContainer');
            messagesContainer.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i><span>Loading messages...</span></div>';
            
            // Stop previous polling
            this.stopMessagePolling();
            
            // Load initial messages
            this.messages = await this.apiCall(`/api/posts?SubjectId=${subjectId}`);
            this.renderMessages();
            
            // Start real-time polling
            this.startMessagePolling(subjectId);
            
        } catch (error) {
            console.error('Failed to load messages:', error);
            this.renderMessagesError();
        }
    }

    // Start real-time message polling
    startMessagePolling(subjectId) {
        if (this.messagePollingInterval) {
            clearInterval(this.messagePollingInterval);
        }
        
        this.messagePollingInterval = setInterval(async () => {
            try {
                if (this.currentSubjectId === subjectId && navigator.onLine) {
                    const newMessages = await this.apiCall(`/api/posts?SubjectId=${subjectId}`);
                    
                    // Check if there are new messages
                    if (newMessages.length !== this.messages.length) {
                        const oldCount = this.messages.length;
                        this.messages = newMessages;
                        this.renderMessages();
                        
                        // Show notification for new messages from others
                        const newCount = newMessages.length;
                        if (newCount > oldCount) {
                            const newMessagesFromOthers = newMessages.slice(oldCount).filter(msg => 
                                msg.PostedBy !== this.userName
                            );
                            
                            if (newMessagesFromOthers.length > 0) {
                                this.showToast(`${newMessagesFromOthers.length} new message(s) received!`, 'success');
                                
                                // Play notification sound (optional)
                                this.playNotificationSound();
                            }
                        }
                    }
                }
            } catch (error) {
                console.warn('Polling error:', error);
            }
        }, 2000); // Poll every 2 seconds
    }

    // Stop message polling
    stopMessagePolling() {
        if (this.messagePollingInterval) {
            clearInterval(this.messagePollingInterval);
            this.messagePollingInterval = null;
        }
    }

    // Play notification sound
    playNotificationSound() {
        try {
            const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwaSDmP1O/LeSsFJHfH8N2OQAkTXbTp66hWEwlFnt/yv2wbSzqP0+7NeSsFJHfH8N2OPwkTXbTp66pVFApGnt/yv2waSDqP0+7NeSsFJHfH8N2OPwkTXbTo66pWEgpGnt/xv2waSDqP0+7NeSsFJHbH8N2OPwkTXbXo66pWEgpGnt/xv2waSDqP0+7NeSsFJHbH8N2OPwkTXbXo66pWEgpGnl/x');
            audio.volume = 0.3;
            audio.play().catch(() => {}); // Ignore errors
        } catch (error) {
            // Ignore audio errors
        }
    }

    // Create new subject
    async createSubject() {
        const title = document.getElementById('subjectTitle').value.trim();
        
        if (!title) {
            this.showToast('Please enter a conversation title', 'error');
            return;
        }

        // Get creator name from auth or fallback
        let createdBy = this.userName;
        if (!createdBy) {
            if (this.authManager && this.authManager.isAuthenticated()) {
                createdBy = this.authManager.getUserDisplayName();
            } else {
                createdBy = prompt('What is your name?');
                if (!createdBy) return;
                localStorage.setItem('kitchenChatUserName', createdBy);
                this.userName = createdBy;
            }
        }

        try {
            await this.apiCall('/api/subjects', 'POST', {
                Title: title,
                CreatedBy: createdBy
            });

            this.showToast('Conversation created successfully!', 'success');
            this.closeModal();
            this.clearModalForm();
            
            // Reload subjects to show the new one
            setTimeout(() => this.loadSubjects(), 1000);
        } catch (error) {
            console.error('Failed to create subject:', error);
        }
    }

    // Enhanced send message with media support
    async sendMessage(messageData = null) {
        let content, messageType = 'text', mediaData = null;
        
        if (messageData) {
            // Sending media message
            content = messageData.content || '';
            messageType = messageData.type;
            mediaData = messageData.data;
        } else {
            // Regular text message
            content = document.getElementById('messageInput').value.trim();
            if (!content || !this.currentSubjectId) {
                return;
            }
        }

        // Get poster name from auth or fallback
        let postedBy = this.userName;
        if (!postedBy) {
            if (this.authManager && this.authManager.isAuthenticated()) {
                postedBy = this.authManager.getUserDisplayName();
            } else {
                postedBy = prompt('What is your name?');
                if (!postedBy) return;
                localStorage.setItem('kitchenChatUserName', postedBy);
                this.userName = postedBy;
            }
        }

        try {
            // Create message object with media support
            const messagePayload = {
                Content: content,
                SubjectId: this.currentSubjectId,
                PostedBy: postedBy,
                MessageType: messageType,
                MediaData: mediaData
            };

            // Clear input for text messages
            if (messageType === 'text') {
                document.getElementById('messageInput').value = '';
                document.getElementById('charCount').textContent = '0/500';
                this.validateMessageInput();
            }

            // Send to backend
            const result = await this.apiCall('/api/posts', 'POST', messagePayload);
            
            // Show success message
            if (messageType === 'text') {
                this.showToast('Message sent!', 'success');
            } else {
                this.showToast(`${messageType} message sent! 🚀`, 'success');
            }
            
            // Immediately refresh messages to show the sent message
            setTimeout(() => {
                if (this.currentSubjectId) {
                    this.loadMessages(this.currentSubjectId);
                }
            }, 500);
            
        } catch (error) {
            console.error('Failed to send message:', error);
            this.showToast('Failed to send message. Please try again.', 'error');
        }
    }

    // Enhanced renderMessages with media support
    renderMessages() {
        const messagesContainer = document.getElementById('messagesContainer');
        
        if (this.messages.length === 0) {
            messagesContainer.innerHTML = `
                <div class="loading">
                    <i class="fas fa-comments"></i>
                    <span>No messages yet. Start the conversation!</span>
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
            
            // Render different message types
            switch (message.MessageType) {
                case 'voice':
                    return this.renderVoiceMessage(message, isOwn);
                case 'image':
                    return this.renderImageMessage(message, isOwn);
                case 'file':
                    return this.renderFileMessage(message, isOwn);
                default:
                    return this.renderTextMessage(message, isOwn);
            }
        }).join('');

        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        // Add animation classes for new messages
        setTimeout(() => {
            const newMessages = messagesContainer.querySelectorAll('.message:not(.animated)');
            newMessages.forEach((msg, index) => {
                msg.classList.add('animated');
                msg.style.animationDelay = `${index * 0.1}s`;
            });
        }, 100);
    }

    renderTextMessage(message, isOwn) {
        return `
            <div class="message ${isOwn ? 'own' : 'other'}">
                <div class="message-header">
                    <span class="message-author">${this.escapeHtml(message.PostedBy)}</span>
                    <span class="message-time">${this.formatTime(message.CreatedAt)}</span>
                </div>
                <div class="message-content">${this.processEmojis(this.escapeHtml(message.Content))}</div>
                <div class="message-reactions"></div>
            </div>
        `;
    }

    renderVoiceMessage(message, isOwn) {
        const mediaData = message.MediaData || {};
        return `
            <div class="message ${isOwn ? 'own' : 'other'}">
                <div class="message-header">
                    <span class="message-author">${this.escapeHtml(message.PostedBy)}</span>
                    <span class="message-time">${this.formatTime(message.CreatedAt)}</span>
                </div>
                <div class="voice-message" data-audio-url="${message.AttachmentUrl || ''}">
                    <button class="voice-play-btn" onclick="kitchenChat.playVoiceMessage(this)">
                        <i class="fas fa-play"></i>
                    </button>
                    <div class="voice-waveform">
                        ${(mediaData.waveform || []).map((height, index) => 
                            `<div class="voice-waveform-bar" style="height: ${height}%"></div>`
                        ).join('')}
                    </div>
                    <span class="voice-duration">${mediaData.duration || '0:05'}</span>
                </div>
                ${message.Content ? `<div class="message-content">${this.escapeHtml(message.Content)}</div>` : ''}
                <div class="message-reactions"></div>
            </div>
        `;
    }

    renderImageMessage(message, isOwn) {
        const mediaData = message.MediaData || {};
        const imageUrl = message.AttachmentUrl || '#';
        return `
            <div class="message ${isOwn ? 'own' : 'other'}">
                <div class="message-header">
                    <span class="message-author">${this.escapeHtml(message.PostedBy)}</span>
                    <span class="message-time">${this.formatTime(message.CreatedAt)}</span>
                </div>
                <div class="image-message" onclick="kitchenChat.openImageInLightbox('${imageUrl}', '${mediaData.name || 'Image'}')">
                    <img class="message-image" src="${imageUrl}" alt="${mediaData.name || 'Image'}" loading="lazy">
                </div>
                ${message.Content ? `<div class="message-content">${this.escapeHtml(message.Content)}</div>` : ''}
                <div class="message-reactions"></div>
            </div>
        `;
    }

    renderFileMessage(message, isOwn) {
        const mediaData = message.MediaData || {};
        return `
            <div class="message ${isOwn ? 'own' : 'other'}">
                <div class="message-header">
                    <span class="message-author">${this.escapeHtml(message.PostedBy)}</span>
                    <span class="message-time">${this.formatTime(message.CreatedAt)}</span>
                </div>
                <div class="file-message" onclick="kitchenChat.downloadFile('${mediaData.name || 'file'}', '${message.AttachmentUrl || '#'}')">
                    <div class="file-icon">
                        <i class="${mediaData.icon || 'fas fa-file'}"></i>
                    </div>
                    <div class="file-info">
                        <div class="file-name">${mediaData.name || 'Unknown File'}</div>
                        <div class="file-size">${mediaData.size || '0 KB'} • ${mediaData.extension || 'FILE'}</div>
                    </div>
                </div>
                ${message.Content ? `<div class="message-content">${this.escapeHtml(message.Content)}</div>` : ''}
                <div class="message-reactions"></div>
            </div>
        `;
    }

    // Media message handlers
    playVoiceMessage(button) {
        const voiceMessage = button.closest('.voice-message');
        const audioUrl = voiceMessage.dataset.audioUrl;
        
        if (!audioUrl || audioUrl === '' || audioUrl === '#') {
            this.showToast('Voice message not available (demo mode)', 'info');
            return;
        }
        
        const audio = new Audio(audioUrl);
        const icon = button.querySelector('i');
        
        if (audio.paused) {
            audio.play();
            icon.className = 'fas fa-pause';
            
            audio.onended = () => {
                icon.className = 'fas fa-play';
            };
        } else {
            audio.pause();
            icon.className = 'fas fa-play';
        }
    }

    openImageInLightbox(src, name) {
        if (window.advancedComm && window.advancedComm.openLightbox) {
            const img = document.createElement('img');
            img.src = src;
            img.alt = name;
            window.advancedComm.openLightbox(img);
        } else {
            // Fallback: open in new tab
            window.open(src, '_blank');
        }
    }

    downloadFile(name, url) {
        if (url === '#') {
            this.showToast(`File download: ${name} (demo mode)`, 'info');
            return;
        }
        
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    // Integration with advanced features
    sendVoiceMessage(voiceData) {
        const messageData = {
            content: `🎙️ Voice message (${voiceData.duration})`,
            type: 'voice',
            data: voiceData
        };
        this.sendMessage(messageData);
    }

    sendFileMessage(fileData) {
        const messageData = {
            content: fileData.type === 'image' ? `📷 ${fileData.name}` : `📁 ${fileData.name}`,
            type: fileData.type,
            data: fileData
        };
        this.sendMessage(messageData);
    }

    // UI Rendering Methods
    renderSubjects() {
        const subjectsList = document.getElementById('subjectsList');
        
        if (this.subjects.length === 0) {
            subjectsList.innerHTML = `
                <div class="loading">
                    <i class="fas fa-comments"></i>
                    <span>No conversations found. Create one to get started!</span>
                </div>
            `;
            return;
        }

        subjectsList.innerHTML = this.subjects.map(subject => `
            <div class="subject-item" data-id="${subject.id}" onclick="kitchenChat.selectSubject('${subject.id}', '${this.escapeHtml(subject.Title)}')">
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
                <span>Error loading conversations</span>
            </div>
        `;
    }

    renderMessagesError() {
        document.getElementById('messagesContainer').innerHTML = `
            <div class="loading">
                <i class="fas fa-exclamation-triangle"></i>
                <span>Error loading messages</span>
            </div>
        `;
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
        
        // Load messages with real-time polling
        this.currentSubjectId = subjectId;
        this.loadMessages(subjectId);
    }

    // Modal methods
    openModal() {
        // Check if user is authenticated (if auth is enabled)
        if (this.authManager && !this.authManager.isAuthenticated()) {
            this.showToast('Please sign in to create conversations', 'error');
            return;
        }
        
        const modal = document.getElementById('modalOverlay');
        modal.classList.add('active');
        
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
        document.getElementById('titleCharCount').textContent = '0/100';
        this.validateSubjectForm();
    }

    // Validation methods
    validateSubjectForm() {
        const title = document.getElementById('subjectTitle').value.trim();
        const createBtn = document.getElementById('createSubjectBtn');
        
        createBtn.disabled = !title;
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

    // Toast notifications
    showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        if (!container) return;
        
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

// EMOJI PICKER CLASS - COMPLETELY REWRITTEN FOR GUARANTEED FUNCTIONALITY
class EmojiPicker {
    constructor() {
        this.isVisible = false;
        this.currentCategory = 'smileys';
        this.recentEmojis = JSON.parse(localStorage.getItem('recentEmojis') || '[]');
        this.searchTimeout = null;
        
        // Emoji data with Unicode emojis
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
                '🍠', '🥐', '🥖', '🫓', '🥨', '🥯', '🥞', '🧇', '🧀', '🍖',
                '🍗', '🥩', '🥓', '🍔', '🍟', '🍕', '🌭', '🥪', '🌮', '🌯',
                '🫔', '🥙', '🧆', '🥚', '🍳', '🥘', '🍲', '🫕', '🥣', '🥗',
                '🍿', '🧈', '🧂', '🥫', '🍱', '🍘', '🍙', '🍚', '🍛', '🍜',
                '🍝', '🍠', '🍢', '🍣', '🍤', '🍥', '🥮', '🍡', '🥟', '🥠',
                '🥡', '🦀', '🦞', '🦐', '🦑', '🦪', '🍦', '🍧', '🍨', '🍩',
                '🍪', '🎂', '🍰', '🧁', '🥧', '🍫', '🍬', '🍭', '🍮', '🍯'
            ],
            animals: [
                '🐶', '🐱', '🐭', '🐹', '🐰', '🦊', '🐻', '🐼', '🐻‍❄️', '🐨',
                '🐯', '🦁', '🐮', '🐷', '🐽', '🐸', '🐵', '🙈', '🙉', '🙊',
                '🐒', '🐔', '🐧', '🐦', '🐤', '🐣', '🐥', '🦆', '🦅', '🦉',
                '🦇', '🐺', '🐗', '🐴', '🦄', '🐝', '🪱', '🐛', '🦋', '🐌',
                '🐞', '🐜', '🪰', '🪲', '🪳', '🦟', '🦗', '🕷️', '🕸️', '🦂',
                '🐢', '🐍', '🦎', '🦖', '🦕', '🐙', '🦑', '🦐', '🦞', '🦀',
                '🐡', '🐠', '🐟', '🐬', '🐳', '🐋', '🦈', '🐊', '🐅', '🐆',
                '🦓', '🦍', '🦧', '🦣', '🐘', '🦛', '🦏', '🐪', '🐫', '🦒',
                '🦘', '🦬', '🐃', '🐂', '🐄', '🐎', '🐖', '🐏', '🐑', '🦙'
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
                '🔨', '⚒️', '🛠️', '⛏️', '🪓', '🔩', '⚙️', '🪤', '🧱', '⛓️'
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
        this.bindEvents();
        this.renderEmojis(this.currentCategory);
        this.renderRecentEmojis();
    }

    bindEvents() {
        // Category buttons
        document.querySelectorAll('.emoji-category').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const category = e.currentTarget.dataset.category;
                this.selectCategory(category);
            });
        });

        // Emoji search
        const emojiSearch = document.getElementById('emojiSearch');
        if (emojiSearch) {
            emojiSearch.addEventListener('input', (e) => {
                clearTimeout(this.searchTimeout);
                this.searchTimeout = setTimeout(() => {
                    this.searchEmojis(e.target.value);
                }, 300);
            });
        }
    }

    toggle() {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }

    show() {
        const picker = document.getElementById('emojiPicker');
        const emojiBtn = document.getElementById('emojiBtn');
        
        if (!picker) {
            console.error('Emoji picker element not found!');
            return;
        }
        
        // Force show with inline styles to override any CSS conflicts
        picker.style.display = 'flex';
        picker.style.visibility = 'visible';
        picker.style.opacity = '1';
        picker.style.position = 'fixed';
        picker.style.zIndex = '999999';
        picker.classList.add('show');
        
        if (emojiBtn) {
            emojiBtn.classList.add('active');
            emojiBtn.setAttribute('aria-expanded', 'true');
        }
        
        this.isVisible = true;
        
        // Ensure emojis are rendered
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
        const picker = document.getElementById('emojiPicker');
        const emojiBtn = document.getElementById('emojiBtn');
        
        if (!picker) return;
        
        picker.classList.remove('show');
        picker.style.display = 'none';
        picker.setAttribute('aria-hidden', 'true');
        
        if (emojiBtn) {
            emojiBtn.classList.remove('active');
            emojiBtn.setAttribute('aria-expanded', 'false');
        }
        
        this.isVisible = false;
        
        // Clear search
        const searchInput = document.getElementById('emojiSearch');
        if (searchInput) {
            searchInput.value = '';
            this.renderEmojis(this.currentCategory);
        }
    }

    selectCategory(category) {
        // Update active category button
        document.querySelectorAll('.emoji-category').forEach(btn => {
            btn.classList.remove('active');
            btn.setAttribute('aria-selected', 'false');
        });
        
        const activeBtn = document.querySelector(`[data-category="${category}"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
            activeBtn.setAttribute('aria-selected', 'true');
        }
        
        this.currentCategory = category;
        this.renderEmojis(category);
    }

    renderEmojis(category) {
        const grid = document.getElementById('emojiGrid');
        
        if (!grid) {
            console.error('Emoji grid element not found!');
            return;
        }
        
        const emojis = this.emojiData[category] || [];
        
        grid.innerHTML = emojis.map(emoji => `
            <button class="emoji-item" onclick="kitchenChat.emojiPicker.selectEmoji('${emoji}')" aria-label="${emoji} emoji">
                ${emoji}
            </button>
        `).join('');
    }

    searchEmojis(query) {
        if (!query.trim()) {
            this.renderEmojis(this.currentCategory);
            return;
        }

        const grid = document.getElementById('emojiGrid');
        if (!grid) return;
        
        const allEmojis = Object.values(this.emojiData).flat();
        
        // Simple search by emoji keywords
        const filteredEmojis = allEmojis.filter(emoji => {
            return this.getEmojiKeywords(emoji).some(keyword => 
                keyword.toLowerCase().includes(query.toLowerCase())
            );
        });
        
        grid.innerHTML = filteredEmojis.slice(0, 64).map(emoji => `
            <button class="emoji-item" onclick="kitchenChat.emojiPicker.selectEmoji('${emoji}')" aria-label="${emoji} emoji">
                ${emoji}
            </button>
        `).join('');
    }

    getEmojiKeywords(emoji) {
        // Basic emoji keyword mapping
        const keywords = {
            '😀': ['happy', 'smile', 'joy', 'grin'],
            '😍': ['love', 'heart', 'eyes', 'crush'],
            '🍕': ['pizza', 'food', 'slice', 'italian'],
            '🎉': ['party', 'celebration', 'confetti', 'festive'],
            '❤️': ['heart', 'love', 'red', 'romance'],
            '🔥': ['fire', 'hot', 'flame', 'burn'],
            '👍': ['thumbs', 'up', 'good', 'like', 'approve'],
            '😂': ['laugh', 'cry', 'funny', 'lol', 'tears'],
            '🤔': ['think', 'hmm', 'wondering', 'consider'],
            '💯': ['hundred', 'perfect', 'score', 'complete'],
            '🚀': ['rocket', 'space', 'launch', 'fast'],
            '💪': ['strong', 'muscle', 'power', 'flex'],
            '🎯': ['target', 'goal', 'aim', 'bullseye'],
            '⭐': ['star', 'favorite', 'rating', 'excellent']
        };
        return keywords[emoji] || [emoji];
    }

    selectEmoji(emoji) {
        const messageInput = document.getElementById('messageInput');
        if (!messageInput) {
            console.error('Message input not found!');
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
        
        if (!container) return;
        
        if (this.recentEmojis.length === 0) {
            container.innerHTML = '<span style="color: rgba(255, 255, 255, 0.6); font-size: 0.8rem;">None yet</span>';
            return;
        }
        
        container.innerHTML = this.recentEmojis.map(emoji => `
            <button class="recent-emoji" onclick="kitchenChat.emojiPicker.selectEmoji('${emoji}')" aria-label="${emoji} recent emoji">
                ${emoji}
            </button>
        `).join('');
    }
}

// Integration bridge with AdvancedCommunication
if (typeof window !== 'undefined') {
    // Hook into advanced communication callbacks
    window.addEventListener('voiceMessageRecorded', (event) => {
        if (window.kitchenChat) {
            window.kitchenChat.sendVoiceMessage(event.detail);
        }
    });
    
    window.addEventListener('fileSelected', (event) => {
        if (window.kitchenChat) {
            window.kitchenChat.sendFileMessage(event.detail);
        }
    });
}

// Initialize the application when DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        // Make sure all required classes are available
        if (typeof AuthManager === 'undefined') {
            console.warn('AuthManager not loaded, running without authentication');
        }
        if (typeof AuthUI === 'undefined') {
            console.warn('AuthUI not loaded, running without authentication UI');
        }
        
        window.kitchenChat = new KitchenChat();
        
        // Make AuthUI available globally for button clicks
        if (typeof AuthUI !== 'undefined' && window.kitchenChat.authUI) {
            window.authUI = window.kitchenChat.authUI;
        }
    });
} else {
    // Make sure all required classes are available
    if (typeof AuthManager === 'undefined') {
        console.warn('AuthManager not loaded, running without authentication');
    }
    if (typeof AuthUI === 'undefined') {
        console.warn('AuthUI not loaded, running without authentication UI');
    }
    
    window.kitchenChat = new KitchenChat();
    
    // Make AuthUI available globally for button clicks
    if (typeof AuthUI !== 'undefined' && window.kitchenChat.authUI) {
        window.authUI = window.kitchenChat.authUI;
    }
}

// Service Worker registration for PWA capabilities
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('SW registered: ', registration);
            })
            .catch(registrationError => {
                console.log('SW registration failed: ', registrationError);
            });
    });
}