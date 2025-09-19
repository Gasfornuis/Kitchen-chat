from http.server import BaseHTTPRequestHandler
import json
import os
from google.cloud import firestore
from urllib.parse import urlparse, parse_qs
import firebase_admin
from firebase_admin import credentials, firestore
import uuid
from datetime import datetime

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

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed_url = urlparse(self.path)
            query = parse_qs(parsed_url.query)
            message_id = query.get("messageId", [None])[0]

            if not message_id:
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing messageId"}).encode())
                return

            if not db:
                # Demo mode - return empty reactions
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps([]).encode())
                return

            # Query Firestore for reactions
            reactions_ref = db.collection("Reactions").where("MessageId", "==", message_id)
            docs = reactions_ref.stream()

            reactions = []
            for doc in docs:
                data = doc.to_dict()
                reactions.append({
                    "id": doc.id,
                    "MessageId": data.get("MessageId", ""),
                    "Emoji": data.get("Emoji", ""),
                    "UserId": data.get("UserId", ""),
                    "UserName": data.get("UserName", "Anonymous"),
                    "CreatedAt": str(data.get("CreatedAt", datetime.now()))
                })

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(reactions).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            message_id = data.get("MessageId")
            emoji = data.get("Emoji")
            user_name = data.get("UserName", "Anonymous")
            action = data.get("Action", "add")  # "add" or "remove"
            
            if not message_id or not emoji:
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing MessageId or Emoji"}).encode())
                return

            if not db:
                # Demo mode - just return success
                self.send_response(201)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "message": "Reaction added (demo mode)",
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.now().isoformat()
                }).encode())
                return

            # Create a unique user ID based on username (simple approach)
            user_id = f"user_{hash(user_name) % 10000}"

            if action == "add":
                # Check if user already reacted with this emoji
                existing_reactions = db.collection("Reactions")\
                    .where("MessageId", "==", message_id)\
                    .where("UserId", "==", user_id)\
                    .where("Emoji", "==", emoji)\
                    .stream()
                
                existing_reaction = None
                for doc in existing_reactions:
                    existing_reaction = doc
                    break
                
                if existing_reaction:
                    # User already reacted with this emoji, remove it (toggle behavior)
                    existing_reaction.reference.delete()
                    action_performed = "removed"
                else:
                    # Add new reaction
                    db.collection("Reactions").add({
                        "MessageId": message_id,
                        "Emoji": emoji,
                        "UserId": user_id,
                        "UserName": user_name,
                        "CreatedAt": firestore.SERVER_TIMESTAMP,
                        "secret": FIREBASE_SECRET
                    })
                    action_performed = "added"
            
            elif action == "remove":
                # Remove user's reaction
                reactions_to_remove = db.collection("Reactions")\
                    .where("MessageId", "==", message_id)\
                    .where("UserId", "==", user_id)\
                    .where("Emoji", "==", emoji)\
                    .stream()
                
                for doc in reactions_to_remove:
                    doc.reference.delete()
                
                action_performed = "removed"
            
            self.send_response(201)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "message": f"Reaction {action_performed} successfully",
                "action": action_performed,
                "emoji": emoji
            }).encode())

        except Exception as e:
            print(f"Error handling reaction: {str(e)}")  # Server-side logging
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()