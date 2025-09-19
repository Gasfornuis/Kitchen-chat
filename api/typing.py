from http.server import BaseHTTPRequestHandler
import json
import os
from google.cloud import firestore
from urllib.parse import urlparse, parse_qs
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta

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
            subject_id = query.get("SubjectId", [None])[0]

            if not subject_id:
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing SubjectId"}).encode())
                return

            if not db:
                # Demo mode - return empty typing status
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps([]).encode())
                return

            # Clean up old typing statuses (older than 10 seconds)
            cutoff_time = datetime.now() - timedelta(seconds=10)
            
            # Query Firestore for typing statuses
            typing_ref = db.collection("TypingStatus").where("SubjectId", "==", f"/subjects/{subject_id}")
            docs = typing_ref.stream()

            typing_statuses = []
            batch = db.batch()
            cleanup_needed = False

            for doc in docs:
                data = doc.to_dict()
                timestamp = data.get("Timestamp")
                
                # Convert timestamp to datetime if it's a string
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    except:
                        timestamp = datetime.now() - timedelta(seconds=11)  # Mark as old
                elif hasattr(timestamp, 'seconds'):  # Firestore timestamp
                    timestamp = timestamp.to_datetime()
                
                # Check if status is too old
                if timestamp < cutoff_time:
                    # Mark for deletion
                    batch.delete(doc.reference)
                    cleanup_needed = True
                else:
                    typing_statuses.append({
                        "UserId": data.get("UserId", ""),
                        "UserName": data.get("UserName", "Anonymous"),
                        "IsTyping": data.get("IsTyping", False),
                        "Timestamp": timestamp.isoformat()
                    })
            
            # Execute cleanup if needed
            if cleanup_needed:
                try:
                    batch.commit()
                except Exception as e:
                    print(f"Cleanup error: {e}")

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(typing_statuses).encode())

        except Exception as e:
            print(f"Error getting typing status: {str(e)}")
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            subject_id = data.get("SubjectId")
            user_id = data.get("UserId")
            user_name = data.get("UserName", "Anonymous")
            is_typing = data.get("IsTyping", False)
            
            if not subject_id or not user_id:
                self.send_response(400)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing SubjectId or UserId"}).encode())
                return

            if not db:
                # Demo mode - just return success
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "message": "Typing status updated (demo mode)",
                    "isTyping": is_typing
                }).encode())
                return

            # Prepare document data
            doc_data = {
                "SubjectId": f"/subjects/{subject_id}",
                "UserId": user_id,
                "UserName": user_name,
                "IsTyping": is_typing,
                "Timestamp": datetime.now().isoformat(),
                "secret": FIREBASE_SECRET
            }

            if is_typing:
                # Update or create typing status
                db.collection("TypingStatus").document(f"{subject_id}_{user_id}").set(doc_data)
            else:
                # Remove typing status when not typing
                try:
                    db.collection("TypingStatus").document(f"{subject_id}_{user_id}").delete()
                except Exception as e:
                    # Document might not exist, which is fine
                    pass
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "message": "Typing status updated successfully",
                "isTyping": is_typing
            }).encode())

        except Exception as e:
            print(f"Error updating typing status: {str(e)}")
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