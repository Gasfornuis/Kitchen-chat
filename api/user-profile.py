from http.server import BaseHTTPRequestHandler
import json
import os
from google.cloud import firestore
from urllib.parse import urlparse, parse_qs
import firebase_admin
from firebase_admin import credentials, firestore
import base64
import uuid
from datetime import datetime

# Import authentication functions from auth.py
from .auth import require_authentication, hash_password, verify_password

if not firebase_admin._apps:
    # Load service account from environment variable
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
        firebase_admin.initialize_app(cred)
    else:
        print("Warning: Running in demo mode without Firebase")

db = firestore.client() if firebase_admin._apps else None
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")

# Demo mode storage
demo_profiles = {}

def send_auth_error(handler):
    """Send authentication error response"""
    handler.send_response(401)
    handler.send_header("Content-type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Credentials", "true")
    handler.end_headers()
    handler.wfile.write(json.dumps({"error": "Authentication required"}).encode())

def send_error_response(handler, code, message):
    """Send standardized error response"""
    handler.send_response(code)
    handler.send_header("Content-type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Credentials", "true")
    handler.end_headers()
    handler.wfile.write(json.dumps({"error": message}).encode())

def send_success_response(handler, data, code=200):
    """Send standardized success response"""
    handler.send_response(code)
    handler.send_header("Content-type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Credentials", "true")
    handler.end_headers()
    handler.wfile.write(json.dumps(data).encode())

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Cookie")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        """Get user profile or list all online users"""
        try:
            # Require authentication
            current_user = require_authentication(self)
            if not current_user:
                return send_auth_error(self)
            
            parsed_url = urlparse(self.path)
            query = parse_qs(parsed_url.query)
            
            # Check if requesting online users list
            if query.get('action', [None])[0] == 'online_users':
                return self.get_online_users()
            
            # Check if requesting specific user profile
            target_username = query.get('username', [None])[0]
            if target_username:
                return self.get_user_profile(target_username, current_user)
            
            # Default: get current user's profile
            return self.get_user_profile(current_user['username'], current_user)
            
        except Exception as e:
            print(f"GET profile error: {e}")
            send_error_response(self, 500, str(e))
    
    def get_online_users(self):
        """Get list of online users"""
        try:
            if not db:
                # Demo mode
                online_users = []
                for username, profile in demo_profiles.items():
                    if profile.get('status') == 'online':
                        online_users.append({
                            'username': username,
                            'displayName': profile.get('displayName', username),
                            'status': profile.get('status', 'offline'),
                            'lastSeen': profile.get('lastSeen', ''),
                            'bio': profile.get('bio', ''),
                            'photoURL': profile.get('photoURL', '')
                        })
                
                send_success_response(self, {'users': online_users})
                return
            
            # Get all users with recent activity (last 5 minutes)
            cutoff_time = datetime.now() - datetime.timedelta(minutes=5)
            
            users_ref = db.collection("UserProfiles")
            docs = users_ref.stream()
            
            online_users = []
            for doc in docs:
                data = doc.to_dict()
                last_seen = data.get('lastSeen')
                
                # Check if user is considered online
                is_online = False
                if last_seen:
                    try:
                        last_seen_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                        is_online = last_seen_dt > cutoff_time or data.get('status') == 'online'
                    except:
                        is_online = data.get('status') == 'online'
                
                if is_online:
                    online_users.append({
                        'username': data.get('username', doc.id),
                        'displayName': data.get('displayName', 'User'),
                        'status': data.get('status', 'online'),
                        'lastSeen': data.get('lastSeen', ''),
                        'bio': data.get('bio', ''),
                        'photoURL': data.get('photoURL', '')
                    })
            
            # Sort by last seen (most recent first)
            online_users.sort(key=lambda x: x.get('lastSeen', ''), reverse=True)
            
            send_success_response(self, {'users': online_users})
            
        except Exception as e:
            print(f"Get online users error: {e}")
            send_error_response(self, 500, str(e))
    
    def get_user_profile(self, username, current_user):
        """Get specific user profile"""
        try:
            if not db:
                # Demo mode
                profile = demo_profiles.get(username.lower())
                if not profile:
                    profile = {
                        'username': username,
                        'displayName': username,
                        'bio': 'Demo user',
                        'status': 'online',
                        'joinedAt': datetime.now().isoformat(),
                        'lastSeen': datetime.now().isoformat(),
                        'photoURL': '',
                        'preferences': {
                            'theme': 'light',
                            'notifications': True,
                            'soundEnabled': True
                        }
                    }
                    
                send_success_response(self, profile)
                return
            
            # Get user profile from Firestore
            user_ref = db.collection("UserProfiles").document(username.lower())
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                # Try to get from Users collection and create profile
                users_ref = db.collection("Users").document(username.lower())
                users_doc = users_ref.get()
                
                if users_doc.exists:
                    user_data = users_doc.to_dict()
                    # Create default profile
                    default_profile = {
                        'username': username.lower(),
                        'displayName': user_data.get('displayName', username),
                        'email': user_data.get('email', ''),
                        'bio': '',
                        'status': 'online',
                        'joinedAt': str(user_data.get('createdAt', datetime.now())),
                        'lastSeen': str(user_data.get('lastLogin', datetime.now())),
                        'photoURL': '',
                        'preferences': {
                            'theme': 'light',
                            'notifications': True,
                            'soundEnabled': True
                        },
                        'secret': FIREBASE_SECRET
                    }
                    
                    user_ref.set(default_profile)
                    send_success_response(self, default_profile)
                    return
                else:
                    send_error_response(self, 404, "User not found")
                    return
            
            profile_data = user_doc.to_dict()
            
            # Hide sensitive information if not own profile
            if username.lower() != current_user['username'].lower():
                profile_data.pop('email', None)
                profile_data.pop('preferences', None)
                profile_data.pop('secret', None)
            
            send_success_response(self, profile_data)
            
        except Exception as e:
            print(f"Get user profile error: {e}")
            send_error_response(self, 500, str(e))

    def do_PUT(self):
        """Update user profile"""
        try:
            # Require authentication
            current_user = require_authentication(self)
            if not current_user:
                return send_auth_error(self)
            
            # Parse request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            updates = json.loads(body)
            
            username = current_user['username']
            
            if not db:
                # Demo mode
                if username not in demo_profiles:
                    demo_profiles[username] = {
                        'username': username,
                        'displayName': current_user['displayName'],
                        'joinedAt': datetime.now().isoformat()
                    }
                
                # Update allowed fields
                allowed_fields = ['displayName', 'bio', 'status', 'photoURL']
                for field in allowed_fields:
                    if field in updates:
                        demo_profiles[username][field] = updates[field]
                
                # Update preferences
                if 'preferences' not in demo_profiles[username]:
                    demo_profiles[username]['preferences'] = {}
                
                pref_fields = ['theme', 'notifications', 'soundEnabled']
                for field in pref_fields:
                    if field in updates:
                        demo_profiles[username]['preferences'][field] = updates[field]
                
                demo_profiles[username]['lastSeen'] = datetime.now().isoformat()
                
                send_success_response(self, demo_profiles[username])
                return
            
            # Get current profile
            user_ref = db.collection("UserProfiles").document(username)
            user_doc = user_ref.get()
            
            if user_doc.exists:
                current_profile = user_doc.to_dict()
            else:
                # Create new profile
                current_profile = {
                    'username': username,
                    'displayName': current_user['displayName'],
                    'email': '',
                    'bio': '',
                    'status': 'online',
                    'joinedAt': datetime.now().isoformat(),
                    'photoURL': '',
                    'preferences': {
                        'theme': 'light',
                        'notifications': True,
                        'soundEnabled': True
                    }
                }
            
            # Update allowed fields
            allowed_fields = ['displayName', 'bio', 'status', 'photoURL']
            update_data = {}
            
            for field in allowed_fields:
                if field in updates:
                    update_data[field] = updates[field]
            
            # Update preferences
            pref_fields = ['theme', 'notifications', 'soundEnabled']
            preferences_updated = False
            for field in pref_fields:
                if field in updates:
                    if 'preferences' not in update_data:
                        update_data['preferences'] = current_profile.get('preferences', {})
                    update_data['preferences'][field] = updates[field]
                    preferences_updated = True
            
            # Handle password change
            if 'newPassword' in updates and 'currentPassword' in updates:
                # Get current user data for password verification
                users_ref = db.collection("Users").document(username)
                users_doc = users_ref.get()
                
                if users_doc.exists:
                    user_data = users_doc.to_dict()
                    
                    # Verify current password
                    if verify_password(updates['currentPassword'], user_data['passwordHash']):
                        # Update password in Users collection
                        new_password_hash = hash_password(updates['newPassword'])
                        users_ref.update({'passwordHash': new_password_hash})
                        update_data['passwordChanged'] = datetime.now().isoformat()
                    else:
                        send_error_response(self, 400, "Current password is incorrect")
                        return
            
            # Always update lastSeen
            update_data['lastSeen'] = datetime.now().isoformat()
            update_data['secret'] = FIREBASE_SECRET
            
            # Merge with current profile
            updated_profile = {**current_profile, **update_data}
            
            # Save to database
            user_ref.set(updated_profile, merge=True)
            
            # Remove sensitive data from response
            response_profile = updated_profile.copy()
            response_profile.pop('secret', None)
            
            send_success_response(self, response_profile)
            
        except json.JSONDecodeError:
            send_error_response(self, 400, "Invalid JSON data")
        except Exception as e:
            print(f"PUT profile error: {e}")
            send_error_response(self, 500, str(e))

    def do_POST(self):
        """Update user status (online/away/busy/offline)"""
        try:
            # Require authentication
            current_user = require_authentication(self)
            if not current_user:
                return send_auth_error(self)
            
            # Parse request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            status = data.get('status', 'online')
            valid_statuses = ['online', 'away', 'busy', 'offline']
            
            if status not in valid_statuses:
                send_error_response(self, 400, f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
                return
            
            username = current_user['username']
            
            if not db:
                # Demo mode
                if username not in demo_profiles:
                    demo_profiles[username] = {
                        'username': username,
                        'displayName': current_user['displayName']
                    }
                
                demo_profiles[username]['status'] = status
                demo_profiles[username]['lastSeen'] = datetime.now().isoformat()
                
                send_success_response(self, {
                    'status': status,
                    'lastSeen': demo_profiles[username]['lastSeen']
                })
                return
            
            # Update status in Firestore
            user_ref = db.collection("UserProfiles").document(username)
            user_ref.set({
                'username': username,
                'displayName': current_user['displayName'],
                'status': status,
                'lastSeen': datetime.now().isoformat(),
                'secret': FIREBASE_SECRET
            }, merge=True)
            
            send_success_response(self, {
                'status': status,
                'lastSeen': datetime.now().isoformat()
            })
            
        except json.JSONDecodeError:
            send_error_response(self, 400, "Invalid JSON data")
        except Exception as e:
            print(f"POST status error: {e}")
            send_error_response(self, 500, str(e))