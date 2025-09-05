from http.server import BaseHTTPRequestHandler
import json
import pyodbc
from pydantic import BaseModel
import os

server = os.environ.get("DB_SERVER")
database = os.environ.get("DB_NAME")
username = os.environ.get("DB_USER")
password = os.environ.get("DB_PASSWORD")
driver = '{ODBC Driver 18 for SQL Server}'

conn = pyodbc.connect(
    f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
)
cursor = conn.cursor()

class Post(BaseModel):
    user_id: int
    subject_id: int
    content: str

def handler(request, response):
    method = request.method

    if method == "GET":
        qs = request.query
        subject_id = int(qs.get("subject_id", [0])[0])
        cursor.execute("""
            SELECT p.PostID, p.Content, p.CreatedAt, u.Username
            FROM Posts p
            JOIN Users u ON p.UserID = u.UserID
            WHERE p.SubjectID = ?
            ORDER BY p.CreatedAt ASC
        """, (subject_id,))
        posts = [{"id": row.PostID, "content": row.Content, "created_at": str(row.CreatedAt), "user": row.Username} for row in cursor.fetchall()]
        response.status_code = 200
        response.write(json.dumps(posts))

    elif method == "POST":
        body = json.loads(request.body)
        user_id = body.get("user_id")
        subject_id = body.get("subject_id")
        content = body.get("content")
        if not (user_id and subject_id and content):
            response.status_code = 400
            response.write(json.dumps({"error": "Missing fields"}))
            return
        cursor.execute("INSERT INTO Posts (UserID, SubjectID, Content) VALUES (?, ?, ?)",
                       (user_id, subject_id, content))
        conn.commit()
        response.status_code = 201
        response.write(json.dumps({"message": "Post created"}))
    
    else:
        response.status_code = 405
        response.write(json.dumps({"error": "Method not allowed"}))
