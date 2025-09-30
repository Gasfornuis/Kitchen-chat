import http.server
import json
import os
import uuid
import io
import base64
from datetime import datetime
import mimetypes
import cgi

try:
    from PIL import Image
except ImportError:
    print("Warning: Pillow not installed. Install with: pip install Pillow")
    Image = None

try:
    import firebase_admin
    from firebase_admin import storage
except ImportError:
    print("Warning: Firebase not configured, using local storage")
    firebase_admin = None
    storage = None

class AvatarUploadHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.max_file_size = 5 * 1024 * 1024  # 5MB
        self.allowed_types = ['image/jpeg', 'image/png', 'image/gif']
        self.avatar_size = 200  # Final avatar size
        
        # Initialize Firebase Storage (if available)
        self.bucket = None
        if firebase_admin and storage:
            try:
                self.bucket = storage.bucket()
            except:
                print("Firebase not initialized, using local storage")
        
        super().__init__(*args, **kwargs)
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        if self.path == '/api/avatar-upload':
            self.handle_avatar_upload()
        else:
            self.send_error(404, "Not Found")
    
    def handle_avatar_upload(self):
        try:
            # Parse multipart form data
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_error_response('Invalid content type', 400)
                return
            
            # Check content length
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > self.max_file_size:
                self.send_error_response('File too large (max 5MB)', 413)
                return
            
            # Parse form data
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    'REQUEST_METHOD': 'POST',
                    'CONTENT_TYPE': self.headers['Content-Type'],
                    'CONTENT_LENGTH': self.headers['Content-Length']
                }
            )
            
            # Get file and user ID
            if 'avatar' not in form:
                self.send_error_response('No file uploaded', 400)
                return
            
            file_item = form['avatar']
            user_id = form.getvalue('userId')
            
            if not user_id:
                self.send_error_response('User ID required', 400)
                return
            
            # Validate file
            if not file_item.filename:
                self.send_error_response('No file selected', 400)
                return
            
            # Check file type
            mime_type = file_item.type or mimetypes.guess_type(file_item.filename)[0]
            if mime_type not in self.allowed_types:
                self.send_error_response('Invalid file type. Use JPG, PNG, or GIF', 400)
                return
            
            # Read file data
            file_data = file_item.file.read()
            if len(file_data) > self.max_file_size:
                self.send_error_response('File too large (max 5MB)', 413)
                return
            
            # Process and upload avatar
            avatar_url = self.process_avatar(file_data, user_id, mime_type)
            
            self.send_json_response({
                'success': True,
                'avatarUrl': avatar_url,
                'message': 'Avatar uploaded successfully'
            })
            
        except Exception as e:
            print(f"Avatar upload error: {e}")
            self.send_error_response(f'Upload failed: {str(e)}', 500)
    
    def process_avatar(self, file_data, user_id, mime_type):
        """Process avatar image: resize, crop, optimize"""
        if not Image:
            # Fallback: save original file without processing
            return self.upload_raw_file(file_data, user_id, mime_type)
        
        try:
            # Open image
            image = Image.open(io.BytesIO(file_data))
            
            # Convert to RGB if necessary (for JPEG output)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparency
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.split()[-1])
                else:
                    background.paste(image)
                image = background
            
            # Crop to square (center crop)
            width, height = image.size
            if width != height:
                size = min(width, height)
                left = (width - size) // 2
                top = (height - size) // 2
                image = image.crop((left, top, left + size, top + size))
            
            # Resize to avatar size
            image = image.resize((self.avatar_size, self.avatar_size), Image.Resampling.LANCZOS)
            
            # Optimize and save
            output = io.BytesIO()
            
            # Use JPEG for better compression
            image.save(output, format='JPEG', optimize=True, quality=85)
            file_extension = '.jpg'
            content_type = 'image/jpeg'
            
            output.seek(0)
            processed_data = output.getvalue()
            
            # Upload to storage
            return self.upload_to_storage(processed_data, user_id, file_extension, content_type)
            
        except Exception as e:
            print(f"Image processing failed: {e}")
            # Fallback to raw upload
            return self.upload_raw_file(file_data, user_id, mime_type)
    
    def upload_raw_file(self, file_data, user_id, mime_type):
        """Upload original file without processing (fallback)"""
        extension_map = {
            'image/jpeg': '.jpg',
            'image/png': '.png', 
            'image/gif': '.gif'
        }
        file_extension = extension_map.get(mime_type, '.jpg')
        return self.upload_to_storage(file_data, user_id, file_extension, mime_type)
    
    def upload_to_storage(self, image_data, user_id, file_extension, content_type):
        """Upload processed image to storage"""
        
        # Generate unique filename
        timestamp = int(datetime.now().timestamp())
        filename = f"avatars/{user_id}_{timestamp}{file_extension}"
        
        if self.bucket:  # Firebase Storage
            return self.upload_to_firebase(image_data, filename, content_type)
        else:  # Local storage
            return self.upload_to_local(image_data, filename)
    
    def upload_to_firebase(self, image_data, filename, content_type):
        """Upload to Firebase Storage"""
        try:
            blob = self.bucket.blob(filename)
            blob.upload_from_string(image_data, content_type=content_type)
            
            # Make blob publicly readable
            blob.make_public()
            
            return blob.public_url
            
        except Exception as e:
            raise Exception(f"Firebase upload failed: {str(e)}")
    
    def upload_to_local(self, image_data, filename):
        """Upload to local storage (for development)"""
        try:
            # Create avatars directory if it doesn't exist
            avatar_dir = 'static/avatars'
            os.makedirs(avatar_dir, exist_ok=True)
            
            # Save file
            file_path = os.path.join(avatar_dir, os.path.basename(filename))
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            # Return public URL (adjust based on your setup)
            return f'/static/avatars/{os.path.basename(filename)}'
            
        except Exception as e:
            raise Exception(f"Local upload failed: {str(e)}")
    
    def send_json_response(self, data, status=200):
        """Send JSON response with CORS headers"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_error_response(self, message, status):
        """Send error response"""
        self.send_json_response({'error': message, 'success': False}, status)

# For Vercel deployment
def handler(request, response):
    """Vercel serverless function handler"""
    import urllib.parse
    from http.server import HTTPServer
    
    class MockServer:
        def __init__(self):
            self.server_name = 'localhost'
            self.server_port = 80
    
    class MockRequest:
        def __init__(self, request):
            self.request = request
            self.rfile = io.BytesIO(request.get('body', b''))
            self.wfile = io.BytesIO()
    
    # Create handler instance
    handler_instance = AvatarUploadHandler(MockRequest(request), ('127.0.0.1', 80), MockServer())
    
    # Process request
    if request.method == 'POST':
        handler_instance.do_POST()
    elif request.method == 'OPTIONS':
        handler_instance.do_OPTIONS()
    
    # Return response
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': handler_instance.wfile.getvalue().decode()
    }

if __name__ == '__main__':
    # For local testing
    from http.server import HTTPServer
    
    server = HTTPServer(('localhost', 8000), AvatarUploadHandler)
    print("Avatar upload server running on http://localhost:8000")
    server.serve_forever()
