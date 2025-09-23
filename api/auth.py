from http.server import BaseHTTPRequestHandler
import json
import os
import hashlib
import secrets
import time
from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta

if not firebase_admin._apps:
    # Load service account from environment variable
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
        firebase_admin.initialize_app(cred)
    else:
        print("Warning: Running in demo mode without Firebase")

db = firestore.client() if firebase_admin._apps else None
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")

# Demo mode storage
demo_users = {}
demo_sessions = {}

def hash_password(password):
    """Hash password using SHA-256 with salt"""
    salt = secrets.token_hex(32)  # Generate random salt
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{pwd_hash}"

def verify_password(password, stored_hash):
    """Verify password against stored hash"""
    try:
        salt, pwd_hash = stored_hash.split(':')
        return hashlib.sha256((password + salt).encode()).hexdigest() == pwd_hash
    except:
        return False

def generate_session_token():
    """Generate secure session token"""
    return secrets.token_urlsafe(32)

def is_valid_session(token):
    """Check if session token is valid and not expired"""
    if not db:
        # Demo mode
        session = demo_sessions.get(token)
        if not session:
            return None
        
        if time.time() > session['expires']:
            del demo_sessions[token]
            return None
            
        return session['username']
    
    # Firebase mode
    try:
        sessions_ref = db.collection("Sessions").where("token", "==", token).limit(1)
        docs = list(sessions_ref.stream())
        
        if not docs:
            return None
            
        session_data = docs[0].to_dict()
        expires_at = session_data.get('expiresAt')
        
        if expires_at and expires_at.timestamp() < time.time():
            # Session expired - delete it
            docs[0].reference.delete()
            return None
            
        return session_data.get('username')
        
    except Exception as e:
        print(f"Session validation error: {e}")
        return None

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            action = data.get("action", "")
            
            if action == "register":
                return self.handle_register(data)
            elif action == "login":
                return self.handle_login(data)
            elif action == "logout":
                return self.handle_logout(data)
            elif action == "verify":
                return self.handle_verify_session(data)
            else:
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid action"}).encode())
                
        except Exception as e:
            print(f"Auth API Error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
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
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Username and password required"}).encode())
            return
        
        if len(username) < 3:
            self.send_response(400)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Username must be at least 3 characters"}).encode())
            return
            
        if len(password) < 6:
            self.send_response(400)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Password must be at least 6 characters"}).encode())
            return
        
        try:
            if not db:
                # Demo mode
                if username.lower() in demo_users:
                    self.send_response(400)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Username already exists"}).encode())
                    return
                
                # Hash password and store user
                password_hash = hash_password(password)
                demo_users[username.lower()] = {
                    "username": username,
                    "email": email,
                    "passwordHash": password_hash,
                    "createdAt": datetime.now().isoformat(),
                    "lastLogin": None
                }
                
                self.send_response(201)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "message": "User registered successfully",
                    "username": username
                }).encode())
                return
            
            # Check if username already exists
            users_ref = db.collection("Users").where("username", "==", username.lower()).limit(1)
            existing_users = list(users_ref.stream())
            
            if existing_users:
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Username already exists"}).encode())
                return
            
            # Hash password and create user
            password_hash = hash_password(password)
            
            user_data = {
                "username": username.lower(),  # Store lowercase for consistency
                "displayName": username,  # Original case for display
                "email": email,
                "passwordHash": password_hash,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "lastLogin": None,
                "secret": FIREBASE_SECRET
            }
            
            # Add to Firestore
            db.collection("Users").add(user_data)
            
            self.send_response(201)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "message": "User registered successfully",
                "username": username
            }).encode())
            
        except Exception as e:
            print(f"Registration error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Registration failed"}).encode())
    
    def handle_login(self, data):
        """Handle user login"""
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        
        if not username or not password:
            self.send_response(400)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Username and password required"}).encode())
            return
        
        try:
            if not db:
                # Demo mode
                user = demo_users.get(username.lower())
                if not user or not verify_password(password, user["passwordHash"]):
                    self.send_response(401)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Invalid username or password"}).encode())
                    return
                
                # Create session
                session_token = generate_session_token()
                demo_sessions[session_token] = {
                    "username": user["username"],
                    "expires": time.time() + (24 * 60 * 60)  # 24 hours
                }
                
                # Update last login
                demo_users[username.lower()]["lastLogin"] = datetime.now().isoformat()
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "message": "Login successful",
                    "username": user["username"],
                    "displayName": user["username"],
                    "sessionToken": session_token
                }).encode())
                return
            
            # Check if user exists
            users_ref = db.collection("Users").where("username", "==", username.lower()).limit(1)
            docs = list(users_ref.stream())
            
            if not docs:
                self.send_response(401)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid username or password"}).encode())
                return
            
            user_data = docs[0].to_dict()
            
            # Verify password
            if not verify_password(password, user_data["passwordHash"]):
                self.send_response(401)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid username or password"}).encode())
                return
            
            # Create session token
            session_token = generate_session_token()
            expires_at = datetime.now() + timedelta(days=1)  # 24 hours
            
            # Store session in Firestore
            session_data = {
                "token": session_token,
                "username": user_data["username"],
                "displayName": user_data["displayName"],
                "createdAt": firestore.SERVER_TIMESTAMP,
                "expiresAt": expires_at,
                "secret": FIREBASE_SECRET
            }
            
            db.collection("Sessions").add(session_data)
            
            # Update user's last login
            docs[0].reference.update({
                "lastLogin": firestore.SERVER_TIMESTAMP
            })
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "message": "Login successful",
                "username": user_data["username"],
                "displayName": user_data["displayName"],
                "sessionToken": session_token
            }).encode())
            
        except Exception as e:
            print(f"Login error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Login failed"}).encode())
    
    def handle_logout(self, data):
        """Handle user logout"""
        session_token = data.get("sessionToken", "")
        
        if not session_token:
            self.send_response(400)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Session token required"}).encode())
            return
        
        try:
            if not db:
                # Demo mode
                if session_token in demo_sessions:
                    del demo_sessions[session_token]
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"message": "Logged out successfully"}).encode())
                return
            
            # Delete session from Firestore
            sessions_ref = db.collection("Sessions").where("token", "==", session_token)
            docs = list(sessions_ref.stream())
            
            for doc in docs:
                doc.reference.delete()
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Logged out successfully"}).encode())
            
        except Exception as e:
            print(f"Logout error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Logout failed"}).encode())
    
    def handle_verify_session(self, data):
        """Verify if session token is valid"""
        session_token = data.get("sessionToken", "")
        
        if not session_token:
            self.send_response(400)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Session token required"}).encode())
            return
        
        try:
            username = is_valid_session(session_token)
            
            if not username:
                self.send_response(401)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid or expired session"}).encode())
                return
            
            # Get user display name
            display_name = username
            
            if db:
                users_ref = db.collection("Users").where("username", "==", username.lower()).limit(1)
                docs = list(users_ref.stream())
                if docs:
                    user_data = docs[0].to_dict()
                    display_name = user_data.get("displayName", username)
            else:
                # Demo mode
                user = demo_users.get(username.lower())
                if user:
                    display_name = user.get("username", username)
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "valid": True,
                "username": username,
                "displayName": display_name
            }).encode())
            
        except Exception as e:
            print(f"Session verification error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Session verification failed"}).encode())
    
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()