from http.server import BaseHTTPRequestHandler
import json
import os
from google.cloud import firestore
from urllib.parse import urlparse, parse_qs
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
            parsed_url = urlparse(self.path)
            query = parse_qs(parsed_url.query)
            subject_id = query.get("subjectId", [None])[0]

            if not subject_id:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing subjectId"}).encode())
                return

            posts_ref = db.collection("Posts").where("SubjectId", "==", f"/subjects/{subject_id}").order_by("CreatedAt")
            docs = posts_ref.stream()

            posts = []
            for doc in docs:
                data = doc.to_dict()
                posts.append({
                    "id": doc.id,
                    "Content": data.get("Content"),
                    "CreatedAt": str(data.get("CreatedAt")),
                    "PostedBy": data.get("PostedBy"),
                    "SubjectId": data.get("SubjectId")
                })

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(posts).encode())

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            content = data.get("Content")
            subject_id = data.get("SubjectId")
            posted_by = data.get("PostedBy", "Anonymous")

            if not content or not subject_id:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing Content or SubjectId"}).encode())
                return

            db.collection("posts").add({
                "Content": content,
                "CreatedAt": firestore.SERVER_TIMESTAMP,
                "PostedBy": posted_by,
                "SubjectId": f"/subjects/{subject_id}",
                "secret": FIREBASE_SECRET
            })

            self.send_response(201)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Post created"}).encode())

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

