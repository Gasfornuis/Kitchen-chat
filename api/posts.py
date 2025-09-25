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

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import auth
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

# Firebase setup
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

# Simple CORS
def send_response_with_cors(handler, data, status=200):
    try:
        logger.info(f"Sending response with status {status}")
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        
        handler.send_response(status)
        handler.send_header('Content-Type', 'application/json; charset=utf-8')
        handler.send_header('Content-Length', str(len(body)))
        handler.send_header('Access-Control-Allow-Origin', '*')
        handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
        handler.end_headers()
        
        handler.wfile.write(body)
        logger.info("Response sent successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to send response: {e}")
        logger.error(traceback.format_exc())
        return False

class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to use our logger
        logger.info(f"HTTP: {format % args}")
    
    def do_OPTIONS(self):
        try:
            logger.info("Handling OPTIONS request")
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
            self.send_header('Access-Control-Max-Age', '86400')
            self.end_headers()
            logger.info("OPTIONS response sent")
        except Exception as e:
            logger.error(f"OPTIONS error: {e}")
            logger.error(traceback.format_exc())

    def do_GET(self):
        try:
            logger.info("=== GET REQUEST START ===")
            logger.info(f"Path: {self.path}")
            
            # Parse query parameters
            parsed_url = urlparse(self.path)
            query = parse_qs(parsed_url.query or "")
            subject_vals = query.get("SubjectId", [])
            subject_id = subject_vals[0] if subject_vals else None
            
            logger.info(f"SubjectId from query: {subject_id}")
            
            if not subject_id:
                return send_response_with_cors(self, {"error": "Missing SubjectId parameter"}, 400)
            
            # Auth check
            if require_authentication:
                current_user = require_authentication(self)
                if not current_user:
                    return send_response_with_cors(self, {"error": "Authentication required"}, 401)
                logger.info(f"User authenticated: {current_user.get('username', 'unknown')}")
            
            if not db:
                logger.info("No database - returning demo messages")
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
            
            # Real Firestore query with ORDER BY CreatedAt
            try:
                logger.info(f"Querying Firestore for subject: {subject_id}")
                posts_ref = (
                    db.collection("Posts")
                    .where("SubjectId", "==", f"/subjects/{subject_id}")
                    .order_by("CreatedAt", direction=admin_firestore.Query.ASCENDING)  # Sorteer op tijd, oudste eerst
                    .limit(100)
                )
                
                docs = list(posts_ref.stream())
                logger.info(f"Found {len(docs)} messages")
                
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
                
                logger.info(f"Returning {len(posts)} messages in chronological order")
                return send_response_with_cors(self, posts, 200)
                
            except Exception as firestore_error:
                logger.error(f"Firestore query error: {firestore_error}")
                logger.error(traceback.format_exc())
                return send_response_with_cors(self, {"error": "Database query failed"}, 500)
            
        except Exception as e:
            logger.error(f"GET error: {e}")
            logger.error(traceback.format_exc())
            return send_response_with_cors(self, {"error": f"GET failed: {str(e)}"}, 500)

    def do_POST(self):
        step = "unknown"
        try:
            logger.info("=== POST REQUEST START ===")
            step = "headers"
            logger.info(f"Path: {self.path}")
            logger.info(f"Content-Length: {self.headers.get('Content-Length', 'None')}")
            
            step = "read_body"
            content_length = int(self.headers.get('Content-Length', 0))
            
            if content_length <= 0:
                return send_response_with_cors(self, {"error": "No data provided"}, 400)
            
            body = self.rfile.read(content_length)
            body_str = body.decode('utf-8')
            
            step = "parse_json"
            data = json.loads(body_str)
            logger.info(f"JSON parsed, keys: {list(data.keys())}")
            
            step = "validate_data"
            content = data.get("Content", "").strip()
            subject_id = data.get("SubjectId", "").strip()
            
            logger.info(f"Content: '{content[:50]}...' SubjectId: '{subject_id}'")
            
            if not content:
                return send_response_with_cors(self, {"error": "Content is required"}, 400)
            if not subject_id:
                return send_response_with_cors(self, {"error": "SubjectId is required"}, 400)
            
            step = "auth_check"
            if require_authentication:
                logger.info("Checking authentication...")
                current_user = require_authentication(self)
                if not current_user:
                    logger.warning("Authentication failed")
                    return send_response_with_cors(self, {"error": "Authentication required"}, 401)
                logger.info(f"User authenticated: {current_user.get('username', 'unknown')}")
                posted_by = current_user.get("displayName", "Anonymous")
            else:
                logger.warning("No auth function available - skipping auth")
                posted_by = "TestUser"
            
            step = "database_check"
            if not db:
                logger.warning("No database available - returning demo response")
                response_data = {
                    "ok": True,
                    "id": str(uuid.uuid4()),
                    "type": "text",
                    "demo": True,
                    "message": "Message would be saved if database was available"
                }
                return send_response_with_cors(self, response_data, 201)
            
            step = "firestore_write"
            logger.info("Writing to Firestore...")
            
            # FIXED: Correct Firestore write with proper timestamp handling
            doc_data = {
                "Content": content,
                "CreatedAt": admin_firestore.SERVER_TIMESTAMP,  # Use SERVER_TIMESTAMP for proper Firestore handling
                "PostedBy": posted_by,
                "SubjectId": f"/subjects/{subject_id}",
                "MessageType": "text"
            }
            
            logger.info(f"Document data prepared with SERVER_TIMESTAMP")
            
            # Single write operation - correctly handle Firestore response
            try:
                # Method 1: Use add() which returns (doc_ref, write_result) tuple
                update_time, doc_ref = db.collection("Posts").add(doc_data)
                doc_id = doc_ref.id
                logger.info(f"SUCCESS: Document saved with ID: {doc_id} at {update_time}")
                
            except Exception as write_error:
                logger.error(f"Firestore add() failed, trying alternative method: {write_error}")
                
                # Method 2: Use document().set() as fallback
                try:
                    doc_ref = db.collection("Posts").document()
                    doc_data["CreatedAt"] = datetime.now()  # Use regular datetime for set method
                    doc_ref.set(doc_data)
                    doc_id = doc_ref.id
                    logger.info(f"SUCCESS: Document saved with set() method, ID: {doc_id}")
                    
                except Exception as set_error:
                    logger.error(f"All Firestore write methods failed: {set_error}")
                    logger.error(f"Original add() error: {write_error}")
                    logger.error(traceback.format_exc())
                    return send_response_with_cors(self, {
                        "error": "Failed to save message",
                        "details": f"add() failed: {str(write_error)}, set() failed: {str(set_error)}"
                    }, 500)
            
            step = "success_response"
            response_data = {
                "ok": True,
                "id": doc_id,
                "type": "text",
                "message": "Message saved successfully"
            }
            
            logger.info(f"Sending success response: {response_data}")
            success = send_response_with_cors(self, response_data, 201)
            logger.info(f"POST completed successfully: {success}")
            
        except Exception as e:
            logger.error(f"POST error at step '{step}': {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(traceback.format_exc())
            
            try:
                error_response = {
                    "error": f"POST failed at step '{step}'",
                    "details": str(e),
                    "type": type(e).__name__
                }
                send_response_with_cors(self, error_response, 500)
            except Exception as send_error:
                logger.error(f"Failed to send error response: {send_error}")