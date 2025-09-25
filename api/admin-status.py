"""Secure Admin Status API - CRITICAL SECURITY FIX

FIXES PRIVILEGE ESCALATION VULNERABILITY:
- No more hardcoded admin lists
- No more displayName-based admin checks  
- Uses immutable UID-based role checking
- Server-side only validation
"""

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

# Import secure RBAC system
from .rbac import is_admin, has_permission, log_admin_action, RBACError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security.admin')

# Initialize Firebase (consistent with other files)
if not firebase_admin._apps:
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized successfully")
    else:
        logger.warning("Warning: Running in demo mode without Firebase")

db = fb_firestore.client() if firebase_admin._apps else None

# SECURE CORS CONFIGURATION - No wildcards!
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

if ENVIRONMENT == "production":
    ALLOWED_ORIGINS = [
        'https://kitchenchat.live',
        'https://www.kitchenchat.live',
        'https://kitchen-chat.vercel.app'
    ]
else:
    ALLOWED_ORIGINS = [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'https://kitchen-chat.vercel.app',
        'https://kitchenchat.live',
        'https://www.kitchenchat.live'
    ]

# Rate limiting storage
rate_limit_storage = defaultdict(list)

def get_client_ip(headers):
    """Get real client IP from headers"""
    forwarded = headers.get('x-forwarded-for', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return headers.get('x-real-ip', headers.get('remote-addr', 'unknown'))

def check_rate_limit(client_ip, endpoint, max_requests=20, time_window=60):
    """Rate limiting for API calls"""
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
    """Get safe CORS origin instead of wildcard - NO VULNERABILITIES!"""
    origin = request_headers.get('Origin', '')
    if origin in ALLOWED_ORIGINS:
        return origin
    
    # Log suspicious origin attempts
    if origin:
        security_logger.warning(f"Blocked suspicious origin: {origin}")
    
    return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else 'null'

def sha256_hash(text):
    """SHA-256 hash utility for session tokens (not passwords!)"""
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
    """Verify session token and return user info with UID"""
    if not token:
        return None
    
    token_hash = hash_session_token(token)
    
    if not db:
        # Demo mode - return demo user for testing
        return {
            "uid": "demo_admin_uid",  # Demo UID for testing
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
        
        # CRITICAL: Return UID for RBAC, not just username/displayName!
        return {
            "uid": session_data.get('uid'),  # Must be stored in session!
            "username": session_data.get('username'),
            "displayName": session_data.get('displayName')
        }
        
    except Exception as e:
        logger.error(f"Session verification error: {e}")
        return None

def require_authentication(request):
    """Require valid authentication, return user info with UID or None"""
    token = get_session_token_from_request(request)
    return verify_session_token(token)

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
        self.send_header('X-XSS-Protection', '1; mode=block')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        
        self.end_headers()
    
    def send_json_response(self, data, status=200):
        """Send JSON response with comprehensive security headers"""
        safe_origin = get_safe_origin(self.headers)
        
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', safe_origin)
        self.send_header('Access-Control-Allow-Credentials', 'true')
        
        # Comprehensive security headers
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'X-Permitted-Cross-Domain-Policies': 'none',
            'Cache-Control': 'no-store, no-cache, must-revalidate, private',
            'Pragma': 'no-cache'
        }
        
        # Apply security headers
        for header, value in security_headers.items():
            self.send_header(header, value)
        
        # Production-only headers
        if ENVIRONMENT == 'production':
            self.send_header('Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload')
        
        self.end_headers()
        
        # Ensure UTF-8 encoding
        json_str = json.dumps(data, ensure_ascii=False)
        self.wfile.write(json_str.encode('utf-8'))
    
    def send_error_response(self, error, status=500):
        """Send secure error response without information disclosure"""
        client_ip = get_client_ip(self.headers)
        logger.error(f"Admin Status API Error {status} from {client_ip}: {error}")
        
        # Sanitize error for client security
        public_error = error
        if status >= 500:
            public_error = "Internal server error. Please try again."
        elif 'database' in str(error).lower() or 'firestore' in str(error).lower():
            public_error = "Service temporarily unavailable."
        
        self.send_json_response({'error': public_error}, status)
    
    def do_GET(self):
        """SECURE admin status check - UID-based RBAC only!"""
        client_ip = get_client_ip(self.headers)
        
        # Rate limiting - admin status checks
        if not check_rate_limit(client_ip, 'admin_status', max_requests=20, time_window=60):
            return self.send_error_response("Too many requests. Please slow down.", 429)
        
        try:
            # Get authenticated user with UID
            current_user = require_authentication(self)
            
            if not current_user:
                return self.send_error_response("Authentication required", 401)
            
            # SECURE: Check admin permissions by UID only!
            user_uid = current_user.get('uid')
            if not user_uid:
                security_logger.error(f"Session missing UID for user: {current_user.get('username')}")
                return self.send_error_response("Invalid session data", 401)
            
            # Server-side RBAC check - NO displayName, NO hardcoded lists!
            is_user_admin = is_admin(user_uid)
            
            # Build permissions based on role
            permissions = {}
            if is_user_admin:
                permissions = {
                    'canCreateAnnouncements': True,
                    'canDeleteAnnouncements': True,
                    'canUpdateAnnouncements': True,
                    'canModeratePosts': True,
                    'canManageUsers': True
                }
            else:
                # Check granular permissions for non-admins
                permissions = {
                    'canCreateAnnouncements': has_permission(user_uid, 'announcements'),
                    'canDeleteAnnouncements': has_permission(user_uid, 'announcements'),
                    'canUpdateAnnouncements': has_permission(user_uid, 'announcements'),
                    'canModeratePosts': has_permission(user_uid, 'moderation'),
                    'canManageUsers': has_permission(user_uid, 'users')
                }
            
            # Return ONLY boolean and permissions - no sensitive data!
            response_data = {
                'success': True,
                'isAdmin': is_user_admin,
                'permissions': permissions,
                'user': {
                    'username': current_user.get('username'),
                    'displayName': current_user.get('displayName')
                    # NOTE: UID is NOT returned to client for security
                }
            }
            
            # Log admin status checks (but not too verbose)
            if is_user_admin:
                security_logger.info(f"Admin status confirmed for UID: {user_uid[:8]}...")
            
            return self.send_json_response(response_data)
        
        except RBACError as e:
            return self.send_error_response(str(e), 403)
        except Exception as e:
            logger.error(f"Admin status check failed: {e}")
            return self.send_error_response("Failed to check admin status", 500)