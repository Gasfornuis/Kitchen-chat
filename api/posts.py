from http.server import BaseHTTPRequestHandler
import json
import os
import re
from google.cloud import firestore
from urllib.parse import urlparse, parse_qs
import firebase_admin
from firebase_admin import credentials, firestore
import base64
import uuid
from datetime import datetime
import logging
import traceback

# Import authentication functions from auth.py
try:
    from .auth import require_authentication
except ImportError:
    from auth import require_authentication

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize Firebase with better error handling
db = None
try:
    if not firebase_admin._apps:
        # Load service account from environment variable
        sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if sa_json:
            cred = credentials.Certificate(json.loads(sa_json))
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            logger.info("Firebase initialized successfully")
        else:
            logger.warning("Warning: Running in demo mode without Firebase")
    else:
        db = firestore.client()
except Exception as e:
    logger.error(f"Firebase initialization error: {str(e)}")
    db = None

FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")

# Simplified CORS - matching what auth.py uses
def send_cors_headers(handler):
    """Send consistent CORS headers"""
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Credentials', 'true')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')

def send_json_response(handler, data, status=200):
    """Send JSON response with CORS headers"""
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    send_cors_headers(handler)
    handler.end_headers()
    
    json_str = json.dumps(data, ensure_ascii=False)
    handler.wfile.write(json_str.encode('utf-8'))

def send_error_response(handler, message, status=400):
    """Send error response with CORS headers"""
    logger.error(f"Error {status}: {message}")
    send_json_response(handler, {'error': message}, status)

def validate_message_content(content, message_type='text'):
    """Validate message content for security and policy compliance"""
    if not content or not isinstance(content, str):
        return False, "Message content is required"
    
    content = content.strip()
    
    if len(content) == 0:
        return False, "Message cannot be empty"
    
    if len(content) > 2000:
        return False, "Message too long (max 2000 characters)"
    
    return True, None

