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
    from firebase_admin import storage, credentials
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("Warning: Firebase not available, using demo mode")

# Initialize Firebase if not already done
if FIREBASE_AVAILABLE and not firebase_admin._apps:
    try:
        sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if sa_json:
            cred = credentials.Certificate(json.loads(sa_json))
            firebase_admin.initialize_app(cred, {
                'storageBucket': 'kitchen-chat-f8b7b.appspot.com'  # Replace with your bucket name
            })
        else:
            print("Warning: FIREBASE_SERVICE_ACCOUNT not found")
            FIREBASE_AVAILABLE = False
    except Exception as e:
        print(f"Firebase initialization failed: {e}")
        FIREBASE_AVAILABLE = False

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
            # Check if all dependencies are available
            if not PIL_AVAILABLE:
                self.send_error_response('Pillow library not installed. Cannot process images.', 500)
                return
            
            if not FIREBASE_AVAILABLE:
                self.send_error_response('Firebase not configured. Cannot upload avatars.', 500)
                return
            
            # Process the actual upload
            self.process_upload_full()
            
        except Exception as e:
            print(f"Avatar upload error: {e}")
            self.send_error_response(f'Upload failed: {str(e)}', 500)
    
    def process_upload_full(self):
        """Full upload processing"""
        try:
            # Parse multipart form data
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_error_response('Invalid content type. Expected multipart/form-data.', 400)
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
                self.send_error_response('No file uploaded. Please select an image file.', 400)
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
                self.send_error_response('Invalid file type. Please use JPG, PNG, or GIF images only.', 400)
                return
            
            # Process and upload avatar
            avatar_url = self.process_avatar(file_data, user_id, file_type)
            
            if not avatar_url:
                self.send_error_response('Failed to process and upload avatar', 500)
                return
            
            self.send_json_response({
                'success': True,
                'avatarUrl': avatar_url,
                'message': 'Avatar uploaded successfully!',
                'debug': {
                    'userId': user_id,
                    'fileSize': len(file_data),
                    'fileType': file_type,
                    'processedSize': f'{self.avatar_size}x{self.avatar_size}'
                }
            })
            
        except Exception as e:
            print(f"Full upload processing error: {e}")
            self.send_error_response(f'Upload processing failed: {str(e)}', 500)
    
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
        try:
            # Open image
            image = Image.open(io.BytesIO(file_data))
            
            # Convert to RGB if necessary (for transparency support)
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                if image.mode in ('RGBA', 'LA'):
                    background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                else:
                    background.paste(image)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Crop to square (center crop)
            width, height = image.size
            if width != height:
                size = min(width, height)
                left = (width - size) // 2
                top = (height - size) // 2
                image = image.crop((left, top, left + size, top + size))
            
            # Resize to avatar size with high-quality resampling
            image = image.resize((self.avatar_size, self.avatar_size), Image.Resampling.LANCZOS)
            
            # Optimize and save as JPEG
            output = io.BytesIO()
            image.save(output, format='JPEG', optimize=True, quality=85)
            output.seek(0)
            processed_data = output.getvalue()
            
            # Upload to storage
            return self.upload_to_storage(processed_data, user_id)
            
        except Exception as e:
            print(f"Image processing failed: {e}")
            raise Exception(f"Image processing failed: {str(e)}")
    
    def upload_to_storage(self, image_data, user_id):
        """Upload processed image to Firebase Storage"""
        try:
            # Generate unique filename with timestamp
            timestamp = int(datetime.now().timestamp())
            filename = f"avatars/{user_id}_{timestamp}.jpg"
            
            # Get Firebase storage bucket
            bucket = storage.bucket()
            blob = bucket.blob(filename)
            
            # Upload image data
            blob.upload_from_string(
                image_data, 
                content_type='image/jpeg'
            )
            
            # Make the image publicly accessible
            blob.make_public()
            
            # Return the public URL
            return blob.public_url
            
        except Exception as e:
            print(f"Firebase upload failed: {e}")
            raise Exception(f"Storage upload failed: {str(e)}")
    
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
                'firebase_available': FIREBASE_AVAILABLE,
                'timestamp': datetime.now().isoformat()
            }
        }, status)