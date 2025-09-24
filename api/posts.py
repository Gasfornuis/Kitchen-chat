from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import urlparse, parse_qs
import firebase_admin
from firebase_admin import credentials, firestore as admin_firestore
from google.cloud import firestore as gcf  # for SERVER_TIMESTAMP sentinel
import uuid
from datetime import datetime
import logging
import traceback

# Import authentication functions from auth.py
try:
    from .auth import require_authentication
except ImportError:
    from auth import require_authentication

# Logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Debug controls
def is_debug(handler=None):
    try:
        if os.environ.get("DEBUG", "0") == "1":
            return True
        # Optional per-request triggers:
        if handler:
            # Header
            if handler.headers.get("X-Debug") == "1":
                return True
            # Query param
            parsed = urlparse(handler.path)
            q = parse_qs(parsed.query or "")
            if q.get("debug", ["0"])[0] == "1":
                return True
    except Exception:
        pass
    return False

# Firebase init (avoid name shadowing)
db = None
try:
    if not firebase_admin._apps:
        sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if sa_json:
            cred = credentials.Certificate(json.loads(sa_json))
            firebase_admin.initialize_app(cred)
        else:
            logger.warning("Warning: Running in demo mode without Firebase (no FIREBASE_SERVICE_ACCOUNT found)")
    if firebase_admin._apps:
        db = admin_firestore.client()
        logger.info("Firebase initialized successfully")
except Exception as e:
    logger.error(f"Firebase initialization error: {e}")
    db = None

# CORS
ALLOWED_ORIGINS = {
    "https://www.kitchenchat.live",
    "https://kitchenchat.live",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://kitchen-chat.vercel.app",
    "https://kitchen-chat-gasfornuis.vercel.app",
    "https://gasfornuis.github.io",
}

def send_cors_headers(handler):
    origin = handler.headers.get('Origin')
    if origin in ALLOWED_ORIGINS:
        handler.send_header('Access-Control-Allow-Origin', origin)
        handler.send_header('Vary', 'Origin')
        handler.send_header('Access-Control-Allow-Credentials', 'true')
    else:
        handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')

