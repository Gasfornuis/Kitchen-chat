from http.server import BaseHTTPRequestHandler
import json
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore as fb_firestore
import os
import hashlib
import logging
import time
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')

# Initialize Firebase (consistent with other files)
if not firebase_admin._apps:
    # Load service account from environment variable
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized successfully")
    else:
        logger.warning("Warning: Running in demo mode without Firebase")

db = fb_firestore.client() if firebase_admin._apps else None

# VEILIGE CORS CONFIGURATIE
ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'https://kitchen-chat.vercel.app',
    'https://gasfornuis.github.io',
    'https://kitchenchat.live',
    'https://www.kitchenchat.live'
]

# Rate limiting storage
rate_limit_storage = defaultdict(list)

# VEILIGE SERVER-SIDE ADMIN CONFIGURATIE
ADMIN_USERS = ['daan25', 'gasfornuis']

def get_client_ip(headers):
    """Get real client IP from headers"""
    forwarded = headers.get('x-forwarded-for', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return headers.get('x-real-ip', headers.get('remote-addr', 'unknown'))

def check_rate_limit(client_ip, endpoint, max_requests=30, time_window=60):
    """Rate limiting voor API calls"""
    now = time.time()
    key = f"{client_ip}:{endpoint}"
    
    # Clean old entries
    rate_limit_storage[key] = [req_time for req_time in rate_limit_storage[key] if now - req_time < time_window]
    
    if len(rate_limit_storage[key]) >= max_requests:
        security_logger.warning(f"Rate limit exceeded for {client_ip} on {endpoint}")
        return False
    
    rate_limit_storage[key].append(now)
    return True

def get_safe_origin(request_headers):
    """Get safe CORS origin instead of wildcard"""
    origin = request_headers.get('Origin', '')
    if origin in ALLOWED_ORIGINS:
        return origin
    return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else 'null'

def sha256_hash(text):
    """SHA-256 hash utility"""
    return hashlib.sha256(text.encode()).hexdigest()

def get_session_token_from_request(request):
    """Extract session token from request headers or cookies"""
    # Try Authorization header first
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    
    # Try cookie (for web browsers)
    cookie_header = request.headers.get('Cookie', '')
    if cookie_header:
        cookies = {}
        for cookie in cookie_header.split(';'):
            if '=' in cookie:
                key, value = cookie.strip().split('=', 1)
                cookies[key] = value
        
        return cookies.get('kc_session')
    
    return None

def hash_session_token(token):
    """Hash session token for secure storage"""
    return sha256_hash(token)

def verify_session_token(token):
    """Verify session token and return user info"""
    if not token:
        return None
    
    token_hash = hash_session_token(token)
    
    if not db:
        # Demo mode - return demo user for testing
        return {
            "username": "demo",
            "displayName": "Demo User"
        }
    
    # Firestore mode
    try:
        doc = db.collection("Sessions").document(token_hash).get()
        
        if not doc.exists:
            return None
            
        session_data = doc.to_dict()
        expires_at = session_data.get('expiresAt')
        
        if expires_at and expires_at.timestamp() < datetime.now().timestamp():
            # Lazy cleanup - delete expired session
            doc.reference.delete()
            return None
            
        return {
            "username": session_data.get('username'),
            "displayName": session_data.get('displayName')
        }
        
    except Exception as e:
        logger.error(f"Session verification error: {e}")
        return None

def require_authentication(request):
    """Require valid authentication, return user info or None"""
    token = get_session_token_from_request(request)
    return verify_session_token(token)

def check_admin_permissions(user):
    """Check if user has admin permissions (server-side veilige controle)"""
    if not user:
        return False
    
    # Check if user is in de admin lijst (case insensitive)
    username = user.get('username', '').lower()
    display_name = user.get('displayName', '').lower()
    
    # Controleer beide username en displayName tegen de admin lijst
    for admin_user in ADMIN_USERS:
        if username == admin_user.lower() or display_name == admin_user.lower():
            return True
    
    return False

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle preflight requests with secure CORS"""
        safe_origin = get_safe_origin(self.headers)
        
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', safe_origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Access-Control-Max-Age', '86400')
        # Security headers
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.end_headers()
    
    def send_json_response(self, data, status=200):
        """Send JSON response with secure CORS headers"""
        safe_origin = get_safe_origin(self.headers)
        
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', safe_origin)
        self.send_header('Access-Control-Allow-Credentials', 'true')
        # Security headers
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('X-XSS-Protection', '1; mode=block')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_error_response(self, error, status=500):
        """Send secure error response"""
        logger.error(f"Admin Status API Error {status}: {error}")
        
        # Generic error for client security
        public_error = error
        if status == 500:
            public_error = "Internal server error. Please try again."
        
        self.send_json_response({'error': public_error}, status)
    
    def do_GET(self):
        """Check admin status for authenticated user with rate limiting"""
        client_ip = get_client_ip(self.headers)
        
        # Rate limiting - admin status checks
        if not check_rate_limit(client_ip, 'admin_status', max_requests=20, time_window=60):
            return self.send_error_response("Too many requests. Please slow down.", 429)
        
        try:
            # Get user from session
            current_user = require_authentication(self)
            
            if not current_user:
                return self.send_error_response("Authentication required", 401)
            
            # Check admin permissions
            is_admin = check_admin_permissions(current_user)
            
            # Return admin status with user info (no sensitive data)
            response_data = {
                'success': True,
                'user': {
                    'username': current_user.get('username'),
                    'displayName': current_user.get('displayName')
                },
                'isAdmin': is_admin,
                'permissions': {
                    'canCreateAnnouncements': is_admin,
                    'canDeleteAnnouncements': is_admin,
                    'canUpdateAnnouncements': is_admin,
                    'canManageBanlist': is_admin,
                    'canBanUsers': is_admin,
                    'canUnbanUsers': is_admin,
                    'canViewBanlist': is_admin
                }
            }
            
            # Log admin status check (but not too verbose)
            if is_admin:
                logger.info(f"Admin status confirmed for user: {current_user.get('username')}")
            
            return self.send_json_response(response_data)
        
        except Exception as e:
            return self.send_error_response(f"Failed to check admin status", 500)