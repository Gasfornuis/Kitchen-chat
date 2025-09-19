from http.server import BaseHTTPRequestHandler
import json
import os
from google.cloud import firestore
from urllib.parse import urlparse, parse_qs
import firebase_admin
from firebase_admin import credentials, firestore, auth
import base64
import uuid
from datetime import datetime

if not firebase_admin._apps:
    # Load service account from environment variable
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    cred = credentials.Certificate(json.loads(sa_json))
    firebase_admin.initialize_app(cred)

db = firestore.client()
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def verify_token(self):
        """Verify Firebase ID token from Authorization header"""
        auth_header = self.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split('Bearer ')[1]
        try:
            decoded_token = auth.verify_id_token(token)
            return decoded_token
        except Exception as e:
            print(f"Token verification failed: {e}")
            return None

    def send_error_response(self, code, message):
        """Send standardized error response"""
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

    def send_success_response(self, data, code=200):
        """Send standardized success response"""
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        """Get user profile"""
        try:
            # Verify authentication
            decoded_token = self.verify_token()
            if not decoded_token:
                self.send_error_response(401, "Unauthorized")
                return

            user_id = decoded_token['uid']
            
            # Get user profile from Firestore
            user_ref = db.collection("UserProfiles").document(user_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                # Create default profile if it doesn't exist
                default_profile = {
                    "uid": user_id,
                    "displayName": decoded_token.get('name', 'Anonymous'),
                    "email": decoded_token.get('email', ''),
                    "photoURL": decoded_token.get('picture', ''),
                    "bio": "",
                    "status": "online",
                    "joinedAt": datetime.utcnow().isoformat(),
                    "lastSeen": datetime.utcnow().isoformat(),
                    "preferences": {
                        "theme": "dark",
                        "notifications": True,
                        "soundEnabled": True
                    }
                }
                
                user_ref.set(default_profile)
                self.send_success_response(default_profile)
                return
            
            profile_data = user_doc.to_dict()
            self.send_success_response(profile_data)
            
        except Exception as e:
            print(f"GET profile error: {e}")
            self.send_error_response(500, str(e))

    def do_POST(self):
        """Create user profile"""
        try:
            # Verify authentication
            decoded_token = self.verify_token()
            if not decoded_token:
                self.send_error_response(401, "Unauthorized")
                return

            user_id = decoded_token['uid']
            
            # Parse request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            profile_data = json.loads(body)
            
            # Validate required fields
            required_fields = ['displayName', 'email']
            for field in required_fields:
                if field not in profile_data:
                    self.send_error_response(400, f"Missing required field: {field}")
                    return
            
            # Create profile document
            profile = {
                "uid": user_id,
                "displayName": profile_data['displayName'],
                "email": profile_data['email'],
                "photoURL": profile_data.get('photoURL', ''),
                "bio": profile_data.get('bio', ''),
                "status": profile_data.get('status', 'online'),
                "joinedAt": datetime.utcnow().isoformat(),
                "lastSeen": datetime.utcnow().isoformat(),
                "preferences": {
                    "theme": profile_data.get('theme', 'dark'),
                    "notifications": profile_data.get('notifications', True),
                    "soundEnabled": profile_data.get('soundEnabled', True)
                }
            }
            
            # Save to Firestore
            user_ref = db.collection("UserProfiles").document(user_id)
            user_ref.set(profile)
            
            self.send_success_response(profile, 201)
            
        except json.JSONDecodeError:
            self.send_error_response(400, "Invalid JSON data")
        except Exception as e:
            print(f"POST profile error: {e}")
            self.send_error_response(500, str(e))

    def do_PUT(self):
        """Update user profile"""
        try:
            # Verify authentication
            decoded_token = self.verify_token()
            if not decoded_token:
                self.send_error_response(401, "Unauthorized")
                return

            user_id = decoded_token['uid']
            
            # Parse request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            updates = json.loads(body)
            
            # Get current profile
            user_ref = db.collection("UserProfiles").document(user_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                self.send_error_response(404, "Profile not found")
                return
            
            current_profile = user_doc.to_dict()
            
            # Update allowed fields
            allowed_fields = [
                'displayName', 'bio', 'photoURL', 'status', 
                'theme', 'notifications', 'soundEnabled'
            ]
            
            update_data = {}
            for field in allowed_fields:
                if field in updates:
                    if field in ['theme', 'notifications', 'soundEnabled']:
                        # Update preferences
                        if 'preferences' not in update_data:
                            update_data['preferences'] = current_profile.get('preferences', {})
                        update_data['preferences'][field] = updates[field]
                    else:
                        update_data[field] = updates[field]
            
            # Always update lastSeen
            update_data['lastSeen'] = datetime.utcnow().isoformat()
            
            # Update document
            user_ref.update(update_data)
            
            # Get updated profile
            updated_doc = user_ref.get()
            updated_profile = updated_doc.to_dict()
            
            self.send_success_response(updated_profile)
            
        except json.JSONDecodeError:
            self.send_error_response(400, "Invalid JSON data")
        except Exception as e:
            print(f"PUT profile error: {e}")
            self.send_error_response(500, str(e))

    def do_DELETE(self):
        """Delete user profile"""
        try:
            # Verify authentication
            decoded_token = self.verify_token()
            if not decoded_token:
                self.send_error_response(401, "Unauthorized")
                return

            user_id = decoded_token['uid']
            
            # Delete profile document
            user_ref = db.collection("UserProfiles").document(user_id)
            user_ref.delete()
            
            # Also delete user's posts (optional - you might want to keep them)
            posts_query = db.collection("Posts").where("PostedBy", "==", user_id)
            posts = posts_query.stream()
            
            batch = db.batch()
            for post in posts:
                batch.delete(post.reference)
            batch.commit()
            
            self.send_success_response({"message": "Profile deleted successfully"})
            
        except Exception as e:
            print(f"DELETE profile error: {e}")
            self.send_error_response(500, str(e))