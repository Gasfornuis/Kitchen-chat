"""Centrale security utilities voor Kitchen Chat API"""

import time
import logging
import re
import json
import hashlib
from collections import defaultdict
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')

# VEILIGE CORS CONFIGURATIE - GEEN WILDCARD MEER!
ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000', 
    'https://kitchen-chat.vercel.app',
    'https://gasfornuis.github.io',
    'https://kitchen-chat-gasfornuis.vercel.app'
    'https://kitchenchat.live'
]

# In-memory rate limiting (voor productie: gebruik Redis of database)
rate_limit_storage = defaultdict(list)
blocked_ips = {}

def get_client_ip(headers):
    """Get real client IP from request headers"""
    # Check proxy headers in order of preference
    forwarded = headers.get('x-forwarded-for', '')
    if forwarded:
        # Take first IP (original client)
        return forwarded.split(',')[0].strip()
    
    real_ip = headers.get('x-real-ip', '')
    if real_ip:
        return real_ip
        
    cf_connecting_ip = headers.get('cf-connecting-ip', '')  # Cloudflare
    if cf_connecting_ip:
        return cf_connecting_ip
        
    return headers.get('remote-addr', 'unknown')

def check_rate_limit(client_ip, endpoint, max_requests=30, time_window=60):
    """Advanced rate limiting with IP tracking"""
    now = time.time()
    key = f"{client_ip}:{endpoint}"
    
    # Clean expired entries
    rate_limit_storage[key] = [
        req_time for req_time in rate_limit_storage[key] 
        if now - req_time < time_window
    ]
    
    # Check if limit exceeded
    current_count = len(rate_limit_storage[key])
    if current_count >= max_requests:
        security_logger.warning(
            f"Rate limit exceeded: {client_ip} on {endpoint} "
            f"({current_count}/{max_requests} in {time_window}s)"
        )
        return False
    
    # Add current request
    rate_limit_storage[key].append(now)
    return True

def is_ip_blocked(client_ip):
    """Check if IP is temporarily blocked"""
    if client_ip in blocked_ips:
        if time.time() < blocked_ips[client_ip]:
            return True, int(blocked_ips[client_ip] - time.time())
        else:
            # Unblock expired IPs
            del blocked_ips[client_ip]
    return False, 0

def block_ip_temporarily(client_ip, duration_seconds):
    """Block IP temporarily"""
    blocked_ips[client_ip] = time.time() + duration_seconds
    security_logger.error(f"IP {client_ip} temporarily blocked for {duration_seconds} seconds")

def get_safe_origin(request_headers):
    """Get safe CORS origin - NO MORE WILDCARDS!"""
    origin = request_headers.get('Origin', '')
    
    # Check if origin is explicitly allowed
    if origin in ALLOWED_ORIGINS:
        logger.debug(f"Allowed origin: {origin}")
        return origin
    
    # For non-browser requests or development
    if not origin:
        return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else 'null'
    
    # Log suspicious origin attempts
    security_logger.warning(f"Blocked origin attempt: {origin}")
    return 'null'  # Deny unknown origins

def send_secure_response(handler, data, status=200, set_cookie=None):
    """Send response with comprehensive security headers"""
    safe_origin = get_safe_origin(handler.headers)
    
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    
    # CORS headers - VEILIG!
    handler.send_header('Access-Control-Allow-Origin', safe_origin)
    handler.send_header('Access-Control-Allow-Credentials', 'true')
    
    # Comprehensive security headers
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('X-Frame-Options', 'DENY')
    handler.send_header('X-XSS-Protection', '1; mode=block')
    handler.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
    handler.send_header('X-Permitted-Cross-Domain-Policies', 'none')
    
    # Content Security Policy
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:; "
        "frame-ancestors 'none';"
    )
    handler.send_header('Content-Security-Policy', csp)
    
    if set_cookie:
        handler.send_header('Set-Cookie', set_cookie)
    
    handler.end_headers()
    handler.wfile.write(json.dumps(data).encode('utf-8'))

def send_secure_error(handler, message, status=400, log_level='error'):
    """Send error response without exposing internal system details"""
    client_ip = get_client_ip(handler.headers)
    
    # Log detailed error server-side
    if log_level == 'error':
        security_logger.error(f"API Error {status} from {client_ip}: {message}")
    elif log_level == 'warning':
        security_logger.warning(f"API Warning {status} from {client_ip}: {message}")
    
    # Send generic error message to client for security
    public_message = message
    
    # Hide internal system details
    if status >= 500:
        public_message = "Internal server error. Please try again later."
    elif any(keyword in str(message).lower() for keyword in 
             ['database', 'firestore', 'firebase', 'collection', 'document']):
        public_message = "Service temporarily unavailable. Please try again."
    elif 'traceback' in str(message).lower() or 'exception' in str(message).lower():
        public_message = "An unexpected error occurred. Please try again."
    
    send_secure_response(handler, {'error': public_message}, status)

