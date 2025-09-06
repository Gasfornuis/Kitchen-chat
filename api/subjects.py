from http.server import BaseHTTPRequestHandler
import json
import os
from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    # Load service account from environment variable
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    cred = credentials.Certificate(json.loads(sa_json))
    firebase_admin.initialize_app(cred)

db = firestore.client()
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Query subjects ordered by CreatedAt descending
            subjects_ref = db.collection("subjects").order_by("CreatedAt", direction=firestore.Query.DESCENDING)
            docs = subjects_ref.stream()

            subjects = []
            for doc in docs:
                data = doc.to_dict()
                subjects.append({
                    "id": doc.id,
                    "Title": data.get("Title"),
                    "CreatedAt": str(data.get("CreatedAt")),
                    "CreatedBy": data.get("CreatedBy")
                })

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(subjects).encode())

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            title = data.get("Title")
            created_by = data.get("CreatedBy", "Anonymous")  # default until you add users

            if not title:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing Title"}).encode())
                return

            db.collection("subjects").add({
                "Title": title,
                "CreatedAt": firestore.SERVER_TIMESTAMP,
                "CreatedBy": created_by,
                "secret": FIREBASE_SECRET
            })

            self.send_response(201)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Subject created"}).encode())

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

