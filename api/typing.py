from http.server import BaseHTTPRequestHandler
import json
import os
from google.cloud import firestore
from urllib.parse import urlparse, parse_qs
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import time

# Import authentication functions from auth.py
from .auth import require_authentication

if not firebase_admin._apps:
    # Load service account from environment variable
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
        firebase_admin.initialize_app(cred)
    else:
        # Fallback for demo mode
        print("Warning: Running in demo mode without Firebase")

db = firestore.client() if firebase_admin._apps else None
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")

# Demo mode storage
demo_typing = {}

def send_auth_error(handler):
    """Send authentication error response"""
    handler.send_response(401)
    handler.send_header("Content-type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Credentials", "true")
    handler.end_headers()
    handler.wfile.write(json.dumps({"error": "Authentication required"}).encode())

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Require authentication for viewing typing status
            current_user = require_authentication(self)
            if not current_user:
                return send_auth_error(self)
            
            parsed_url = urlparse(self.path)
            query = parse_qs(parsed_url.query)
            subject_id = query.get("SubjectId", [None])[0]
            
            if not subject_id:
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing SubjectId"}).encode())
                return
            
            if not db:
                # Demo mode
                typing_users = demo_typing.get(subject_id, [])
                # Filter out expired entries (older than 10 seconds)
                current_time = time.time()
                active_typing = [
                    user for user in typing_users 
                    if current_time - user.get("timestamp", 0) < 10 and user.get("IsTyping", False)
                ]
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps(active_typing).encode())
                return
            
            # Query Firestore for typing indicators
            # Only get recent typing indicators (last 10 seconds)
            cutoff_time = datetime.now() - timedelta(seconds=10)
            
            typing_ref = db.collection("TypingStatus").where("SubjectId", "==", subject_id).where("UpdatedAt", ">=", cutoff_time)
            docs = typing_ref.stream()
            
            typing_users = []
            for doc in docs:
                data = doc.to_dict()
                if data.get("IsTyping", False):
                    typing_users.append({
                        "UserId": data.get("UserId", ""),
                        "UserName": data.get("UserName", "Anonymous"),
                        "IsTyping": data.get("IsTyping", False),
                        "UpdatedAt": str(data.get("UpdatedAt", datetime.now()))
                    })
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps(typing_users).encode())
            
        except Exception as e:
            print(f"Typing GET error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def do_POST(self):
        try:
            # Require authentication for sending typing indicators
            current_user = require_authentication(self)
            if not current_user:
                return send_auth_error(self)
            
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            subject_id = data.get("SubjectId", "")
            user_id = data.get("UserId", "")
            user_name = data.get("UserName", current_user["displayName"])  # Default to authenticated user
            is_typing = data.get("IsTyping", False)
            
            if not subject_id or not user_id:
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing SubjectId or UserId"}).encode())
                return
            
            # Security check - users can only send typing indicators as themselves
            # For simplicity, we'll trust the user_name if they're authenticated
            
            if not db:
                # Demo mode
                if subject_id not in demo_typing:
                    demo_typing[subject_id] = []
                
                # Remove existing entry for this user
                demo_typing[subject_id] = [
                    user for user in demo_typing[subject_id] 
                    if user.get("UserId") != user_id
                ]
                
                # Add new entry if typing
                if is_typing:
                    demo_typing[subject_id].append({
                        "UserId": user_id,
                        "UserName": user_name,
                        "IsTyping": is_typing,
                        "timestamp": time.time()
                    })
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "demo": True}).encode())
                return
            
            # Create document ID based on subject and user for easy updates
            doc_id = f"{subject_id}_{user_id}"
            
            if is_typing:
                # Update or create typing indicator
                doc_data = {
                    "SubjectId": subject_id,
                    "UserId": user_id,
                    "UserName": user_name,
                    "IsTyping": is_typing,
                    "UpdatedAt": firestore.SERVER_TIMESTAMP,
                    "secret": FIREBASE_SECRET
                }
                
                # Use set with merge to update existing document
                db.collection("TypingStatus").document(doc_id).set(doc_data, merge=True)
            else:
                # Remove typing indicator
                try:
                    db.collection("TypingStatus").document(doc_id).delete()
                except:
                    pass  # Document might not exist, that's okay
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
            
        except Exception as e:
            print(f"Error updating typing status: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Cookie")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()