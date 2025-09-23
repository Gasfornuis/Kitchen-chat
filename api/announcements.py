from http.server import BaseHTTPRequestHandler
import json
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore as fb_firestore
import os
import hashlib
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase (consistent with other files)
if not firebase_admin._apps:
    # Load service account from environment variable
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized successfully")
    else:
        logger.warning("Warning: Running in demo mode without Firebase")

db = fb_firestore.client() if firebase_admin._apps else None
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")

# Demo mode storage
demo_announcements = []

def sha256_hash(text):
    """SHA-256 hash utility"""
    return hashlib.sha256(text.encode()).hexdigest()

def get_session_token_from_request(request):
    """Extract session token from request headers or cookies"""
    # Try Authorization header first
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    
    # Try cookie (for web browsers)
    cookie_header = request.headers.get('Cookie', '')
    if cookie_header:
        cookies = {}
        for cookie in cookie_header.split(';'):
            if '=' in cookie:
                key, value = cookie.strip().split('=', 1)
                cookies[key] = value
        
        return cookies.get('kc_session')
    
    return None

def hash_session_token(token):
    """Hash session token for secure storage"""
    return sha256_hash(token)

def verify_session_token(token):
    """Verify session token and return user info"""
    if not token:
        return None
    
    token_hash = hash_session_token(token)
    
    if not db:
        # Demo mode - return demo user for testing
        return {
            "username": "demo",
            "displayName": "Demo User"
        }
    
    # Firestore mode
    try:
        doc = db.collection("Sessions").document(token_hash).get()
        
        if not doc.exists:
            return None
            
        session_data = doc.to_dict()
        expires_at = session_data.get('expiresAt')
        
        if expires_at and expires_at.timestamp() < datetime.now().timestamp():
            # Lazy cleanup - delete expired session
            doc.reference.delete()
            return None
            
        return {
            "username": session_data.get('username'),
            "displayName": session_data.get('displayName')
        }
        
    except Exception as e:
        logger.error(f"Session verification error: {e}")
        return None

def require_authentication(request):
    """Require valid authentication, return user info or None"""
    token = get_session_token_from_request(request)
    return verify_session_token(token)

