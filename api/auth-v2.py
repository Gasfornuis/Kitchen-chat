"""Enhanced Secure Authentication API for Kitchen Chat

KRITIEKE VERBETERINGEN:
- Bcrypt password hashing (in plaats van SHA-256)
- Geavanceerde brute force protection
- Verbeterde rate limiting
- Veilige CORS zonder wildcards
- Input validation en sanitization
- Security event logging
- Session management met rolling expiration
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta
import bcrypt
import hashlib
import re
import logging
from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials, firestore as fb_firestore

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/kitchen-chat-auth.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')

# Initialize Firebase with error handling
if not firebase_admin._apps:
    try:
        sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if sa_json:
            cred = credentials.Certificate(json.loads(sa_json))
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized successfully")
        else:
            logger.warning("Running in demo mode - no Firebase credentials")
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")

db = fb_firestore.client() if firebase_admin._apps else None
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET") or secrets.token_hex(32)
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

# PRODUCTIE-VEILIGE CORS CONFIGURATIE
if ENVIRONMENT == "production":
    ALLOWED_ORIGINS = [
        'https://kitchenchat.live',
        'https://www.kitchenchat.live',
        'https://kitchen-chat.vercel.app'
    ]
else:
    # Development origins
    ALLOWED_ORIGINS = [
        'http://localhost:3000',
        'http://127.0.0.1:3000', 
        'https://kitchen-chat.vercel.app',
        'https://kitchenchat.live',
        'https://www.kitchenchat.live'
    ]

# Enhanced security storage (in productie: gebruik Redis)
rate_limit_storage = defaultdict(list)
login_attempts = defaultdict(lambda: {'count': 0, 'first_attempt': None, 'last_attempt': None})
blocked_ips = {}
session_storage = {}  # Voor demo mode
demo_users = {}

# Security constants
MAX_LOGIN_ATTEMPTS = 5
BLOCK_DURATION_BASE = 300  # 5 minuten base
MAX_BLOCK_DURATION = 7200  # 2 uur maximum
SESSION_DURATION = 28800  # 8 uur
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
BCRYPT_ROUNDS = 12

def get_client_ip(headers):
    """Extract real client IP from various proxy headers"""
    # Check proxy headers in order of preference
    forwarded = headers.get('x-forwarded-for', '')
    if forwarded:
        # Take first IP (original client) and validate format
        ip = forwarded.split(',')[0].strip()
        if validate_ip_format(ip):
            return ip
    
    real_ip = headers.get('x-real-ip', '')
    if real_ip and validate_ip_format(real_ip):
        return real_ip
        
    cf_ip = headers.get('cf-connecting-ip', '')  # Cloudflare
    if cf_ip and validate_ip_format(cf_ip):
        return cf_ip
        
    return headers.get('remote-addr', 'unknown')

def validate_ip_format(ip):
    """Basic IP format validation"""
    if not ip or ip == 'unknown':
        return False
    # Basic IPv4/IPv6 validation
    parts = ip.split('.')
    if len(parts) == 4:
        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False
    # IPv6 basic validation
    return ':' in ip and len(ip) <= 39

def check_rate_limit(client_ip, endpoint, max_requests=20, time_window=60):
    """Enhanced rate limiting with configurable limits"""
    now = time.time()
    key = f"{client_ip}:{endpoint}"
    
    # Clean expired entries
    rate_limit_storage[key] = [
        req_time for req_time in rate_limit_storage[key] 
        if now - req_time < time_window
    ]
    
    current_count = len(rate_limit_storage[key])
    
    # Check if limit exceeded
    if current_count >= max_requests:
        security_logger.warning(
            f"Rate limit exceeded: {client_ip} on {endpoint} "
            f"({current_count}/{max_requests} in {time_window}s)"
        )
        return False
    
    # Add current request
    rate_limit_storage[key].append(now)
    return True

def check_brute_force_protection(client_ip):
    """Advanced brute force protection with exponential backoff"""
    now = time.time()
    
    # Check if IP is currently blocked
    if client_ip in blocked_ips:
        if now < blocked_ips[client_ip]['until']:
            remaining = int(blocked_ips[client_ip]['until'] - now)
            attempts = blocked_ips[client_ip]['attempts']
            
            security_logger.warning(
                f"Blocked IP {client_ip} attempted access. "
                f"{remaining}s remaining, {attempts} failed attempts"
            )
            
            return False, f"Too many failed attempts ({attempts}). Try again in {remaining} seconds"
        else:
            # Unblock expired IP
            del blocked_ips[client_ip]
    
    return True, None

def record_failed_login(client_ip, username=None):
    """Record failed login with exponential backoff"""
    now = time.time()
    
    if client_ip not in login_attempts:
        login_attempts[client_ip] = {
            'count': 0,
            'first_attempt': now,
            'last_attempt': now
        }
    
    login_attempts[client_ip]['count'] += 1
    login_attempts[client_ip]['last_attempt'] = now
    
    attempts = login_attempts[client_ip]['count']
    
    security_logger.warning(
        f"Failed login attempt #{attempts} from {client_ip}" + 
        (f" for username: {username}" if username else "")
    )
    
    # Exponential backoff calculation
    if attempts >= MAX_LOGIN_ATTEMPTS:
        # Calculate block duration: base * 2^(attempts-5), max 2 hours
        block_duration = min(
            BLOCK_DURATION_BASE * (2 ** (attempts - MAX_LOGIN_ATTEMPTS)),
            MAX_BLOCK_DURATION
        )
        
        blocked_ips[client_ip] = {
            'until': now + block_duration,
            'attempts': attempts,
            'first_attempt': login_attempts[client_ip]['first_attempt']
        }
        
        security_logger.error(
            f"IP {client_ip} blocked for {block_duration}s due to {attempts} failed attempts"
        )

def reset_login_attempts(client_ip):
    """Reset failed login attempts after successful authentication"""
    if client_ip in login_attempts:
        attempts = login_attempts[client_ip]['count']
        if attempts > 0:
            security_logger.info(f"Reset {attempts} failed attempts for {client_ip}")
        del login_attempts[client_ip]
    
    if client_ip in blocked_ips:
        del blocked_ips[client_ip]

def hash_password_secure(password):
    """Secure password hashing with bcrypt - UPGRADED FROM SHA-256"""
    try:
        # Generate salt and hash password with bcrypt
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        password_bytes = password.encode('utf-8')
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Password hashing error: {e}")
        raise ValueError("Password hashing failed")

def verify_password_secure(password, stored_hash):
    """Secure password verification with bcrypt"""
    try:
        password_bytes = password.encode('utf-8')
        stored_bytes = stored_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, stored_bytes)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

def migrate_sha256_password(password, old_hash):
    """Migrate old SHA-256 passwords to bcrypt on login"""
    try:
        if ':' not in old_hash:
            return False
        
        salt, pwd_hash = old_hash.split(':', 1)
        computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        
        if computed_hash == pwd_hash:
            # Password is correct, migrate to bcrypt
            return hash_password_secure(password)
        
        return False
    except Exception as e:
        logger.error(f"Password migration error: {e}")
        return False

def validate_username(username):
    """Enhanced username validation with security checks"""
    if not username or not isinstance(username, str):
        return False, "Username is required"
    
    username = username.strip()
    
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    
    if len(username) > 32:
        return False, "Username must be less than 32 characters"
    
    # Allow alphanumeric, underscore, hyphen, dot
    if not re.match(r'^[a-zA-Z0-9._-]+$', username):
        return False, "Username can only contain letters, numbers, underscore, hyphen, and dot"
    
    # Prevent reserved/admin usernames
    forbidden_usernames = {
        'admin', 'administrator', 'root', 'system', 'mod', 'moderator',
        'support', 'help', 'api', 'www', 'mail', 'ftp', 'ssh', 'null',
        'undefined', 'anonymous', 'guest', 'test', 'demo'
    }
    
    if username.lower() in forbidden_usernames:
        return False, "Username not allowed"
    
    # Prevent usernames that look like IDs or hashes
    if re.match(r'^[0-9]+$', username) or len(username) > 20 and re.match(r'^[a-f0-9]+$', username.lower()):
        return False, "Username format not allowed"
    
    return True, None

def validate_password(password):
    """Enhanced password strength validation"""
    if not password or not isinstance(password, str):
        return False, "Password is required"
    
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
    
    if len(password) > PASSWORD_MAX_LENGTH:
        return False, f"Password too long (max {PASSWORD_MAX_LENGTH} characters)"
    
    # Check for common patterns
    if password.lower() in ['password', '12345678', 'qwerty123', 'letmein', 'welcome123']:
        return False, "Password is too common"
    
    # Strength requirements
    has_lower = re.search(r'[a-z]', password)
    has_upper = re.search(r'[A-Z]', password)
    has_number = re.search(r'[0-9]', password)
    has_special = re.search(r'[!@#$%^&*(),.?":{}|<>]', password)
    
    strength_score = sum([bool(has_lower), bool(has_upper), bool(has_number), bool(has_special)])
    
    if strength_score < 2:
        return False, "Password must contain at least 2 of: lowercase, uppercase, numbers, special characters"
    
    # Check for repeated characters
    if re.search(r'(.)\1{3,}', password):
        return False, "Password cannot contain 4 or more repeated characters"
    
    return True, None

def validate_email(email):
    """Email validation with security considerations"""
    if not email:
        return True, None  # Email is optional
    
    if len(email) > 254:
        return False, "Email too long"
    
    # Enhanced email regex
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "Invalid email format"
    
    # Check for suspicious patterns
    suspicious_domains = ['tempmail', '10minutemail', 'guerrillamail', 'mailinator']
    email_lower = email.lower()
    if any(domain in email_lower for domain in suspicious_domains):
        return False, "Temporary email addresses are not allowed"
    
    return True, None

def get_safe_origin(request_headers):
    """Get safe CORS origin - NO WILDCARDS!"""
    origin = request_headers.get('Origin', '')
    
    # Check if origin is explicitly allowed
    if origin in ALLOWED_ORIGINS:
        return origin
    
    # For non-browser requests or when no origin
    if not origin:
        return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else 'null'
    
    # Log suspicious origin attempts
    security_logger.warning(f"Blocked CORS attempt from origin: {origin}")
    return 'null'  # Deny unknown origins

def send_secure_response(handler, data, status=200, set_cookie=None):
    """Send response with comprehensive security headers"""
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    
    # VEILIGE CORS - geen wildcard!
    safe_origin = get_safe_origin(handler.headers)
    handler.send_header('Access-Control-Allow-Origin', safe_origin)
    handler.send_header('Access-Control-Allow-Credentials', 'true')
    
    # Comprehensive security headers
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('X-Frame-Options', 'DENY')
    handler.send_header('X-XSS-Protection', '1; mode=block')
    handler.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
    handler.send_header('X-Permitted-Cross-Domain-Policies', 'none')
    
    # Enhanced Content Security Policy
    csp_directives = [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: https:",
        "connect-src 'self' https:",
        "font-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'"
    ]
    handler.send_header('Content-Security-Policy', '; '.join(csp_directives))
    
    # HTTPS enforcement in production
    if ENVIRONMENT == 'production':
        handler.send_header('Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload')
    
    if set_cookie:
        handler.send_header('Set-Cookie', set_cookie)
    
    handler.end_headers()
    
    # Ensure UTF-8 encoding
    json_str = json.dumps(data, ensure_ascii=False)
    handler.wfile.write(json_str.encode('utf-8'))

def send_secure_error(handler, message, status=400, log_level='warning'):
    """Send error response without exposing internal details"""
    client_ip = get_client_ip(handler.headers)
    
    # Log detailed error server-side
    if log_level == 'error':
        security_logger.error(f"API Error {status} from {client_ip}: {message}")
    else:
        security_logger.warning(f"API Warning {status} from {client_ip}: {message}")
    
    # Sanitize error message for client
    public_message = message
    
    # Hide internal system details
    if status >= 500:
        public_message = "Internal server error. Please try again later."
    elif any(keyword in str(message).lower() for keyword in 
             ['database', 'firestore', 'firebase', 'collection', 'document']):
        public_message = "Service temporarily unavailable. Please try again."
    elif 'traceback' in str(message).lower() or 'exception' in str(message).lower():
        public_message = "An unexpected error occurred. Please try again."
    
    send_secure_response(handler, {'error': public_message}, status)

def generate_session_token():
    """Generate cryptographically secure session token"""
    # 48 bytes = 384 bits of entropy
    return secrets.token_urlsafe(48)

def hash_session_token(token):
    """Hash session token for secure database storage"""
    # Use SHA-256 for session tokens (not passwords!)
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def create_secure_session(username, display_name, client_ip, user_agent):
    """Create secure session with enhanced metadata"""
    token = generate_session_token()
    token_hash = hash_session_token(token)
    expires_at = datetime.now() + timedelta(seconds=SESSION_DURATION)
    
    session_data = {
        'username': username,
        'displayName': display_name,
        'tokenHash': token_hash,
        'clientIP': client_ip,
        'userAgent': user_agent[:200],  # Limit length
        'createdAt': datetime.now(),
        'lastActivity': datetime.now(),
        'expiresAt': expires_at,
        'secret': FIREBASE_SECRET
    }
    
    if db:
        # Store in Firestore
        db.collection("Sessions").document(token_hash).set({
            **session_data,
            'createdAt': fb_firestore.SERVER_TIMESTAMP,
            'lastActivity': fb_firestore.SERVER_TIMESTAMP,
            'expiresAt': expires_at
        })
    else:
        # Demo mode
        session_storage[token_hash] = session_data
    
    return token

def verify_session_token(token):
    """Verify session token and return user info"""
    if not token:
        return None
    
    token_hash = hash_session_token(token)
    
    if not db:
        # Demo mode
        session = session_storage.get(token_hash)
        if not session:
            return None
        
        if datetime.now() > session['expiresAt']:
            del session_storage[token_hash]
            return None
        
        # Update last activity
        session['lastActivity'] = datetime.now()
        
        return {
            'username': session['username'],
            'displayName': session['displayName']
        }
    
    # Firestore mode
    try:
        doc = db.collection("Sessions").document(token_hash).get()
        
        if not doc.exists:
            return None
        
        session_data = doc.to_dict()
        expires_at = session_data.get('expiresAt')
        
        if expires_at and expires_at.timestamp() < time.time():
            # Session expired, clean up
            doc.reference.delete()
            return None
        
        # Update last activity (rolling session)
        doc.reference.update({
            "lastActivity": fb_firestore.SERVER_TIMESTAMP,
            "expiresAt": datetime.now() + timedelta(seconds=SESSION_DURATION)
        })
        
        return {
            'username': session_data.get('username'),
            'displayName': session_data.get('displayName')
        }
    
    except Exception as e:
        logger.error(f"Session verification error: {e}")
        return None

class handler(BaseHTTPRequestHandler):
    """Enhanced secure authentication handler"""
    
    def log_message(self, format, *args):
        """Override default logging to use our logger"""
        logger.info(f"{self.client_address[0]} - {format % args}")
    
    def do_OPTIONS(self):
        """Handle preflight requests with secure CORS"""
        safe_origin = get_safe_origin(self.headers)
        
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', safe_origin)
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Access-Control-Max-Age', '86400')  # 24 hours
        
        # Security headers for OPTIONS
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        
        self.end_headers()
    
    def do_POST(self):
        """Handle authentication requests with enhanced security"""
        client_ip = get_client_ip(self.headers)
        
        try:
            # Enhanced rate limiting for auth endpoint
            if not check_rate_limit(client_ip, 'auth', max_requests=15, time_window=60):
                return send_secure_error(self, "Too many requests. Please slow down.", 429)
            
            # Brute force protection
            is_allowed, block_message = check_brute_force_protection(client_ip)
            if not is_allowed:
                return send_secure_error(self, block_message, 423)  # 423 Locked
            
            # Validate content length
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 10000:  # 10KB max
                return send_secure_error(self, "Request too large", 413)
            
            if content_length == 0:
                return send_secure_error(self, "No data provided", 400)
            
            # Read and parse JSON
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode('utf-8'))
            except UnicodeDecodeError:
                return send_secure_error(self, "Invalid character encoding", 400)
            
            if not isinstance(data, dict):
                return send_secure_error(self, "Data must be a JSON object", 400)
            
            action = data.get("action", "")
            
            if action == "register":
                return self.handle_register(data, client_ip)
            elif action == "login":
                return self.handle_login(data, client_ip)
            elif action == "logout":
                return self.handle_logout()
            elif action == "verify":
                return self.handle_verify_session()
            else:
                return send_secure_error(self, "Invalid action", 400)
                
        except json.JSONDecodeError as e:
            security_logger.warning(f"Invalid JSON from {client_ip}: {e}")
            return send_secure_error(self, "Invalid JSON format", 400)
        except Exception as e:
            logger.error(f"Auth API unexpected error from {client_ip}: {str(e)}")
            return send_secure_error(self, "An error occurred", 500, 'error')
    
    def handle_register(self, data, client_ip):
        """Handle secure user registration with enhanced validation"""
        username = data.get("username", "")
        password = data.get("password", "")
        email = data.get("email", "")
        
        # Enhanced input validation
        if isinstance(username, str):
            username = username.strip()
        
        if isinstance(email, str):
            email = email.strip()
        
        # Validate all inputs
        username_valid, username_error = validate_username(username)
        if not username_valid:
            return send_secure_error(self, username_error, 400)
        
        password_valid, password_error = validate_password(password)
        if not password_valid:
            return send_secure_error(self, password_error, 400)
        
        email_valid, email_error = validate_email(email)
        if not email_valid:
            return send_secure_error(self, email_error, 400)
        
        username_lower = username.lower()
        
        try:
            # Check if username exists
            if db:
                user_doc = db.collection("Users").document(username_lower).get()
                if user_doc.exists:
                    return send_secure_error(self, "Username already exists", 409)
            else:
                # Demo mode
                if username_lower in demo_users:
                    return send_secure_error(self, "Username already exists", 409)
            
            # Hash password securely with bcrypt
            try:
                password_hash = hash_password_secure(password)
            except ValueError as e:
                logger.error(f"Password hashing failed for {username}: {e}")
                return send_secure_error(self, "Registration failed", 500, 'error')
            
            # Create user data
            user_data = {
                "username": username_lower,
                "displayName": username,  # Original case
                "email": email,
                "passwordHash": password_hash,
                "createdAt": datetime.now() if not db else fb_firestore.SERVER_TIMESTAMP,
                "lastLogin": None,
                "registeredFromIP": client_ip,
                "emailVerified": False,
                "accountStatus": "active"
            }
            
            if db:
                user_data["secret"] = FIREBASE_SECRET
                db.collection("Users").document(username_lower).set(user_data)
            else:
                # Demo mode
                user_data["createdAt"] = datetime.now().isoformat()
                demo_users[username_lower] = user_data
            
            security_logger.info(f"New user registered: {username} from IP: {client_ip}")
            
            return send_secure_response(self, {
                "success": True,
                "message": "User registered successfully"
            }, 201)
            
        except Exception as e:
            logger.error(f"Registration error for {username}: {str(e)}")
            return send_secure_error(self, "Registration failed", 500, 'error')
    
    def handle_login(self, data, client_ip):
        """Handle secure user login with enhanced protection"""
        username = data.get("username", "")
        password = data.get("password", "")
        
        if isinstance(username, str):
            username = username.strip().lower()
        
        if not username or not password:
            record_failed_login(client_ip, username)
            return send_secure_error(self, "Username and password are required", 400)
        
        user_agent = self.headers.get('User-Agent', '')[:200]  # Limit length
        
        try:
            user_data = None
            
            if db:
                # Firestore mode
                user_doc = db.collection("Users").document(username).get()
                if not user_doc.exists:
                    record_failed_login(client_ip, username)
                    return send_secure_error(self, "Invalid credentials", 401)
                
                user_data = user_doc.to_dict()
            else:
                # Demo mode
                user_data = demo_users.get(username)
                if not user_data:
                    record_failed_login(client_ip, username)
                    return send_secure_error(self, "Invalid credentials", 401)
            
            # Check account status
            if user_data.get('accountStatus') == 'blocked':
                security_logger.warning(f"Blocked account login attempt: {username} from {client_ip}")
                return send_secure_error(self, "Account is blocked", 403)
            
            stored_hash = user_data.get("passwordHash", "")
            
            # Try bcrypt verification first
            password_valid = verify_password_secure(password, stored_hash)
            
            # If bcrypt fails and looks like old SHA-256, try migration
            if not password_valid and ':' in stored_hash:
                migrated_hash = migrate_sha256_password(password, stored_hash)
                if migrated_hash:
                    password_valid = True
                    # Update to new hash
                    if db:
                        user_doc.reference.update({"passwordHash": migrated_hash})
                    else:
                        demo_users[username]["passwordHash"] = migrated_hash
                    
                    security_logger.info(f"Password migrated from SHA-256 to bcrypt for user: {username}")
            
            if not password_valid:
                record_failed_login(client_ip, username)
                return send_secure_error(self, "Invalid credentials", 401)
            
            # Create secure session
            try:
                token = create_secure_session(
                    username, 
                    user_data["displayName"], 
                    client_ip, 
                    user_agent
                )
            except Exception as e:
                logger.error(f"Session creation failed for {username}: {e}")
                return send_secure_error(self, "Login failed", 500, 'error')
            
            # Update user's last login
            login_data = {
                "lastLogin": datetime.now() if not db else fb_firestore.SERVER_TIMESTAMP,
                "lastLoginIP": client_ip
            }
            
            if db:
                user_doc.reference.update(login_data)
            else:
                demo_users[username].update({
                    "lastLogin": datetime.now().isoformat(),
                    "lastLoginIP": client_ip
                })
            
            # Reset failed login attempts
            reset_login_attempts(client_ip)
            
            # Create secure HTTP-only cookie
            cookie_attributes = [
                f"kc_session={token}",
                "Path=/",
                "HttpOnly",
                "SameSite=Strict",
                f"Max-Age={SESSION_DURATION}"
            ]
            
            # Add Secure flag in production
            if ENVIRONMENT == 'production':
                cookie_attributes.append("Secure")
            
            cookie_value = '; '.join(cookie_attributes)
            
            security_logger.info(f"Successful login: {username} from IP: {client_ip}")
            
            return send_secure_response(self, {
                "success": True,
                "message": "Login successful",
                "user": {
                    "username": username,
                    "displayName": user_data["displayName"]
                }
            }, 200, cookie_value)
            
        except Exception as e:
            logger.error(f"Login error for {username}: {str(e)}")
            record_failed_login(client_ip, username)
            return send_secure_error(self, "Login failed", 500, 'error')
    
    def handle_logout(self):
        """Handle secure logout with session cleanup"""
        try:
            # Get token from request
            token = self.get_session_token_from_request()
            
            if token:
                token_hash = hash_session_token(token)
                
                if db:
                    try:
                        db.collection("Sessions").document(token_hash).delete()
                    except Exception as e:
                        logger.error(f"Session deletion error: {e}")
                else:
                    # Demo mode
                    session_storage.pop(token_hash, None)
            
            # Clear cookie securely
            cookie_attributes = [
                "kc_session=",
                "Path=/",
                "HttpOnly",
                "SameSite=Strict",
                "Max-Age=0"
            ]
            
            if ENVIRONMENT == 'production':
                cookie_attributes.append("Secure")
            
            cookie_value = '; '.join(cookie_attributes)
            
            return send_secure_response(self, {
                "success": True,
                "message": "Logged out successfully"
            }, 200, cookie_value)
            
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return send_secure_error(self, "Logout failed", 500, 'error')
    
    def handle_verify_session(self):
        """Verify session token with enhanced security"""
        try:
            token = self.get_session_token_from_request()
            user = verify_session_token(token)
            
            if not user:
                return send_secure_error(self, "Invalid or expired session", 401)
            
            return send_secure_response(self, {
                "success": True,
                "valid": True,
                "user": user
            })
            
        except Exception as e:
            logger.error(f"Session verification error: {str(e)}")
            return send_secure_error(self, "Session verification failed", 500, 'error')
    
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

# Health check endpoint
def health_check():
    """Simple health check for monitoring"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0',
        'environment': ENVIRONMENT,
        'features': {
            'bcrypt_hashing': True,
            'rate_limiting': True,
            'brute_force_protection': True,
            'secure_sessions': True,
            'enhanced_validation': True
        }
    }

# Export for testing
__all__ = [
    'handler', 'hash_password_secure', 'verify_password_secure',
    'validate_username', 'validate_password', 'check_rate_limit',
    'check_brute_force_protection', 'health_check'
]