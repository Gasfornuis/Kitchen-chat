from http.server import BaseHTTPRequestHandler
import json
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore as fb_firestore
import os
import hashlib
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# VEILIGE SERVER-SIDE ADMIN CONFIGURATIE
# Deze lijst wordt alleen op de server gecontroleerd en is niet zichtbaar voor clients
ADMIN_USERS = ['daan25', 'gasfornuis']

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
            logger.info(f"Admin status check: GRANTED for user {username} (displayName: {display_name})")
            return True
    
    logger.info(f"Admin status check: DENIED for user {username} (displayName: {display_name})")
    return False

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
    
    def send_json_response(self, data, status=200):
        """Send JSON response with CORS headers"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_error_response(self, error, status=500):
        """Send error response"""
        logger.error(f"Admin Status API Error: {error}")
        self.send_json_response({'error': str(error)}, status)
    
    def do_GET(self):
        """Check admin status for authenticated user"""
        try:
            # Get user from session
            current_user = require_authentication(self)
            
            if not current_user:
                return self.send_error_response("Authentication required", 401)
            
            # Check admin permissions
            is_admin = check_admin_permissions(current_user)
            
            # Return admin status with user info
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
                    'canUpdateAnnouncements': is_admin
                }
            }
            
            # Don't log sensitive info, but log the request
            logger.info(f"Admin status requested by user: {current_user.get('username')} - Admin: {is_admin}")
            
            return self.send_json_response(response_data)
        
        except Exception as e:
            return self.send_error_response(f"Failed to check admin status: {str(e)}", 500)