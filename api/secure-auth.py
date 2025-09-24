from http.server import BaseHTTPRequestHandler
import json
import os
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta
import bcrypt
from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials, firestore as fb_firestore
import logging
import re

# Configure secure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')

# Initialize Firebase
if not firebase_admin._apps:
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized successfully")
    else:
        logger.warning("Warning: Running in demo mode without Firebase")

db = fb_firestore.client() if firebase_admin._apps else None
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")

# VEILIGE CONFIGURATIE
ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000', 
    'https://kitchen-chat.vercel.app',
    'https://gasfornuis.github.io'
    'https://kitchenchat.live'
    'https://www.kitchenchat.live'
]

# Rate limiting storage (in productie: gebruik Redis)
rate_limit_storage = defaultdict(list)
login_attempts = defaultdict(int)
blocked_ips = {}

# Demo mode storage
demo_users = {}
demo_sessions = {}

def get_client_ip(headers):
    """Get real client IP from headers"""
    # Check various proxy headers
    forwarded = headers.get('x-forwarded-for', '')
    if forwarded:
        # Take first IP (real client)
        return forwarded.split(',')[0].strip()
    
    real_ip = headers.get('x-real-ip', '')
    if real_ip:
        return real_ip
        
    return headers.get('remote-addr', 'unknown')

def check_rate_limit(client_ip, endpoint, max_requests=10, time_window=60):
    """Rate limiting: max_requests per time_window seconds"""
    now = time.time()
    key = f"{client_ip}:{endpoint}"
    
    # Clean old entries
    rate_limit_storage[key] = [req_time for req_time in rate_limit_storage[key] if now - req_time < time_window]
    
    # Check if limit exceeded
    if len(rate_limit_storage[key]) >= max_requests:
        security_logger.warning(f"Rate limit exceeded for {client_ip} on {endpoint}")
        return False
    
    # Add current request
    rate_limit_storage[key].append(now)
    return True

def check_brute_force_protection(client_ip, username=None):
    """Check if IP is blocked due to brute force attempts"""
    now = time.time()
    
    # Check if IP is temporarily blocked
    if client_ip in blocked_ips:
        if now < blocked_ips[client_ip]:
            remaining = int(blocked_ips[client_ip] - now)
            security_logger.warning(f"Blocked IP {client_ip} attempted access. {remaining}s remaining")
            return False, f"Too many failed attempts. Try again in {remaining} seconds"
        else:
            # Unblock IP
            del blocked_ips[client_ip]
            login_attempts[client_ip] = 0
    
    return True, None

def record_failed_login(client_ip, username=None):
    """Record failed login attempt and implement exponential backoff"""
    login_attempts[client_ip] += 1
    attempts = login_attempts[client_ip]
    
    security_logger.warning(f"Failed login attempt #{attempts} from {client_ip}" + 
                           (f" for username: {username}" if username else ""))
    
    # Exponential backoff: 5 attempts = 5min, 10 attempts = 30min, 15+ = 2hr
    if attempts >= 15:
        blocked_ips[client_ip] = time.time() + (2 * 60 * 60)  # 2 hours
        security_logger.error(f"IP {client_ip} blocked for 2 hours due to {attempts} failed attempts")
    elif attempts >= 10:
        blocked_ips[client_ip] = time.time() + (30 * 60)  # 30 minutes
    elif attempts >= 5:
        blocked_ips[client_ip] = time.time() + (5 * 60)  # 5 minutes

def reset_login_attempts(client_ip):
    """Reset failed login attempts after successful login"""
    if client_ip in login_attempts:
        del login_attempts[client_ip]
    if client_ip in blocked_ips:
        del blocked_ips[client_ip]

def hash_password_secure(password):
    """VEILIGE password hashing met bcrypt"""
    # Generate salt and hash password
    salt = bcrypt.gensalt(rounds=12)  # Cost factor 12 (goed voor 2025)
    password_bytes = password.encode('utf-8')
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')

def verify_password_secure(password, stored_hash):
    """VEILIGE password verificatie met bcrypt"""
    try:
        password_bytes = password.encode('utf-8')
        stored_bytes = stored_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, stored_bytes)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

