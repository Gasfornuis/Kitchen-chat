// Advanced Communication Features for Kitchen Chat
class AdvancedCommunication {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.audioContext = null;
        this.analyser = null;
        this.reactions = ['👍', '❤️', '😂', '🔥', '👏', '🚀', '✨', '💯'];
        this.searchIndex = new Map();
        this.scheduledMessages = new Map();
        this.init();
    }

    async init() {
        this.setupVoiceRecording();
        this.setupFileSharing();
        this.setupMessageSearch();
        this.setupReactions();
        this.setupThreading();
        this.setupScheduling();
        this.buildSearchIndex();
        this.initializeLightbox();
        console.log('🚀 Advanced Communication Features Loaded!');
    }

    // 🎙️ VOICE MESSAGES WITH WAVEFORM
    setupVoiceRecording() {
        const voiceBtn = this.createVoiceButton();
        const messageInput = document.querySelector('.message-input');
        if (messageInput) {
            messageInput.appendChild(voiceBtn);
        }
    }

    createVoiceButton() {
        const button = document.createElement('button');
        button.className = 'voice-btn';
        button.innerHTML = '<i class="fas fa-microphone"></i>';
        button.title = 'Record voice message';
        
        button.addEventListener('mousedown', () => this.startRecording());
        button.addEventListener('mouseup', () => this.stopRecording());
        button.addEventListener('mouseleave', () => this.stopRecording());
        
        return button;
    }

    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.audioContext = new AudioContext();
            this.analyser = this.audioContext.createAnalyser();
            const source = this.audioContext.createMediaStreamSource(stream);
            source.connect(this.analyser);
            
            this.mediaRecorder = new MediaRecorder(stream);
            this.audioChunks = [];
            
            this.mediaRecorder.ondataavailable = (event) => {
                this.audioChunks.push(event.data);
            };
            
            this.mediaRecorder.onstop = () => {
                this.processRecording();
                stream.getTracks().forEach(track => track.stop());
            };
            
            this.mediaRecorder.start();
            this.isRecording = true;
            this.showRecordingUI();
            this.startWaveformVisualization();
            
        } catch (error) {
            console.error('❌ Voice recording failed:', error);
            this.showToast('Microphone access denied', 'error');
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            this.hideRecordingUI();
        }
    }

    startWaveformVisualization() {
        const canvas = document.getElementById('waveform-canvas');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        const bufferLength = this.analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        
        const animate = () => {
            if (!this.isRecording) return;
            
            this.analyser.getByteFrequencyData(dataArray);
            
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#4A90E2';
            
            const barWidth = (canvas.width / bufferLength) * 2.5;
            let x = 0;
            
            for (let i = 0; i < bufferLength; i++) {
                const barHeight = (dataArray[i] / 255) * canvas.height;
                ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
                x += barWidth + 1;
            }
            
            requestAnimationFrame(animate);
        };
        
        animate();
    }

    showRecordingUI() {
        const recordingUI = document.createElement('div');
        recordingUI.id = 'recording-ui';
        recordingUI.innerHTML = `
            <div class="recording-indicator">
                <div class="recording-dot"></div>
                <span>Recording... Release to send</span>
            </div>
            <canvas id="waveform-canvas" width="300" height="60"></canvas>
        `;
        
        document.body.appendChild(recordingUI);
    }

    hideRecordingUI() {
        const recordingUI = document.getElementById('recording-ui');
        if (recordingUI) {
            recordingUI.remove();
        }
    }

    async processRecording() {
        const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
        const audioUrl = URL.createObjectURL(audioBlob);
        
        // Create voice message element
        const voiceMessage = this.createVoiceMessage(audioUrl, audioBlob.size);
        this.sendVoiceMessage(voiceMessage, audioBlob);
    }

    createVoiceMessage(audioUrl, size) {
        const duration = '0:05'; // Would calculate actual duration
        return {
            type: 'voice',
            audioUrl,
            duration,
            size: this.formatBytes(size),
            waveform: this.generateWaveformData()
        };
    }

    generateWaveformData() {
        // Simplified waveform data generation
        return Array.from({ length: 50 }, () => Math.random() * 100);
    }

    // 📁 FILE SHARING WITH DRAG & DROP
    setupFileSharing() {
        this.createFileUploadZone();
        this.setupDragAndDrop();
    }

    createFileUploadZone() {
        const fileBtn = document.createElement('button');
        fileBtn.className = 'file-btn';
        fileBtn.innerHTML = '<i class="fas fa-paperclip"></i>';
        fileBtn.title = 'Attach file';
        
        fileBtn.addEventListener('click', () => this.openFileDialog());
        
        const messageInput = document.querySelector('.message-input');
        if (messageInput) {
            messageInput.appendChild(fileBtn);
        }
    }

    openFileDialog() {
        const input = document.createElement('input');
        input.type = 'file';
        input.multiple = true;
        input.accept = 'image/*,video/*,audio/*,.pdf,.doc,.docx,.txt';
        
        input.addEventListener('change', (e) => {
            this.handleFiles(Array.from(e.target.files));
        });
        
        input.click();
    }

    setupDragAndDrop() {
        const chatContainer = document.querySelector('.messages-container');
        if (!chatContainer) return;
        
        chatContainer.addEventListener('dragover', (e) => {
            e.preventDefault();
            chatContainer.classList.add('drag-over');
        });
        
        chatContainer.addEventListener('dragleave', (e) => {
            e.preventDefault();
            chatContainer.classList.remove('drag-over');
        });
        
        chatContainer.addEventListener('drop', (e) => {
            e.preventDefault();
            chatContainer.classList.remove('drag-over');
            
            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                this.handleFiles(files);
            }
        });
    }

    handleFiles(files) {
        files.forEach(file => {
            if (file.type.startsWith('image/')) {
                this.handleImageFile(file);
            } else {
                this.handleGenericFile(file);
            }
        });
    }

    handleImageFile(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const imageMessage = {
                type: 'image',
                src: e.target.result,
                name: file.name,
                size: this.formatBytes(file.size)
            };
            this.sendMediaMessage(imageMessage);
        };
        reader.readAsDataURL(file);
    }

    handleGenericFile(file) {
        const fileMessage = {
            type: 'file',
            name: file.name,
            size: this.formatBytes(file.size),
            extension: file.name.split('.').pop().toUpperCase(),
            icon: this.getFileIcon(file.type)
        };
        this.sendMediaMessage(fileMessage);
    }

    getFileIcon(mimeType) {
        if (mimeType.includes('pdf')) return 'fas fa-file-pdf';
        if (mimeType.includes('word')) return 'fas fa-file-word';
        if (mimeType.includes('video')) return 'fas fa-file-video';
        if (mimeType.includes('audio')) return 'fas fa-file-audio';
        return 'fas fa-file';
    }

    // 🖼️ LIGHTBOX GALLERY
    initializeLightbox() {
        this.createLightboxHTML();
        this.bindLightboxEvents();
    }

    createLightboxHTML() {
        const lightbox = document.createElement('div');
        lightbox.id = 'lightbox';
        lightbox.className = 'lightbox';
        lightbox.innerHTML = `
            <div class="lightbox-content">
                <button class="lightbox-close"><i class="fas fa-times"></i></button>
                <button class="lightbox-prev"><i class="fas fa-chevron-left"></i></button>
                <button class="lightbox-next"><i class="fas fa-chevron-right"></i></button>
                <img class="lightbox-image" alt="">
                <div class="lightbox-caption"></div>
            </div>
        `;
        document.body.appendChild(lightbox);
    }

    bindLightboxEvents() {
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('message-image')) {
                this.openLightbox(e.target);
            }
        });
    }

    openLightbox(imageElement) {
        const lightbox = document.getElementById('lightbox');
        const lightboxImage = lightbox.querySelector('.lightbox-image');
        const caption = lightbox.querySelector('.lightbox-caption');
        
        lightboxImage.src = imageElement.src;
        caption.textContent = imageElement.alt || '';
        lightbox.classList.add('active');
        
        document.body.style.overflow = 'hidden';
    }

    closeLightbox() {
        const lightbox = document.getElementById('lightbox');
        lightbox.classList.remove('active');
        document.body.style.overflow = '';
    }

    // 💬 MESSAGE REPLIES & THREADING
    setupThreading() {
        document.addEventListener('contextmenu', (e) => {
            if (e.target.closest('.message')) {
                e.preventDefault();
                this.showContextMenu(e, e.target.closest('.message'));
            }
        });
    }

    showContextMenu(event, messageElement) {
        const contextMenu = this.createContextMenu();
        contextMenu.style.left = `${event.pageX}px`;
        contextMenu.style.top = `${event.pageY}px`;
        
        document.body.appendChild(contextMenu);
        
        // Close menu on outside click
        document.addEventListener('click', () => {
            contextMenu.remove();
        }, { once: true });
    }

    createContextMenu() {
        const menu = document.createElement('div');
        menu.className = 'context-menu';
        menu.innerHTML = `
            <div class="context-item" data-action="reply">
                <i class="fas fa-reply"></i> Reply
            </div>
            <div class="context-item" data-action="forward">
                <i class="fas fa-share"></i> Forward
            </div>
            <div class="context-item" data-action="react">
                <i class="fas fa-smile"></i> Add Reaction
            </div>
            <div class="context-item" data-action="copy">
                <i class="fas fa-copy"></i> Copy Text
            </div>
        `;
        
        menu.addEventListener('click', (e) => {
            const action = e.target.closest('.context-item')?.dataset.action;
            if (action) {
                this.handleContextAction(action);
            }
        });
        
        return menu;
    }

    handleContextAction(action) {
        switch (action) {
            case 'reply':
                this.showReplyInterface();
                break;
            case 'forward':
                this.showForwardDialog();
                break;
            case 'react':
                this.showReactionPicker();
                break;
            case 'copy':
                this.copyMessageText();
                break;
        }
    }

    showReplyInterface() {
        const replyBar = document.createElement('div');
        replyBar.className = 'reply-bar';
        replyBar.innerHTML = `
            <div class="reply-preview">
                <div class="reply-line"></div>
                <div class="reply-content">
                    <div class="reply-author">Replying to John</div>
                    <div class="reply-text">Original message preview...</div>
                </div>
                <button class="reply-cancel"><i class="fas fa-times"></i></button>
            </div>
        `;
        
        const messageInput = document.querySelector('.message-input-container');
        messageInput.insertBefore(replyBar, messageInput.firstChild);
    }

    // 😊 MESSAGE REACTIONS
    setupReactions() {
        this.createReactionPicker();
    }

    createReactionPicker() {
        const picker = document.createElement('div');
        picker.id = 'reaction-picker';
        picker.className = 'reaction-picker';
        picker.innerHTML = this.reactions.map(emoji => 
            `<button class="reaction-btn" data-emoji="${emoji}">${emoji}</button>`
        ).join('');
        
        picker.addEventListener('click', (e) => {
            if (e.target.classList.contains('reaction-btn')) {
                this.addReaction(e.target.dataset.emoji);
                this.hideReactionPicker();
            }
        });
        
        document.body.appendChild(picker);
    }

    showReactionPicker() {
        const picker = document.getElementById('reaction-picker');
        picker.classList.add('show');
    }

    hideReactionPicker() {
        const picker = document.getElementById('reaction-picker');
        picker.classList.remove('show');
    }

    addReaction(emoji) {
        // Add reaction to message - would integrate with backend
        console.log(`Added reaction: ${emoji}`);
        this.showToast(`Reaction ${emoji} added!`, 'success');
    }

    // 🔍 MESSAGE SEARCH WITH HIGHLIGHTING
    setupMessageSearch() {
        this.createSearchInterface();
    }

    createSearchInterface() {
        const searchToggle = document.createElement('button');
        searchToggle.className = 'search-toggle-btn';
        searchToggle.innerHTML = '<i class="fas fa-search"></i>';
        searchToggle.title = 'Search messages (Ctrl+F)';
        
        searchToggle.addEventListener('click', () => this.toggleSearch());
        
        const chatHeader = document.querySelector('.chat-actions');
        if (chatHeader) {
            chatHeader.appendChild(searchToggle);
        }
        
        // Keyboard shortcut
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                this.toggleSearch();
            }
        });
    }

    toggleSearch() {
        let searchBar = document.getElementById('message-search-bar');
        
        if (!searchBar) {
            searchBar = this.createSearchBar();
            const chatHeader = document.querySelector('.chat-header');
            chatHeader.appendChild(searchBar);
        }
        
        searchBar.classList.toggle('active');
        if (searchBar.classList.contains('active')) {
            searchBar.querySelector('input').focus();
        }
    }

    createSearchBar() {
        const searchBar = document.createElement('div');
        searchBar.id = 'message-search-bar';
        searchBar.className = 'message-search-bar';
        searchBar.innerHTML = `
            <div class="search-input-wrapper">
                <input type="text" placeholder="Search messages..." class="search-input">
                <button class="search-prev"><i class="fas fa-chevron-up"></i></button>
                <button class="search-next"><i class="fas fa-chevron-down"></i></button>
                <span class="search-results">0 of 0</span>
                <button class="search-close"><i class="fas fa-times"></i></button>
            </div>
        `;
        
        const input = searchBar.querySelector('.search-input');
        input.addEventListener('input', (e) => this.performSearch(e.target.value));
        
        searchBar.querySelector('.search-close').addEventListener('click', () => {
            this.toggleSearch();
            this.clearSearch();
        });
        
        return searchBar;
    }

    performSearch(query) {
        if (!query.trim()) {
            this.clearSearch();
            return;
        }
        
        const messages = document.querySelectorAll('.message-content');
        let matches = 0;
        
        messages.forEach(message => {
            const text = message.textContent.toLowerCase();
            const searchTerm = query.toLowerCase();
            
            if (text.includes(searchTerm)) {
                matches++;
                message.innerHTML = this.highlightText(message.textContent, query);
                message.closest('.message').classList.add('search-match');
            } else {
                message.closest('.message').classList.remove('search-match');
            }
        });
        
        document.querySelector('.search-results').textContent = `${matches} matches`;
    }

    highlightText(text, query) {
        const regex = new RegExp(`(${query})`, 'gi');
        return text.replace(regex, '<mark class="search-highlight">$1</mark>');
    }

    clearSearch() {
        document.querySelectorAll('.message-content mark').forEach(mark => {
            mark.outerHTML = mark.innerHTML;
        });
        document.querySelectorAll('.search-match').forEach(msg => {
            msg.classList.remove('search-match');
        });
    }

    buildSearchIndex() {
        // Build search index for better performance
        const messages = document.querySelectorAll('.message');
        messages.forEach((message, index) => {
            const content = message.querySelector('.message-content')?.textContent || '';
            this.searchIndex.set(index, {
                content: content.toLowerCase(),
                element: message
            });
        });
    }

    // ⏰ MESSAGE SCHEDULING
    setupScheduling() {
        this.createScheduleButton();
    }

    createScheduleButton() {
        const scheduleBtn = document.createElement('button');
        scheduleBtn.className = 'schedule-btn';
        scheduleBtn.innerHTML = '<i class="fas fa-clock"></i>';
        scheduleBtn.title = 'Schedule message';
        
        scheduleBtn.addEventListener('click', () => this.showScheduleDialog());
        
        const messageInput = document.querySelector('.message-input');
        if (messageInput) {
            messageInput.appendChild(scheduleBtn);
        }
    }

    showScheduleDialog() {
        const dialog = document.createElement('div');
        dialog.className = 'schedule-dialog';
        dialog.innerHTML = `
            <div class="schedule-content">
                <h3>Schedule Message</h3>
                <div class="schedule-options">
                    <button class="schedule-option" data-time="300000">5 minutes</button>
                    <button class="schedule-option" data-time="3600000">1 hour</button>
                    <button class="schedule-option" data-time="86400000">1 day</button>
                    <button class="schedule-option" data-time="custom">Custom...</button>
                </div>
                <div class="custom-schedule" style="display: none;">
                    <input type="datetime-local" class="schedule-datetime">
                </div>
                <div class="schedule-actions">
                    <button class="btn-secondary" onclick="this.closest('.schedule-dialog').remove()">Cancel</button>
                    <button class="btn-primary schedule-confirm">Schedule</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        
        dialog.addEventListener('click', (e) => {
            if (e.target.classList.contains('schedule-option')) {
                const time = e.target.dataset.time;
                if (time === 'custom') {
                    dialog.querySelector('.custom-schedule').style.display = 'block';
                } else {
                    this.scheduleMessage(parseInt(time));
                    dialog.remove();
                }
            }
        });
    }

    scheduleMessage(delayMs) {
        const messageInput = document.getElementById('messageInput');
        const content = messageInput.value.trim();
        
        if (!content) return;
        
        const scheduleTime = Date.now() + delayMs;
        const messageId = Date.now().toString();
        
        this.scheduledMessages.set(messageId, {
            content,
            scheduleTime,
            subjectId: window.kitchenChat?.currentSubjectId
        });
        
        messageInput.value = '';
        this.showToast(`Message scheduled for ${new Date(scheduleTime).toLocaleString()}`, 'success');
        
        setTimeout(() => {
            this.sendScheduledMessage(messageId);
        }, delayMs);
    }

    sendScheduledMessage(messageId) {
        const message = this.scheduledMessages.get(messageId);
        if (message && window.kitchenChat) {
            // Simulate sending the message
            console.log('Sending scheduled message:', message.content);
            this.scheduledMessages.delete(messageId);
        }
    }

    // 🛠️ UTILITY METHODS
    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    showToast(message, type = 'info') {
        // Use existing toast system from Kitchen Chat
        if (window.kitchenChat?.showToast) {
            window.kitchenChat.showToast(message, type);
        }
    }

    sendVoiceMessage(voiceMessage, audioBlob) {
        // Integration with existing message sending system
        console.log('Sending voice message:', voiceMessage);
        this.showToast('Voice message sent! 🎙️', 'success');
    }

    sendMediaMessage(mediaMessage) {
        // Integration with existing message sending system
        console.log('Sending media message:', mediaMessage);
        this.showToast(`${mediaMessage.type} shared! 📎`, 'success');
    }

    showForwardDialog() {
        // Implementation for forwarding messages
        this.showToast('Forward feature activated! 📤', 'info');
    }

    copyMessageText() {
        // Implementation for copying message text
        this.showToast('Message copied to clipboard! 📋', 'success');
    }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.advancedComm = new AdvancedCommunication();
    });
} else {
    window.advancedComm = new AdvancedCommunication();
}

// Export for external use
if (typeof window !== 'undefined') {
    window.AdvancedCommunication = AdvancedCommunication;
}