def validate_content_length(handler, max_length=10000):
    """Validate request content length to prevent large payloads"""
    content_length = int(handler.headers.get('Content-Length', 0))
    
    if content_length > max_length:
        send_secure_error(handler, f"Request too large (max {max_length} bytes)", 413)
        return False
    
    if content_length == 0:
        send_secure_error(handler, "No data provided", 400)
        return False
    
    return True

def sanitize_string_input(input_str, max_length=None):
    """Sanitize string input to prevent XSS and injection attacks"""
    if not input_str or not isinstance(input_str, str):
        return ''
    
    # Remove null bytes and control characters
    sanitized = ''.join(char for char in input_str if ord(char) >= 32 or char in '\n\r\t')
    
    # Trim whitespace
    sanitized = sanitized.strip()
    
    # Apply length limit
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized

def validate_json_input(handler, required_fields=None, max_content_length=10000):
    """Validate and parse JSON input safely"""
    if not validate_content_length(handler, max_content_length):
        return None
    
    try:
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length)
        data = json.loads(body.decode('utf-8'))
        
        if not isinstance(data, dict):
            send_secure_error(handler, "Data must be a JSON object", 400)
            return None
        
        # Check required fields
        if required_fields:
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                send_secure_error(handler, f"Missing required fields: {', '.join(missing_fields)}", 400)
                return None
        
        return data
        
    except json.JSONDecodeError as e:
        send_secure_error(handler, "Invalid JSON format", 400)
        return None
    except UnicodeDecodeError:
        send_secure_error(handler, "Invalid character encoding", 400)
        return None
    except Exception as e:
        logger.error(f"JSON input validation error: {e}")
        send_secure_error(handler, "Invalid request format", 400)
        return None

def detect_xss_patterns(text):
    """Detect potential XSS patterns in text"""
    if not text or not isinstance(text, str):
        return False
    
    # Common XSS patterns
    xss_patterns = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'data:text/html',
        r'vbscript:',
        r'on\w+\s*=',  # onclick, onload, etc.
        r'<iframe[^>]*>',
        r'<object[^>]*>',
        r'<embed[^>]*>',
        r'<applet[^>]*>',
        r'<meta[^>]*>',
        r'<link[^>]*>',
        r'<style[^>]*>',
        r'expression\s*\(',
        r'url\s*\(',
        r'@import',
        r'\\u[0-9a-fA-F]{4}',  # Unicode escapes
        r'&\#[0-9]+;',  # HTML entities
        r'&\#x[0-9a-fA-F]+;'  # Hex HTML entities
    ]
    
    text_lower = text.lower()
    
    for pattern in xss_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            security_logger.warning(f"XSS pattern detected: {pattern} in text: {text[:100]}...")
            return True
    
    return False

def validate_user_input(data, field_rules):
    """Comprehensive input validation
    
    field_rules = {
        'field_name': {
            'required': True,
            'max_length': 100,
            'min_length': 1,
            'allow_html': False,
            'pattern': r'^[a-zA-Z0-9\s]+$'  # Optional regex pattern
        }
    }
    """
    errors = []
    
    for field_name, rules in field_rules.items():
        value = data.get(field_name)
        
        # Check if required
        if rules.get('required', False) and not value:
            errors.append(f"{field_name} is required")
            continue
        
        if value is None:
            continue  # Skip optional empty fields
        
        # Ensure string
        if not isinstance(value, str):
            errors.append(f"{field_name} must be a string")
            continue
        
        value = value.strip()
        
        # Length validation
        min_len = rules.get('min_length', 0)
        max_len = rules.get('max_length', float('inf'))
        
        if len(value) < min_len:
            errors.append(f"{field_name} must be at least {min_len} characters")
        
        if len(value) > max_len:
            errors.append(f"{field_name} must be less than {max_len} characters")
        
        # Pattern validation
        if rules.get('pattern') and not re.match(rules['pattern'], value):
            errors.append(f"{field_name} contains invalid characters")
        
        # XSS detection
        if not rules.get('allow_html', False) and detect_xss_patterns(value):
            errors.append(f"{field_name} contains potentially unsafe content")
        
        # Update sanitized value
        data[field_name] = sanitize_string_input(value, max_len)
    
    return len(errors) == 0, errors

