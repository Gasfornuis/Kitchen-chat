// Enhanced Script Extensions - Message Animations & Visual Effects
class EnhancedEffects {
    constructor() {
        this.observerOptions = {
            threshold: 0.1,
            rootMargin: '50px 0px'
        };
        this.init();
    }

    init() {
        this.setupScrollAnimations();
        this.enhanceMessageAnimations();
        this.setupHoverEffects();
        this.initializeVisualFeedback();
        this.setupPerformanceOptimizations();
    }

    setupScrollAnimations() {
        // Intersection Observer for scroll-triggered animations
        this.observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, this.observerOptions);

        // Observe elements that should animate on scroll
        this.observeElements();
    }

    observeElements() {
        const elementsToObserve = document.querySelectorAll(
            '.subject-item, .welcome-content, .modal, .message'
        );
        
        elementsToObserve.forEach(el => {
            el.classList.add('fade-in-up');
            this.observer.observe(el);
        });
    }

    enhanceMessageAnimations() {
        // Override the original renderMessages function to add animations
        if (window.kitchenChat) {
            const originalRenderMessages = window.kitchenChat.renderMessages.bind(window.kitchenChat);
            
            window.kitchenChat.renderMessages = function() {
                originalRenderMessages();
                this.animateNewMessages();
            };
            
            // Add the animation method to KitchenChat
            window.kitchenChat.animateNewMessages = function() {
                const messages = document.querySelectorAll('.message:not(.animated)');
                messages.forEach((message, index) => {
                    message.classList.add('animated');
                    message.style.animationDelay = `${index * 0.1}s`;
                    
                    // Add stagger effect
                    setTimeout(() => {
                        message.style.animationDelay = '0s';
                    }, 1000);
                });
            };
        }
    }

    setupHoverEffects() {
        // Enhanced 3D tilt effect for cards
        this.setupTiltEffect();
        
        // Magnetic buttons
        this.setupMagneticEffect();
        
        // Ripple effect on clicks
        this.setupRippleEffect();
    }

    setupTiltEffect() {
        const tiltElements = document.querySelectorAll('.subject-item, .message');
        
        tiltElements.forEach(element => {
            element.addEventListener('mousemove', (e) => {
                const rect = element.getBoundingClientRect();
                const centerX = rect.left + rect.width / 2;
                const centerY = rect.top + rect.height / 2;
                
                const deltaX = (e.clientX - centerX) / (rect.width / 2);
                const deltaY = (e.clientY - centerY) / (rect.height / 2);
                
                const rotateX = deltaY * -10; // Max 10 degrees
                const rotateY = deltaX * 10;
                
                element.style.transform = `
                    perspective(1000px) 
                    rotateX(${rotateX}deg) 
                    rotateY(${rotateY}deg) 
                    translateZ(10px)
                `;
            });
            
            element.addEventListener('mouseleave', () => {
                element.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateZ(0px)';
            });
        });
    }

    setupMagneticEffect() {
        const magneticElements = document.querySelectorAll(
            '.btn-primary, .new-subject-btn, .emoji-btn, .refresh-btn'
        );
        
        magneticElements.forEach(element => {
            element.addEventListener('mousemove', (e) => {
                const rect = element.getBoundingClientRect();
                const centerX = rect.left + rect.width / 2;
                const centerY = rect.top + rect.height / 2;
                
                const deltaX = (e.clientX - centerX) * 0.1;
                const deltaY = (e.clientY - centerY) * 0.1;
                
                element.style.transform = `translate(${deltaX}px, ${deltaY}px) scale(1.05)`;
            });
            
            element.addEventListener('mouseleave', () => {
                element.style.transform = 'translate(0px, 0px) scale(1)';
            });
        });
    }

    setupRippleEffect() {
        const rippleElements = document.querySelectorAll(
            'button, .subject-item, .emoji-item'
        );
        
        rippleElements.forEach(element => {
            element.addEventListener('click', (e) => {
                this.createRipple(e, element);
            });
        });
    }

    createRipple(e, element) {
        const ripple = document.createElement('span');
        const rect = element.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = e.clientX - rect.left - size / 2;
        const y = e.clientY - rect.top - size / 2;
        
        ripple.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            left: ${x}px;
            top: ${y}px;
            background: rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            transform: scale(0);
            animation: ripple 0.6s linear;
            pointer-events: none;
            z-index: 1000;
        `;
        
        // Ensure element has relative positioning
        const originalPosition = getComputedStyle(element).position;
        if (originalPosition === 'static') {
            element.style.position = 'relative';
        }
        
        element.appendChild(ripple);
        
        // Remove ripple after animation
        setTimeout(() => {
            if (ripple.parentNode) {
                ripple.parentNode.removeChild(ripple);
            }
        }, 600);
    }

    initializeVisualFeedback() {
        // Enhanced loading states
        this.setupLoadingStates();
        
        // Connection status animations
        this.setupConnectionAnimations();
        
        // Form validation feedback
        this.setupFormFeedback();
    }

    setupLoadingStates() {
        // Enhance existing loading elements
        const loadingElements = document.querySelectorAll('.loading');
        loadingElements.forEach(element => {
            if (!element.classList.contains('enhanced')) {
                element.classList.add('enhanced', 'loading-shimmer');
            }
        });
        
        // Custom loading for API calls
        this.interceptAPICalls();
    }

    interceptAPICalls() {
        if (window.kitchenChat) {
            const originalApiCall = window.kitchenChat.apiCall.bind(window.kitchenChat);
            
            window.kitchenChat.apiCall = async function(endpoint, method = 'GET', data = null) {
                // Show subtle loading indicator
                document.body.classList.add('api-loading');
                
                try {
                    const result = await originalApiCall(endpoint, method, data);
                    return result;
                } finally {
                    // Remove loading indicator after a minimum time for smooth UX
                    setTimeout(() => {
                        document.body.classList.remove('api-loading');
                    }, 300);
                }
            };
        }
    }

    setupConnectionAnimations() {
        // Monitor connection status changes
        const connectionStatus = document.getElementById('connectionStatus');
        if (connectionStatus) {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                        const target = mutation.target;
                        if (target.classList.contains('disconnected')) {
                            this.showConnectionAlert();
                        }
                    }
                });
            });
            
            observer.observe(connectionStatus, { attributes: true });
        }
    }

    showConnectionAlert() {
        // Create animated connection alert
        const alert = document.createElement('div');
        alert.className = 'connection-alert';
        alert.innerHTML = `
            <i class="fas fa-wifi"></i>
            <span>Connection lost - Attempting to reconnect...</span>
        `;
        
        alert.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(245, 158, 11, 0.9);
            color: white;
            padding: 12px 20px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
            z-index: 10000;
            animation: slideInRight 0.3s ease;
            backdrop-filter: blur(10px);
        `;
        
        document.body.appendChild(alert);
        
        // Remove after 5 seconds
        setTimeout(() => {
            if (alert.parentNode) {
                alert.style.animation = 'slideOutRight 0.3s ease';
                setTimeout(() => {
                    if (alert.parentNode) {
                        alert.parentNode.removeChild(alert);
                    }
                }, 300);
            }
        }, 5000);
    }

    setupFormFeedback() {
        // Enhanced form validation with visual feedback
        const inputs = document.querySelectorAll('input, textarea');
        
        inputs.forEach(input => {
            input.addEventListener('blur', () => {
                this.validateInput(input);
            });
            
            input.addEventListener('input', () => {
                // Clear previous validation state
                input.classList.remove('valid', 'invalid');
            });
        });
    }

    validateInput(input) {
        const isValid = input.checkValidity();
        
        if (isValid) {
            input.classList.add('valid');
            input.classList.remove('invalid');
        } else {
            input.classList.add('invalid');
            input.classList.remove('valid');
            this.showValidationError(input);
        }
    }

    showValidationError(input) {
        // Remove existing error message
        const existingError = input.parentNode.querySelector('.validation-error');
        if (existingError) {
            existingError.remove();
        }
        
        // Create new error message
        const errorMsg = document.createElement('div');
        errorMsg.className = 'validation-error';
        errorMsg.textContent = input.validationMessage;
        errorMsg.style.cssText = `
            color: #ef4444;
            font-size: 0.8rem;
            margin-top: 4px;
            animation: fadeInUp 0.3s ease;
        `;
        
        input.parentNode.appendChild(errorMsg);
    }

    setupPerformanceOptimizations() {
        // Throttle resize events
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.handleResize();
            }, 250);
        });
        
        // Pause animations when tab is hidden
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                document.body.classList.add('paused');
            } else {
                document.body.classList.remove('paused');
            }
        });
        
        // Reduce motion for users who prefer it
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            document.body.classList.add('reduce-motion');
        }
    }

    handleResize() {
        // Refresh observer elements after resize
        this.observer.disconnect();
        this.observeElements();
    }

    // Public methods for external control
    pauseAnimations() {
        document.body.classList.add('paused');
    }

    resumeAnimations() {
        document.body.classList.remove('paused');
    }

    destroy() {
        if (this.observer) {
            this.observer.disconnect();
        }
    }
}

