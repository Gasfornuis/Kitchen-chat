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

if not firebase_admin._apps:
    # Load service account from environment variable
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
        firebase_admin.initialize_app(cred)
    else:
        logger.warning("Warning: Running in demo mode without Firebase")

db = firestore.client() if firebase_admin._apps else None
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
        """Get messages with security and rate limiting"""
        client_ip = get_client_ip(self.headers)
        
        # Rate limiting
        if not SecureAPIHandler.check_rate_limit_or_block(self, 'posts_get', max_requests=100, time_window=60):
            return
        
        try:
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
                return SecureAPIHandler.send_error_securely(self, "Missing SubjectId parameter", 400)
            
            # Validate subject ID format
            if not isinstance(subject_id, str) or len(subject_id) > 50:
                return SecureAPIHandler.send_error_securely(self, "Invalid SubjectId format", 400)

            if not db:
                # Demo mode - return empty messages
                return SecureAPIHandler.send_json_securely(self, [])

            # Query Firestore for messages
            posts_ref = db.collection("Posts").where(
                "SubjectId", "==", f"/subjects/{subject_id}"
            ).order_by("CreatedAt").limit(500)  # Limit voor performance
            
            docs = posts_ref.stream()

            posts = []
            for doc in docs:
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

            log_security_event(
                'posts_retrieved',
                f'Retrieved {len(posts)} messages for subject {subject_id}',
                client_ip,
                current_user
            )
            
            return SecureAPIHandler.send_json_securely(self, posts)

        except Exception as e:
            logger.error(f"Posts GET error: {str(e)}")
            return SecureAPIHandler.send_error_securely(self, "Failed to retrieve messages", 500, str(e))

    def do_POST(self):
        """Create message with comprehensive security"""
        client_ip = get_client_ip(self.headers)
        
        # Stricter rate limiting voor POST
        if not SecureAPIHandler.check_rate_limit_or_block(self, 'posts_create', max_requests=30, time_window=60):
            return
        
        try:
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

            # Add to Firestore - FIX: correct tuple unpacking
            doc_ref, write_result = db.collection("Posts").add(doc_data)
            
            log_security_event(
                'message_created',
                f'Message created in subject {subject_id} (ID: {doc_ref.id})',
                client_ip,
                current_user
            )
            
            return SecureAPIHandler.send_json_securely(self, {
                "message": "Message created successfully",
                "id": doc_ref.id,
                "type": message_type
            }, 201)

        except Exception as e:
            logger.error(f"Error creating post: {str(e)}")
            return SecureAPIHandler.send_error_securely(self, "Failed to create message", 500, str(e))

    def do_OPTIONS(self):
        """Handle OPTIONS with secure CORS"""
        SecureAPIHandler.handle_options_securely(self, 'GET, POST, OPTIONS')