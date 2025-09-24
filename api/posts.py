from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import urlparse, parse_qs
import firebase_admin
from firebase_admin import credentials, firestore as admin_firestore
import uuid
from datetime import datetime
import logging
import traceback

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Import auth
try:
    from .auth import require_authentication
except ImportError:
    from auth import require_authentication

# Firebase setup
db = None
try:
    if not firebase_admin._apps:
        sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if sa_json:
            cred = credentials.Certificate(json.loads(sa_json))
            firebase_admin.initialize_app(cred)
        else:
            logger.warning("No FIREBASE_SERVICE_ACCOUNT - running in demo mode")
    
    if firebase_admin._apps:
        db = admin_firestore.client()
        logger.info("Firestore initialized successfully")
        
except Exception as e:
    logger.error(f"Firebase initialization failed: {e}")
    db = None

# CORS setup
def send_response_with_cors(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
    handler.end_headers()
    handler.wfile.write(body)

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def do_GET(self):
        try:
            # Auth check
            current_user = require_authentication(self)
            if not current_user:
                return send_response_with_cors(self, {"error": "Authentication required"}, 401)
            
            # Parse SubjectId
            parsed_url = urlparse(self.path)
            query = parse_qs(parsed_url.query or "")
            subject_vals = query.get("SubjectId", [])
            subject_id = subject_vals[0] if subject_vals else None
            
            if not subject_id:
                return send_response_with_cors(self, {"error": "Missing SubjectId parameter"}, 400)
            
            if not db:
                # Demo mode
                demo_data = [{
                    "id": "demo1",
                    "Content": "Welcome to Kitchen Chat! (Demo mode - no database)",
                    "CreatedAt": datetime.now().isoformat(),
                    "PostedBy": "System",
                    "SubjectId": f"/subjects/{subject_id}",
                    "MessageType": "text"
                }]
                return send_response_with_cors(self, demo_data, 200)
            
            # Query Firestore
            try:
                posts_ref = (
                    db.collection("Posts")
                    .where("SubjectId", "==", f"/subjects/{subject_id}")
                    .limit(500)
                )
                docs = list(posts_ref.stream())
                
                posts = []
                for doc in docs:
                    try:
                        data = doc.to_dict()
                        
                        # Handle CreatedAt
                        created_at = data.get("CreatedAt")
                        if hasattr(created_at, "isoformat"):
                            created_at_str = created_at.isoformat()
                        elif isinstance(created_at, datetime):
                            created_at_str = created_at.isoformat()
                        else:
                            created_at_str = str(created_at) if created_at else datetime.now().isoformat()
                        
                        posts.append({
                            "id": doc.id,
                            "Content": data.get("Content", ""),
                            "CreatedAt": created_at_str,
                            "PostedBy": data.get("PostedBy", "Anonymous"),
                            "SubjectId": data.get("SubjectId", ""),
                            "MessageType": data.get("MessageType", "text")
                        })
                        
                    except Exception as doc_error:
                        logger.error(f"Error processing doc {doc.id}: {doc_error}")
                        continue
                
                return send_response_with_cors(self, posts, 200)
                
            except Exception as firestore_error:
                logger.error(f"Firestore query error: {firestore_error}")
                return send_response_with_cors(self, [], 200)  # Return empty array to keep UI working
            
        except Exception as e:
            logger.error(f"GET error: {e}")
            return send_response_with_cors(self, {"error": "Internal server error"}, 500)

    def do_POST(self):
        try:
            # Parse request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length <= 0:
                return send_response_with_cors(self, {"error": "No data provided"}, 400)
            
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
            
            # Validate required fields
            content = data.get("Content", "").strip()
            subject_id = data.get("SubjectId", "").strip()
            
            if not content:
                return send_response_with_cors(self, {"error": "Content is required"}, 400)
            if not subject_id:
                return send_response_with_cors(self, {"error": "SubjectId is required"}, 400)
            if len(content) > 2000:
                return send_response_with_cors(self, {"error": "Message too long (max 2000 chars)"}, 400)
            
            # Auth check
            current_user = require_authentication(self)
            if not current_user:
                return send_response_with_cors(self, {"error": "Authentication required"}, 401)
            
            posted_by = current_user.get("displayName", "Anonymous")
            
            if not db:
                # Demo mode
                return send_response_with_cors(self, {
                    "ok": True,
                    "id": str(uuid.uuid4()),
                    "demo": True,
                    "message": "Demo mode - message not actually saved"
                }, 201)
            
            # Write to Firestore using the method that worked
            try:
                doc_data = {
                    "Content": content,
                    "CreatedAt": datetime.now(),  # This was the working method
                    "PostedBy": posted_by,
                    "SubjectId": f"/subjects/{subject_id}",
                    "MessageType": "text"
                }
                
                doc_ref, write_result = db.collection("Posts").add(doc_data)
                
                return send_response_with_cors(self, {
                    "ok": True,
                    "id": doc_ref.id,
                    "message": "Message saved successfully"
                }, 201)
                
            except Exception as write_error:
                logger.error(f"Firestore write error: {write_error}")
                return send_response_with_cors(self, {"error": "Failed to save message"}, 500)
            
        except json.JSONDecodeError:
            return send_response_with_cors(self, {"error": "Invalid JSON"}, 400)
        except Exception as e:
            logger.error(f"POST error: {e}")
            return send_response_with_cors(self, {"error": "Internal server error"}, 500)
