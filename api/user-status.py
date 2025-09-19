from http.server import BaseHTTPRequestHandler
import json
import os
from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials, firestore, auth
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
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
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
        """Get online users and their status"""
        try:
            # Verify authentication
            decoded_token = self.verify_token()
            if not decoded_token:
                self.send_error_response(401, "Unauthorized")
                return

            # Get all user profiles with status
            profiles_ref = db.collection("UserProfiles")
            profiles = profiles_ref.stream()
            
            users_status = []
            for profile_doc in profiles:
                profile_data = profile_doc.to_dict()
                
                # Only include necessary fields for status
                user_status = {
                    "uid": profile_data.get("uid"),
                    "displayName": profile_data.get("displayName"),
                    "photoURL": profile_data.get("photoURL"),
                    "status": profile_data.get("status", "offline"),
                    "lastSeen": profile_data.get("lastSeen")
                }
                users_status.append(user_status)
            
            self.send_success_response({"users": users_status})
            
        except Exception as e:
            print(f"GET status error: {e}")
            self.send_error_response(500, str(e))

    def do_PUT(self):
        """Update user status"""
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
            data = json.loads(body)
            
            status = data.get('status')
            if not status:
                self.send_error_response(400, "Missing status field")
                return
            
            # Validate status values
            valid_statuses = ['online', 'away', 'busy', 'offline']
            if status not in valid_statuses:
                self.send_error_response(400, f"Invalid status. Must be one of: {valid_statuses}")
                return
            
            # Update user profile with new status
            user_ref = db.collection("UserProfiles").document(user_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                self.send_error_response(404, "User profile not found")
                return
            
            # Update status and last seen
            update_data = {
                "status": status,
                "lastSeen": datetime.utcnow().isoformat()
            }
            
            user_ref.update(update_data)
            
            # Return updated status
            updated_doc = user_ref.get()
            updated_profile = updated_doc.to_dict()
            
            response_data = {
                "uid": updated_profile.get("uid"),
                "displayName": updated_profile.get("displayName"),
                "status": updated_profile.get("status"),
                "lastSeen": updated_profile.get("lastSeen")
            }
            
            self.send_success_response(response_data)
            
        except json.JSONDecodeError:
            self.send_error_response(400, "Invalid JSON data")
        except Exception as e:
            print(f"PUT status error: {e}")
            self.send_error_response(500, str(e))