def send_json_response(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    send_cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(body)

def send_error_response(handler, message, status=400, details=None):
    # Do not leak sensitive details unless debug is enabled
    payload = {'error': message}
    if details and is_debug(handler):
        payload['details'] = details
    logger.error(f"Error {status}: {message}{' | ' + str(details) if details else ''}")
    send_json_response(handler, payload, status)

def validate_message_content(content, message_type='text'):
    if not content or not isinstance(content, str):
        return False, "Message content is required"
    content = content.strip()
    if len(content) == 0:
        return False, "Message cannot be empty"
    if len(content) > 2000:
        return False, "Message too long (max 2000 characters)"
    return True, None

def sanitize_string_input(input_str, max_length=None):
    if not input_str or not isinstance(input_str, str):
        return ''
    sanitized = ''.join(ch for ch in input_str if ord(ch) >= 32 or ch in '\n\r\t')
    sanitized = sanitized.strip()
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            logger.info("GET /api/posts")
            current_user = require_authentication(self)
            if not current_user:
                return send_error_response(self, "Authentication required", 401)

            parsed_url = urlparse(self.path)
            query = parse_qs(parsed_url.query or "")
            subject_vals = query.get("SubjectId", [])
            subject_id = subject_vals[0] if subject_vals else None

            if not subject_id:
                return send_error_response(self, "Missing SubjectId parameter", 400)

            if not isinstance(subject_id, str) or len(subject_id) > 50:
                return send_error_response(self, "Invalid SubjectId format", 400)

            if not db:
                sample = [{
                    "id": "demo1",
                    "Content": "Welcome to Kitchen Chat! This is a demo message.",
                    "CreatedAt": datetime.now().isoformat(),
                    "PostedBy": "System",
                    "SubjectId": f"/subjects/{subject_id}",
                    "MessageType": "text"
                }]
                return send_json_response(self, sample)

            try:
                posts = []
                try:
                    posts_ref = (
                        db.collection("Posts")
                        .where("SubjectId", "==", f"/subjects/{subject_id}")
                        .order_by("CreatedAt")
                        .limit(500)
                    )
                    docs = list(posts_ref.stream())
                    if not docs:
                        posts_ref = (
                            db.collection("Posts")
                            .where("SubjectId", "==", subject_id)
                            .order_by("CreatedAt")
                            .limit(500)
                        )
                        docs = list(posts_ref.stream())
                except Exception as qerr:
                    logger.warning(f"Query with order_by failed, retry w/o ordering: {qerr}")
                    try:
                        posts_ref = (
                            db.collection("Posts")
                            .where("SubjectId", "==", f"/subjects/{subject_id}")
                            .limit(500)
                        )
                        docs = list(posts_ref.stream())
                    except Exception as q2err:
                        logger.error(f"Fallback query failed: {q2err}")
                        docs = []

                for doc in docs:
                    try:
                        data = doc.to_dict()
                        ts = data.get("CreatedAt")
                        if hasattr(ts, "isoformat"):
                            created_at = ts.isoformat()
                        elif isinstance(ts, datetime):
                            created_at = ts.isoformat()
                        else:
                            created_at = str(ts) if ts is not None else datetime.now().isoformat()

                        posts.append({
                            "id": doc.id,
                            "Content": sanitize_string_input(data.get("Content", ""), 2000),
                            "CreatedAt": created_at,
                            "PostedBy": sanitize_string_input(data.get("PostedBy", "Anonymous"), 50),
                            "SubjectId": data.get("SubjectId", ""),
                            "MessageType": data.get("MessageType", "text"),
                        })
                    except Exception as doc_err:
                        logger.error(f"Doc {doc.id} processing error: {doc_err}")
                        continue

                return send_json_response(self, posts)

            except Exception as fs_err:
                logger.error(f"Firestore read error: {fs_err}\n{traceback.format_exc()}")
                # Return empty list to keep UI responsive
                return send_json_response(self, [])

        except Exception as e:
            logger.error(f"GET handler error: {e}\n{traceback.format_exc()}")
            return send_error_response(self, "Internal server error. Please try again later.", 500, details=str(e))

    def do_POST(self):
        try:
            logger.info("POST /api/posts")
            # Parse body
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length <= 0:
                    return send_error_response(self, "No data provided", 400)
                body = self.rfile.read(content_length)
                data = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError as e:
                return send_error_response(self, "Invalid JSON format", 400, details=str(e))
            except Exception as e:
                return send_error_response(self, "Invalid request format", 400, details=str(e))

            # Auth
            current_user = require_authentication(self)
            if not current_user:
                return send_error_response(self, "Authentication required", 401)

            # Validate
            required = ['Content', 'SubjectId']
            missing = [k for k in required if k not in data or not data[k]]
            if missing:
                return send_error_response(self, f"Missing required fields: {', '.join(missing)}", 400)

            content = str(data.get("Content", "")).strip()
            subject_id = str(data.get("SubjectId", "")).strip()
            posted_by = current_user.get("displayName", "Anonymous")
            message_type = data.get("MessageType", "text")

            ok, err = validate_message_content(content, message_type)
            if not ok:
                return send_error_response(self, err, 400)

            # Sanitize
            content = sanitize_string_input(content, 2000)
            subject_id = sanitize_string_input(subject_id, 50)
            posted_by = sanitize_string_input(posted_by, 50)
            message_type = sanitize_string_input(message_type, 20)

            if not db:
                return send_json_response(self, {
                    "ok": True,
                    "id": str(uuid.uuid4()),
                    "demo": True,
                    "timestamp": datetime.now().isoformat()
                }, 201)

            # Build doc
            doc_data = {
                "Content": content,
                "CreatedAt": gcf.SERVER_TIMESTAMP,  # correct sentinel
                "PostedBy": posted_by,
                "SubjectId": f"/subjects/{subject_id}",
                "MessageType": message_type,
            }

            # Only wrap the Firestore write itself so we don't mask response errors
            try:
                doc_ref, write_result = db.collection("Posts").add(doc_data)
            except Exception as write_err:
                logger.error(f"Firestore write error: {write_err}\n{traceback.format_exc()}")
                return send_error_response(self, "Failed to save message", 500, details=str(write_err))

            # If we got here, the write succeeded. Now respond simply.
            return send_json_response(self, {
                "ok": True,
                "id": doc_ref.id,
                "type": message_type
            }, 201)

        except Exception as e:
            # Any error after a successful write will be correctly labeled here, not as save failure
            logger.error(f"POST handler error: {e}\n{traceback.format_exc()}")
            status = 500
            msg = "Failed to create message"
            det = str(e) if is_debug(self) else None
            return send_error_response(self, msg, status, details=det)

    def do_OPTIONS(self):
        self.send_response(204)
        send_cors_headers(self)
        self.send_header('Access-Control-Max-Age', '86400')
        self.send_header('Vary', 'Origin')
        self.end_headers()