def log_security_event(event_type, details, client_ip, user=None, severity='INFO'):
    """Centralized security event logging"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'event_type': event_type,
        'client_ip': client_ip,
        'user': user.get('username') if user else 'anonymous',
        'details': details,
        'severity': severity
    }
    
    log_message = f"Security Event [{severity}]: {event_type} | IP: {client_ip} | User: {log_entry['user']} | {details}"
    
    if severity == 'ERROR':
        security_logger.error(log_message)
    elif severity == 'WARNING':
        security_logger.warning(log_message)
    else:
        security_logger.info(log_message)
    
    # In productie: verstuur naar security monitoring systeem
    return log_entry

class SecureAPIHandler:
    """Mixin class voor secure API handling"""
    
    @staticmethod
    def setup_secure_cors(handler):
        """Setup secure CORS headers"""
        safe_origin = get_safe_origin(handler.headers)
        
        handler.send_header('Access-Control-Allow-Origin', safe_origin)
        handler.send_header('Access-Control-Allow-Credentials', 'true')
        
        # Security headers
        handler.send_header('X-Content-Type-Options', 'nosniff')
        handler.send_header('X-Frame-Options', 'DENY')
        handler.send_header('X-XSS-Protection', '1; mode=block')
        handler.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        handler.send_header('X-Permitted-Cross-Domain-Policies', 'none')
        
        # Content Security Policy voor API responses
        csp = "default-src 'none'; frame-ancestors 'none';"
        handler.send_header('Content-Security-Policy', csp)
    
    @staticmethod
    def handle_options_securely(handler, allowed_methods='GET, POST, OPTIONS'):
        """Handle OPTIONS requests securely"""
        safe_origin = get_safe_origin(handler.headers)
        
        handler.send_response(204)
        handler.send_header('Access-Control-Allow-Origin', safe_origin)
        handler.send_header('Access-Control-Allow-Methods', allowed_methods)
        handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
        handler.send_header('Access-Control-Allow-Credentials', 'true')
        handler.send_header('Access-Control-Max-Age', '86400')
        
        SecureAPIHandler.setup_secure_cors(handler)
        handler.end_headers()
    
    @staticmethod
    def send_json_securely(handler, data, status=200, set_cookie=None):
        """Send JSON response with all security headers"""
        handler.send_response(status)
        handler.send_header('Content-Type', 'application/json; charset=utf-8')
        
        SecureAPIHandler.setup_secure_cors(handler)
        
        if set_cookie:
            handler.send_header('Set-Cookie', set_cookie)
        
        handler.end_headers()
        
        # Ensure UTF-8 encoding
        json_str = json.dumps(data, ensure_ascii=False)
        handler.wfile.write(json_str.encode('utf-8'))
    
    @staticmethod
    def send_error_securely(handler, message, status=400, log_details=None):
        """Send error without exposing internal details"""
        client_ip = get_client_ip(handler.headers)
        
        # Log detailed error server-side
        log_message = log_details or message
        log_security_event(
            event_type='api_error',
            details=log_message,
            client_ip=client_ip,
            severity='ERROR' if status >= 500 else 'WARNING'
        )
        
        # Send sanitized error to client
        public_message = message
        if status >= 500:
            public_message = "Internal server error. Please try again later."
        elif any(keyword in str(message).lower() for keyword in 
                ['database', 'firestore', 'firebase', 'collection', 'traceback', 'exception']):
            public_message = "Service temporarily unavailable. Please try again."
        
        SecureAPIHandler.send_json_securely(handler, {'error': public_message}, status)
    
    @staticmethod
    def check_rate_limit_or_block(handler, endpoint, max_requests=30, time_window=60):
        """Check rate limiting and send error response if exceeded"""
        client_ip = get_client_ip(handler.headers)
        
        # Check if IP is blocked
        is_blocked, remaining = is_ip_blocked(client_ip)
        if is_blocked:
            SecureAPIHandler.send_error_securely(
                handler, 
                f"IP temporarily blocked. Try again in {remaining} seconds.", 
                423  # 423 Locked
            )
            return False
        
        # Check rate limit
        if not check_rate_limit(client_ip, endpoint, max_requests, time_window):
            SecureAPIHandler.send_error_securely(
                handler,
                "Too many requests. Please slow down.",
                429  # 429 Too Many Requests
            )
            return False
        
        return True

def sanitize_string_input(input_str, max_length=None):
    """Sanitize string input for safe storage and display"""
    if not input_str or not isinstance(input_str, str):
        return ''
    
    # Remove dangerous characters
    sanitized = ''.join(
        char for char in input_str 
        if ord(char) >= 32 or char in '\n\r\t'
    )
    
    # Normalize whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    # Apply length limit
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip()
    
    return sanitized
