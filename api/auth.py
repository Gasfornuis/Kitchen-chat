from http.server import BaseHTTPRequestHandler
import json
import os
import hashlib
import secrets
import time
from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials, firestore as fb_firestore
from datetime import datetime, timedelta

if not firebase_admin._apps:
    # Load service account from environment variable
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
        firebase_admin.initialize_app(cred)
    else:
        print("Warning: Running in demo mode without Firebase")

db = fb_firestore.client() if firebase_admin._apps else None
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")

# Demo mode storage
demo_users = {}
demo_sessions = {}

def sha256_hash(text):
    """SHA-256 hash utility"""
    return hashlib.sha256(text.encode()).hexdigest()

def hash_password(password):
    """Hash password using SHA-256 with salt"""
    salt = secrets.token_hex(32)  # Generate random salt
    pwd_hash = sha256_hash(password + salt)
    return f"{salt}:{pwd_hash}"

def verify_password(password, stored_hash):
    """Verify password against stored hash"""
    try:
        salt, pwd_hash = stored_hash.split(':')
        return sha256_hash(password + salt) == pwd_hash
    except:
        return False

def generate_session_token():
    """Generate secure session token"""
    return secrets.token_urlsafe(32)

def hash_session_token(token):
    """Hash session token for secure storage"""
    return sha256_hash(token)

