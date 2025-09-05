
# backend/api/posts.py
from http.server import BaseHTTPRequestHandler
import json
import os
import pyodbc
from urllib.parse import urlparse, parse_qs
from pydantic import BaseModel

# --- Database connection setup ---
server = os.environ.get("DB_SERVER")
database = os.environ.get("DB_NAME")
username = os.environ.get("DB_USER")
password = os.environ.get("DB_PASSWORD")
driver = '{ODBC Driver 18 for SQL Server}'

conn = pyodbc.connect(
    f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
)
cursor = conn.cursor()

# --- Pydantic model ---
class Post(BaseModel):
    user_id: int
    subject_id: int
    content: str

# --- Vercel handler ---
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Parse query string
            parsed_url = urlparse(self.path)
            query = parse_qs(parsed_url.query)
            subject_id = int(query.get("subject_id", [0])[0])

            cursor.execute("""
                SELECT p.PostID, p.Content, p.CreatedAt, u.Username
                FROM Posts p
                JOIN Users u ON p.UserID = u.UserID
                WHERE p.SubjectID = ?
                ORDER BY p.CreatedAt ASC
            """, (subject_id,))

            posts = [
                {
                    "id": row.PostID,
                    "content": row.Content,
                    "created_at": str(row.CreatedAt),
                    "user": row.Username
                }
                for row in cursor.fetchall()
            ]

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

            user_id = data.get("user_id")
            subject_id = data.get("subject_id")
            content = data.get("content")

            if not (user_id and subject_id and content):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing fields"}).encode())
                return

            cursor.execute(
                "INSERT INTO Posts (UserID, SubjectID, Content) VALUES (?, ?, ?)",
                (user_id, subject_id, content)
            )
            conn.commit()

            self.send_response(201)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Post created"}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        # Enable CORS preflight if needed
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
