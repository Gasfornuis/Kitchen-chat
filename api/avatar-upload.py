from http.server import BaseHTTPRequestHandler
import json
import os
import io
from datetime import datetime
import cgi

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: Pillow not installed. Avatar processing disabled.")

try:
    import firebase_admin
    from firebase_admin import storage
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("Warning: Firebase not available, using demo mode")

class handler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.max_file_size = 5 * 1024 * 1024  # 5MB
        self.allowed_types = ['image/jpeg', 'image/png', 'image/gif']
        self.avatar_size = 200  # Final avatar size
        super().__init__(*args, **kwargs)
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.end_headers()
    
    def do_POST(self):
        """Handle avatar upload"""
        try:
            # Simple success response for now to test API connectivity
            self.send_json_response({
                'success': True,
                'avatarUrl': 'https://via.placeholder.com/200x200/007cba/ffffff?text=TEST',
                'message': 'Avatar upload API is working! (Demo mode)',
                'debug': {
                    'pillow_available': PIL_AVAILABLE,
                    'firebase_available': FIREBASE_AVAILABLE,
                    'content_type': self.headers.get('Content-Type', 'Not provided'),
                    'content_length': self.headers.get('Content-Length', 'Not provided'),
                    'method': 'POST',
                    'path': self.path
                }
            })
            
        except Exception as e:
            print(f"Avatar upload error: {e}")
            self.send_error_response(f'Upload failed: {str(e)}', 500)
    
    def process_upload_full(self):
        """Full upload processing (for when dependencies are available)"""
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
            
            # Parse form data using cgi
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    'REQUEST_METHOD': 'POST',
                    'CONTENT_TYPE': self.headers.get('Content-Type', ''),
                    'CONTENT_LENGTH': self.headers.get('Content-Length', '0')
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
            
            # Read file data
            file_data = file_item.file.read()
            if len(file_data) > self.max_file_size:
                self.send_error_response('File too large (max 5MB)', 413)
                return
            
            # Check file type by reading file header
            file_type = self.detect_file_type(file_data)
            if file_type not in self.allowed_types:
                self.send_error_response('Invalid file type. Use JPG, PNG, or GIF', 400)
                return
            
            # Process and upload avatar
            avatar_url = self.process_avatar(file_data, user_id, file_type)
            
            self.send_json_response({
                'success': True,
                'avatarUrl': avatar_url,
                'message': 'Avatar uploaded successfully'
            })
            
        except Exception as e:
            print(f"Full upload processing error: {e}")
            self.send_error_response(f'Upload failed: {str(e)}', 500)
    
    def detect_file_type(self, file_data):
        """Detect file type from file headers"""
        if file_data.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        elif file_data.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        elif file_data.startswith(b'GIF87a') or file_data.startswith(b'GIF89a'):
            return 'image/gif'
        else:
            return 'unknown'
    
    def process_avatar(self, file_data, user_id, file_type):
        """Process avatar image: resize, crop, optimize"""
        if not PIL_AVAILABLE:
            # Return demo URL if Pillow not available
            return f'https://via.placeholder.com/{self.avatar_size}x{self.avatar_size}/007cba/ffffff?text={user_id[:2].upper()}'
        
        try:
            # Open image
            image = Image.open(io.BytesIO(file_data))
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
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
            
            # Save as JPEG
            output = io.BytesIO()
            image.save(output, format='JPEG', optimize=True, quality=85)
            output.seek(0)
            processed_data = output.getvalue()
            
            # Upload to storage
            return self.upload_to_storage(processed_data, user_id)
            
        except Exception as e:
            print(f"Image processing failed: {e}")
            # Return demo URL on processing failure
            return f'https://via.placeholder.com/{self.avatar_size}x{self.avatar_size}/007cba/ffffff?text={user_id[:2].upper()}'
    
    def upload_to_storage(self, image_data, user_id):
        """Upload processed image to storage"""
        
        # Generate unique filename
        timestamp = int(datetime.now().timestamp())
        filename = f"avatars/{user_id}_{timestamp}.jpg"
        
        if FIREBASE_AVAILABLE:
            return self.upload_to_firebase(image_data, filename)
        else:
            return self.upload_to_demo(image_data, user_id)
    
    def upload_to_firebase(self, image_data, filename):
        """Upload to Firebase Storage"""
        try:
            bucket = storage.bucket()
            blob = bucket.blob(filename)
            blob.upload_from_string(image_data, content_type='image/jpeg')
            blob.make_public()
            return blob.public_url
        except Exception as e:
            print(f"Firebase upload failed: {e}")
            # Return demo URL on Firebase failure
            return f'https://via.placeholder.com/{self.avatar_size}x{self.avatar_size}/007cba/ffffff?text=FB'
    
    def upload_to_demo(self, image_data, user_id):
        """Demo upload (returns placeholder URL)"""
        return f'https://via.placeholder.com/{self.avatar_size}x{self.avatar_size}/007cba/ffffff?text={user_id[:2].upper()}'
    
    def send_json_response(self, data, status=200):
        """Send JSON response with CORS headers"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_error_response(self, message, status):
        """Send error response"""
        self.send_json_response({
            'error': message, 
            'success': False,
            'debug': {
                'status': status,
                'pillow_available': PIL_AVAILABLE,
                'firebase_available': FIREBASE_AVAILABLE
            }
        }, status)
