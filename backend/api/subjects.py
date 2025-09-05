# backend/api/subjects.py
from http.server import BaseHTTPRequestHandler
import json
import os
import pyodbc
from urllib.parse import parse_qs
from pydantic import BaseModel

# --- Database connection setup ---
server = os.environ.get("DB_SERVER")
database = os.environ.get("DB_NAME")
username = os.environ.get("DB_USER")
password = os.environ.get("DB_PASSWORD")
driver = '{ODBC Driver 18 for SQL Server}'

# NOTE: This connection is created outside the handler so it can be reused across invocations.
#       If pyodbc fails to connect on Vercel, consider switching to pymssql or another pure Python driver.
conn = pyodbc.connect(
    f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
)
cursor = conn.cursor()

# --- Pydantic model ---
class Subject(BaseModel):
    title: str

# --- Vercel handler ---
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            cursor.execute("SELECT SubjectID, Title FROM Subjects ORDER BY CreatedAt DESC")
            subjects = [{"id": row.SubjectID, "title": row.Title} for row in cursor.fetchall()]
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
            
            title = data.get("title")
            if not title:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing title"}).encode())
                return

            cursor.execute("INSERT INTO Subjects (Title) VALUES (?)", (title,))
            conn.commit()

            self.send_response(201)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Subject created"}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        # Allow CORS (if frontend is calling this)
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

