from http.server import BaseHTTPRequestHandler
import json
import os
import base64
import logging
import traceback
import firebase_admin
from firebase_admin import credentials, firestore as admin_firestore

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import auth
try:
    from .auth import require_authentication
except ImportError:
    try:
        from auth import require_authentication
    except ImportError:
        require_authentication = None

# Firebase setup
db = None
try:
    if not firebase_admin._apps:
        sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if sa_json:
            cred = credentials.Certificate(json.loads(sa_json))
            firebase_admin.initialize_app(cred)
    if firebase_admin._apps:
        db = admin_firestore.client()
except Exception as e:
    logger.error(f"Firebase initialization failed: {e}")

# Firestore doc limit is 1 MiB; base64 adds ~33% overhead
# 700 KB original -> ~933 KB base64 -> fits in 1 MiB doc with other fields
MAX_FILE_SIZE = 700 * 1024  # 700 KB

ALLOWED_TYPES = {
    'image/jpeg': '.jpg', 'image/png': '.png', 'image/gif': '.gif', 'image/webp': '.webp',
    'video/mp4': '.mp4', 'video/quicktime': '.mov', 'video/webm': '.webm',
    'application/pdf': '.pdf', 'text/plain': '.txt',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
}

def get_file_category(mime_type):
    if mime_type.startswith('image/'): return 'image'
    if mime_type.startswith('video/'): return 'video'
    return 'document'

def get_file_icon(mime_type):
    if mime_type.startswith('image/'): return '🖼️'
    if mime_type.startswith('video/'): return '🎬'
    if mime_type == 'application/pdf': return '📄'
    if mime_type == 'text/plain': return '📝'
    if 'word' in mime_type or 'document' in mime_type: return '📃'
    return '📁'

def format_file_size(size_bytes):
    if size_bytes < 1024: return f"{size_bytes} B"
    if size_bytes < 1024 * 1024: return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"

def send_response_with_cors(handler, data, status=200):
    try:
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        handler.send_response(status)
        handler.send_header('Content-Type', 'application/json; charset=utf-8')
        handler.send_header('Content-Length', str(len(body)))
        handler.send_header('Access-Control-Allow-Origin', '*')
        handler.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
        handler.end_headers()
        handler.wfile.write(body)
        return True
    except Exception as e:
        logger.error(f"Failed to send response: {e}")
        return False

class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info(f"HTTP: {format % args}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def do_POST(self):
        try:
            # Auth check
            if require_authentication:
                current_user = require_authentication(self)
                if not current_user:
                    return send_response_with_cors(self, {"error": "Authentication required"}, 401)
                username = current_user.get("displayName", "Anonymous")
            else:
                username = "TestUser"

            # Read body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length <= 0:
                return send_response_with_cors(self, {"error": "No data provided"}, 400)

            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            file_data_b64 = data.get("fileData")
            file_name = data.get("fileName", "file")
            file_type = data.get("fileType", "application/octet-stream")

            if not file_data_b64:
                return send_response_with_cors(self, {"error": "No file data provided"}, 400)

            if file_type not in ALLOWED_TYPES:
                return send_response_with_cors(self, {
                    "error": f"File type '{file_type}' not supported. Use images, videos, PDF, TXT, or DOC."
                }, 400)

            # Decode to check actual size
            try:
                file_bytes = base64.b64decode(file_data_b64)
            except Exception:
                return send_response_with_cors(self, {"error": "Invalid file data"}, 400)

            if len(file_bytes) > MAX_FILE_SIZE:
                return send_response_with_cors(self, {
                    "error": f"File too large ({format_file_size(len(file_bytes))}). Maximum is {format_file_size(MAX_FILE_SIZE)}."
                }, 413)

            # Sanitize filename
            safe_name = "".join(c for c in file_name if c.isalnum() or c in '.-_ ').strip()
            if not safe_name:
                safe_name = "file" + ALLOWED_TYPES.get(file_type, '')

            # Build data URL - stored directly in Firestore with the message
            data_url = f"data:{file_type};base64,{file_data_b64}"
            file_category = get_file_category(file_type)

            logger.info(f"File processed by {username}: {safe_name} ({format_file_size(len(file_bytes))})")

            return send_response_with_cors(self, {
                "ok": True,
                "url": data_url,
                "fileName": safe_name,
                "fileSize": format_file_size(len(file_bytes)),
                "fileSizeBytes": len(file_bytes),
                "fileType": file_type,
                "fileCategory": file_category,
                "fileIcon": get_file_icon(file_type)
            }, 201)

        except json.JSONDecodeError:
            return send_response_with_cors(self, {"error": "Invalid JSON data"}, 400)
        except Exception as e:
            logger.error(f"Upload error: {e}")
            logger.error(traceback.format_exc())
            return send_response_with_cors(self, {"error": f"Upload failed: {str(e)}"}, 500)
