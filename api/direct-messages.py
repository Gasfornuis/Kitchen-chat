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
from .auth import require_authentication, get_session_token_from_request, verify_session_token

if not firebase_admin._apps:
    # Load service account from environment variable
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
        firebase_admin.initialize_app(cred)
    else:
        # Fallback for demo mode
        print("Warning: Running in demo mode without Firebase")

db = firestore.client() if firebase_admin._apps else None
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")

# In-memory storage for demo mode
demo_messages = {}

def get_dm_id(user1, user2):
    """Create a consistent DM conversation ID from two usernames"""
    users = sorted([user1.lower(), user2.lower()])
    return f"dm_{users[0]}_{users[1]}"

def send_auth_error(handler, message="Authentication required"):
    """Send authentication error response"""
    handler.send_response(401)
    handler.send_header("Content-type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Credentials", "true")
    handler.end_headers()
    handler.wfile.write(json.dumps({"error": message}).encode())

def send_access_denied(handler, message="Access denied"):
    """Send access denied error response"""
    handler.send_response(403)
    handler.send_header("Content-type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Credentials", "true")
    handler.end_headers()
    handler.wfile.write(json.dumps({"error": message}).encode())

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Require authentication for all DM access
            current_user_auth = require_authentication(self)
            if not current_user_auth:
                return send_auth_error(self)
            
            parsed_url = urlparse(self.path)
            query = parse_qs(parsed_url.query)
            
            # Get query parameters
            user1 = query.get("user1", [None])[0]
            user2 = query.get("user2", [None])[0]
            current_user = query.get("currentUser", [None])[0]
            
            # Security check - authenticated user must match currentUser parameter
            if current_user and current_user.lower() != current_user_auth["username"].lower():
                return send_access_denied(self, "You can only access your own messages")
            
            # Use authenticated user as current user if not provided
            if not current_user:
                current_user = current_user_auth["displayName"]
            
            # For getting conversation list
            if not user1 and not user2:
                return self.get_dm_conversations(current_user)
            
            # For getting messages between two users
            if not user1 or not user2:
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing user1 or user2"}).encode())
                return
            
            # Security check - authenticated user can only access their own DMs
            if current_user.lower() not in [user1.lower(), user2.lower()]:
                return send_access_denied(self, "You can only access your own messages")
            
            dm_id = get_dm_id(user1, user2)
            
            if not db:
                # Demo mode - return demo messages
                messages = demo_messages.get(dm_id, [])
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps(messages).encode())
                return
            
            # Query Firestore for DM messages
            dm_ref = db.collection("DirectMessages").where("conversationId", "==", dm_id).order_by("CreatedAt")
            docs = dm_ref.stream()
            
            messages = []
            for doc in docs:
                data = doc.to_dict()
                messages.append({
                    "id": doc.id,
                    "content": data.get("content", ""),
                    "createdAt": str(data.get("CreatedAt", datetime.now())),
                    "sender": data.get("sender", "Anonymous"),
                    "recipient": data.get("recipient", "Anonymous"),
                    "conversationId": data.get("conversationId", ""),
                    "messageType": data.get("messageType", "text"),
                    "mediaData": data.get("mediaData", None),
                    "attachmentUrl": data.get("attachmentUrl", None)
                })
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps(messages).encode())
            
        except Exception as e:
            print(f"DM GET error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def get_dm_conversations(self, current_user):
        """Get list of DM conversations for a user"""
        try:
            if not db:
                # Demo mode - return demo conversations
                conversations = []
                for dm_id in demo_messages.keys():
                    if current_user.lower() in dm_id:
                        # Extract other user from dm_id
                        parts = dm_id.replace('dm_', '').split('_')
                        other_user = parts[1] if parts[0] == current_user.lower() else parts[0]
                        
                        # Get last message
                        messages = demo_messages[dm_id]
                        last_message = messages[-1] if messages else None
                        
                        conversations.append({
                            "conversationId": dm_id,
                            "otherUser": other_user,
                            "lastMessage": last_message["content"] if last_message else "",
                            "lastMessageTime": last_message["createdAt"] if last_message else "",
                            "unreadCount": 0  # TODO: Implement unread count
                        })
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps(conversations).encode())
                return
            
            # Query Firestore for conversations involving the current user
            # Get all DM messages where user is sender or recipient
            dm_ref = db.collection("DirectMessages").where("sender", "==", current_user)
            sent_docs = list(dm_ref.stream())
            
            dm_ref2 = db.collection("DirectMessages").where("recipient", "==", current_user)
            received_docs = list(dm_ref2.stream())
            
            # Combine and group by conversation
            conversations = {}
            all_docs = sent_docs + received_docs
            
            for doc in all_docs:
                data = doc.to_dict()
                conv_id = data.get("conversationId", "")
                sender = data.get("sender", "")
                recipient = data.get("recipient", "")
                other_user = recipient if sender == current_user else sender
                
                if conv_id not in conversations:
                    conversations[conv_id] = {
                        "conversationId": conv_id,
                        "otherUser": other_user,
                        "lastMessage": data.get("content", ""),
                        "lastMessageTime": str(data.get("CreatedAt", datetime.now())),
                        "unreadCount": 0
                    }
                else:
                    # Update if this message is more recent
                    current_time = data.get("CreatedAt")
                    stored_time_str = conversations[conv_id]["lastMessageTime"]
                    
                    try:
                        # Compare timestamps
                        if hasattr(current_time, 'timestamp'):
                            current_timestamp = current_time.timestamp()
                        else:
                            current_timestamp = datetime.fromisoformat(str(current_time)).timestamp()
                        
                        stored_timestamp = datetime.fromisoformat(stored_time_str).timestamp()
                        
                        if current_timestamp > stored_timestamp:
                            conversations[conv_id]["lastMessage"] = data.get("content", "")
                            conversations[conv_id]["lastMessageTime"] = str(current_time)
                    except:
                        # Fallback - just update with latest
                        conversations[conv_id]["lastMessage"] = data.get("content", "")
                        conversations[conv_id]["lastMessageTime"] = str(current_time)
            
            conversation_list = list(conversations.values())
            # Sort by most recent message
            conversation_list.sort(key=lambda x: x["lastMessageTime"], reverse=True)
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps(conversation_list).encode())
            
        except Exception as e:
            print(f"DM conversations error: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def do_POST(self):
        try:
            # Require authentication for sending DMs
            current_user_auth = require_authentication(self)
            if not current_user_auth:
                return send_auth_error(self)
            
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            sender = data.get("sender", "")
            recipient = data.get("recipient", "")
            content = data.get("content", "")
            message_type = data.get("messageType", "text")
            media_data = data.get("mediaData", None)
            
            if not sender or not recipient or not content:
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing sender, recipient, or content"}).encode())
                return
            
            # Security check - authenticated user can only send as themselves
            if sender.lower() != current_user_auth["username"].lower() and sender != current_user_auth["displayName"]:
                return send_access_denied(self, "You can only send messages as yourself")
            
            # Can't send message to yourself
            if sender.lower() == recipient.lower():
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Cannot send message to yourself"}).encode())
                return
            
            dm_id = get_dm_id(sender, recipient)
            message_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            if not db:
                # Demo mode - store in memory
                if dm_id not in demo_messages:
                    demo_messages[dm_id] = []
                
                message = {
                    "id": message_id,
                    "content": content,
                    "createdAt": timestamp,
                    "sender": sender,
                    "recipient": recipient,
                    "conversationId": dm_id,
                    "messageType": message_type,
                    "mediaData": media_data,
                    "attachmentUrl": data.get("attachmentUrl", None)
                }
                
                demo_messages[dm_id].append(message)
                
                self.send_response(201)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "message": "DM sent successfully (demo mode)",
                    "id": message_id,
                    "timestamp": timestamp
                }).encode())
                return
            
            # Prepare document data for Firestore
            doc_data = {
                "content": content,
                "CreatedAt": firestore.SERVER_TIMESTAMP,
                "sender": sender,
                "recipient": recipient,
                "conversationId": dm_id,
                "messageType": message_type,
                "secret": FIREBASE_SECRET
            }
            
            # Handle media data (similar to posts.py)
            if media_data:
                if message_type == "file":
                    doc_data["mediaData"] = {
                        "name": media_data.get("name", "file.txt"),
                        "size": media_data.get("size", "0 KB"),
                        "extension": media_data.get("extension", "FILE"),
                        "icon": media_data.get("icon", "📁")
                    }
                    doc_data["attachmentUrl"] = media_data.get("url", "#")
            
            # Add to Firestore
            doc_ref = db.collection("DirectMessages").add(doc_data)
            
            self.send_response(201)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({
                "message": "DM sent successfully",
                "id": doc_ref[1].id,
                "conversationId": dm_id
            }).encode())
            
        except Exception as e:
            print(f"Error sending DM: {str(e)}")  # Server-side logging
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Cookie")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()