// CSS for additional effects (injected dynamically)
const additionalCSS = `
/* Ripple Animation */
@keyframes ripple {
    to {
        transform: scale(4);
        opacity: 0;
    }
}

/* Slide animations */
@keyframes slideInRight {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

@keyframes slideOutRight {
    to {
        transform: translateX(100%);
        opacity: 0;
    }
}

/* API Loading State */
body.api-loading::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 3px;
    background: linear-gradient(90deg, transparent, #667eea, transparent);
    z-index: 10000;
    animation: loadingBar 1s ease-in-out infinite;
}

@keyframes loadingBar {
    0% {
        transform: translateX(-100%);
    }
    100% {
        transform: translateX(100%);
    }
}

/* Form Validation States */
input.valid, textarea.valid {
    border-color: #10b981;
    box-shadow: 0 0 0 1px #10b981;
}

input.invalid, textarea.invalid {
    border-color: #ef4444;
    box-shadow: 0 0 0 1px #ef4444;
    animation: shake 0.3s ease;
}

/* Paused animations */
body.paused * {
    animation-play-state: paused !important;
}

/* Reduced motion */
body.reduce-motion * {
    animation: none !important;
    transition: none !important;
}
`;

// Inject additional CSS
const style = document.createElement('style');
style.textContent = additionalCSS;
document.head.appendChild(style);

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.enhancedEffects = new EnhancedEffects();
    });
} else {
    window.enhancedEffects = new EnhancedEffects();
}

// Export for external use
if (typeof window !== 'undefined') {
    window.EnhancedEffects = EnhancedEffects;
}