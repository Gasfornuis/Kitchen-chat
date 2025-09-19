// Kitchen Chat Authentication UI Module
class AuthUI {
    constructor(authManager) {
        this.authManager = authManager;
        this.currentView = 'login'; // 'login', 'register', 'profile', 'forgot'
        this.init();
    }

    init() {
        this.createAuthModal();
        this.bindEvents();
        
        // Listen to auth state changes
        this.authManager.addAuthStateListener((user) => {
            this.handleAuthStateChange(user);
        });
    }

    createAuthModal() {
        const authModalHTML = `
            <div class="auth-modal-overlay" id="authModalOverlay">
                <div class="auth-modal">
                    <div class="auth-modal-header">
                        <h2 id="authModalTitle">Welcome to Kitchen Chat</h2>
                        <button class="auth-close-btn" id="authCloseBtn">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    
                    <div class="auth-modal-body">
                        <!-- Login Form -->
                        <div class="auth-form" id="loginForm">
                            <div class="auth-social-buttons">
                                <button class="google-signin-btn" id="googleSigninBtn">
                                    <i class="fab fa-google"></i>
                                    <span>Continue with Google</span>
                                </button>
                            </div>
                            
                            <div class="auth-divider">
                                <span>or</span>
                            </div>
                            
                            <form id="emailLoginForm">
                                <div class="form-group">
                                    <label for="loginEmail">Email</label>
                                    <input type="email" id="loginEmail" placeholder="your@email.com" required>
                                </div>
                                
                                <div class="form-group">
                                    <label for="loginPassword">Password</label>
                                    <div class="password-input">
                                        <input type="password" id="loginPassword" placeholder="Your password" required>
                                        <button type="button" class="password-toggle" data-target="loginPassword">
                                            <i class="fas fa-eye"></i>
                                        </button>
                                    </div>
                                </div>
                                
                                <button type="submit" class="auth-submit-btn">
                                    <span class="btn-text">Sign In</span>
                                    <i class="fas fa-arrow-right btn-icon"></i>
                                </button>
                            </form>
                            
                            <div class="auth-links">
                                <button class="auth-link" id="showRegisterBtn">Create an account</button>
                                <button class="auth-link" id="showForgotBtn">Forgot password?</button>
                            </div>
                        </div>
                        
                        <!-- Register Form -->
                        <div class="auth-form" id="registerForm" style="display: none;">
                            <form id="emailRegisterForm">
                                <div class="form-group">
                                    <label for="registerName">Display Name</label>
                                    <input type="text" id="registerName" placeholder="Your name" required maxlength="50">
                                </div>
                                
                                <div class="form-group">
                                    <label for="registerEmail">Email</label>
                                    <input type="email" id="registerEmail" placeholder="your@email.com" required>
                                </div>
                                
                                <div class="form-group">
                                    <label for="registerPassword">Password</label>
                                    <div class="password-input">
                                        <input type="password" id="registerPassword" placeholder="Choose a password" required minlength="6">
                                        <button type="button" class="password-toggle" data-target="registerPassword">
                                            <i class="fas fa-eye"></i>
                                        </button>
                                    </div>
                                    <div class="password-requirements">
                                        <small>At least 6 characters</small>
                                    </div>
                                </div>
                                
                                <div class="form-group">
                                    <label for="confirmPassword">Confirm Password</label>
                                    <div class="password-input">
                                        <input type="password" id="confirmPassword" placeholder="Confirm password" required>
                                        <button type="button" class="password-toggle" data-target="confirmPassword">
                                            <i class="fas fa-eye"></i>
                                        </button>
                                    </div>
                                </div>
                                
                                <button type="submit" class="auth-submit-btn">
                                    <span class="btn-text">Create Account</span>
                                    <i class="fas fa-arrow-right btn-icon"></i>
                                </button>
                            </form>
                            
                            <div class="auth-links">
                                <button class="auth-link" id="showLoginBtn">Already have an account?</button>
                            </div>
                        </div>
                        
                        <!-- Forgot Password Form -->
                        <div class="auth-form" id="forgotForm" style="display: none;">
                            <form id="forgotPasswordForm">
                                <p class="auth-description">Enter your email address and we'll send you a link to reset your password.</p>
                                
                                <div class="form-group">
                                    <label for="forgotEmail">Email</label>
                                    <input type="email" id="forgotEmail" placeholder="your@email.com" required>
                                </div>
                                
                                <button type="submit" class="auth-submit-btn">
                                    <span class="btn-text">Send Reset Link</span>
                                    <i class="fas fa-paper-plane btn-icon"></i>
                                </button>
                            </form>
                            
                            <div class="auth-links">
                                <button class="auth-link" id="backToLoginBtn">Back to sign in</button>
                            </div>
                        </div>
                        
                        <!-- Loading State -->
                        <div class="auth-loading" id="authLoading" style="display: none;">
                            <div class="loading-spinner">
                                <i class="fas fa-spinner fa-spin"></i>
                            </div>
                            <p>Please wait...</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- User Profile Modal -->
            <div class="profile-modal-overlay" id="profileModalOverlay">
                <div class="profile-modal">
                    <div class="profile-modal-header">
                        <h2>Profile Settings</h2>
                        <button class="profile-close-btn" id="profileCloseBtn">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    
                    <div class="profile-modal-body">
                        <div class="profile-picture-section">
                            <div class="profile-picture-wrapper">
                                <img id="profilePicture" src="" alt="Profile picture" class="profile-picture">
                                <button class="change-picture-btn" id="changePictureBtn">
                                    <i class="fas fa-camera"></i>
                                </button>
                                <input type="file" id="profilePictureInput" accept="image/*" style="display: none;">
                            </div>
                        </div>
                        
                        <form id="profileForm">
                            <div class="form-group">
                                <label for="profileDisplayName">Display Name</label>
                                <input type="text" id="profileDisplayName" maxlength="50" required>
                            </div>
                            
                            <div class="form-group">
                                <label for="profileBio">Bio</label>
                                <textarea id="profileBio" placeholder="Tell others about yourself..." maxlength="200" rows="3"></textarea>
                                <div class="char-count" id="bioCharCount">0/200</div>
                            </div>
                            
                            <div class="form-group">
                                <label for="profileStatus">Status</label>
                                <select id="profileStatus">
                                    <option value="online">🟢 Online</option>
                                    <option value="away">🟡 Away</option>
                                    <option value="busy">🔴 Busy</option>
                                    <option value="offline">⚫ Offline</option>
                                </select>
                            </div>
                            
                            <div class="form-section">
                                <h3>Preferences</h3>
                                
                                <div class="form-group checkbox-group">
                                    <label class="checkbox-label">
                                        <input type="checkbox" id="notificationsEnabled">
                                        <span class="checkbox-custom"></span>
                                        Enable notifications
                                    </label>
                                </div>
                                
                                <div class="form-group checkbox-group">
                                    <label class="checkbox-label">
                                        <input type="checkbox" id="soundEnabled">
                                        <span class="checkbox-custom"></span>
                                        Enable sounds
                                    </label>
                                </div>
                            </div>
                            
                            <div class="profile-actions">
                                <button type="submit" class="profile-save-btn">
                                    <span class="btn-text">Save Changes</span>
                                    <i class="fas fa-check btn-icon"></i>
                                </button>
                                
                                <button type="button" class="profile-logout-btn" id="logoutBtn">
                                    <span class="btn-text">Sign Out</span>
                                    <i class="fas fa-sign-out-alt btn-icon"></i>
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', authModalHTML);
    }

    bindEvents() {
        // Auth modal events
        document.getElementById('authCloseBtn').addEventListener('click', () => this.hideAuthModal());
        document.getElementById('profileCloseBtn').addEventListener('click', () => this.hideProfileModal());
        
        // View switching
        document.getElementById('showRegisterBtn').addEventListener('click', () => this.showView('register'));
        document.getElementById('showLoginBtn').addEventListener('click', () => this.showView('login'));
        document.getElementById('showForgotBtn').addEventListener('click', () => this.showView('forgot'));
        document.getElementById('backToLoginBtn').addEventListener('click', () => this.showView('login'));
        
        // Form submissions
        document.getElementById('emailLoginForm').addEventListener('submit', (e) => this.handleLogin(e));
        document.getElementById('emailRegisterForm').addEventListener('submit', (e) => this.handleRegister(e));
        document.getElementById('forgotPasswordForm').addEventListener('submit', (e) => this.handleForgotPassword(e));
        document.getElementById('profileForm').addEventListener('submit', (e) => this.handleProfileUpdate(e));
        
        // Social login
        document.getElementById('googleSigninBtn').addEventListener('click', () => this.handleGoogleSignin());
        
        // Profile actions
        document.getElementById('logoutBtn').addEventListener('click', () => this.handleLogout());
        document.getElementById('changePictureBtn').addEventListener('click', () => {
            document.getElementById('profilePictureInput').click();
        });
        document.getElementById('profilePictureInput').addEventListener('change', (e) => this.handleProfilePictureChange(e));
        
        // Password toggles
        document.querySelectorAll('.password-toggle').forEach(btn => {
            btn.addEventListener('click', (e) => this.togglePasswordVisibility(e));
        });
        
        // Bio character count
        document.getElementById('profileBio').addEventListener('input', (e) => {
            document.getElementById('bioCharCount').textContent = `${e.target.value.length}/200`;
        });
        
        // Close modals on overlay click
        document.getElementById('authModalOverlay').addEventListener('click', (e) => {
            if (e.target.id === 'authModalOverlay') this.hideAuthModal();
        });
        document.getElementById('profileModalOverlay').addEventListener('click', (e) => {
            if (e.target.id === 'profileModalOverlay') this.hideProfileModal();
        });
    }

    handleAuthStateChange(user) {
        if (user) {
            // User is logged in
            this.hideAuthModal();
            this.updateUserUI(user);
        } else {
            // User is logged out
            this.showAuthModal();
            this.clearUserUI();
        }
    }

    showAuthModal() {
        document.getElementById('authModalOverlay').classList.add('active');
        this.showView('login');
    }

    hideAuthModal() {
        document.getElementById('authModalOverlay').classList.remove('active');
    }

    showProfileModal() {
        if (!this.authManager.isAuthenticated()) return;
        
        const user = this.authManager.currentUser;
        const profile = user.profile || {};
        
        // Populate form
        document.getElementById('profileDisplayName').value = user.displayName || '';
        document.getElementById('profileBio').value = profile.bio || '';
        document.getElementById('profileStatus').value = profile.status || 'online';
        document.getElementById('notificationsEnabled').checked = profile.preferences?.notifications !== false;
        document.getElementById('soundEnabled').checked = profile.preferences?.soundEnabled !== false;
        
        // Set profile picture
        const profilePicture = document.getElementById('profilePicture');
        if (user.photoURL) {
            profilePicture.src = user.photoURL;
            profilePicture.style.display = 'block';
        } else {
            profilePicture.style.display = 'none';
        }
        
        // Update character count
        const bioLength = (profile.bio || '').length;
        document.getElementById('bioCharCount').textContent = `${bioLength}/200`;
        
        document.getElementById('profileModalOverlay').classList.add('active');
    }

    hideProfileModal() {
        document.getElementById('profileModalOverlay').classList.remove('active');
    }

    showView(viewName) {
        // Hide all forms
        document.querySelectorAll('.auth-form').forEach(form => {
            form.style.display = 'none';
        });
        
        // Show selected form
        const targetForm = document.getElementById(`${viewName}Form`);
        if (targetForm) {
            targetForm.style.display = 'block';
        }
        
        // Update title
        const titles = {
            login: 'Welcome to Kitchen Chat',
            register: 'Create Your Account',
            forgot: 'Reset Your Password'
        };
        
        document.getElementById('authModalTitle').textContent = titles[viewName] || 'Kitchen Chat';
        this.currentView = viewName;
    }

    showLoading(show) {
        document.getElementById('authLoading').style.display = show ? 'block' : 'none';
        document.querySelectorAll('.auth-form').forEach(form => {
            form.style.display = show ? 'none' : (form.id === `${this.currentView}Form` ? 'block' : 'none');
        });
    }

    async handleLogin(e) {
        e.preventDefault();
        
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;
        
        this.showLoading(true);
        
        const result = await this.authManager.signInWithEmail(email, password);
        
        this.showLoading(false);
        
        if (!result.success) {
            this.showError(result.error);
        }
    }

    async handleRegister(e) {
        e.preventDefault();
        
        const displayName = document.getElementById('registerName').value;
        const email = document.getElementById('registerEmail').value;
        const password = document.getElementById('registerPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        
        if (password !== confirmPassword) {
            this.showError('Passwords do not match');
            return;
        }
        
        this.showLoading(true);
        
        const result = await this.authManager.signUpWithEmail(email, password, displayName);
        
        this.showLoading(false);
        
        if (result.success) {
            this.showSuccess('Account created successfully! Please check your email.');
        } else {
            this.showError(result.error);
        }
    }

    async handleForgotPassword(e) {
        e.preventDefault();
        
        const email = document.getElementById('forgotEmail').value;
        
        this.showLoading(true);
        
        const result = await this.authManager.resetPassword(email);
        
        this.showLoading(false);
        
        if (result.success) {
            this.showSuccess('Password reset email sent! Check your inbox.');
            this.showView('login');
        } else {
            this.showError(result.error);
        }
    }

    async handleGoogleSignin() {
        this.showLoading(true);
        
        const result = await this.authManager.signInWithGoogle();
        
        this.showLoading(false);
        
        if (!result.success) {
            this.showError(result.error);
        }
    }

    async handleProfileUpdate(e) {
        e.preventDefault();
        
        const updates = {
            displayName: document.getElementById('profileDisplayName').value,
            bio: document.getElementById('profileBio').value,
            status: document.getElementById('profileStatus').value,
            notifications: document.getElementById('notificationsEnabled').checked,
            soundEnabled: document.getElementById('soundEnabled').checked
        };
        
        const result = await this.authManager.updateUserProfile(updates);
        
        if (result.success) {
            this.showSuccess('Profile updated successfully!');
            this.hideProfileModal();
        } else {
            this.showError(result.error);
        }
    }

    async handleProfilePictureChange(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        // Validate file
        if (!file.type.startsWith('image/')) {
            this.showError('Please select an image file');
            return;
        }
        
        if (file.size > 5 * 1024 * 1024) { // 5MB limit
            this.showError('File size must be less than 5MB');
            return;
        }
        
        // Show preview
        const reader = new FileReader();
        reader.onload = (e) => {
            document.getElementById('profilePicture').src = e.target.result;
            document.getElementById('profilePicture').style.display = 'block';
        };
        reader.readAsDataURL(file);
        
        // Upload file
        const result = await this.authManager.uploadProfilePicture(file);
        
        if (!result.success) {
            this.showError(result.error);
            // Reset preview on error
            const currentPhotoURL = this.authManager.getUserPhotoURL();
            if (currentPhotoURL) {
                document.getElementById('profilePicture').src = currentPhotoURL;
            } else {
                document.getElementById('profilePicture').style.display = 'none';
            }
        }
    }

    async handleLogout() {
        const result = await this.authManager.signOut();
        
        if (result.success) {
            this.hideProfileModal();
        } else {
            this.showError(result.error);
        }
    }

    togglePasswordVisibility(e) {
        const button = e.currentTarget;
        const targetId = button.dataset.target;
        const input = document.getElementById(targetId);
        const icon = button.querySelector('i');
        
        if (input.type === 'password') {
            input.type = 'text';
            icon.className = 'fas fa-eye-slash';
        } else {
            input.type = 'password';
            icon.className = 'fas fa-eye';
        }
    }

    updateUserUI(user) {
        // Update header with user info
        const header = document.querySelector('.header-content');
        if (header) {
            const existingUserInfo = header.querySelector('.user-info');
            if (existingUserInfo) {
                existingUserInfo.remove();
            }
            
            const userInfo = document.createElement('div');
            userInfo.className = 'user-info';
            userInfo.innerHTML = `
                <div class="user-avatar" onclick="window.authUI.showProfileModal()">
                    ${user.photoURL ? 
                        `<img src="${user.photoURL}" alt="${user.displayName}" class="avatar-image">` :
                        `<div class="avatar-placeholder">${(user.displayName || 'U').charAt(0).toUpperCase()}</div>`
                    }
                    <div class="status-indicator ${this.authManager.getUserStatus()}"></div>
                </div>
                <div class="user-details">
                    <span class="user-name">${user.displayName}</span>
                    <span class="user-status">${this.getStatusText(this.authManager.getUserStatus())}</span>
                </div>
            `;
            
            header.appendChild(userInfo);
        }
    }

    clearUserUI() {
        const userInfo = document.querySelector('.user-info');
        if (userInfo) {
            userInfo.remove();
        }
    }

    getStatusText(status) {
        const statusMap = {
            online: '🟢 Online',
            away: '🟡 Away',
            busy: '🔴 Busy',
            offline: '⚫ Offline'
        };
        return statusMap[status] || statusMap.offline;
    }

    showError(message) {
        // Use existing toast system from main app
        if (window.kitchenChat) {
            window.kitchenChat.showToast(message, 'error');
        } else {
            alert(message); // Fallback
        }
    }

    showSuccess(message) {
        // Use existing toast system from main app
        if (window.kitchenChat) {
            window.kitchenChat.showToast(message, 'success');
        } else {
            alert(message); // Fallback
        }
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.AuthUI = AuthUI;
}