/**
 * Enhanced UI System for Kitchen Chat - Professional & Mature Design
 * Implements sophisticated interactions and animations
 */

class EnhancedUISystem {
    constructor() {
        this.isInitialized = false;
        this.animationQueue = [];
        this.observers = new Map();
        this.modernEffects = {
            parallax: true,
            particles: false, // Disabled for mature look
            smoothScrolling: true,
            hoverEffects: true,
            typeWriter: false // Disabled for professional feel
        };
        
        this.init();
    }

    init() {
        if (this.isInitialized) return;
        
        console.log('🎨 Initializing Enhanced UI System...');
        
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setup());
        } else {
            this.setup();
        }
        
        this.isInitialized = true;
    }

    setup() {
        this.setupIntersectionObserver();
        this.setupSmoothInteractions();
        this.setupAdvancedAnimations();
        this.setupResponsiveHandlers();
        this.setupKeyboardNavigation();
        this.setupFocusManagement();
        this.initializeLoadingSequence();
        
        console.log('✨ Enhanced UI System initialized');
    }

    /**
     * Professional loading sequence with sophisticated transitions
     */
    initializeLoadingSequence() {
        const loadingScreen = document.getElementById('loadingScreen');
        const appContainer = document.getElementById('appContainer');
        
        if (!loadingScreen || !appContainer) return;

        // Enhanced loading with multiple phases
        const loadingPhases = [
            { text: 'Initializing secure connection...', delay: 800 },
            { text: 'Loading advanced features...', delay: 600 },
            { text: 'Optimizing user experience...', delay: 500 },
            { text: 'Ready to communicate...', delay: 400 }
        ];

        let currentPhase = 0;
        const loadingText = loadingScreen.querySelector('p');
        
        const advancePhase = () => {
            if (currentPhase < loadingPhases.length) {
                const phase = loadingPhases[currentPhase];
                if (loadingText) {
                    loadingText.style.opacity = '0';
                    setTimeout(() => {
                        loadingText.textContent = phase.text;
                        loadingText.style.opacity = '1';
                    }, 150);
                }
                currentPhase++;
                setTimeout(advancePhase, phase.delay);
            } else {
                this.completeLoading(loadingScreen, appContainer);
            }
        };

        // Start the loading sequence
        setTimeout(advancePhase, 500);
    }

    completeLoading(loadingScreen, appContainer) {
        // Professional fade-out with scale effect
        loadingScreen.style.transition = 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
        loadingScreen.style.opacity = '0';
        loadingScreen.style.transform = 'scale(1.05)';
        
        setTimeout(() => {
            loadingScreen.classList.add('hidden');
            appContainer.classList.add('loaded');
            this.animateAppEntrance();
        }, 800);
    }

    animateAppEntrance() {
        const elements = [
            { selector: '.header', delay: 0, animation: 'slideInDown' },
            { selector: '.sidebar', delay: 100, animation: 'slideInLeft' },
            { selector: '.chat-container', delay: 200, animation: 'fadeInUp' },
            { selector: '.welcome-content', delay: 400, animation: 'scaleIn' }
        ];

        elements.forEach(({ selector, delay, animation }) => {
            const element = document.querySelector(selector);
            if (element) {
                setTimeout(() => {
                    element.style.animation = `${animation} 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards`;
                }, delay);
            }
        });
    }

    /**
     * Setup intersection observer for scroll-based animations
     */
    setupIntersectionObserver() {
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '50px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.animateElement(entry.target);
                }
            });
        }, observerOptions);

        // Observe elements that should animate on scroll
        const animatedElements = document.querySelectorAll(
            '.subject-item, .message, .stat-item, .welcome-content > *'
        );
        
        animatedElements.forEach(el => observer.observe(el));
        this.observers.set('intersection', observer);
    }

    /**
     * Setup smooth interactions and micro-animations
     */
    setupSmoothInteractions() {
        // Enhanced button interactions
        this.setupButtonEffects();
        
        // Smooth hover effects for interactive elements
        this.setupHoverEffects();
        
        // Professional ripple effects
        this.setupRippleEffects();
        
        // Smooth transitions for modals and overlays
        this.setupModalTransitions();
    }

    setupButtonEffects() {
        const buttons = document.querySelectorAll(
            'button, .btn-primary, .btn-secondary, .new-subject-btn, .refresh-btn'
        );

        buttons.forEach(button => {
            // Add magnetic effect for large buttons
            if (button.classList.contains('new-subject-btn')) {
                this.addMagneticEffect(button);
            }

            // Enhanced click feedback
            button.addEventListener('mousedown', (e) => {
                this.createRipple(e, button);
            });

            // Smooth focus states
            button.addEventListener('focus', () => {
                button.style.transform = 'translateY(-1px)';
                button.style.boxShadow = '0 8px 25px rgba(0, 102, 255, 0.3)';
            });

            button.addEventListener('blur', () => {
                button.style.transform = '';
                button.style.boxShadow = '';
            });
        });
    }

    addMagneticEffect(element) {
        element.addEventListener('mousemove', (e) => {
            const rect = element.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;
            
            const strength = 0.1;
            element.style.transform = `translate(${x * strength}px, ${y * strength}px)`;
        });

        element.addEventListener('mouseleave', () => {
            element.style.transform = '';
            element.style.transition = 'transform 0.3s ease';
            setTimeout(() => {
                element.style.transition = '';
            }, 300);
        });
    }

    setupHoverEffects() {
        const hoverElements = document.querySelectorAll(
            '.subject-item, .message, .stat-item, .emoji-item, .context-item'
        );

        hoverElements.forEach(element => {
            element.addEventListener('mouseenter', () => {
                this.addHoverGlow(element);
            });

            element.addEventListener('mouseleave', () => {
                this.removeHoverGlow(element);
            });
        });
    }

    addHoverGlow(element) {
        element.style.boxShadow = '0 8px 32px rgba(0, 102, 255, 0.15), 0 2px 8px rgba(0, 0, 0, 0.1)';
        element.style.transform = 'translateY(-2px)';
    }

    removeHoverGlow(element) {
        element.style.boxShadow = '';
        element.style.transform = '';
    }

    setupRippleEffects() {
        const rippleElements = document.querySelectorAll(
            'button:not(.no-ripple), .clickable, .subject-item'
        );

        rippleElements.forEach(element => {
            element.style.position = 'relative';
            element.style.overflow = 'hidden';
        });
    }

    createRipple(event, element) {
        const ripple = document.createElement('div');
        const rect = element.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = event.clientX - rect.left - size / 2;
        const y = event.clientY - rect.top - size / 2;

        ripple.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            left: ${x}px;
            top: ${y}px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 50%;
            transform: scale(0);
            animation: ripple 0.6s cubic-bezier(0.4, 0, 0.2, 1);
            pointer-events: none;
            z-index: 1;
        `;

        element.appendChild(ripple);

        setTimeout(() => {
            ripple.remove();
        }, 600);
    }

    /**
     * Setup advanced animations and transitions
     */
    setupAdvancedAnimations() {
        // Add CSS animations for ripple effect
        if (!document.querySelector('#ripple-styles')) {
            const style = document.createElement('style');
            style.id = 'ripple-styles';
            style.textContent = `
                @keyframes ripple {
                    to {
                        transform: scale(2);
                        opacity: 0;
                    }
                }
                
                @keyframes slideInDown {
                    from {
                        opacity: 0;
                        transform: translateY(-20px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
                
                .professional-glow {
                    box-shadow: 0 0 30px rgba(0, 102, 255, 0.3);
                    transition: box-shadow 0.3s ease;
                }
                
                .smooth-scale {
                    transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
                }
                
                .smooth-scale:hover {
                    transform: scale(1.02);
                }
            `;
            document.head.appendChild(style);
        }
    }

    setupModalTransitions() {
        const modalOverlay = document.getElementById('modalOverlay');
        if (!modalOverlay) return;

        // Enhanced modal opening
        const originalShow = modalOverlay.style.display;
        const showModal = () => {
            modalOverlay.style.display = 'flex';
            modalOverlay.style.opacity = '0';
            
            requestAnimationFrame(() => {
                modalOverlay.classList.add('active');
                modalOverlay.style.opacity = '1';
            });
        };

        // Enhanced modal closing
        const hideModal = () => {
            modalOverlay.style.opacity = '0';
            setTimeout(() => {
                modalOverlay.classList.remove('active');
                modalOverlay.style.display = 'none';
            }, 300);
        };

        // Override default modal behavior if needed
        window.enhancedShowModal = showModal;
        window.enhancedHideModal = hideModal;
    }

    /**
     * Setup responsive behavior handlers
     */
    setupResponsiveHandlers() {
        let resizeTimeout;
        
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.handleResize();
            }, 250);
        });

        // Initial responsive setup
        this.handleResize();
    }

    handleResize() {
        const isMobile = window.innerWidth <= 768;
        const isTablet = window.innerWidth <= 1024 && window.innerWidth > 768;
        
        // Adjust animations based on screen size
        document.body.classList.toggle('mobile-view', isMobile);
        document.body.classList.toggle('tablet-view', isTablet);
        
        // Disable heavy animations on mobile for performance
        if (isMobile) {
            this.modernEffects.parallax = false;
            this.modernEffects.particles = false;
        } else {
            this.modernEffects.parallax = true;
        }
        
        // Update layout-dependent elements
        this.updateLayoutElements();
    }

    updateLayoutElements() {
        // Update emoji picker position on mobile
        const emojiPicker = document.getElementById('emojiPicker');
        if (emojiPicker && window.innerWidth <= 768) {
            emojiPicker.style.position = 'fixed';
            emojiPicker.style.bottom = '20px';
            emojiPicker.style.left = '20px';
            emojiPicker.style.right = '20px';
            emojiPicker.style.width = 'auto';
        }
    }

    /**
     * Setup professional keyboard navigation
     */
    setupKeyboardNavigation() {
        document.addEventListener('keydown', (e) => {
            // Professional shortcuts
            if (e.ctrlKey || e.metaKey) {
                switch(e.code) {
                    case 'KeyK':
                        e.preventDefault();
                        this.focusSearch();
                        break;
                    case 'KeyN':
                        e.preventDefault();
                        this.openNewConversation();
                        break;
                    case 'KeyF':
                        if (e.shiftKey) {
                            e.preventDefault();
                            this.toggleSearch();
                        }
                        break;
                    case 'Slash':
                        e.preventDefault();
                        this.showShortcuts();
                        break;
                }
            }
            
            // Escape key handling
            if (e.code === 'Escape') {
                this.handleEscape();
            }
        });
    }

    focusSearch() {
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.focus();
            searchInput.select();
        }
    }

    openNewConversation() {
        const newBtn = document.getElementById('newSubjectBtn');
        if (newBtn) {
            newBtn.click();
        }
    }

    toggleSearch() {
        // This would integrate with advanced search if implemented
        console.log('🔍 Advanced search toggle');
    }

    showShortcuts() {
        const shortcutsHelp = document.getElementById('shortcutsHelp');
        if (shortcutsHelp) {
            shortcutsHelp.style.display = shortcutsHelp.style.display === 'none' ? 'block' : 'none';
        }
    }

    handleEscape() {
        // Close any open modals or overlays
        const modal = document.getElementById('modalOverlay');
        const emojiPicker = document.getElementById('emojiPicker');
        const shortcuts = document.getElementById('shortcutsHelp');
        
        if (modal && modal.classList.contains('active')) {
            const closeBtn = modal.querySelector('.close-btn');
            if (closeBtn) closeBtn.click();
        }
        
        if (emojiPicker && emojiPicker.classList.contains('show')) {
            emojiPicker.classList.remove('show');
        }
        
        if (shortcuts && shortcuts.style.display !== 'none') {
            shortcuts.style.display = 'none';
        }
    }

    /**
     * Setup professional focus management
     */
    setupFocusManagement() {
        // Track focus for accessibility
        let focusedElement = null;
        
        document.addEventListener('focus', (e) => {
            focusedElement = e.target;
            this.enhanceFocus(e.target);
        }, true);
        
        document.addEventListener('blur', (e) => {
            this.removeFocusEnhancement(e.target);
        }, true);
        
        // Improve focus visibility
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Tab') {
                document.body.classList.add('keyboard-nav');
            }
        });
        
        document.addEventListener('mousedown', () => {
            document.body.classList.remove('keyboard-nav');
        });
    }

    enhanceFocus(element) {
        if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA' || element.tagName === 'BUTTON') {
            element.style.boxShadow = '0 0 0 2px rgba(0, 102, 255, 0.3)';
            element.style.borderColor = 'var(--accent-primary)';
        }
    }

    removeFocusEnhancement(element) {
        if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA' || element.tagName === 'BUTTON') {
            element.style.boxShadow = '';
            element.style.borderColor = '';
        }
    }

    /**
     * Animate element when it comes into view
     */
    animateElement(element) {
        if (element.classList.contains('animated')) return;
        
        element.classList.add('animated');
        
        // Choose animation based on element type
        let animation = 'fadeInUp';
        
        if (element.classList.contains('subject-item')) {
            animation = 'slideInLeft';
        } else if (element.classList.contains('stat-item')) {
            animation = 'scaleIn';
        } else if (element.classList.contains('message')) {
            animation = 'fadeInUp';
        }
        
        element.style.animation = `${animation} 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards`;
    }

    /**
     * Add professional toast notification
     */
    showToast(message, type = 'info', duration = 4000) {
        const toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        
        toastContainer.appendChild(toast);
        
        // Animate in
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Auto remove
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, duration);
        
        return toast;
    }

    /**
     * Professional loading state management
     */
    setLoadingState(element, loading = true) {
        if (loading) {
            element.classList.add('loading-state');
            element.style.opacity = '0.6';
            element.style.pointerEvents = 'none';
            
            // Add loading spinner if it's a button
            if (element.tagName === 'BUTTON') {
                const originalText = element.innerHTML;
                element.dataset.originalText = originalText;
                element.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            }
        } else {
            element.classList.remove('loading-state');
            element.style.opacity = '';
            element.style.pointerEvents = '';
            
            // Restore button text
            if (element.tagName === 'BUTTON' && element.dataset.originalText) {
                element.innerHTML = element.dataset.originalText;
                delete element.dataset.originalText;
            }
        }
    }

    /**
     * Enhanced smooth scrolling
     */
    smoothScrollTo(element, offset = 0) {
        const targetPosition = element.offsetTop - offset;
        const startPosition = window.pageYOffset;
        const distance = targetPosition - startPosition;
        const duration = 800;
        let start = null;
        
        const animation = (currentTime) => {
            if (start === null) start = currentTime;
            const timeElapsed = currentTime - start;
            const run = this.easeInOutCubic(timeElapsed, startPosition, distance, duration);
            window.scrollTo(0, run);
            if (timeElapsed < duration) requestAnimationFrame(animation);
        };
        
        requestAnimationFrame(animation);
    }

    easeInOutCubic(t, b, c, d) {
        t /= d / 2;
        if (t < 1) return c / 2 * t * t * t + b;
        t -= 2;
        return c / 2 * (t * t * t + 2) + b;
    }

    /**
     * Cleanup and destroy
     */
    destroy() {
        // Clean up observers
        this.observers.forEach(observer => observer.disconnect());
        this.observers.clear();
        
        // Remove event listeners
        // Note: In a real implementation, you'd want to store and remove all listeners
        
        console.log('🧹 Enhanced UI System destroyed');
    }
}

// Initialize the enhanced UI system
window.enhancedUI = new EnhancedUISystem();

// Export for potential module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EnhancedUISystem;
}

console.log('🚀 Enhanced UI System loaded');