def sanitize_string_input(input_str, max_length=None):
    """Basic string sanitization"""
    if not input_str or not isinstance(input_str, str):
        return ''
    
    # Remove dangerous characters
    sanitized = ''.join(
        char for char in input_str 
        if ord(char) >= 32 or char in '\n\r\t'
    )
    
    sanitized = sanitized.strip()
    
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Get messages with enhanced error handling"""
        try:
            logger.info("GET request to posts API")
            
            # Require authentication for reading posts
            current_user = require_authentication(self)
            if not current_user:
                return send_error_response(self, "Authentication required", 401)
            
            parsed_url = urlparse(self.path)
            query = parse_qs(parsed_url.query)
            
            # Fix SubjectId parsing from query
            subject_vals = query.get("SubjectId", [])
            subject_id = subject_vals[0] if subject_vals else None

            if not subject_id:
                logger.warning("Missing SubjectId parameter")
                return send_error_response(self, "Missing SubjectId parameter", 400)
            
            logger.info(f"Fetching messages for SubjectId: {subject_id}")
            
            # Validate subject ID format
            if not isinstance(subject_id, str) or len(subject_id) > 50:
                logger.warning(f"Invalid SubjectId format: {subject_id}")
                return send_error_response(self, "Invalid SubjectId format", 400)

            if not db:
                # Demo mode - return sample messages
                logger.info("Running in demo mode - returning sample messages")
                sample_messages = [
                    {
                        "id": "demo1",
                        "Content": "Welcome to Kitchen Chat! This is a demo message.",
                        "CreatedAt": datetime.now().isoformat(),
                        "PostedBy": "System",
                        "SubjectId": f"/subjects/{subject_id}",
                        "MessageType": "text"
                    }
                ]
                return send_json_response(self, sample_messages)

            try:
                posts = []
                
                # Try multiple query variations to handle different SubjectId formats
                try:
                    posts_ref = db.collection("Posts").where(
                        "SubjectId", "==", f"/subjects/{subject_id}"
                    ).order_by("CreatedAt").limit(500)
                    
                    docs = list(posts_ref.stream())
                    logger.info(f"Query 1: Found {len(docs)} messages with SubjectId '/subjects/{subject_id}'")
                    
                    if not docs:
                        # Second try: without /subjects/ prefix
                        posts_ref = db.collection("Posts").where(
                            "SubjectId", "==", subject_id
                        ).order_by("CreatedAt").limit(500)
                        
                        docs = list(posts_ref.stream())
                        logger.info(f"Query 2: Found {len(docs)} messages with SubjectId '{subject_id}'")
                
                except Exception as query_error:
                    logger.error(f"Firestore query error: {str(query_error)}")
                    logger.error(f"Query error traceback: {traceback.format_exc()}")
                    
                    # Try a simple query without ordering (in case CreatedAt index is missing)
                    try:
                        posts_ref = db.collection("Posts").where(
                            "SubjectId", "==", f"/subjects/{subject_id}"
                        ).limit(500)
                        docs = list(posts_ref.stream())
                        logger.info(f"Fallback query: Found {len(docs)} messages without ordering")
                    except Exception as fallback_error:
                        logger.error(f"Fallback query also failed: {str(fallback_error)}")
                        docs = []

                for doc in docs:
                    try:
                        data = doc.to_dict()
                        
                        # Sanitize output data
                        clean_post = {
                            "id": doc.id,
                            "Content": sanitize_string_input(data.get("Content", ""), 2000),
                            "CreatedAt": str(data.get("CreatedAt", datetime.now())),
                            "PostedBy": sanitize_string_input(data.get("PostedBy", "Anonymous"), 50),
                            "SubjectId": data.get("SubjectId", ""),
                            "MessageType": data.get("MessageType", "text"),
                        }
                        
                        posts.append(clean_post)
                        
                    except Exception as doc_error:
                        logger.error(f"Error processing document {doc.id}: {str(doc_error)}")
                        continue
                
                logger.info(f"Successfully returning {len(posts)} messages")
                return send_json_response(self, posts)
                
            except Exception as firestore_error:
                logger.error(f"Firestore operation error: {str(firestore_error)}")
                logger.error(f"Firestore traceback: {traceback.format_exc()}")
                
                # Return empty array instead of error to prevent frontend breakage
                return send_json_response(self, [])

        except Exception as e:
            logger.error(f"Posts GET error: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return send_error_response(self, "Internal server error. Please try again later.", 500)

    def do_POST(self):
        """Create message with comprehensive error handling"""
        try:
            logger.info("POST request to posts API")
            
            # Read request body
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length == 0:
                    return send_error_response(self, "No data provided", 400)
                
                body = self.rfile.read(content_length)
                data = json.loads(body.decode('utf-8'))
                
                logger.info(f"Received POST data: {list(data.keys())}")
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}")
                return send_error_response(self, "Invalid JSON format", 400)
            except Exception as e:
                logger.error(f"Request parsing error: {str(e)}")
                return send_error_response(self, "Invalid request format", 400)
            
            # Require authentication
            current_user = require_authentication(self)
            if not current_user:
                logger.warning("Authentication required for POST")
                return send_error_response(self, "Authentication required", 401)
            
            logger.info(f"Authenticated user: {current_user.get('username')}")
            
            # Validate required fields
            required_fields = ['Content', 'SubjectId']
            missing_fields = [field for field in required_fields if field not in data or not data[field]]
            if missing_fields:
                return send_error_response(self, f"Missing required fields: {', '.join(missing_fields)}", 400)
            
            # Extract and validate fields
            content = str(data.get("Content", "")).strip()
            subject_id = str(data.get("SubjectId", "")).strip()
            posted_by = current_user.get("displayName", "Anonymous")
            message_type = data.get("MessageType", "text")
            
            logger.info(f"Creating message for subject: {subject_id}, user: {posted_by}")
            
            # Validate message content
            is_valid, error_msg = validate_message_content(content, message_type)
            if not is_valid:
                return send_error_response(self, error_msg, 400)
            
            # Sanitize inputs
            content = sanitize_string_input(content, 2000)
            subject_id = sanitize_string_input(subject_id, 50)
            posted_by = sanitize_string_input(posted_by, 50)
            message_type = sanitize_string_input(message_type, 20)
            
            if not db:
                # Demo mode - just return success
                logger.info("Demo mode - message creation simulated")
                return send_json_response(self, {
                    "message": "Message created successfully (demo mode)",
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.now().isoformat()
                }, 201)

            try:
                # Prepare document data
                doc_data = {
                    "Content": content,
                    "CreatedAt": firestore.SERVER_TIMESTAMP,
                    "PostedBy": posted_by,
                    "SubjectId": f"/subjects/{subject_id}",
                    "MessageType": message_type,
                }
                
                if FIREBASE_SECRET:
                    doc_data["secret"] = FIREBASE_SECRET

                # Add to Firestore with better error handling
                doc_ref, write_result = db.collection("Posts").add(doc_data)
                
                logger.info(f"Message created successfully: {doc_ref.id}")
                
                return send_json_response(self, {
                    "message": "Message created successfully",
                    "id": doc_ref.id,
                    "type": message_type
                }, 201)
                
            except Exception as firestore_error:
                logger.error(f"Firestore write error: {str(firestore_error)}")
                logger.error(f"Write traceback: {traceback.format_exc()}")
                return send_error_response(self, "Failed to save message", 500)

        except Exception as e:
            logger.error(f"Error creating post: {str(e)}")
            logger.error(f"POST traceback: {traceback.format_exc()}")
            return send_error_response(self, "Failed to create message", 500)

    def do_OPTIONS(self):
        """Handle OPTIONS with CORS"""
        self.send_response(204)
        send_cors_headers(self)
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()