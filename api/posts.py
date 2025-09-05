# backend/api/posts.py
import json
import os
import pymssql
from pydantic import BaseModel

# --- Database connection setup ---
server = os.environ.get("DB_SERVER")
database = os.environ.get("DB_NAME")
username = os.environ.get("DB_USER")
password = os.environ.get("DB_PASSWORD")

conn = pymssql.connect(
    server=server,
    user=username,
    password=password,
    database=database
)
cursor = conn.cursor(as_dict=True)

# --- Pydantic model ---
class Post(BaseModel):
    user_id: int
    subject_id: int
    content: str

# --- Vercel serverless handler ---
def handler(request, response):
    try:
        if request.method == "GET":
            subject_id = int(request.query.get("subject_id", [0])[0])
            cursor.execute("""
                SELECT p.PostID, p.Content, p.CreatedAt, u.Username
                FROM Posts p
                JOIN Users u ON p.UserID = u.UserID
                WHERE p.SubjectID = %s
                ORDER BY p.CreatedAt ASC
            """, (subject_id,))
            posts = [
                {
                    "id": row["PostID"],
                    "content": row["Content"],
                    "created_at": str(row["CreatedAt"]),
                    "user": row["Username"]
                }
                for row in cursor.fetchall()
            ]
            response.status_code = 200
            response.write(json.dumps(posts))

        elif request.method == "POST":
            body = json.loads(request.body)
            user_id = body.get("user_id")
            subject_id = body.get("subject_id")
            content = body.get("content")

            if not (user_id and subject_id and content):
                response.status_code = 400
                response.write(json.dumps({"error": "Missing fields"}))
                return

            cursor.execute(
                "INSERT INTO Posts (UserID, SubjectID, Content) VALUES (%s, %s, %s)",
                (user_id, subject_id, content)
            )
            conn.commit()
            response.status_code = 201
            response.write(json.dumps({"message": "Post created"}))

        else:
            response.status_code = 405
            response.write(json.dumps({"error": "Method not allowed"}))

    except Exception as e:
        response.status_code = 500
        response.write(json.dumps({"error": str(e)}))
