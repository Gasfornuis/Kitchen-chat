from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from urllib.parse import urlparse, parse_qs
import firebase_admin
from firebase_admin import credentials, firestore as admin_firestore
import uuid
from datetime import datetime
import logging
import traceback

# Setup logging (behouden - dit was belangrijk)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import auth (exact hetzelfde)
try:
    from .auth import require_authentication
    logger.info("Auth imported successfully (relative)")
except ImportError:
    try:
        from auth import require_authentication
        logger.info("Auth imported successfully (absolute)")
    except ImportError as e:
        logger.error(f"Failed to import auth: {e}")
        require_authentication = None

# Firebase setup (exact hetzelfde)
db = None
try:
    logger.info("Initializing Firebase...")
    if not firebase_admin._apps:
        sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if sa_json:
            logger.info("Firebase service account found, initializing...")
            cred = credentials.Certificate(json.loads(sa_json))
            firebase_admin.initialize_app(cred)
            logger.info("Firebase app initialized")
        else:
            logger.warning("No FIREBASE_SERVICE_ACCOUNT found - running in demo mode")
    
    if firebase_admin._apps:
        db = admin_firestore.client()
        logger.info("Firestore client created successfully")
    else:
        logger.warning("No Firebase app - db will be None")
        
except Exception as e:
    logger.error(f"Firebase initialization failed: {e}")
    logger.error(traceback.format_exc())
    db = None

# Simple CORS (exact hetzelfde als werkende versie)
def send_response_with_cors(handler, data, status=200):
    try:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        
        handler.send_response(status)
        handler.send_header('Content-Type', 'application/json; charset=utf-8')
        handler.send_header('Content-Length', str(len(body)))
        handler.send_header('Access-Control-Allow-Origin', '*')
        handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
        handler.end_headers()
        
        handler.wfile.write(body)
        return True
    except Exception as e:
        logger.error(f"Failed to send response: {e}")
        logger.error(traceback.format_exc())
        return False

class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to use our logger (behouden)
        logger.info(f"HTTP: {format % args}")
    
    def do_OPTIONS(self):
        try:
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
            self.send_header('Access-Control-Max-Age', '86400')
            self.end_headers()
        except Exception as e:
            logger.error(f"OPTIONS error: {e}")

    def do_GET(self):
        try:
            # Parse query parameters
            parsed_url = urlparse(self.path)
            query = parse_qs(parsed_url.query or "")
            subject_vals = query.get("SubjectId", [])
            subject_id = subject_vals[0] if subject_vals else None
            
            if not subject_id:
                return send_response_with_cors(self, {"error": "Missing SubjectId parameter"}, 400)
            
            # Auth check
            if require_authentication:
                current_user = require_authentication(self)
                if not current_user:
                    return send_response_with_cors(self, {"error": "Authentication required"}, 401)
            
            if not db:
                demo_data = [
                    {
                        "id": "demo1",
                        "Content": "Demo message - database not available",
                        "CreatedAt": datetime.now().isoformat(),
                        "PostedBy": "System",
                        "SubjectId": f"/subjects/{subject_id}",
                        "MessageType": "text"
                    }
                ]
                return send_response_with_cors(self, demo_data, 200)
            
            # Real Firestore query
            try:
                posts_ref = (
                    db.collection("Posts")
                    .where("SubjectId", "==", f"/subjects/{subject_id}")
                    .limit(100)
                )
                
                docs = list(posts_ref.stream())
                
                posts = []
                for doc in docs:
                    try:
                        data = doc.to_dict()
                        
                        # Handle CreatedAt safely
                        created_at = data.get("CreatedAt")
                        if hasattr(created_at, "isoformat"):
                            created_at_str = created_at.isoformat()
                        elif isinstance(created_at, datetime):
                            created_at_str = created_at.isoformat()
                        else:
                            created_at_str = str(created_at) if created_at else datetime.now().isoformat()
                        
                        post = {
                            "id": doc.id,
                            "Content": data.get("Content", ""),
                            "CreatedAt": created_at_str,
                            "PostedBy": data.get("PostedBy", "Anonymous"),
                            "SubjectId": data.get("SubjectId", ""),
                            "MessageType": data.get("MessageType", "text")
                        }
                        posts.append(post)
                        
                    except Exception as doc_error:
                        logger.error(f"Error processing doc {doc.id}: {doc_error}")
                        continue
                
                return send_response_with_cors(self, posts, 200)
                
            except Exception as firestore_error:
                logger.error(f"Firestore query error: {firestore_error}")
                return send_response_with_cors(self, [], 200)
            
        except Exception as e:
            logger.error(f"GET error: {e}")
            return send_response_with_cors(self, {"error": f"GET failed: {str(e)}"}, 500)

    def do_POST(self):
        try:
            # Parse body
            content_length = int(self.headers.get('Content-Length', 0))
            
            if content_length <= 0:
                return send_response_with_cors(self, {"error": "No data provided"}, 400)
            
            body = self.rfile.read(content_length)
            body_str = body.decode('utf-8')
            data = json.loads(body_str)
            
            # Validate data
            content = data.get("Content", "").strip()
            subject_id = data.get("SubjectId", "").strip()
            
            if not content:
                return send_response_with_cors(self, {"error": "Content is required"}, 400)
            if not subject_id:
                return send_response_with_cors(self, {"error": "SubjectId is required"}, 400)
            
            # Auth check
            if require_authentication:
                current_user = require_authentication(self)
                if not current_user:
                    return send_response_with_cors(self, {"error": "Authentication required"}, 401)
                posted_by = current_user.get("displayName", "Anonymous")
            else:
                posted_by = "TestUser"
            
            if not db:
                response_data = {
                    "ok": True,
                    "id": str(uuid.uuid4()),
                    "type": "text",
                    "demo": True,
                    "message": "Message would be saved if database was available"
                }
                return send_response_with_cors(self, response_data, 201)
            
            # Write to Firestore using the EXACT method that worked before
            try:
                logger.info("Writing to Firestore...")
                doc_data = {
                    "Content": content,
                    "CreatedAt": datetime.now(),  # Dit was de werkende methode
                    "PostedBy": posted_by,
                    "SubjectId": f"/subjects/{subject_id}",
                    "MessageType": "text"
                }
                
                doc_ref, write_result = db.collection("Posts").add(doc_data)
                logger.info(f"Document written successfully with ID: {doc_ref.id}")
                
                response_data = {
                    "ok": True,
                    "id": doc_ref.id,
                    "type": "text",
                    "message": "Message saved successfully"
                }
                
                return send_response_with_cors(self, response_data, 201)
                
            except Exception as write_error:
                logger.error(f"Firestore write error: {write_error}")
                logger.error(traceback.format_exc())
                return send_response_with_cors(self, {"error": "Failed to save message"}, 500)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return send_response_with_cors(self, {"error": "Invalid JSON format"}, 400)
        except Exception as e:
            logger.error(f"POST error: {e}")
            logger.error(traceback.format_exc())
            return send_response_with_cors(self, {"error": "Failed to create message"}, 500)