def validate_username(username):
    """Validate username format and security"""
    if not username or not isinstance(username, str):
        return False, "Username is required"
    
    username = username.strip()
    
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    
    if len(username) > 32:
        return False, "Username must be less than 32 characters"
    
    # Allow only alphanumeric + underscore + hyphen
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, underscore and hyphen"
    
    # Prevent admin impersonation
    if username.lower() in ['admin', 'administrator', 'root', 'system', 'mod', 'moderator']:
        return False, "Username not allowed"
    
    return True, None

def validate_password(password):
    """Validate password strength"""
    if not password or not isinstance(password, str):
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    
    if len(password) > 128:
        return False, "Password too long (max 128 characters)"
    
    # Check for at least one letter and one number
    has_letter = re.search(r'[a-zA-Z]', password)
    has_number = re.search(r'[0-9]', password)
    
    if not has_letter or not has_number:
        return False, "Password must contain at least one letter and one number"
    
    return True, None

def get_safe_origin(request_headers):
    """Get safe CORS origin instead of wildcard"""
    origin = request_headers.get('Origin', '')
    
    # Check if origin is in allowed list
    if origin in ALLOWED_ORIGINS:
        return origin
    
    # Default to first allowed origin (for non-browser requests)
    return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else '*'

def send_secure_response(handler, data, status=200, set_cookie=None):
    """Send response with secure headers"""
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    
    # VEILIGE CORS - geen wildcard meer!
    safe_origin = get_safe_origin(handler.headers)
    handler.send_header('Access-Control-Allow-Origin', safe_origin)
    handler.send_header('Access-Control-Allow-Credentials', 'true')
    
    # Security headers
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('X-Frame-Options', 'DENY')
    handler.send_header('X-XSS-Protection', '1; mode=block')
    handler.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
    
    if set_cookie:
        handler.send_header('Set-Cookie', set_cookie)
    
    handler.end_headers()
    handler.wfile.write(json.dumps(data).encode())

def send_secure_error(handler, message, status=400, log_error=True):
    """Send error without exposing internal details"""
    if log_error:
        security_logger.error(f"API Error {status}: {message}")
    
    # Generic error messages voor security
    public_message = message
    if status == 500:
        public_message = "Internal server error. Please try again."
    elif "database" in message.lower() or "firestore" in message.lower():
        public_message = "Service temporarily unavailable. Please try again."
    
    send_secure_response(handler, {'error': public_message}, status)

def generate_session_token():
    """Generate cryptographically secure session token"""
    return secrets.token_urlsafe(48)  # 48 bytes = 384 bits

