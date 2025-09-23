from http.server import BaseHTTPRequestHandler
import json
import os
from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials, firestore
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
            # Require authentication for viewing subjects
            current_user = require_authentication(self)
            if not current_user:
                return send_auth_error(self)
            
            if not db:
                # Demo mode - return demo subjects
                demo_subjects = [
                    {
                        "id": "demo1",
                        "Title": "General Chat",
                        "CreatedBy": "System",
                        "CreatedAt": datetime.now().isoformat()
                    },
                    {
                        "id": "demo2",
                        "Title": "Random",
                        "CreatedBy": "System",
                        "CreatedAt": datetime.now().isoformat()
                    }
                ]
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps(demo_subjects).encode())
                return

            # Query Firestore for subjects
            subjects_ref = db.collection("Subjects").order_by("CreatedAt", direction=firestore.Query.DESCENDING)
            docs = subjects_ref.stream()

            subjects = []
            for doc in docs:
                data = doc.to_dict()
                subjects.append({
                    "id": doc.id,
                    "Title": data.get("Title", ""),
                    "CreatedBy": data.get("CreatedBy", "Anonymous"),
                    "CreatedAt": str(data.get("CreatedAt", datetime.now()))
                })

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps(subjects).encode())

        except Exception as e:
            print(f"Subjects GET error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_POST(self):
        try:
            # Require authentication for creating subjects
            current_user = require_authentication(self)
            if not current_user:
                return send_auth_error(self)
            
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            title = data.get("Title", "").strip()
            created_by = data.get("CreatedBy", current_user["displayName"])  # Default to authenticated user

            if not title:
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Title is required"}).encode())
                return
            
            # Security check - user can only create subjects as themselves
            if created_by.lower() != current_user["displayName"].lower() and created_by.lower() != current_user["username"].lower():
                self.send_response(403)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "You can only create subjects as yourself"}).encode())
                return

            if not db:
                # Demo mode - just return success
                self.send_response(201)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "message": "Subject created successfully (demo mode)",
                    "id": "demo_" + str(datetime.now().timestamp()),
                    "title": title
                }).encode())
                return

            # Create document data
            doc_data = {
                "Title": title,
                "CreatedBy": created_by,
                "CreatedAt": firestore.SERVER_TIMESTAMP,
                "secret": FIREBASE_SECRET
            }

            # Add to Firestore
            doc_ref = db.collection("Subjects").add(doc_data)
            
            self.send_response(201)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({
                "message": "Subject created successfully",
                "id": doc_ref[1].id,
                "title": title
            }).encode())

        except Exception as e:
            print(f"Error creating subject: {str(e)}")
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