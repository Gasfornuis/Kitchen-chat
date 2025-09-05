from http.server import BaseHTTPRequestHandler
import json
import pyodbc
from urllib.parse import parse_qs
from pydantic import BaseModel
import os

# --- Database connection ---
server = os.environ.get("DB_SERVER")
database = os.environ.get("DB_NAME")
username = os.environ.get("DB_USER")
password = os.environ.get("DB_PASSWORD")
driver = '{ODBC Driver 18 for SQL Server}'

import pyodbc
conn = pyodbc.connect(
    f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
)
cursor = conn.cursor()

# --- Pydantic model ---
class Subject(BaseModel):
    title: str

# --- Vercel Python serverless handler ---
def handler(request, response):
    method = request.method

    if method == "GET":
        cursor.execute("SELECT SubjectID, Title FROM Subjects ORDER BY CreatedAt DESC")
        subjects = [{"id": row.SubjectID, "title": row.Title} for row in cursor.fetchall()]
        response.status_code = 200
        response.write(json.dumps(subjects))
    
    elif method == "POST":
        body = json.loads(request.body)
        title = body.get("title")
        if not title:
            response.status_code = 400
            response.write(json.dumps({"error": "Missing title"}))
            return
        
        cursor.execute("INSERT INTO Subjects (Title) VALUES (?)", (title,))
        conn.commit()
        response.status_code = 201
        response.write(json.dumps({"message": "Subject created"}))
    
    else:
        response.status_code = 405
        response.write(json.dumps({"error": "Method not allowed"}))