def hash_session_token(token):
    """Hash session token for database storage"""
    return bcrypt.hashpw(token.encode('utf-8'), bcrypt.gensalt(rounds=8)).decode('utf-8')

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle preflight requests with secure CORS"""
        safe_origin = get_safe_origin(self.headers)
        
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', safe_origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
    
    def do_POST(self):
        """Handle authentication requests"""
        client_ip = get_client_ip(self.headers)
        
        try:
            # Rate limiting voor auth endpoint
            if not check_rate_limit(client_ip, 'auth', max_requests=15, time_window=60):
                return send_secure_error(self, "Too many requests. Please try again later.", 429)
            
            # Check brute force protection
            is_allowed, block_message = check_brute_force_protection(client_ip)
            if not is_allowed:
                return send_secure_error(self, block_message, 423)  # 423 Locked
            
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body) if body else {}
            
            action = data.get("action", "")
            
            if action == "register":
                return self.handle_register(data, client_ip)
            elif action == "login":
                return self.handle_login(data, client_ip)
            elif action == "logout":
                return self.handle_logout(data)
            elif action == "verify":
                return self.handle_verify_session()
            else:
                return send_secure_error(self, "Invalid action", 400)
                
        except json.JSONDecodeError:
            return send_secure_error(self, "Invalid JSON format", 400)
        except Exception as e:
            logger.error(f"Auth API unexpected error: {str(e)}")
            return send_secure_error(self, "An error occurred", 500)
    
    def handle_register(self, data, client_ip):
        """Handle secure user registration"""
        username = data.get("username", "").strip()
        password = data.get("password", "")
        email = data.get("email", "").strip()
        
        # Strikte input validatie
        username_valid, username_error = validate_username(username)
        if not username_valid:
            return send_secure_error(self, username_error, 400)
        
        password_valid, password_error = validate_password(password)
        if not password_valid:
            return send_secure_error(self, password_error, 400)
        
        # Email validation (optioneel)
        if email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            return send_secure_error(self, "Invalid email format", 400)
        
        username_lower = username.lower()
        
        try:
            if not db:
                # Demo mode
                if username_lower in demo_users:
                    return send_secure_error(self, "Username already exists", 409)
                
                # VEILIGE bcrypt hashing
                password_hash = hash_password_secure(password)
                demo_users[username_lower] = {
                    "username": username,
                    "usernameLower": username_lower,
                    "displayName": username,
                    "email": email,
                    "passwordHash": password_hash,
                    "createdAt": datetime.now().isoformat(),
                    "lastLogin": None
                }
                
                security_logger.info(f"New user registered: {username} from IP: {client_ip}")
                return send_secure_response(self, {
                    "success": True,
                    "message": "User registered successfully"
                }, 201)
            
            # Check if username exists
            user_doc = db.collection("Users").document(username_lower).get()
            if user_doc.exists:
                return send_secure_error(self, "Username already exists", 409)
            
            # VEILIGE bcrypt hashing
            password_hash = hash_password_secure(password)
            
            user_data = {
                "username": username_lower,
                "displayName": username,
                "email": email,
                "passwordHash": password_hash,
                "createdAt": fb_firestore.SERVER_TIMESTAMP,
                "lastLogin": None,
                "registeredFromIP": client_ip,
                "secret": FIREBASE_SECRET
            }
            
            db.collection("Users").document(username_lower).set(user_data)
            
            security_logger.info(f"New user registered: {username} from IP: {client_ip}")
            return send_secure_response(self, {
                "success": True,
                "message": "User registered successfully"
            }, 201)
            
        except Exception as e:
            logger.error(f"Registration error for {username}: {str(e)}")
            return send_secure_error(self, "Registration failed", 500)
    
    def handle_login(self, data, client_ip):
        """Handle secure user login"""
        username = data.get("username", "").strip().lower()
        password = data.get("password", "")
        
        if not username or not password:
            record_failed_login(client_ip, username)
            return send_secure_error(self, "Username and password are required", 400)
        
        user_agent = self.headers.get('User-Agent', '')[:200]  # Limit length
        
        try:
            if not db:
                # Demo mode
                user = demo_users.get(username)
                if not user or not verify_password_secure(password, user["passwordHash"]):
                    record_failed_login(client_ip, username)
                    return send_secure_error(self, "Invalid credentials", 401)
                
                # Create session
                token = generate_session_token()
                token_hash = hash_session_token(token)
                
                demo_sessions[token_hash] = {
                    "username": username,
                    "displayName": user["displayName"],
                    "expires": time.time() + (8 * 60 * 60),  # 8 uur (korter!)
                    "userAgent": user_agent,
                    "clientIP": client_ip,
                    "createdAt": datetime.now().isoformat()
                }
                
                demo_users[username]["lastLogin"] = datetime.now().isoformat()
                reset_login_attempts(client_ip)
                
                # Veilige HTTP-only cookie
                cookie_value = f"kc_session={token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=28800"
                
                security_logger.info(f"Successful login: {username} from IP: {client_ip}")
                return send_secure_response(self, {
                    "success": True,
                    "message": "Login successful",
                    "user": {
                        "username": user["usernameLower"],
                        "displayName": user["displayName"]
                    }
                }, 200, cookie_value)
            
            # Firestore mode
            user_doc = db.collection("Users").document(username).get()
            
            if not user_doc.exists:
                record_failed_login(client_ip, username)
                return send_secure_error(self, "Invalid credentials", 401)
            
            user_data = user_doc.to_dict()
            
            # VEILIGE password verificatie met bcrypt
            if not verify_password_secure(password, user_data["passwordHash"]):
                record_failed_login(client_ip, username)
                return send_secure_error(self, "Invalid credentials", 401)
            
            # Create secure session
            token = generate_session_token()
            token_hash = hash_session_token(token)
            
            expires_at = datetime.now() + timedelta(hours=8)  # 8 uur sessie
            
            session_data = {
                "tokenHash": token_hash,
                "username": username,
                "displayName": user_data["displayName"],
                "createdAt": fb_firestore.SERVER_TIMESTAMP,
                "lastActivity": fb_firestore.SERVER_TIMESTAMP,
                "expiresAt": expires_at,
                "userAgent": user_agent,
                "clientIP": client_ip,
                "secret": FIREBASE_SECRET
            }
            
            db.collection("Sessions").document(token_hash).set(session_data)
            
            # Update user's last login
            user_doc.reference.update({
                "lastLogin": fb_firestore.SERVER_TIMESTAMP,
                "lastLoginIP": client_ip
            })
            
            reset_login_attempts(client_ip)
            
            # Veilige HTTP-only cookie
            cookie_value = f"kc_session={token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=28800"
            
            security_logger.info(f"Successful login: {username} from IP: {client_ip}")
            return send_secure_response(self, {
                "success": True,
                "message": "Login successful",
                "user": {
                    "username": user_data["username"],
                    "displayName": user_data["displayName"]
                }
            }, 200, cookie_value)
            
        except Exception as e:
            logger.error(f"Login error for {username}: {str(e)}")
            record_failed_login(client_ip, username)
            return send_secure_error(self, "Login failed", 500)
    
    def handle_logout(self, data):
        """Handle secure logout"""
        try:
            # Get token from request
            token = self.get_session_token_from_request()
            
            if token:
                token_hash = hash_session_token(token)
                
                if not db:
                    demo_sessions.pop(token_hash, None)
                else:
                    try:
                        db.collection("Sessions").document(token_hash).delete()
                    except Exception as e:
                        logger.error(f"Session deletion error: {e}")
            
            # Clear cookie securely
            cookie_value = "kc_session=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0"
            
            return send_secure_response(self, {
                "success": True,
                "message": "Logged out successfully"
            }, 200, cookie_value)
            
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return send_secure_error(self, "Logout failed", 500)
    
    def handle_verify_session(self):
        """Verify session token"""
        try:
            user = self.require_authentication()
            
            if not user:
                return send_secure_error(self, "Invalid or expired session", 401)
            
            return send_secure_response(self, {
                "success": True,
                "valid": True,
                "user": user
            })
            
        except Exception as e:
            logger.error(f"Session verification error: {str(e)}")
            return send_secure_error(self, "Session verification failed", 500)
    
    def get_session_token_from_request(self):
        """Extract session token from request headers or cookies"""
        # Try Authorization header first
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]
        
        # Try cookie
        cookie_header = self.headers.get('Cookie', '')
        if cookie_header:
            cookies = {}
            for cookie in cookie_header.split(';'):
                if '=' in cookie:
                    key, value = cookie.strip().split('=', 1)
                    cookies[key] = value
            
            return cookies.get('kc_session')
        
        return None
    
    def require_authentication(self):
        """Require valid authentication with secure token verification"""
        token = self.get_session_token_from_request()
        if not token:
            return None
        
        token_hash = hash_session_token(token)
        
        if not db:
            # Demo mode
            session = demo_sessions.get(token_hash)
            if not session:
                return None
            
            if time.time() > session['expires']:
                del demo_sessions[token_hash]
                return None
            
            return {
                "username": session["username"],
                "displayName": session["displayName"]
            }
        
        # Firestore mode
        try:
            doc = db.collection("Sessions").document(token_hash).get()
            
            if not doc.exists:
                return None
            
            session_data = doc.to_dict()
            expires_at = session_data.get('expiresAt')
            
            if expires_at and expires_at.timestamp() < time.time():
                doc.reference.delete()
                return None
            
            # Update last activity
            doc.reference.update({"lastActivity": fb_firestore.SERVER_TIMESTAMP})
            
            return {
                "username": session_data.get('username'),
                "displayName": session_data.get('displayName')
            }
            
        except Exception as e:
            logger.error(f"Session verification error: {e}")
            return None
