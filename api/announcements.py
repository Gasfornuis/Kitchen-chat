from http.server import BaseHTTPRequestHandler
import json
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore
import os
import hashlib
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase (similar to other files)
try:
    if not firebase_admin._apps:
        # In Vercel, Firebase config is in environment variables
        firebase_config = {
            "type": "service_account",
            "project_id": os.getenv('FIREBASE_PROJECT_ID'),
            "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
            "private_key": os.getenv('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n'),
            "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
            "client_id": os.getenv('FIREBASE_CLIENT_ID'),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.getenv('FIREBASE_CLIENT_EMAIL')}"
        }
        
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
        
    db = firestore.client()
    logger.info("Firebase initialized successfully")
except Exception as e:
    logger.error(f"Firebase initialization error: {e}")
    db = None

def get_session_user(headers):
    """Extract user from session cookie"""
    try:
        cookie_header = headers.get('cookie', '')
        if 'session=' in cookie_header:
            session_id = None
            for cookie in cookie_header.split(';'):
                cookie = cookie.strip()
                if cookie.startswith('session='):
                    session_id = cookie.split('=')[1]
                    break
            
            if session_id:
                # Check session in database
                sessions_ref = db.collection('sessions')
                session_doc = sessions_ref.document(session_id).get()
                
                if session_doc.exists:
                    session_data = session_doc.to_dict()
                    if session_data.get('valid', False):
                        return session_data.get('user')
        
        return None
    except Exception as e:
        logger.error(f"Session validation error: {e}")
        return None

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
            if not db:
                return self.send_error_response("Database connection failed", 503)
            
            # Get user from session
            current_user = get_session_user(dict(self.headers))
            
            if not current_user:
                return self.send_error_response("Authentication required", 401)
            
            # Get announcements from database
            announcements_ref = db.collection('announcements').order_by('createdAt', direction=firestore.Query.DESCENDING)
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
            if not db:
                return self.send_error_response("Database connection failed", 503)
            
            # Get user from session
            current_user = get_session_user(dict(self.headers))
            
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
            if not db:
                return self.send_error_response("Database connection failed", 503)
            
            # Get user from session
            current_user = get_session_user(dict(self.headers))
            
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
            if not db:
                return self.send_error_response("Database connection failed", 503)
            
            # Get user from session
            current_user = get_session_user(dict(self.headers))
            
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