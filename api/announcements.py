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
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")

# Demo mode storage
demo_announcements = []

# VEILIGE CORS CONFIGURATIE
ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'https://kitchen-chat.vercel.app',
    'https://gasfornuis.github.io'
    'https://kitchenchat.live'
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
    
    username = user.get('username', '').lower()
    display_name = user.get('displayName', '').lower()
    
    for admin_user in ADMIN_USERS:
        if username == admin_user.lower() or display_name == admin_user.lower():
            logger.info(f"Admin access granted for user: {username} (displayName: {display_name})")
            return True
    
    security_logger.warning(f"Admin access denied for user: {username} (displayName: {display_name})")
    return False

def validate_announcement_input(data):
    """Validate announcement input data"""
    title = data.get('title', '').strip() if data.get('title') else ''
    content = data.get('content', '').strip() if data.get('content') else ''
    priority = data.get('priority', 'normal')
    
    if not title or not content:
        return False, "Title and content are required"
    
    if len(title) > 200:
        return False, "Title too long (max 200 characters)"
    
    if len(content) > 2000:
        return False, "Content too long (max 2000 characters)"
    
    if priority not in ['normal', 'high', 'urgent']:
        return False, "Invalid priority level"
    
    # Basic content filtering
    forbidden_words = ['<script', 'javascript:', 'data:text/html']
    title_lower = title.lower()
    content_lower = content.lower()
    
    for word in forbidden_words:
        if word in title_lower or word in content_lower:
            return False, "Content contains forbidden elements"
    
    return True, None

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle preflight requests with secure CORS"""
        safe_origin = get_safe_origin(self.headers)
        
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', safe_origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
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
        """Send secure error response without exposing internals"""
        # Log detailed error server-side
        logger.error(f"API Error {status}: {error}")
        
        # Send generic error to client for security
        public_error = error
        if status == 500:
            public_error = "Internal server error. Please try again."
        elif "database" in str(error).lower() or "firestore" in str(error).lower():
            public_error = "Service temporarily unavailable. Please try again."
        
        self.send_json_response({'error': public_error}, status)
    
    def do_GET(self):
        """Get announcements with rate limiting"""
        client_ip = get_client_ip(self.headers)
        
        # Rate limiting
        if not check_rate_limit(client_ip, 'announcements_get', max_requests=60, time_window=60):
            return self.send_error_response("Too many requests. Please slow down.", 429)
        
        try:
            # Get user from session
            current_user = require_authentication(self)
            
            if not current_user:
                return self.send_error_response("Authentication required", 401)
            
            if not db:
                # Demo mode
                logger.info(f"Retrieved {len(demo_announcements)} announcements (demo mode)")
                return self.send_json_response(demo_announcements)
            
            # Get announcements from database
            announcements_ref = db.collection('announcements').order_by('createdAt', direction=fb_firestore.Query.DESCENDING).limit(50)
            announcements = announcements_ref.get()
            
            result = []
            for announcement in announcements:
                data = announcement.to_dict()
                data['id'] = announcement.id
                
                # Convert timestamp for JSON serialization
                if 'createdAt' in data and data['createdAt']:
                    data['createdAt'] = data['createdAt'].isoformat()
                
                # Remove sensitive fields
                data.pop('secret', None)
                
                result.append(data)
            
            logger.info(f"Retrieved {len(result)} announcements for user: {current_user.get('username')}")
            return self.send_json_response(result)
        
        except Exception as e:
            return self.send_error_response(f"Failed to retrieve announcements: {str(e)}")
    
    def do_POST(self):
        """Create new announcement (admin only) with rate limiting"""
        client_ip = get_client_ip(self.headers)
        
        # Stricter rate limiting voor POST requests
        if not check_rate_limit(client_ip, 'announcements_post', max_requests=5, time_window=60):
            return self.send_error_response("Too many requests. Please slow down.", 429)
        
        try:
            # Get user from session
            current_user = require_authentication(self)
            
            if not current_user:
                return self.send_error_response("Authentication required", 401)
            
            # VEILIGE SERVER-SIDE ADMIN CHECK
            if not check_admin_permissions(current_user):
                username = current_user.get('username', 'unknown')
                security_logger.warning(f"Non-admin user {username} from IP {client_ip} attempted to create announcement")
                return self.send_error_response("Access denied. Administrator privileges required.", 403)
            
            # Parse and validate request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 10000:  # 10KB limit
                return self.send_error_response("Request too large", 413)
            
            if content_length > 0:
                post_data = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(post_data)
            else:
                return self.send_error_response("No data provided", 400)
            
            # STRIKTE input validatie
            is_valid, validation_error = validate_announcement_input(data)
            if not is_valid:
                return self.send_error_response(validation_error, 400)
            
            title = data['title'].strip()
            content = data['content'].strip()
            priority = data.get('priority', 'normal')
            
            # Create announcement document
            announcement_data = {
                'title': title,
                'content': content,
                'author': current_user.get('displayName', current_user.get('username', 'Unknown')),
                'authorUsername': current_user.get('username', ''),
                'createdAt': datetime.now(timezone.utc),
                'type': 'announcement',
                'priority': priority,
                'active': True,
                'createdFromIP': client_ip
            }
            
            if not db:
                # Demo mode
                announcement_data['id'] = str(len(demo_announcements) + 1)
                announcement_data['createdAt'] = announcement_data['createdAt'].isoformat()
                demo_announcements.append(announcement_data)
                
                security_logger.info(f"Announcement created in demo mode by admin: {current_user.get('username')}")
                
                return self.send_json_response({
                    'success': True,
                    'message': 'Announcement created successfully (demo mode)',
                    'announcement': announcement_data
                })
            
            # Add to database
            doc_ref = db.collection('announcements').add(announcement_data)
            announcement_id = doc_ref[1].id
            
            security_logger.info(f"Announcement created with ID: {announcement_id} by admin: {current_user.get('username')} from IP: {client_ip}")
            
            # Return created announcement (without sensitive data)
            announcement_data['id'] = announcement_id
            announcement_data['createdAt'] = announcement_data['createdAt'].isoformat()
            announcement_data.pop('createdFromIP', None)  # Don't send IP to client
            
            return self.send_json_response({
                'success': True,
                'message': 'Announcement created successfully',
                'announcement': announcement_data
            })
        
        except json.JSONDecodeError:
            return self.send_error_response("Invalid JSON format", 400)
        except Exception as e:
            return self.send_error_response(f"Failed to create announcement: {str(e)}")
    
    def do_DELETE(self):
        """Delete announcement (admin only) with rate limiting"""
        client_ip = get_client_ip(self.headers)
        
        # Rate limiting voor DELETE
        if not check_rate_limit(client_ip, 'announcements_delete', max_requests=10, time_window=60):
            return self.send_error_response("Too many requests. Please slow down.", 429)
        
        try:
            # Get user from session
            current_user = require_authentication(self)
            
            if not current_user:
                return self.send_error_response("Authentication required", 401)
            
            # VEILIGE SERVER-SIDE ADMIN CHECK
            if not check_admin_permissions(current_user):
                username = current_user.get('username', 'unknown')
                security_logger.warning(f"Non-admin user {username} from IP {client_ip} attempted to delete announcement")
                return self.send_error_response("Access denied. Administrator privileges required.", 403)
            
            # Get announcement ID from request
            announcement_id = None
            
            # Try URL parameters first
            if '?' in self.path:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(self.path)
                query_params = parse_qs(parsed.query)
                if 'id' in query_params:
                    announcement_id = query_params['id'][0]
            
            # Try request body if not in URL
            if not announcement_id:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0 and content_length < 1000:  # Reasonable limit
                    post_data = self.rfile.read(content_length).decode('utf-8')
                    data = json.loads(post_data)
                    announcement_id = data.get('id')
            
            if not announcement_id:
                return self.send_error_response("Announcement ID is required", 400)
            
            # Validate ID format
            if not isinstance(announcement_id, str) or len(announcement_id) > 100:
                return self.send_error_response("Invalid announcement ID format", 400)
            
            if not db:
                # Demo mode
                return self.send_json_response({
                    'success': True,
                    'message': 'Delete functionality not available in demo mode'
                })
            
            # Check if announcement exists
            doc_ref = db.collection('announcements').document(announcement_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return self.send_error_response("Announcement not found", 404)
            
            # Log before deletion
            announcement_data = doc.to_dict()
            security_logger.info(f"Announcement '{announcement_data.get('title', 'Unknown')}' (ID: {announcement_id}) deleted by admin: {current_user.get('username')} from IP: {client_ip}")
            
            # Delete from database
            doc_ref.delete()
            
            return self.send_json_response({
                'success': True,
                'message': 'Announcement deleted successfully'
            })
        
        except json.JSONDecodeError:
            return self.send_error_response("Invalid JSON format", 400)
        except Exception as e:
            return self.send_error_response(f"Failed to delete announcement: {str(e)}", 500)

# Helper function for input validation (moved outside class)
def validate_announcement_input(data):
    """Validate announcement input data"""
    if not isinstance(data, dict):
        return False, "Invalid data format"
    
    title = data.get('title', '').strip() if data.get('title') else ''
    content = data.get('content', '').strip() if data.get('content') else ''
    priority = data.get('priority', 'normal')
    
    if not title or not content:
        return False, "Title and content are required"
    
    if len(title) > 200:
        return False, "Title too long (max 200 characters)"
    
    if len(content) > 2000:
        return False, "Content too long (max 2000 characters)"
    
    if priority not in ['normal', 'high', 'urgent']:
        return False, "Invalid priority level"
    
    # Basic XSS/injection prevention
    dangerous_patterns = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'data:text/html',
        r'on\w+\s*=',  # onclick, onload, etc.
        r'<iframe',
        r'<object',
        r'<embed'
    ]
    
    import re
    combined_text = (title + ' ' + content).lower()
    
    for pattern in dangerous_patterns:
        if re.search(pattern, combined_text, re.IGNORECASE):
            security_logger.warning(f"Potentially malicious content blocked: {pattern}")
            return False, "Content contains potentially unsafe elements"
    
    return True, None
