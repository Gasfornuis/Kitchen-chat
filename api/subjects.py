# backend/api/subjects.py
import json
import os
import pymssql
from pydantic import BaseModel

# --- Database connection setup ---
server = os.environ.get("DB_SERVER")      # e.g., "myserver.database.windows.net"
database = os.environ.get("DB_NAME")      # your database name
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
class Subject(BaseModel):
    title: str

# --- Vercel serverless handler ---
def handler(request, response):
    try:
        if request.method == "GET":
            cursor.execute("SELECT SubjectID, Title FROM Subjects ORDER BY CreatedAt DESC")
            subjects = [{"id": row["SubjectID"], "title": row["Title"]} for row in cursor.fetchall()]
            response.status_code = 200
            response.write(json.dumps(subjects))

        elif request.method == "POST":
            data = json.loads(request.body)
            title = data.get("title")

            if not title:
                response.status_code = 400
                response.write(json.dumps({"error": "Missing title"}))
                return

            cursor.execute("INSERT INTO Subjects (Title) VALUES (%s)", (title,))
            conn.commit()
            response.status_code = 201
            response.write(json.dumps({"message": "Subject created"}))

        else:
            response.status_code = 405
            response.write(json.dumps({"error": "Method not allowed"}))

    except Exception as e:
        response.status_code = 500
        response.write(json.dumps({"error": str(e)}))

