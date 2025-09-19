// Kitchen Chat Authentication Module
class AuthManager {
    constructor() {
        this.currentUser = null;
        this.authStateListeners = [];
        this.init();
    }

    async init() {
        try {
            // Initialize Firebase Auth (will be loaded from CDN)
            this.initFirebaseAuth();
            
            // Check for existing session
            await this.checkAuthState();
            
            console.log('Auth Manager initialized');
        } catch (error) {
            console.error('Failed to initialize Auth Manager:', error);
        }
    }

    initFirebaseAuth() {
        // Firebase auth state listener
        if (typeof firebase !== 'undefined') {
            firebase.auth().onAuthStateChanged((user) => {
                this.handleAuthStateChange(user);
            });
        } else {
            console.error('Firebase not loaded');
        }
    }

    async checkAuthState() {
        // Check localStorage for cached user data
        const cachedUser = localStorage.getItem('kitchenChatUser');
        if (cachedUser) {
            try {
                this.currentUser = JSON.parse(cachedUser);
                this.notifyAuthStateListeners(this.currentUser);
            } catch (error) {
                console.error('Failed to parse cached user:', error);
                localStorage.removeItem('kitchenChatUser');
            }
        }
    }

    handleAuthStateChange(firebaseUser) {
        if (firebaseUser) {
            // User is signed in
            this.currentUser = {
                uid: firebaseUser.uid,
                email: firebaseUser.email,
                displayName: firebaseUser.displayName || 'Anonymous',
                photoURL: firebaseUser.photoURL,
                emailVerified: firebaseUser.emailVerified,
                createdAt: firebaseUser.metadata.creationTime,
                lastSignIn: firebaseUser.metadata.lastSignInTime
            };
            
            // Cache user data
            localStorage.setItem('kitchenChatUser', JSON.stringify(this.currentUser));
            
            // Load user profile from Firestore
            this.loadUserProfile();
        } else {
            // User is signed out
            this.currentUser = null;
            localStorage.removeItem('kitchenChatUser');
            localStorage.removeItem('kitchenChatUserProfile');
        }
        
        this.notifyAuthStateListeners(this.currentUser);
    }

    async loadUserProfile() {
        if (!this.currentUser) return;
        
        try {
            const response = await fetch('/api/user-profile', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${await this.getIdToken()}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const profile = await response.json();
                this.currentUser.profile = profile;
                localStorage.setItem('kitchenChatUser', JSON.stringify(this.currentUser));
                this.notifyAuthStateListeners(this.currentUser);
            }
        } catch (error) {
            console.error('Failed to load user profile:', error);
        }
    }

    async getIdToken() {
        if (firebase.auth().currentUser) {
            return await firebase.auth().currentUser.getIdToken();
        }
        return null;
    }

    // Authentication Methods
    async signUpWithEmail(email, password, displayName) {
        try {
            const userCredential = await firebase.auth().createUserWithEmailAndPassword(email, password);
            
            // Update profile with display name
            await userCredential.user.updateProfile({
                displayName: displayName
            });
            
            // Create user profile in Firestore
            await this.createUserProfile({
                displayName: displayName,
                email: email,
                bio: '',
                status: 'online',
                joinedAt: new Date().toISOString()
            });
            
            return { success: true, user: userCredential.user };
        } catch (error) {
            console.error('Sign up error:', error);
            return { success: false, error: error.message };
        }
    }

    async signInWithEmail(email, password) {
        try {
            const userCredential = await firebase.auth().signInWithEmailAndPassword(email, password);
            return { success: true, user: userCredential.user };
        } catch (error) {
            console.error('Sign in error:', error);
            return { success: false, error: error.message };
        }
    }

    async signInWithGoogle() {
        try {
            const provider = new firebase.auth.GoogleAuthProvider();
            provider.addScope('profile');
            provider.addScope('email');
            
            const result = await firebase.auth().signInWithPopup(provider);
            
            // Check if this is a new user and create profile
            if (result.additionalUserInfo.isNewUser) {
                await this.createUserProfile({
                    displayName: result.user.displayName,
                    email: result.user.email,
                    photoURL: result.user.photoURL,
                    bio: '',
                    status: 'online',
                    joinedAt: new Date().toISOString()
                });
            }
            
            return { success: true, user: result.user };
        } catch (error) {
            console.error('Google sign in error:', error);
            return { success: false, error: error.message };
        }
    }

    async signOut() {
        try {
            await firebase.auth().signOut();
            return { success: true };
        } catch (error) {
            console.error('Sign out error:', error);
            return { success: false, error: error.message };
        }
    }

    async resetPassword(email) {
        try {
            await firebase.auth().sendPasswordResetEmail(email);
            return { success: true };
        } catch (error) {
            console.error('Password reset error:', error);
            return { success: false, error: error.message };
        }
    }

