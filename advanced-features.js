// Advanced Communication Features for Kitchen Chat - Enhanced Integration
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
        this.kitchenChat = null; // Reference to main app
        this.init();
    }

    async init() {
        // Wait for main KitchenChat to be available
        this.waitForKitchenChat();
        
        this.setupVoiceRecording();
        this.setupFileSharing();
        this.setupMessageSearch();
        this.setupReactions();
        this.setupThreading();
        this.setupScheduling();
        this.buildSearchIndex();
        this.initializeLightbox();
        
        console.log('🚀 Advanced Communication Features Loaded and Integrated!');
    }

    waitForKitchenChat() {
        const checkForKitchenChat = () => {
            if (window.kitchenChat) {
                this.kitchenChat = window.kitchenChat;
                console.log('🔗 Advanced features connected to KitchenChat');
            } else {
                setTimeout(checkForKitchenChat, 100);
            }
        };
        checkForKitchenChat();
    }

    // 🎙️ VOICE MESSAGES WITH WAVEFORM
    setupVoiceRecording() {
        // Wait a bit to ensure message input is available
        setTimeout(() => {
            const voiceBtn = this.createVoiceButton();
            const messageInput = document.querySelector('.message-input');
            if (messageInput && !messageInput.querySelector('.voice-btn')) {
                messageInput.appendChild(voiceBtn);
            }
        }, 1000);
    }

    createVoiceButton() {
        const button = document.createElement('button');
        button.className = 'voice-btn';
        button.innerHTML = '<i class="fas fa-microphone"></i>';
        button.title = 'Hold to record voice message';
        button.type = 'button';
        
        // Touch events for mobile
        button.addEventListener('touchstart', (e) => {
            e.preventDefault();
            this.startRecording();
        });
        
        button.addEventListener('touchend', (e) => {
            e.preventDefault();
            this.stopRecording();
        });
        
        // Mouse events for desktop
        button.addEventListener('mousedown', (e) => {
            e.preventDefault();
            this.startRecording();
        });
        
        button.addEventListener('mouseup', (e) => {
            e.preventDefault();
            this.stopRecording();
        });
        
        button.addEventListener('mouseleave', (e) => {
            this.stopRecording();
        });
        
        return button;
    }

    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            // Set up audio analysis
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioContext.createAnalyser();
            const source = this.audioContext.createMediaStreamSource(stream);
            source.connect(this.analyser);
            
            this.mediaRecorder = new MediaRecorder(stream, {
                mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/wav'
            });
            this.audioChunks = [];
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = () => {
                this.processRecording();
                stream.getTracks().forEach(track => track.stop());
            };
            
            this.mediaRecorder.start(100); // Collect data every 100ms
            this.isRecording = true;
            this.showRecordingUI();
            this.startWaveformVisualization();
            
            // Update button style
            const voiceBtn = document.querySelector('.voice-btn');
            if (voiceBtn) {
                voiceBtn.classList.add('recording');
                voiceBtn.innerHTML = '<i class="fas fa-stop"></i>';
            }
            
        } catch (error) {
            console.error('❌ Voice recording failed:', error);
            this.showToast('Microphone access denied. Please allow microphone access to record voice messages.', 'error');
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            this.hideRecordingUI();
            
            // Reset button style
            const voiceBtn = document.querySelector('.voice-btn');
            if (voiceBtn) {
                voiceBtn.classList.remove('recording');
                voiceBtn.innerHTML = '<i class="fas fa-microphone"></i>';
            }
            
            if (this.audioContext) {
                this.audioContext.close();
            }
        }
    }

    startWaveformVisualization() {
        const canvas = document.getElementById('waveform-canvas');
        if (!canvas || !this.analyser) return;
        
        const ctx = canvas.getContext('2d');
        this.analyser.fftSize = 256;
        const bufferLength = this.analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        
        const animate = () => {
            if (!this.isRecording) return;
            
            this.analyser.getByteFrequencyData(dataArray);
            
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            const barWidth = (canvas.width / bufferLength) * 2.5;
            let x = 0;
            
            for (let i = 0; i < bufferLength; i++) {
                const barHeight = (dataArray[i] / 255) * canvas.height * 0.8;
                
                // Create gradient
                const gradient = ctx.createLinearGradient(0, canvas.height - barHeight, 0, canvas.height);
                gradient.addColorStop(0, '#4A90E2');
                gradient.addColorStop(1, '#667eea');
                ctx.fillStyle = gradient;
                
                ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
                x += barWidth + 1;
            }
            
            requestAnimationFrame(animate);
        };
        
        animate();
    }

    showRecordingUI() {
        // Remove existing recording UI
        const existing = document.getElementById('recording-ui');
        if (existing) existing.remove();
        
        const recordingUI = document.createElement('div');
        recordingUI.id = 'recording-ui';
        recordingUI.innerHTML = `
            <div class="recording-indicator">
                <div class="recording-dot"></div>
                <span>Recording... Release to send</span>
            </div>
            <canvas id="waveform-canvas" width="300" height="60"></canvas>
            <div style="margin-top: 8px; font-size: 12px; color: rgba(255,255,255,0.7); text-align: center;">
                Tap and hold microphone button or release to cancel
            </div>
        `;
        
        document.body.appendChild(recordingUI);
    }

    hideRecordingUI() {
        const recordingUI = document.getElementById('recording-ui');
        if (recordingUI) {
            recordingUI.style.animation = 'fadeOut 0.3s ease';
            setTimeout(() => {
                if (recordingUI.parentNode) {
                    recordingUI.remove();
                }
            }, 300);
        }
    }

    async processRecording() {
        if (this.audioChunks.length === 0) {
            this.showToast('Recording too short, please try again', 'error');
            return;
        }
        
        const audioBlob = new Blob(this.audioChunks, { 
            type: this.mediaRecorder.mimeType || 'audio/webm' 
        });
        
        // Calculate duration (approximate)
        const duration = this.audioChunks.length * 0.1; // Rough estimate
        const durationString = this.formatDuration(duration);
        
        const audioUrl = URL.createObjectURL(audioBlob);
        
        // Create voice message data
        const voiceMessage = {
            type: 'voice',
            audioUrl: audioUrl,
            duration: durationString,
            size: this.formatBytes(audioBlob.size),
            waveform: this.generateWaveformData(),
            blob: audioBlob
        };
        
        this.sendVoiceMessage(voiceMessage);
    }

    formatDuration(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    generateWaveformData() {
        // Generate realistic waveform data
        return Array.from({ length: 40 }, () => Math.random() * 60 + 20);
    }

    sendVoiceMessage(voiceData) {
        if (this.kitchenChat) {
            this.kitchenChat.sendVoiceMessage(voiceData);
            this.showToast('Voice message sent! 🎙️', 'success');
        } else {
            console.log('Voice message recorded:', voiceData);
            this.showToast('Voice message recorded (demo mode)', 'info');
        }
    }

    // 📁 FILE SHARING WITH DRAG & DROP
    setupFileSharing() {
        setTimeout(() => {
            this.createFileUploadButton();
            this.setupDragAndDrop();
        }, 1000);
    }

    createFileUploadButton() {
        const fileBtn = document.createElement('button');
        fileBtn.className = 'file-btn';
        fileBtn.innerHTML = '<i class="fas fa-paperclip"></i>';
        fileBtn.title = 'Attach file or image';
        fileBtn.type = 'button';
        
        fileBtn.addEventListener('click', () => this.openFileDialog());
        
        const messageInput = document.querySelector('.message-input');
        if (messageInput && !messageInput.querySelector('.file-btn')) {
            messageInput.appendChild(fileBtn);
        }
    }

    openFileDialog() {
        const input = document.createElement('input');
        input.type = 'file';
        input.multiple = true;
        input.accept = 'image/*,video/*,audio/*,.pdf,.doc,.docx,.txt,.zip,.rar';
        
        input.addEventListener('change', (e) => {
            const files = Array.from(e.target.files);
            if (files.length > 0) {
                this.handleFiles(files);
            }
        });
        
        input.click();
    }

    setupDragAndDrop() {
        const chatContainer = document.querySelector('.messages-container');
        if (!chatContainer) return;
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            chatContainer.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });
        
        chatContainer.addEventListener('dragover', (e) => {
            chatContainer.classList.add('drag-over');
        });
        
        chatContainer.addEventListener('dragleave', (e) => {
            // Only remove if leaving the container entirely
            if (!chatContainer.contains(e.relatedTarget)) {
                chatContainer.classList.remove('drag-over');
            }
        });
        
        chatContainer.addEventListener('drop', (e) => {
            chatContainer.classList.remove('drag-over');
            
            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                this.handleFiles(files);
            }
        });
    }

    handleFiles(files) {
        files.forEach(file => {
            if (file.size > 50 * 1024 * 1024) { // 50MB limit
                this.showToast(`File "${file.name}" is too large (max 50MB)`, 'error');
                return;
            }
            
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
            const imageData = {
                type: 'image',
                src: e.target.result,
                name: file.name,
                size: this.formatBytes(file.size),
                file: file
            };
            this.sendFileMessage(imageData);
        };
        reader.readAsDataURL(file);
    }

    handleGenericFile(file) {
        const fileData = {
            type: 'file',
            name: file.name,
            size: this.formatBytes(file.size),
            extension: file.name.split('.').pop().toUpperCase(),
            icon: this.getFileIcon(file.type),
            file: file,
            url: URL.createObjectURL(file)
        };
        this.sendFileMessage(fileData);
    }

    getFileIcon(mimeType) {
        if (mimeType.includes('pdf')) return 'fas fa-file-pdf';
        if (mimeType.includes('word') || mimeType.includes('document')) return 'fas fa-file-word';
        if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) return 'fas fa-file-excel';
        if (mimeType.includes('powerpoint') || mimeType.includes('presentation')) return 'fas fa-file-powerpoint';
        if (mimeType.includes('video')) return 'fas fa-file-video';
        if (mimeType.includes('audio')) return 'fas fa-file-audio';
        if (mimeType.includes('image')) return 'fas fa-file-image';
        if (mimeType.includes('zip') || mimeType.includes('rar')) return 'fas fa-file-archive';
        if (mimeType.includes('text')) return 'fas fa-file-alt';
        return 'fas fa-file';
    }

    sendFileMessage(fileData) {
        if (this.kitchenChat) {
            this.kitchenChat.sendFileMessage(fileData);
            this.showToast(`${fileData.type === 'image' ? 'Image' : 'File'} shared! 📎`, 'success');
        } else {
            console.log('File message:', fileData);
            this.showToast(`${fileData.type === 'image' ? 'Image' : 'File'} shared (demo mode)`, 'info');
        }
    }

    // 🖼️ LIGHTBOX GALLERY
    initializeLightbox() {
        this.createLightboxHTML();
        this.bindLightboxEvents();
    }

    createLightboxHTML() {
        // Remove existing lightbox
        const existing = document.getElementById('lightbox');
        if (existing) existing.remove();
        
        const lightbox = document.createElement('div');
        lightbox.id = 'lightbox';
        lightbox.className = 'lightbox';
        lightbox.innerHTML = `
            <div class="lightbox-content">
                <button class="lightbox-close" onclick="window.advancedComm.closeLightbox()">
                    <i class="fas fa-times"></i>
                </button>
                <img class="lightbox-image" alt="">
                <div class="lightbox-caption"></div>
            </div>
        `;
        document.body.appendChild(lightbox);
    }

    bindLightboxEvents() {
        // Use event delegation for dynamically added images
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('message-image')) {
                this.openLightbox(e.target);
            }
        });
        
        // Close on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeLightbox();
            }
        });
        
        // Close on backdrop click
        const lightbox = document.getElementById('lightbox');
        if (lightbox) {
            lightbox.addEventListener('click', (e) => {
                if (e.target === lightbox) {
                    this.closeLightbox();
                }
            });
        }
    }

    openLightbox(imageElement) {
        const lightbox = document.getElementById('lightbox');
        const lightboxImage = lightbox.querySelector('.lightbox-image');
        const caption = lightbox.querySelector('.lightbox-caption');
        
        lightboxImage.src = imageElement.src;
        caption.textContent = imageElement.alt || 'Image';
        lightbox.classList.add('active');
        
        document.body.style.overflow = 'hidden';
    }

    closeLightbox() {
        const lightbox = document.getElementById('lightbox');
        if (lightbox) {
            lightbox.classList.remove('active');
            document.body.style.overflow = '';
        }
    }

    // 💬 MESSAGE REPLIES & THREADING
    setupThreading() {
        // Use event delegation for dynamically added messages
        document.addEventListener('contextmenu', (e) => {
            const messageElement = e.target.closest('.message');
            if (messageElement) {
                e.preventDefault();
                this.showContextMenu(e, messageElement);
            }
        });
    }

    showContextMenu(event, messageElement) {
        // Remove existing context menu
        const existing = document.querySelector('.context-menu');
        if (existing) existing.remove();
        
        const contextMenu = this.createContextMenu(messageElement);
        contextMenu.style.left = `${event.pageX}px`;
        contextMenu.style.top = `${event.pageY}px`;
        
        document.body.appendChild(contextMenu);
        
        // Adjust position if near screen edge
        const rect = contextMenu.getBoundingClientRect();
        if (rect.right > window.innerWidth) {
            contextMenu.style.left = `${event.pageX - rect.width}px`;
        }
        if (rect.bottom > window.innerHeight) {
            contextMenu.style.top = `${event.pageY - rect.height}px`;
        }
        
        // Close menu on outside click
        const closeMenu = (e) => {
            if (!contextMenu.contains(e.target)) {
                contextMenu.remove();
                document.removeEventListener('click', closeMenu);
            }
        };
        
        setTimeout(() => {
            document.addEventListener('click', closeMenu);
        }, 100);
    }

    createContextMenu(messageElement) {
        const menu = document.createElement('div');
        menu.className = 'context-menu';
        
        const messageContent = messageElement.querySelector('.message-content')?.textContent || '';
        const isOwnMessage = messageElement.classList.contains('own');
        
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
            ${isOwnMessage ? `
                <div class="context-item" data-action="delete" style="color: #ef4444;">
                    <i class="fas fa-trash"></i> Delete
                </div>
            ` : ''}
        `;
        
        menu.addEventListener('click', (e) => {
            const action = e.target.closest('.context-item')?.dataset.action;
            if (action) {
                this.handleContextAction(action, messageElement, messageContent);
                menu.remove();
            }
        });
        
        return menu;
    }

    handleContextAction(action, messageElement, messageContent) {
        switch (action) {
            case 'reply':
                this.showReplyInterface(messageElement);
                break;
            case 'forward':
                this.showForwardDialog(messageContent);
                break;
            case 'react':
                this.showReactionPicker(messageElement);
                break;
            case 'copy':
                this.copyMessageText(messageContent);
                break;
            case 'delete':
                this.deleteMessage(messageElement);
                break;
        }
    }

    showReplyInterface(messageElement) {
        const author = messageElement.querySelector('.message-author')?.textContent || 'User';
        const content = messageElement.querySelector('.message-content')?.textContent || '';
        const preview = content.length > 50 ? content.substring(0, 50) + '...' : content;
        
        // Remove existing reply bar
        const existing = document.querySelector('.reply-bar');
        if (existing) existing.remove();
        
        const replyBar = document.createElement('div');
        replyBar.className = 'reply-bar';
        replyBar.innerHTML = `
            <div class="reply-preview">
                <div class="reply-line"></div>
                <div class="reply-content">
                    <div class="reply-author">Replying to ${author}</div>
                    <div class="reply-text">${preview}</div>
                </div>
                <button class="reply-cancel" onclick="this.parentElement.parentElement.remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        const messageInput = document.querySelector('.message-input-container');
        if (messageInput) {
            messageInput.insertBefore(replyBar, messageInput.firstChild);
            
            // Focus message input
            const input = document.getElementById('messageInput');
            if (input) {
                input.focus();
            }
        }
    }

    // 😊 MESSAGE REACTIONS
    setupReactions() {
        this.createReactionPicker();
    }

    createReactionPicker() {
        // Remove existing picker
        const existing = document.getElementById('reaction-picker');
        if (existing) existing.remove();
        
        const picker = document.createElement('div');
        picker.id = 'reaction-picker';
        picker.className = 'reaction-picker';
        picker.innerHTML = this.reactions.map(emoji => 
            `<button class="reaction-btn" data-emoji="${emoji}" onclick="window.advancedComm.selectReaction('${emoji}')">${emoji}</button>`
        ).join('');
        
        document.body.appendChild(picker);
    }

    showReactionPicker(messageElement) {
        this.currentReactionMessage = messageElement;
        const picker = document.getElementById('reaction-picker');
        if (picker) {
            picker.classList.add('show');
            
            // Position near the message
            const rect = messageElement.getBoundingClientRect();
            picker.style.left = `${rect.left + rect.width / 2}px`;
            picker.style.top = `${rect.top - 60}px`;
            picker.style.transform = 'translateX(-50%)';
            
            // Close after selection or outside click
            const closePicker = (e) => {
                if (!picker.contains(e.target) && !messageElement.contains(e.target)) {
                    this.hideReactionPicker();
                    document.removeEventListener('click', closePicker);
                }
            };
            
            setTimeout(() => {
                document.addEventListener('click', closePicker);
            }, 100);
        }
    }

    selectReaction(emoji) {
        if (this.currentReactionMessage) {
            this.addReaction(emoji, this.currentReactionMessage);
        }
        this.hideReactionPicker();
    }

    hideReactionPicker() {
        const picker = document.getElementById('reaction-picker');
        if (picker) {
            picker.classList.remove('show');
        }
        this.currentReactionMessage = null;
    }

    addReaction(emoji, messageElement) {
        let reactionsContainer = messageElement.querySelector('.message-reactions');
        if (!reactionsContainer) {
            reactionsContainer = document.createElement('div');
            reactionsContainer.className = 'message-reactions';
            messageElement.appendChild(reactionsContainer);
        }
        
        // Check if reaction already exists
        let existingReaction = reactionsContainer.querySelector(`[data-emoji="${emoji}"]`);
        
        if (existingReaction) {
            // Increment count
            const countSpan = existingReaction.querySelector('.reaction-count');
            const currentCount = parseInt(countSpan.textContent) || 1;
            countSpan.textContent = currentCount + 1;
            existingReaction.classList.add('own');
        } else {
            // Create new reaction
            const reaction = document.createElement('div');
            reaction.className = 'message-reaction own';
            reaction.dataset.emoji = emoji;
            reaction.innerHTML = `
                <span class="reaction-emoji">${emoji}</span>
                <span class="reaction-count">1</span>
            `;
            
            reaction.addEventListener('click', () => {
                this.toggleReaction(reaction);
            });
            
            reactionsContainer.appendChild(reaction);
        }
        
        this.showToast(`Reaction ${emoji} added!`, 'success');
    }

    toggleReaction(reactionElement) {
        if (reactionElement.classList.contains('own')) {
            // Remove own reaction
            const countSpan = reactionElement.querySelector('.reaction-count');
            const currentCount = parseInt(countSpan.textContent);
            
            if (currentCount > 1) {
                countSpan.textContent = currentCount - 1;
                reactionElement.classList.remove('own');
            } else {
                reactionElement.remove();
            }
        } else {
            // Add own reaction
            const countSpan = reactionElement.querySelector('.reaction-count');
            const currentCount = parseInt(countSpan.textContent);
            countSpan.textContent = currentCount + 1;
            reactionElement.classList.add('own');
        }
    }

    // 🔍 MESSAGE SEARCH WITH HIGHLIGHTING
    setupMessageSearch() {
        // Add search button to chat header
        setTimeout(() => {
            const chatActions = document.querySelector('.chat-actions');
            if (chatActions && !chatActions.querySelector('.search-toggle-btn')) {
                const searchToggle = document.createElement('button');
                searchToggle.className = 'search-toggle-btn';
                searchToggle.innerHTML = '<i class="fas fa-search"></i>';
                searchToggle.title = 'Search messages (Ctrl+F)';
                
                searchToggle.addEventListener('click', () => this.toggleSearch());
                chatActions.appendChild(searchToggle);
            }
        }, 1000);
        
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
            if (chatHeader) {
                chatHeader.style.position = 'relative';
                chatHeader.appendChild(searchBar);
            }
        }
        
        searchBar.classList.toggle('active');
        if (searchBar.classList.contains('active')) {
            const input = searchBar.querySelector('.search-input');
            if (input) {
                input.focus();
            }
        } else {
            this.clearSearch();
        }
    }

    createSearchBar() {
        const searchBar = document.createElement('div');
        searchBar.id = 'message-search-bar';
        searchBar.className = 'message-search-bar';
        searchBar.innerHTML = `
            <div class="search-input-wrapper">
                <input type="text" placeholder="Search messages..." class="search-input">
                <button class="search-prev" title="Previous match">
                    <i class="fas fa-chevron-up"></i>
                </button>
                <button class="search-next" title="Next match">
                    <i class="fas fa-chevron-down"></i>
                </button>
                <span class="search-results">0 matches</span>
                <button class="search-close" title="Close search">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        const input = searchBar.querySelector('.search-input');
        input.addEventListener('input', (e) => this.performSearch(e.target.value));
        
        searchBar.querySelector('.search-close').addEventListener('click', () => {
            this.toggleSearch();
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
            // Reset previous highlights
            const originalText = message.dataset.originalText || message.textContent;
            message.dataset.originalText = originalText;
            
            const text = originalText.toLowerCase();
            const searchTerm = query.toLowerCase();
            
            if (text.includes(searchTerm)) {
                matches++;
                message.innerHTML = this.highlightText(originalText, query);
                message.closest('.message').classList.add('search-match');
            } else {
                message.innerHTML = originalText;
                message.closest('.message').classList.remove('search-match');
            }
        });
        
        const resultsSpan = document.querySelector('.search-results');
        if (resultsSpan) {
            resultsSpan.textContent = `${matches} matches`;
        }
        
        // Scroll to first match
        if (matches > 0) {
            const firstMatch = document.querySelector('.search-match');
            if (firstMatch) {
                firstMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    }

    highlightText(text, query) {
        const regex = new RegExp(`(${this.escapeRegExp(query)})`, 'gi');
        return text.replace(regex, '<mark class="search-highlight">$1</mark>');
    }

    escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    clearSearch() {
        document.querySelectorAll('.message-content').forEach(message => {
            if (message.dataset.originalText) {
                message.innerHTML = message.dataset.originalText;
                delete message.dataset.originalText;
            }
        });
        
        document.querySelectorAll('.search-match').forEach(msg => {
            msg.classList.remove('search-match');
        });
        
        const resultsSpan = document.querySelector('.search-results');
        if (resultsSpan) {
            resultsSpan.textContent = '0 matches';
        }
    }

    // ⏰ MESSAGE SCHEDULING
    setupScheduling() {
        setTimeout(() => {
            this.createScheduleButton();
        }, 1000);
    }

    createScheduleButton() {
        const scheduleBtn = document.createElement('button');
        scheduleBtn.className = 'schedule-btn';
        scheduleBtn.innerHTML = '<i class="fas fa-clock"></i>';
        scheduleBtn.title = 'Schedule message';
        scheduleBtn.type = 'button';
        
        scheduleBtn.addEventListener('click', () => this.showScheduleDialog());
        
        const messageInput = document.querySelector('.message-input');
        if (messageInput && !messageInput.querySelector('.schedule-btn')) {
            messageInput.appendChild(scheduleBtn);
        }
    }

    showScheduleDialog() {
        // Remove existing dialog
        const existing = document.querySelector('.schedule-dialog');
        if (existing) existing.remove();
        
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
                    <button class="btn-secondary schedule-cancel">Cancel</button>
                    <button class="btn-primary schedule-confirm">Schedule</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        
        // Bind events
        dialog.querySelector('.schedule-cancel').addEventListener('click', () => dialog.remove());
        dialog.querySelector('.schedule-confirm').addEventListener('click', () => this.confirmSchedule(dialog));
        
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
        
        // Close on backdrop click
        dialog.addEventListener('click', (e) => {
            if (e.target === dialog) {
                dialog.remove();
            }
        });
    }

    confirmSchedule(dialog) {
        const datetimeInput = dialog.querySelector('.schedule-datetime');
        if (datetimeInput.style.display !== 'none' && datetimeInput.value) {
            const scheduleTime = new Date(datetimeInput.value).getTime();
            const now = Date.now();
            const delay = scheduleTime - now;
            
            if (delay <= 0) {
                this.showToast('Please select a future time', 'error');
                return;
            }
            
            this.scheduleMessage(delay);
            dialog.remove();
        }
    }

    scheduleMessage(delayMs) {
        const messageInput = document.getElementById('messageInput');
        if (!messageInput) return;
        
        const content = messageInput.value.trim();
        
        if (!content) {
            this.showToast('Please enter a message to schedule', 'error');
            return;
        }
        
        const scheduleTime = Date.now() + delayMs;
        const messageId = Date.now().toString();
        
        this.scheduledMessages.set(messageId, {
            content,
            scheduleTime,
            subjectId: this.kitchenChat?.currentSubjectId
        });
        
        messageInput.value = '';
        const charCount = document.getElementById('charCount');
        if (charCount) charCount.textContent = '0/500';
        
        this.showToast(`Message scheduled for ${new Date(scheduleTime).toLocaleString()}`, 'success');
        
        setTimeout(() => {
            this.sendScheduledMessage(messageId);
        }, delayMs);
    }

    sendScheduledMessage(messageId) {
        const message = this.scheduledMessages.get(messageId);
        if (message && this.kitchenChat) {
            // Check if still in the same subject
            if (message.subjectId === this.kitchenChat.currentSubjectId) {
                const messageInput = document.getElementById('messageInput');
                if (messageInput) {
                    messageInput.value = message.content;
                    // Trigger send
                    this.kitchenChat.sendMessage();
                }
            }
            this.scheduledMessages.delete(messageId);
            this.showToast('Scheduled message sent! ⏰', 'success');
        }
    }

    // 🔧 UTILITY METHODS
    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    showToast(message, type = 'info') {
        // Use existing toast system from Kitchen Chat
        if (this.kitchenChat?.showToast) {
            this.kitchenChat.showToast(message, type);
        } else {
            // Fallback toast system
            console.log(`Toast [${type}]: ${message}`);
            
            let container = document.getElementById('toastContainer');
            if (!container) {
                container = document.createElement('div');
                container.id = 'toastContainer';
                container.className = 'toast-container';
                document.body.appendChild(container);
            }
            
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            
            container.appendChild(toast);
            
            setTimeout(() => toast.classList.add('show'), 100);
            
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => {
                    if (container.contains(toast)) {
                        container.removeChild(toast);
                    }
                }, 300);
            }, 4000);
        }
    }

    showForwardDialog(messageContent) {
        this.showToast('Forward feature: Select a conversation to forward to', 'info');
        console.log('Forwarding message:', messageContent);
    }

    copyMessageText(messageContent) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(messageContent).then(() => {
                this.showToast('Message copied to clipboard! 📋', 'success');
            }).catch(() => {
                this.fallbackCopyTextToClipboard(messageContent);
            });
        } else {
            this.fallbackCopyTextToClipboard(messageContent);
        }
    }

    fallbackCopyTextToClipboard(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            document.execCommand('copy');
            this.showToast('Message copied to clipboard! 📋', 'success');
        } catch (err) {
            this.showToast('Failed to copy message', 'error');
        }
        
        document.body.removeChild(textArea);
    }

    deleteMessage(messageElement) {
        if (confirm('Are you sure you want to delete this message?')) {
            messageElement.style.animation = 'fadeOut 0.3s ease';
            setTimeout(() => {
                if (messageElement.parentNode) {
                    messageElement.remove();
                }
            }, 300);
            this.showToast('Message deleted', 'success');
        }
    }

    buildSearchIndex() {
        // This will be called when messages are loaded
        const messages = document.querySelectorAll('.message');
        this.searchIndex.clear();
        
        messages.forEach((message, index) => {
            const content = message.querySelector('.message-content')?.textContent || '';
            this.searchIndex.set(index, {
                content: content.toLowerCase(),
                element: message
            });
        });
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

// Add missing CSS animations
const additionalStyles = `
<style>
@keyframes fadeOut {
    from { opacity: 1; transform: scale(1); }
    to { opacity: 0; transform: scale(0.9); }
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.messages-container.drag-over::before {
    position: absolute;
    content: '📁 Drop files here to share';
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(74, 144, 226, 0.9);
    color: white;
    padding: 20px 40px;
    border-radius: 16px;
    font-size: 16px;
    font-weight: 600;
    z-index: 1000;
    animation: fadeIn 0.3s ease;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    border: 2px solid rgba(255, 255, 255, 0.2);
}
</style>
`;

document.head.insertAdjacentHTML('beforeend', additionalStyles);