def get_client_ip(headers):
    """Get client IP from headers"""
    forwarded = headers.get('x-forwarded-for', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return headers.get('x-real-ip', 'unknown')

def create_session_firestore(username, display_name, user_agent, client_ip):
    """Create session in Firestore"""
    token = generate_session_token()
    token_hash = hash_session_token(token)
    
    expires_at = datetime.now() + timedelta(days=1)  # 24 hours
    
    session_data = {
        "tokenHash": token_hash,
        "username": username.lower(),
        "displayName": display_name,
        "createdAt": fb_firestore.SERVER_TIMESTAMP,
        "lastActivity": fb_firestore.SERVER_TIMESTAMP,
        "expiresAt": expires_at,
        "userAgent": user_agent or '',
        "clientIP": client_ip,
        "secret": FIREBASE_SECRET
    }
    
    # Use tokenHash as document ID for fast lookups
    db.collection("Sessions").document(token_hash).set(session_data)
    
    return token, token_hash

def create_session_demo(username, display_name, user_agent, client_ip):
    """Create session in demo mode"""
    token = generate_session_token()
    token_hash = hash_session_token(token)
    
    demo_sessions[token_hash] = {
        "username": username,
        "displayName": display_name,
        "expires": time.time() + (24 * 60 * 60),  # 24 hours
        "userAgent": user_agent or '',
        "clientIP": client_ip,
        "createdAt": datetime.now().isoformat()
    }
    
    return token, token_hash

def verify_session_token(token):
    """Verify session token and return user info"""
    if not token:
        return None
    
    token_hash = hash_session_token(token)
    
    if not db:
        # Demo mode
        session = demo_sessions.get(token_hash)
        if not session:
            return None
        
        if time.time() > session['expires']:
            # Lazy cleanup - remove expired session
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
            # Lazy cleanup - delete expired session
            doc.reference.delete()
            return None
        
        # Update last activity (optional - can be expensive)
        # doc.reference.update({"lastActivity": fb_firestore.SERVER_TIMESTAMP})
            
        return {
            "username": session_data.get('username'),
            "displayName": session_data.get('displayName')
        }
        
    except Exception as e:
        print(f"Session verification error: {e}")
        return None

def delete_session(token):
    """Delete a session"""
    if not token:
        return
        
    token_hash = hash_session_token(token)
    
    if not db:
        # Demo mode
        demo_sessions.pop(token_hash, None)
        return
    
    # Firestore mode
    try:
        db.collection("Sessions").document(token_hash).delete()
    except Exception as e:
        print(f"Session deletion error: {e}")

def delete_all_user_sessions(username):
    """Delete all sessions for a user (logout from all devices)"""
    if not db:
        # Demo mode
        to_delete = []
        for token_hash, session in demo_sessions.items():
            if session.get('username', '').lower() == username.lower():
                to_delete.append(token_hash)
        
        for token_hash in to_delete:
            del demo_sessions[token_hash]
        return
    
    # Firestore mode
    try:
        sessions_ref = db.collection("Sessions").where("username", "==", username.lower())
        docs = list(sessions_ref.stream())
        
        for doc in docs:
            doc.reference.delete()
            
    except Exception as e:
        print(f"Bulk session deletion error: {e}")

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

def require_authentication(request):
    """Require valid authentication, return user info or None"""
    token = get_session_token_from_request(request)
    return verify_session_token(token)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body) if body else {}
            
            action = data.get("action", "")
            
            if action == "register":
                return self.handle_register(data)
            elif action == "login":
                return self.handle_login(data)
            elif action == "logout":
                return self.handle_logout(data)
            elif action == "logout-all":
                return self.handle_logout_all(data)
            elif action == "verify":
                return self.handle_verify_session(data)
            else:
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid action"}).encode())
                
        except Exception as e:
            print(f"Auth API Error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_register(self, data):
        """Handle user registration"""
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        email = data.get("email", "").strip()
        
        # Validation
        if not username or not password:
            self.send_response(400)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Username and password required"}).encode())
            return
        
        if len(username) < 3 or len(username) > 32:
            self.send_response(400)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Username must be 3-32 characters"}).encode())
            return
            
        if len(password) < 6:
            self.send_response(400)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Password must be at least 6 characters"}).encode())
            return
        
        username_lower = username.lower()
        
        try:
            if not db:
                # Demo mode
                if username_lower in demo_users:
                    self.send_response(409)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Access-Control-Allow-Credentials", "true")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Username already exists"}).encode())
                    return
                
                # Hash password and store user
                password_hash = hash_password(password)
                demo_users[username_lower] = {
                    "username": username,
                    "usernameLower": username_lower,
                    "displayName": username,
                    "email": email,
                    "passwordHash": password_hash,
                    "createdAt": datetime.now().isoformat(),
                    "lastLogin": None
                }
                
                self.send_response(201)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "message": "User registered successfully"
                }).encode())
                return
            
            # Check if username already exists in Firestore
            user_doc = db.collection("Users").document(username_lower).get()
            
            if user_doc.exists:
                self.send_response(409)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Username already exists"}).encode())
                return
            
            # Hash password and create user
            password_hash = hash_password(password)
            
            user_data = {
                "username": username_lower,
                "displayName": username,
                "email": email,
                "passwordHash": password_hash,
                "createdAt": fb_firestore.SERVER_TIMESTAMP,
                "lastLogin": None,
                "secret": FIREBASE_SECRET
            }
            
            # Add to Firestore using username as document ID
            db.collection("Users").document(username_lower).set(user_data)
            
            self.send_response(201)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "message": "User registered successfully"
            }).encode())
            
        except Exception as e:
            print(f"Registration error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Registration failed"}).encode())
    
    def handle_login(self, data):
        """Handle user login"""
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        
        if not username or not password:
            self.send_response(400)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Username and password required"}).encode())
            return
        
        username_lower = username.lower()
        user_agent = self.headers.get('User-Agent', '')
        client_ip = get_client_ip(self.headers)
        
        try:
            if not db:
                # Demo mode
                user = demo_users.get(username_lower)
                if not user or not verify_password(password, user["passwordHash"]):
                    self.send_response(401)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Access-Control-Allow-Credentials", "true")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Invalid username or password"}).encode())
                    return
                
                # Create session
                token, token_hash = create_session_demo(username_lower, user["username"], user_agent, client_ip)
                
                # Update last login
                demo_users[username_lower]["lastLogin"] = datetime.now().isoformat()
                
                # Set HTTP-only cookie
                cookie_value = f"kc_session={token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=86400"
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.send_header("Set-Cookie", cookie_value)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "message": "Login successful",
                    "user": {
                        "username": user["usernameLower"],
                        "displayName": user["username"]
                    },
                    "sessionToken": token  # Also return for compatibility
                }).encode())
                return
            
            # Firestore mode - get user by document ID
            user_doc = db.collection("Users").document(username_lower).get()
            
            if not user_doc.exists:
                self.send_response(401)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid username or password"}).encode())
                return
            
            user_data = user_doc.to_dict()
            
            # Verify password
            if not verify_password(password, user_data["passwordHash"]):
                self.send_response(401)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid username or password"}).encode())
                return
            
            # Create session
            token, token_hash = create_session_firestore(
                username_lower, 
                user_data["displayName"], 
                user_agent, 
                client_ip
            )
            
            # Update user's last login
            user_doc.reference.update({
                "lastLogin": fb_firestore.SERVER_TIMESTAMP
            })
            
            # Set HTTP-only cookie
            cookie_value = f"kc_session={token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=86400"
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Set-Cookie", cookie_value)
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "message": "Login successful",
                "user": {
                    "username": user_data["username"],
                    "displayName": user_data["displayName"]
                },
                "sessionToken": token  # Also return for compatibility
            }).encode())
            
        except Exception as e:
            print(f"Login error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Login failed"}).encode())
    
    def handle_logout(self, data):
        """Handle user logout"""
        # Get token from request
        token = get_session_token_from_request(self)
        
        try:
            # Delete session
            delete_session(token)
            
            # Clear cookie
            cookie_value = "kc_session=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0"
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Set-Cookie", cookie_value)
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "message": "Logged out successfully"
            }).encode())
            
        except Exception as e:
            print(f"Logout error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Logout failed"}).encode())
    
    def handle_logout_all(self, data):
        """Handle logout from all devices"""
        # Get current user from session
        user = require_authentication(self)
        if not user:
            self.send_response(401)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Authentication required"}).encode())
            return
        
        try:
            # Delete all sessions for this user
            delete_all_user_sessions(user["username"])
            
            # Clear cookie
            cookie_value = "kc_session=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0"
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Set-Cookie", cookie_value)
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "message": "Logged out from all devices"
            }).encode())
            
        except Exception as e:
            print(f"Logout all error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Logout all failed"}).encode())
    
    def handle_verify_session(self, data):
        """Verify if session is valid"""
        try:
            user = require_authentication(self)
            
            if not user:
                self.send_response(401)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid or expired session"}).encode())
                return
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "valid": True,
                "user": user
            }).encode())
            
        except Exception as e:
            print(f"Session verification error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Session verification failed"}).encode())
    
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Cookie")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()