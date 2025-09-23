from http.server import BaseHTTPRequestHandler
import json
import os
from google.cloud import firestore
from urllib.parse import urlparse, parse_qs
import firebase_admin
from firebase_admin import credentials, firestore
import base64
import uuid
from datetime import datetime

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
            # Require authentication for reading posts
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
                # Demo mode - return empty messages
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps([]).encode())
                return

            # Query Firestore for messages
            posts_ref = db.collection("Posts").where("SubjectId", "==", f"/subjects/{subject_id}").order_by("CreatedAt")
            docs = posts_ref.stream()

            posts = []
            for doc in docs:
                data = doc.to_dict()
                posts.append({
                    "id": doc.id,
                    "Content": data.get("Content", ""),
                    "CreatedAt": str(data.get("CreatedAt", datetime.now())),
                    "PostedBy": data.get("PostedBy", "Anonymous"),
                    "SubjectId": data.get("SubjectId", ""),
                    "MessageType": data.get("MessageType", "text"),
                    "MediaData": data.get("MediaData", None),
                    "AttachmentUrl": data.get("AttachmentUrl", None),
                    "AttachmentType": data.get("AttachmentType", None)
                })

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps(posts).encode())

        except Exception as e:
            print(f"Posts GET error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_POST(self):
        try:
            # Require authentication for posting messages
            current_user = require_authentication(self)
            if not current_user:
                return send_auth_error(self)
            
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            content = data.get("Content", "")
            subject_id = data.get("SubjectId")
            posted_by = data.get("PostedBy", current_user["displayName"])  # Default to authenticated user
            message_type = data.get("MessageType", "text")
            media_data = data.get("MediaData", None)
            
            if not subject_id:
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing SubjectId"}).encode())
                return
            
            # Security check - user can only post as themselves
            if posted_by.lower() != current_user["displayName"].lower() and posted_by.lower() != current_user["username"].lower():
                self.send_response(403)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "You can only post as yourself"}).encode())
                return

            if not db:
                # Demo mode - just return success
                self.send_response(201)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "message": "Message created (demo mode)",
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.now().isoformat()
                }).encode())
                return

            # Prepare document data
            doc_data = {
                "Content": content,
                "CreatedAt": firestore.SERVER_TIMESTAMP,
                "PostedBy": posted_by,
                "SubjectId": f"/subjects/{subject_id}",
                "MessageType": message_type,
                "secret": FIREBASE_SECRET
            }

            # Handle media data
            if media_data:
                if message_type == "voice":
                    # Store voice message metadata
                    doc_data["MediaData"] = {
                        "duration": media_data.get("duration", "0:05"),
                        "size": media_data.get("size", "0 KB"),
                        "waveform": media_data.get("waveform", [])
                    }
                    # Note: In production, you'd upload the audio blob to Firebase Storage
                    # and store the download URL in AttachmentUrl
                    doc_data["AttachmentType"] = "audio/webm"
                    
                elif message_type == "image":
                    # Store image metadata
                    doc_data["MediaData"] = {
                        "name": media_data.get("name", "image.jpg"),
                        "size": media_data.get("size", "0 KB")
                    }
                    # For demo, we'll store the base64 data directly (not recommended for production)
                    if "src" in media_data and media_data["src"].startswith("data:"):
                        doc_data["AttachmentUrl"] = media_data["src"]
                    doc_data["AttachmentType"] = "image/*"
                    
                elif message_type == "file":
                    # Store file metadata
                    doc_data["MediaData"] = {
                        "name": media_data.get("name", "file.txt"),
                        "size": media_data.get("size", "0 KB"),
                        "extension": media_data.get("extension", "FILE"),
                        "icon": media_data.get("icon", "fas fa-file")
                    }
                    doc_data["AttachmentUrl"] = media_data.get("url", "#")
                    doc_data["AttachmentType"] = "application/octet-stream"

            # Add to Firestore
            doc_ref = db.collection("Posts").add(doc_data)
            
            self.send_response(201)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({
                "message": "Message created successfully",
                "id": doc_ref[1].id,
                "type": message_type
            }).encode())

        except Exception as e:
            print(f"Error creating post: {str(e)}")  # Server-side logging
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