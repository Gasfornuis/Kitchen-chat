from http.server import BaseHTTPRequestHandler
import json
import os
import uuid
import base64
import logging
import traceback
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import firebase_admin
from firebase_admin import credentials, firestore as admin_firestore, storage
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import auth
try:
    from .auth import require_authentication
    logger.info("Auth imported successfully (relative)")
except ImportError:
    try:
        from auth import require_authentication
        logger.info("Auth imported successfully (absolute)")
    except ImportError as e:
        logger.error(f"Failed to import auth: {e}")
        require_authentication = None

# Firebase setup
db = None
bucket = None
bucket_name = None
try:
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_json:
        sa_data = json.loads(sa_json)
        project_id = sa_data.get("project_id", "")
        bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET", f"{project_id}.appspot.com")

        if not firebase_admin._apps:
            cred = credentials.Certificate(sa_data)
            firebase_admin.initialize_app(cred, {'storageBucket': bucket_name})

    if firebase_admin._apps:
        db = admin_firestore.client()
        try:
            # Always pass bucket name explicitly in case app was initialized without storageBucket
            bucket = storage.bucket(bucket_name) if bucket_name else storage.bucket()
            logger.info(f"Firebase Storage bucket initialized: {bucket.name}")
        except Exception as storage_err:
            logger.warning(f"Firebase Storage not available: {storage_err}")
            bucket = None
except Exception as e:
    logger.error(f"Firebase initialization failed: {e}")

# Constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_TYPES = {
    # Images
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
    # Videos
    'video/mp4': '.mp4',
    'video/quicktime': '.mov',
    'video/webm': '.webm',
    # Documents
    'application/pdf': '.pdf',
    'text/plain': '.txt',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
}

FILE_ICONS = {
    'image': '🖼️',
    'video': '🎬',
    'application/pdf': '📄',
    'text/plain': '📝',
    'application/msword': '📃',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '📃',
}

def get_file_category(mime_type):
    if mime_type.startswith('image/'):
        return 'image'
    elif mime_type.startswith('video/'):
        return 'video'
    return 'document'

def get_file_icon(mime_type):
    if mime_type.startswith('image/'):
        return FILE_ICONS['image']
    if mime_type.startswith('video/'):
        return FILE_ICONS['video']
    return FILE_ICONS.get(mime_type, '📁')

def format_file_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"

def send_response_with_cors(handler, data, status=200):
    try:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
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
            if content_length > MAX_FILE_SIZE + 1024 * 100:  # file + JSON overhead
                return send_response_with_cors(self, {"error": f"File too large. Maximum size is {format_file_size(MAX_FILE_SIZE)}"}, 413)

            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            # Extract fields
            file_data_b64 = data.get("fileData")  # base64 encoded file content
            file_name = data.get("fileName", "file")
            file_type = data.get("fileType", "application/octet-stream")
            context = data.get("context", "chat")  # 'chat' or 'dm'
            conversation_id = data.get("conversationId", "general")

            if not file_data_b64:
                return send_response_with_cors(self, {"error": "No file data provided"}, 400)

            # Validate MIME type
            if file_type not in ALLOWED_TYPES:
                return send_response_with_cors(self, {
                    "error": f"File type '{file_type}' is not allowed. Supported: images, videos, PDF, TXT, DOC/DOCX"
                }, 400)

            # Decode base64
            try:
                file_bytes = base64.b64decode(file_data_b64)
            except Exception:
                return send_response_with_cors(self, {"error": "Invalid file data encoding"}, 400)

            # Validate size
            if len(file_bytes) > MAX_FILE_SIZE:
                return send_response_with_cors(self, {
                    "error": f"File too large ({format_file_size(len(file_bytes))}). Maximum is {format_file_size(MAX_FILE_SIZE)}"
                }, 413)

            # Sanitize filename
            safe_name = "".join(c for c in file_name if c.isalnum() or c in '.-_ ').strip()
            if not safe_name:
                safe_name = "file" + ALLOWED_TYPES.get(file_type, '')

            # Generate storage path
            unique_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            storage_path = f"chat-attachments/{conversation_id}/{timestamp}_{unique_id}_{safe_name}"

            if not bucket:
                # Demo mode - return a placeholder
                file_category = get_file_category(file_type)
                return send_response_with_cors(self, {
                    "ok": True,
                    "url": f"data:{file_type};base64,{file_data_b64[:100]}...",
                    "fileName": safe_name,
                    "fileSize": format_file_size(len(file_bytes)),
                    "fileSizeBytes": len(file_bytes),
                    "fileType": file_type,
                    "fileCategory": file_category,
                    "fileIcon": get_file_icon(file_type),
                    "demo": True
                }, 201)

            # Upload to Firebase Storage
            blob = bucket.blob(storage_path)
            blob.upload_from_string(file_bytes, content_type=file_type)

            # Generate a signed URL (valid for 7 days)
            download_url = blob.generate_signed_url(
                expiration=timedelta(days=7),
                method='GET'
            )

            file_category = get_file_category(file_type)

            logger.info(f"File uploaded by {username}: {safe_name} ({format_file_size(len(file_bytes))}) -> {storage_path}")

            return send_response_with_cors(self, {
                "ok": True,
                "url": download_url,
                "fileName": safe_name,
                "fileSize": format_file_size(len(file_bytes)),
                "fileSizeBytes": len(file_bytes),
                "fileType": file_type,
                "fileCategory": file_category,
                "fileIcon": get_file_icon(file_type),
                "storagePath": storage_path
            }, 201)

        except json.JSONDecodeError:
            return send_response_with_cors(self, {"error": "Invalid JSON data"}, 400)
        except Exception as e:
            logger.error(f"Upload error: {e}")
            logger.error(traceback.format_exc())
            return send_response_with_cors(self, {"error": f"Upload failed: {str(e)}"}, 500)
