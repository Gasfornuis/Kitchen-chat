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
            logger.info(f"Headers: {dict(self.headers)}")
            
            # Simple demo response for now
            demo_data = [
                {
                    "id": "demo1",
                    "Content": "Demo message 1",
                    "CreatedAt": datetime.now().isoformat(),
                    "PostedBy": "System",
                    "MessageType": "text"
                }
            ]
            
            success = send_response_with_cors(self, demo_data, 200)
            logger.info(f"GET completed successfully: {success}")
            
        except Exception as e:
            logger.error(f"GET error: {e}")
            logger.error(traceback.format_exc())
            try:
                send_response_with_cors(self, {"error": f"GET failed: {str(e)}"}, 500)
            except:
                logger.error("Failed to send error response for GET")

    def do_POST(self):
        step = "unknown"
        try:
            logger.info("=== POST REQUEST START ===")
            step = "headers"
            logger.info(f"Path: {self.path}")
            logger.info(f"Headers: {dict(self.headers)}")
            logger.info(f"Content-Length: {self.headers.get('Content-Length', 'None')}")
            
            step = "read_body"
            content_length = int(self.headers.get('Content-Length', 0))
            logger.info(f"Reading {content_length} bytes")
            
            if content_length <= 0:
                logger.warning("No content provided")
                return send_response_with_cors(self, {"error": "No data provided"}, 400)
            
            body = self.rfile.read(content_length)
            logger.info(f"Body read: {len(body)} bytes")
            
            step = "parse_json"
            body_str = body.decode('utf-8')
            logger.info(f"Body string: {body_str[:200]}...")  # First 200 chars
            
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
            
            step = "demo_response"
            # For now, always return success without actually saving
            response_data = {
                "ok": True,
                "id": str(uuid.uuid4()),
                "type": "text",
                "demo": True,
                "received": {
                    "content": content[:50],
                    "subject_id": subject_id,
                    "posted_by": posted_by
                }
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
                logger.error(traceback.format_exc())
