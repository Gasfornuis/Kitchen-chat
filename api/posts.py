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

# Import security utilities
try:
    from .security_utils import (
        SecureAPIHandler, get_client_ip, log_security_event,
        validate_json_input, validate_user_input, sanitize_string_input
    )
except ImportError:
    # Fallback voor als security_utils nog niet bestaat
    from security_utils import (
        SecureAPIHandler, get_client_ip, log_security_event,
        validate_json_input, validate_user_input, sanitize_string_input
    )

# Import authentication functions from auth.py
try:
    from .auth import require_authentication
except ImportError:
    from auth import require_authentication

# Configure logging
logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')
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

def validate_message_content(content, message_type='text'):
    """Validate message content for security and policy compliance"""
    if not content or not isinstance(content, str):
        return False, "Message content is required"
    
    content = content.strip()
    
    if len(content) == 0:
        return False, "Message cannot be empty"
    
    if len(content) > 2000:
        return False, "Message too long (max 2000 characters)"
    
    # Check for spam patterns
    spam_patterns = [
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',  # URLs
        r'(.)\1{10,}',  # Repeated characters
        r'[A-Z]{10,}',  # All caps spam
    ]
    
    for pattern in spam_patterns:
        if re.search(pattern, content):
            return False, "Message contains spam-like content"
    
    return True, None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Get messages with enhanced error handling"""
        client_ip = get_client_ip(self.headers)
        
        try:
            # Rate limiting
            if not SecureAPIHandler.check_rate_limit_or_block(self, 'posts_get', max_requests=100, time_window=60):
                return
            
            # Require authentication for reading posts
            current_user = require_authentication(self)
            if not current_user:
                return SecureAPIHandler.send_error_securely(self, "Authentication required", 401)
            
            parsed_url = urlparse(self.path)
            query = parse_qs(parsed_url.query)
            
            # Fix SubjectId parsing from query
            subject_vals = query.get("SubjectId", [])
            subject_id = subject_vals[0] if subject_vals else None

            if not subject_id:
                logger.warning("Missing SubjectId parameter")
                return SecureAPIHandler.send_error_securely(self, "Missing SubjectId parameter", 400)
            
            logger.info(f"Fetching messages for SubjectId: {subject_id}")
            
            # Validate subject ID format
            if not isinstance(subject_id, str) or len(subject_id) > 50:
                logger.warning(f"Invalid SubjectId format: {subject_id}")
                return SecureAPIHandler.send_error_securely(self, "Invalid SubjectId format", 400)

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
                return SecureAPIHandler.send_json_securely(self, sample_messages)

            try:
                # Try multiple query variations to handle different SubjectId formats
                posts = []
                
                # First try: exact match with current format
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
                    
                    if not docs:
                        # Third try: check if there are any posts at all
                        all_posts_ref = db.collection("Posts").limit(10)
                        all_docs = list(all_posts_ref.stream())
                        logger.info(f"Total posts in collection: {len(all_docs)}")
                        
                        if all_docs:
                            logger.info(f"Sample SubjectId from existing post: {all_docs[0].to_dict().get('SubjectId', 'N/A')}")
                
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
                            "MediaData": data.get("MediaData", None),
                            "AttachmentUrl": data.get("AttachmentUrl", None),
                            "AttachmentType": data.get("AttachmentType", None)
                        }
                        
                        # Remove sensitive data
                        if 'secret' in data:
                            del clean_post['secret']
                        
                        posts.append(clean_post)
                        
                    except Exception as doc_error:
                        logger.error(f"Error processing document {doc.id}: {str(doc_error)}")
                        continue

                log_security_event(
                    'posts_retrieved',
                    f'Retrieved {len(posts)} messages for subject {subject_id}',
                    client_ip,
                    current_user
                )
                
                logger.info(f"Successfully returning {len(posts)} messages")
                return SecureAPIHandler.send_json_securely(self, posts)
                
            except Exception as firestore_error:
                logger.error(f"Firestore operation error: {str(firestore_error)}")
                logger.error(f"Firestore traceback: {traceback.format_exc()}")
                
                # Return empty array instead of error to prevent frontend breakage
                return SecureAPIHandler.send_json_securely(self, [])

        except Exception as e:
            logger.error(f"Posts GET error: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return SecureAPIHandler.send_error_securely(self, "Internal server error. Please try again later.", 500)

    def do_POST(self):
        """Create message with comprehensive security"""
        client_ip = get_client_ip(self.headers)
        
        try:
            # Stricter rate limiting voor POST
            if not SecureAPIHandler.check_rate_limit_or_block(self, 'posts_create', max_requests=30, time_window=60):
                return
            
            # Require authentication
            current_user = require_authentication(self)
            if not current_user:
                return SecureAPIHandler.send_error_securely(self, "Authentication required", 401)
            
            # Validate and parse JSON input
            data = validate_json_input(self, required_fields=['Content', 'SubjectId'], max_content_length=5000)
            if data is None:
                return  # Error already sent
            
            # Extract and validate fields with case-insensitive fallbacks
            content = (data.get("Content") or data.get("content") or "").strip()
            subject_id = (data.get("SubjectId") or data.get("subjectId") or "").strip()
            posted_by = (data.get("PostedBy") or current_user["displayName"]).strip()
            message_type = data.get("MessageType", "text").strip()
            media_data = data.get("MediaData", None)
            
            logger.info(f"Creating message for subject: {subject_id}")
            
            # SECURITY CHECK - user can only post as themselves
            current_display = current_user.get("displayName", "").lower()
            current_username = current_user.get("username", "").lower()
            
            if (posted_by.lower() != current_display and 
                posted_by.lower() != current_username):
                log_security_event(
                    'impersonation_attempt',
                    f'User {current_username} tried to post as {posted_by}',
                    client_ip,
                    current_user,
                    'WARNING'
                )
                return SecureAPIHandler.send_error_securely(self, "You can only post messages as yourself", 403)
            
            # Validate message content
            is_valid, error_msg = validate_message_content(content, message_type)
            if not is_valid:
                return SecureAPIHandler.send_error_securely(self, error_msg, 400)
            
            # Sanitize inputs
            content = sanitize_string_input(content, 2000)
            subject_id = sanitize_string_input(subject_id, 50)
            posted_by = sanitize_string_input(posted_by, 50)
            message_type = sanitize_string_input(message_type, 20)
            
            if not db:
                # Demo mode - just return success
                logger.info("Demo mode - message creation simulated")
                log_security_event(
                    'message_created',
                    f'Demo message created in subject {subject_id}',
                    client_ip,
                    current_user
                )
                
                return SecureAPIHandler.send_json_securely(self, {
                    "message": "Message created successfully (demo mode)",
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.now().isoformat()
                }, 201)

            try:
                # Prepare secure document data
                doc_data = {
                    "Content": content,
                    "CreatedAt": firestore.SERVER_TIMESTAMP,
                    "PostedBy": posted_by,
                    "SubjectId": f"/subjects/{subject_id}",
                    "MessageType": message_type,
                    "ClientIP": client_ip,  # For abuse tracking
                    "secret": FIREBASE_SECRET
                }

                # Handle media data securely
                if media_data and isinstance(media_data, dict):
                    if message_type == "voice":
                        # Validate voice data
                        duration = sanitize_string_input(str(media_data.get("duration", "0:05")), 10)
                        size = sanitize_string_input(str(media_data.get("size", "0 KB")), 20)
                        
                        doc_data["MediaData"] = {
                            "duration": duration,
                            "size": size,
                            "waveform": media_data.get("waveform", [])[:100]  # Limit array size
                        }
                        doc_data["AttachmentType"] = "audio/webm"
                        
                    elif message_type == "image":
                        # Validate image data
                        name = sanitize_string_input(str(media_data.get("name", "image.jpg")), 100)
                        size = sanitize_string_input(str(media_data.get("size", "0 KB")), 20)
                        
                        doc_data["MediaData"] = {
                            "name": name,
                            "size": size
                        }
                        
                        # Validate base64 image data
                        if "src" in media_data and media_data["src"].startswith("data:image/"):
                            # In productie: upload naar secure storage in plaats van base64
                            src = str(media_data["src"])[:50000]  # Limit base64 size
                            doc_data["AttachmentUrl"] = src
                        
                        doc_data["AttachmentType"] = "image/*"

                # Add to Firestore with better error handling
                doc_ref, write_result = db.collection("Posts").add(doc_data)
                
                log_security_event(
                    'message_created',
                    f'Message created in subject {subject_id} (ID: {doc_ref.id})',
                    client_ip,
                    current_user
                )
                
                logger.info(f"Message created successfully: {doc_ref.id}")
                
                return SecureAPIHandler.send_json_securely(self, {
                    "message": "Message created successfully",
                    "id": doc_ref.id,
                    "type": message_type
                }, 201)
                
            except Exception as firestore_error:
                logger.error(f"Firestore write error: {str(firestore_error)}")
                logger.error(f"Write traceback: {traceback.format_exc()}")
                return SecureAPIHandler.send_error_securely(self, "Failed to save message", 500)

        except Exception as e:
            logger.error(f"Error creating post: {str(e)}")
            logger.error(f"POST traceback: {traceback.format_exc()}")
            return SecureAPIHandler.send_error_securely(self, "Failed to create message", 500)

    def do_OPTIONS(self):
        """Handle OPTIONS with secure CORS"""
        SecureAPIHandler.handle_options_securely(self, 'GET, POST, OPTIONS')