def check_admin_permissions(user):
    """Check if user has admin permissions (only Daan25)"""
    if not user:
        return False
    
    # Check if user is Daan25 (case insensitive)
    username = user.get('username', '').lower()
    display_name = user.get('displayName', '').lower()
    
    return username == 'daan25' or display_name == 'daan25'

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
    
    def send_json_response(self, data, status=200):
        """Send JSON response with CORS headers"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_error_response(self, error, status=500):
        """Send error response"""
        logger.error(f"API Error: {error}")
        self.send_json_response({'error': str(error)}, status)
    
    def do_GET(self):
        """Get announcements"""
        try:
            # Get user from session
            current_user = require_authentication(self)
            
            if not current_user:
                return self.send_error_response("Authentication required", 401)
            
            if not db:
                # Demo mode
                logger.info(f"Retrieved {len(demo_announcements)} announcements (demo mode)")
                return self.send_json_response(demo_announcements)
            
            # Get announcements from database
            announcements_ref = db.collection('announcements').order_by('createdAt', direction=fb_firestore.Query.DESCENDING)
            announcements = announcements_ref.get()
            
            result = []
            for announcement in announcements:
                data = announcement.to_dict()
                data['id'] = announcement.id
                
                # Convert timestamp for JSON serialization
                if 'createdAt' in data and data['createdAt']:
                    data['createdAt'] = data['createdAt'].isoformat()
                
                result.append(data)
            
            logger.info(f"Retrieved {len(result)} announcements")
            return self.send_json_response(result)
        
        except Exception as e:
            return self.send_error_response(f"Failed to retrieve announcements: {str(e)}")
    
    def do_POST(self):
        """Create new announcement (admin only)"""
        try:
            # Get user from session
            current_user = require_authentication(self)
            
            if not current_user:
                return self.send_error_response("Authentication required", 401)
            
            # Check if user has admin permissions
            if not check_admin_permissions(current_user):
                return self.send_error_response("Only Daan25 can create announcements", 403)
            
            # Parse request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(post_data)
            else:
                return self.send_error_response("No data provided", 400)
            
            # Validate required fields
            title = data.get('title', '').strip()
            content = data.get('content', '').strip()
            
            if not title or not content:
                return self.send_error_response("Title and content are required", 400)
            
            if len(title) > 200:
                return self.send_error_response("Title too long (max 200 characters)", 400)
            
            if len(content) > 2000:
                return self.send_error_response("Content too long (max 2000 characters)", 400)
            
            # Create announcement document
            announcement_data = {
                'title': title,
                'content': content,
                'author': current_user.get('displayName', current_user.get('username', 'Unknown')),
                'authorUsername': current_user.get('username', ''),
                'createdAt': datetime.now(timezone.utc),
                'type': 'announcement',
                'priority': data.get('priority', 'normal'),  # normal, high, urgent
                'active': True
            }
            
            if not db:
                # Demo mode
                announcement_data['id'] = str(len(demo_announcements) + 1)
                announcement_data['createdAt'] = announcement_data['createdAt'].isoformat()
                demo_announcements.append(announcement_data)
                
                logger.info(f"Announcement created in demo mode by {current_user.get('username')}")
                
                return self.send_json_response({
                    'success': True,
                    'message': 'Announcement created successfully (demo mode)',
                    'announcement': announcement_data
                })
            
            # Add to database
            doc_ref = db.collection('announcements').add(announcement_data)
            announcement_id = doc_ref[1].id
            
            logger.info(f"Announcement created with ID: {announcement_id} by {current_user.get('username')}")
            
            # Return created announcement
            announcement_data['id'] = announcement_id
            announcement_data['createdAt'] = announcement_data['createdAt'].isoformat()
            
            return self.send_json_response({
                'success': True,
                'message': 'Announcement created successfully',
                'announcement': announcement_data
            })
        
        except json.JSONDecodeError:
            return self.send_error_response("Invalid JSON data", 400)
        except Exception as e:
            return self.send_error_response(f"Failed to create announcement: {str(e)}")
    
    def do_PUT(self):
        """Update announcement (admin only)"""
        try:
            # Get user from session
            current_user = require_authentication(self)
            
            if not current_user:
                return self.send_error_response("Authentication required", 401)
            
            # Check if user has admin permissions
            if not check_admin_permissions(current_user):
                return self.send_error_response("Only Daan25 can update announcements", 403)
            
            # Parse request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(post_data)
            else:
                return self.send_error_response("No data provided", 400)
            
            # Get announcement ID
            announcement_id = data.get('id')
            if not announcement_id:
                return self.send_error_response("Announcement ID is required", 400)
            
            if not db:
                # Demo mode
                return self.send_json_response({
                    'success': True,
                    'message': 'Update functionality not available in demo mode'
                })
            
            # Check if announcement exists
            doc_ref = db.collection('announcements').document(announcement_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return self.send_error_response("Announcement not found", 404)
            
            # Prepare update data
            update_data = {}
            
            if 'title' in data:
                title = data['title'].strip()
                if not title:
                    return self.send_error_response("Title cannot be empty", 400)
                if len(title) > 200:
                    return self.send_error_response("Title too long (max 200 characters)", 400)
                update_data['title'] = title
            
            if 'content' in data:
                content = data['content'].strip()
                if not content:
                    return self.send_error_response("Content cannot be empty", 400)
                if len(content) > 2000:
                    return self.send_error_response("Content too long (max 2000 characters)", 400)
                update_data['content'] = content
            
            if 'priority' in data:
                priority = data['priority']
                if priority not in ['normal', 'high', 'urgent']:
                    return self.send_error_response("Invalid priority level", 400)
                update_data['priority'] = priority
            
            if 'active' in data:
                update_data['active'] = bool(data['active'])
            
            if not update_data:
                return self.send_error_response("No valid fields to update", 400)
            
            # Add update timestamp
            update_data['updatedAt'] = datetime.now(timezone.utc)
            update_data['updatedBy'] = current_user.get('displayName', current_user.get('username', 'Unknown'))
            
            # Update in database
            doc_ref.update(update_data)
            
            logger.info(f"Announcement {announcement_id} updated by {current_user.get('username')}")
            
            return self.send_json_response({
                'success': True,
                'message': 'Announcement updated successfully',
                'updatedFields': list(update_data.keys())
            })
        
        except json.JSONDecodeError:
            return self.send_error_response("Invalid JSON data", 400)
        except Exception as e:
            return self.send_error_response(f"Failed to update announcement: {str(e)}")
    
    def do_DELETE(self):
        """Delete announcement (admin only)"""
        try:
            # Get user from session
            current_user = require_authentication(self)
            
            if not current_user:
                return self.send_error_response("Authentication required", 401)
            
            # Check if user has admin permissions
            if not check_admin_permissions(current_user):
                return self.send_error_response("Only Daan25 can delete announcements", 403)
            
            # Parse request body or query parameters
            announcement_id = None
            
            # Try to get ID from URL path
            if '?' in self.path:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(self.path)
                query_params = parse_qs(parsed.query)
                if 'id' in query_params:
                    announcement_id = query_params['id'][0]
            
            # Try to get ID from body if not in URL
            if not announcement_id:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    post_data = self.rfile.read(content_length).decode('utf-8')
                    data = json.loads(post_data)
                    announcement_id = data.get('id')
            
            if not announcement_id:
                return self.send_error_response("Announcement ID is required", 400)
            
            if not db:
                # Demo mode
                return self.send_json_response({
                    'success': True,
                    'message': 'Delete functionality not available in demo mode'
                })
            
            # Check if announcement exists
            doc_ref = db.collection('announcements').document(announcement_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return self.send_error_response("Announcement not found", 404)
            
            # Delete from database
            doc_ref.delete()
            
            logger.info(f"Announcement {announcement_id} deleted by {current_user.get('username')}")
            
            return self.send_json_response({
                'success': True,
                'message': 'Announcement deleted successfully'
            })
        
        except json.JSONDecodeError:
            return self.send_error_response("Invalid JSON data", 400)
        except Exception as e:
            return self.send_error_response(f"Failed to delete announcement: {str(e)}")