    // Profile Management
    async createUserProfile(profileData) {
        try {
            const response = await fetch('/api/user-profile', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${await this.getIdToken()}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(profileData)
            });
            
            if (response.ok) {
                const profile = await response.json();
                return { success: true, profile };
            } else {
                throw new Error('Failed to create profile');
            }
        } catch (error) {
            console.error('Create profile error:', error);
            return { success: false, error: error.message };
        }
    }

    async updateUserProfile(updates) {
        try {
            // Update Firebase Auth profile
            if (updates.displayName || updates.photoURL) {
                await firebase.auth().currentUser.updateProfile({
                    displayName: updates.displayName,
                    photoURL: updates.photoURL
                });
            }
            
            // Update Firestore profile
            const response = await fetch('/api/user-profile', {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${await this.getIdToken()}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updates)
            });
            
            if (response.ok) {
                const updatedProfile = await response.json();
                this.currentUser.profile = updatedProfile;
                localStorage.setItem('kitchenChatUser', JSON.stringify(this.currentUser));
                this.notifyAuthStateListeners(this.currentUser);
                return { success: true, profile: updatedProfile };
            } else {
                throw new Error('Failed to update profile');
            }
        } catch (error) {
            console.error('Update profile error:', error);
            return { success: false, error: error.message };
        }
    }

    async uploadProfilePicture(file) {
        if (!file || !this.currentUser) {
            return { success: false, error: 'No file or user' };
        }
        
        try {
            // Create FormData for file upload
            const formData = new FormData();
            formData.append('profilePicture', file);
            
            const response = await fetch('/api/upload-profile-picture', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${await this.getIdToken()}`
                },
                body: formData
            });
            
            if (response.ok) {
                const result = await response.json();
                
                // Update profile with new photo URL
                await this.updateUserProfile({ photoURL: result.photoURL });
                
                return { success: true, photoURL: result.photoURL };
            } else {
                throw new Error('Failed to upload picture');
            }
        } catch (error) {
            console.error('Upload profile picture error:', error);
            return { success: false, error: error.message };
        }
    }

    // Status Management
    async updateUserStatus(status) {
        if (!this.currentUser) return;
        
        try {
            const response = await fetch('/api/user-status', {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${await this.getIdToken()}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ status })
            });
            
            if (response.ok) {
                this.currentUser.profile.status = status;
                localStorage.setItem('kitchenChatUser', JSON.stringify(this.currentUser));
                this.notifyAuthStateListeners(this.currentUser);
            }
        } catch (error) {
            console.error('Update status error:', error);
        }
    }

    // Event Listeners
    addAuthStateListener(callback) {
        this.authStateListeners.push(callback);
        // Immediately call with current state
        callback(this.currentUser);
    }

    removeAuthStateListener(callback) {
        this.authStateListeners = this.authStateListeners.filter(listener => listener !== callback);
    }

    notifyAuthStateListeners(user) {
        this.authStateListeners.forEach(listener => {
            try {
                listener(user);
            } catch (error) {
                console.error('Auth state listener error:', error);
            }
        });
    }

    // Utility Methods
    isAuthenticated() {
        return this.currentUser !== null;
    }

    getUserDisplayName() {
        if (!this.currentUser) return 'Anonymous';
        return this.currentUser.profile?.displayName || this.currentUser.displayName || 'User';
    }

    getUserPhotoURL() {
        if (!this.currentUser) return null;
        return this.currentUser.profile?.photoURL || this.currentUser.photoURL;
    }

    getUserStatus() {
        if (!this.currentUser?.profile) return 'offline';
        return this.currentUser.profile.status || 'offline';
    }

    // Activity Tracking
    startActivityTracking() {
        if (!this.isAuthenticated()) return;
        
        // Update status to online
        this.updateUserStatus('online');
        
        // Set up activity tracking
        this.lastActivity = Date.now();
        
        // Track mouse/keyboard activity
        const updateActivity = () => {
            this.lastActivity = Date.now();
        };
        
        document.addEventListener('mousemove', updateActivity);
        document.addEventListener('keypress', updateActivity);
        document.addEventListener('click', updateActivity);
        
        // Check for inactivity every minute
        this.activityInterval = setInterval(() => {
            const now = Date.now();
            const timeSinceActivity = now - this.lastActivity;
            
            if (timeSinceActivity > 300000) { // 5 minutes
                this.updateUserStatus('away');
            } else if (timeSinceActivity > 60000) { // 1 minute
                // User is active but not moving mouse/typing
            }
        }, 60000);
        
        // Update status to offline when page unloads
        window.addEventListener('beforeunload', () => {
            this.updateUserStatus('offline');
        });
    }

    stopActivityTracking() {
        if (this.activityInterval) {
            clearInterval(this.activityInterval);
        }
        this.updateUserStatus('offline');
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.AuthManager = AuthManager;
}