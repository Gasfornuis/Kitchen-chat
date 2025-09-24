"""Enhanced Security Utilities voor Kitchen Chat API v2.0

KRITIEKE VERBETERINGEN:
- Redis-compatible rate limiting
- Enhanced XSS/injection protection
- Improved CORS handling
- Advanced input validation
- Security event monitoring
- IP reputation checking
- Content analysis and filtering
"""

import time
import logging
import re
import json
import hashlib
import secrets
import ipaddress
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Union, Any
import bcrypt
from urllib.parse import urlparse

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')

# Environment-based configuration
import os
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
ALLOWED_ORIGINS_ENV = os.environ.get("ALLOWED_ORIGINS", "")

# PRODUCTIE-VEILIGE CORS CONFIGURATIE
if ALLOWED_ORIGINS_ENV:
    ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS_ENV.split(",") if origin.strip()]
elif ENVIRONMENT == "production":
    ALLOWED_ORIGINS = [
        'https://kitchenchat.live',
        'https://www.kitchenchat.live',
        'https://kitchen-chat.vercel.app'
    ]
else:
    # Development origins - REMOVED IN PRODUCTION
    ALLOWED_ORIGINS = [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'https://kitchen-chat.vercel.app',
        'https://kitchenchat.live',
        'https://www.kitchenchat.live'
    ]

# Security storage - In productie: gebruik Redis of database
rate_limit_storage = defaultdict(list)
blocked_ips = {}
security_events = defaultdict(list)
suspicious_patterns = defaultdict(int)

# Security constants
MAX_REQUEST_SIZE = 50000  # 50KB
MAX_REQUESTS_PER_MINUTE = 60
MAX_AUTH_REQUESTS_PER_MINUTE = 15
BLOCK_DURATION_MINUTES = 15
SUSPICIOUS_THRESHOLD = 10
MAX_SESSION_DURATION = 8 * 60 * 60  # 8 uur

# Known bad IP ranges (basic examples - in productie: use threat intelligence)
KNOWN_BAD_RANGES = [
    '0.0.0.0/8',      # "This" Network
    '10.0.0.0/8',     # Private networks (kunnen legitiem zijn in internal setups)
    '127.0.0.0/8',    # Loopback
    '169.254.0.0/16', # Link-local
    '224.0.0.0/4',    # Multicast
    '240.0.0.0/4',    # Reserved
]

def get_client_ip(headers: Dict[str, str]) -> str:
    """Extract real client IP with enhanced validation"""
    # Check proxy headers in order of preference
    forwarded = headers.get('x-forwarded-for', '')
    if forwarded:
        # Take first IP (original client)
        ip = forwarded.split(',')[0].strip()
        if is_valid_ip(ip):
            return ip
    
    real_ip = headers.get('x-real-ip', '')
    if real_ip and is_valid_ip(real_ip):
        return real_ip
    
    cf_connecting_ip = headers.get('cf-connecting-ip', '')  # Cloudflare
    if cf_connecting_ip and is_valid_ip(cf_connecting_ip):
        return cf_connecting_ip
    
    # Fallback headers
    for header in ['x-client-ip', 'x-forwarded', 'forwarded-for', 'forwarded']:
        value = headers.get(header, '')
        if value and is_valid_ip(value):
            return value
    
    return headers.get('remote-addr', 'unknown')

def is_valid_ip(ip: str) -> bool:
    """Validate IP address format (IPv4 and IPv6)"""
    if not ip or ip == 'unknown':
        return False
    
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def is_suspicious_ip(ip: str) -> Tuple[bool, str]:
    """Check if IP is in suspicious ranges or patterns"""
    if not is_valid_ip(ip):
        return True, "Invalid IP format"
    
    try:
        ip_obj = ipaddress.ip_address(ip)
        
        # Check against known bad ranges
        for bad_range in KNOWN_BAD_RANGES:
            if ip_obj in ipaddress.ip_network(bad_range, strict=False):
                # Allow localhost in development
                if ENVIRONMENT != 'development' or not str(ip_obj).startswith('127.'):
                    return True, f"IP in suspicious range: {bad_range}"
        
        # Check for private IPs in production
        if ENVIRONMENT == 'production' and ip_obj.is_private:
            return True, "Private IP not allowed in production"
        
        # Check for reserved/special use IPs
        if ip_obj.is_reserved or ip_obj.is_multicast:
            return True, "Reserved or multicast IP"
        
        return False, ""
    
    except Exception as e:
        logger.error(f"IP validation error: {e}")
        return True, "IP validation failed"

def check_rate_limit(client_ip: str, endpoint: str, 
                    max_requests: int = MAX_REQUESTS_PER_MINUTE, 
                    time_window: int = 60) -> bool:
    """Enhanced rate limiting with sliding window"""
    now = time.time()
    key = f"{client_ip}:{endpoint}"
    
    # Clean expired entries (sliding window)
    rate_limit_storage[key] = [
        req_time for req_time in rate_limit_storage[key] 
        if now - req_time < time_window
    ]
    
    current_count = len(rate_limit_storage[key])
    
    # Check if limit exceeded
    if current_count >= max_requests:
        # Log security event
        log_security_event(
            'rate_limit_exceeded',
            f"Rate limit exceeded: {current_count}/{max_requests} in {time_window}s",
            client_ip,
            severity='WARNING'
        )
        
        # Increase suspicious pattern count
        suspicious_patterns[client_ip] += 1
        
        return False
    
    # Add current request
    rate_limit_storage[key].append(now)
    return True

def is_ip_blocked(client_ip: str) -> Tuple[bool, int]:
    """Check if IP is temporarily blocked with remaining time"""
    if client_ip in blocked_ips:
        if time.time() < blocked_ips[client_ip]['until']:
            remaining = int(blocked_ips[client_ip]['until'] - time.time())
            return True, remaining
        else:
            # Unblock expired IPs
            del blocked_ips[client_ip]
            if client_ip in suspicious_patterns:
                # Reduce suspicious count on unblock
                suspicious_patterns[client_ip] = max(0, suspicious_patterns[client_ip] - 2)
    
    return False, 0

def block_ip_temporarily(client_ip: str, duration_minutes: int = BLOCK_DURATION_MINUTES, 
                        reason: str = "Security violation"):
    """Block IP temporarily with enhanced logging"""
    duration_seconds = duration_minutes * 60
    blocked_ips[client_ip] = {
        'until': time.time() + duration_seconds,
        'reason': reason,
        'blocked_at': datetime.now(),
        'duration_minutes': duration_minutes
    }
    
    log_security_event(
        'ip_blocked',
        f"IP blocked for {duration_minutes}m: {reason}",
        client_ip,
        severity='ERROR'
    )

def get_safe_origin(request_headers: Dict[str, str]) -> str:
    """Get safe CORS origin - ABSOLUTELY NO WILDCARDS!"""
    origin = request_headers.get('Origin', '')
    
    # Check if origin is explicitly allowed
    if origin in ALLOWED_ORIGINS:
        logger.debug(f"Allowed origin: {origin}")
        return origin
    
    # For non-browser requests or development
    if not origin:
        return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else 'null'
    
    # Log and block suspicious origin attempts
    log_security_event(
        'cors_violation',
        f"Blocked origin attempt: {origin}",
        get_client_ip(request_headers),
        severity='WARNING'
    )
    
    # Increase suspicious pattern for this IP
    client_ip = get_client_ip(request_headers)
    suspicious_patterns[client_ip] += 1
    
    return 'null'  # Deny unknown origins

def send_secure_response(handler, data: Dict[str, Any], status: int = 200, 
                        set_cookie: Optional[str] = None):
    """Send response with comprehensive security headers"""
    safe_origin = get_safe_origin(handler.headers)
    
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    
    # SECURE CORS - NO WILDCARDS!
    handler.send_header('Access-Control-Allow-Origin', safe_origin)
    handler.send_header('Access-Control-Allow-Credentials', 'true')
    
    # Comprehensive security headers
    security_headers = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'X-Permitted-Cross-Domain-Policies': 'none',
        'Cache-Control': 'no-store, no-cache, must-revalidate, private',
        'Pragma': 'no-cache',
        'Expires': '0'
    }
    
    # Enhanced Content Security Policy
    csp_directives = [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: https:",
        "connect-src 'self' https:",
        "font-src 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "upgrade-insecure-requests"
    ]
    security_headers['Content-Security-Policy'] = '; '.join(csp_directives)
    
    # Production-only headers
    if ENVIRONMENT == 'production':
        security_headers.update({
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
            'X-Robots-Tag': 'noindex, nofollow, nosnippet, noarchive'
        })
    
    # Apply all security headers
    for header, value in security_headers.items():
        handler.send_header(header, value)
    
    if set_cookie:
        handler.send_header('Set-Cookie', set_cookie)
    
    handler.end_headers()
    
    # Ensure UTF-8 encoding and prevent JSON injection
    try:
        json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        handler.wfile.write(json_str.encode('utf-8'))
    except Exception as e:
        logger.error(f"JSON serialization error: {e}")
        handler.wfile.write(json.dumps({'error': 'Response serialization failed'}).encode('utf-8'))

def send_secure_error(handler, message: str, status: int = 400, 
                     log_level: str = 'warning', client_ip: str = None):
    """Send error response without exposing internal system details"""
    if not client_ip:
        client_ip = get_client_ip(handler.headers)
    
    # Log detailed error server-side
    log_entry = f"API Error {status} from {client_ip}: {message}"
    
    if log_level == 'error':
        security_logger.error(log_entry)
    elif log_level == 'warning':
        security_logger.warning(log_entry)
    else:
        logger.info(log_entry)
    
    # Sanitize error message for client (prevent information disclosure)
    public_message = sanitize_error_message(message, status)
    
    # Log security event for errors
    if status >= 400:
        severity = 'ERROR' if status >= 500 else 'WARNING'
        log_security_event(
            'api_error',
            f"HTTP {status}: {message}",
            client_ip,
            severity=severity
        )
    
    send_secure_response(handler, {'error': public_message}, status)

def sanitize_error_message(message: str, status: int) -> str:
    """Sanitize error messages to prevent information disclosure"""
    message_lower = str(message).lower()
    
    # Hide internal system details
    if status >= 500:
        return "Internal server error. Please try again later."
    
    # Hide database/system information
    sensitive_keywords = [
        'database', 'firestore', 'firebase', 'collection', 'document',
        'traceback', 'exception', 'error:', 'line ', 'file ', 'module',
        'connection', 'timeout', 'credential', 'token', 'key', 'secret'
    ]
    
    if any(keyword in message_lower for keyword in sensitive_keywords):
        return "Service temporarily unavailable. Please try again."
    
    # Hide file system paths
    if '/' in message or '\\' in message:
        return "An error occurred while processing your request."
    
    return message

def validate_content_length(handler, max_length: int = MAX_REQUEST_SIZE) -> bool:
    """Validate request content length to prevent large payloads"""
    try:
        content_length = int(handler.headers.get('Content-Length', 0))
        
        if content_length > max_length:
            send_secure_error(
                handler, 
                f"Request too large (max {max_length} bytes)", 
                413,
                client_ip=get_client_ip(handler.headers)
            )
            return False
        
        if content_length == 0:
            send_secure_error(
                handler, 
                "No data provided", 
                400,
                client_ip=get_client_ip(handler.headers)
            )
            return False
        
        return True
    
    except (ValueError, TypeError):
        send_secure_error(
            handler, 
            "Invalid content length", 
            400,
            client_ip=get_client_ip(handler.headers)
        )
        return False

def sanitize_string_input(input_str: Union[str, None], max_length: Optional[int] = None) -> str:
    """Enhanced string sanitization with XSS prevention"""
    if not input_str or not isinstance(input_str, str):
        return ''
    
    # Remove null bytes and dangerous control characters
    sanitized = ''.join(
        char for char in input_str 
        if ord(char) >= 32 or char in '\n\r\t'
    )
    
    # Normalize whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized.strip())
    
    # Apply length limit
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized

def validate_json_input(handler, required_fields: Optional[List[str]] = None, 
                       max_content_length: int = MAX_REQUEST_SIZE) -> Optional[Dict[str, Any]]:
    """Enhanced JSON input validation with security checks"""
    if not validate_content_length(handler, max_content_length):
        return None
    
    try:
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length)
        
        # Validate encoding
        try:
            text = body.decode('utf-8')
        except UnicodeDecodeError:
            send_secure_error(handler, "Invalid character encoding (must be UTF-8)", 400)
            return None
        
        # Check for suspicious patterns before parsing
        if detect_json_injection(text):
            client_ip = get_client_ip(handler.headers)
            log_security_event(
                'json_injection_attempt',
                "Suspicious JSON patterns detected",
                client_ip,
                severity='ERROR'
            )
            send_secure_error(handler, "Invalid request format", 400)
            return None
        
        # Parse JSON
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            log_security_event(
                'json_parse_error',
                f"JSON decode error: {e}",
                get_client_ip(handler.headers),
                severity='WARNING'
            )
            send_secure_error(handler, "Invalid JSON format", 400)
            return None
        
        # Validate data type
        if not isinstance(data, dict):
            send_secure_error(handler, "Data must be a JSON object", 400)
            return None
        
        # Check for nested depth (prevent DoS)
        if get_json_depth(data) > 10:
            send_secure_error(handler, "JSON structure too complex", 400)
            return None
        
        # Validate required fields
        if required_fields:
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                send_secure_error(
                    handler, 
                    f"Missing required fields: {', '.join(missing_fields)}", 
                    400
                )
                return None
        
        # Sanitize all string values
        sanitized_data = sanitize_json_data(data)
        
        return sanitized_data
    
    except Exception as e:
        logger.error(f"JSON input validation error: {e}")
        send_secure_error(handler, "Invalid request format", 400, 'error')
        return None

def get_json_depth(obj: Any, current_depth: int = 0) -> int:
    """Calculate maximum depth of JSON object"""
    if current_depth > 20:  # Prevent infinite recursion
        return current_depth
    
    if isinstance(obj, dict):
        if not obj:
            return current_depth
        return max(get_json_depth(value, current_depth + 1) for value in obj.values())
    elif isinstance(obj, list):
        if not obj:
            return current_depth
        return max(get_json_depth(item, current_depth + 1) for item in obj)
    else:
        return current_depth

def sanitize_json_data(data: Union[Dict, List, str, Any]) -> Union[Dict, List, str, Any]:
    """Recursively sanitize JSON data"""
    if isinstance(data, dict):
        return {key: sanitize_json_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_json_data(item) for item in data]
    elif isinstance(data, str):
        return sanitize_string_input(data, 10000)  # Max 10KB per string
    else:
        return data

def detect_json_injection(json_str: str) -> bool:
    """Detect potential JSON injection attacks"""
    if not json_str:
        return False
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r'\\u[0-9a-fA-F]{4}',  # Unicode escapes (can bypass filters)
        r'\\["\'\\/bfnrt]',    # Excessive escaping
        r'"\s*:\s*"[^"]*<script',  # Script injection in values
        r'"\s*:\s*"[^"]*javascript:',  # JavaScript protocol
        r'"\s*:\s*"[^"]*vbscript:',   # VBScript protocol
        r'__proto__',          # Prototype pollution
        r'constructor',        # Constructor access
        r'prototype',          # Prototype access
    ]
    
    json_lower = json_str.lower()
    
    for pattern in suspicious_patterns:
        if re.search(pattern, json_lower, re.IGNORECASE):
            return True
    
    return False

def detect_xss_patterns(text: str) -> bool:
    """Enhanced XSS pattern detection"""
    if not text or not isinstance(text, str):
        return False
    
    # Comprehensive XSS patterns
    xss_patterns = [
        # Script tags
        r'<script[^>]*>.*?</script>',
        r'<script[^>]*>',
        
        # Event handlers
        r'on\w+\s*=',  # onclick, onload, etc.
        r'javascript:',
        r'vbscript:',
        r'data:text/html',
        r'data:application/',
        
        # HTML tags that can execute scripts
        r'<iframe[^>]*>',
        r'<object[^>]*>',
        r'<embed[^>]*>',
        r'<applet[^>]*>',
        r'<meta[^>]*http-equiv',
        r'<link[^>]*>',
        r'<style[^>]*>',
        r'<svg[^>]*>',
        
        # CSS expressions
        r'expression\s*\(',
        r'url\s*\(',
        r'@import',
        
        # Encoded attacks
        r'&lt;script',
        r'%3Cscript',
        r'&#x3C;script',
        
        # Unicode/HTML entities
        r'\\u[0-9a-fA-F]{4}',
        r'&\#[0-9]+;',
        r'&\#x[0-9a-fA-F]+;',
        
        # Base64 encoded scripts
        r'data:[^;]*base64',
        
        # Template injection
        r'\{\{.*?\}\}',
        r'\$\{.*?\}',
        
        # LDAP injection
        r'\*\)|\&\(|\|\(',
        
        # Path traversal
        r'\.\.[\\/]',
        r'\.\.%[0-9a-fA-F]{2}',
    ]
    
    text_lower = text.lower()
    
    for pattern in xss_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL):
            return True
    
    return False

def validate_user_input(data: Dict[str, Any], field_rules: Dict[str, Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Comprehensive input validation with enhanced security checks"""
    errors = []
    
    for field_name, rules in field_rules.items():
        value = data.get(field_name)
        
        # Check if required
        if rules.get('required', False) and not value:
            errors.append(f"{field_name} is required")
            continue
        
        if value is None:
            continue  # Skip optional empty fields
        
        # Ensure string for validation
        if not isinstance(value, str):
            errors.append(f"{field_name} must be a string")
            continue
        
        # Sanitize value
        value = sanitize_string_input(value)
        
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
            
            # Log XSS attempt
            log_security_event(
                'xss_attempt',
                f"XSS patterns detected in field: {field_name}",
                'unknown',  # IP will be added by caller
                severity='ERROR'
            )
        
        # SQL injection patterns
        if detect_sql_injection(value):
            errors.append(f"{field_name} contains invalid patterns")
            
            log_security_event(
                'sql_injection_attempt',
                f"SQL injection patterns detected in field: {field_name}",
                'unknown',
                severity='ERROR'
            )
        
        # Update sanitized value
        data[field_name] = value
    
    return len(errors) == 0, errors

def detect_sql_injection(text: str) -> bool:
    """Detect potential SQL injection patterns"""
    if not text or not isinstance(text, str):
        return False
    
    sql_patterns = [
        # Basic SQL injection
        r"'\s*(or|and)\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?",
        r"'\s*;\s*(drop|delete|update|insert|create)\s+",
        r"union\s+select",
        r"select\s+.*\s+from\s+",
        r"insert\s+into\s+",
        r"delete\s+from\s+",
        r"update\s+.*\s+set\s+",
        r"drop\s+(table|database)\s+",
        
        # Blind SQL injection
        r"'\s*(or|and)\s+\d+\s*=\s*\d+",
        r"'\s*(or|and)\s+['\"]?[a-z]+['\"]?\s*like\s*['\"]?",
        
        # Time-based injection
        r"(sleep|benchmark|waitfor)\s*\(",
        
        # Comment patterns
        r"--\s*$",
        r"/\*.*?\*/",
        
        # UNION attacks
        r"'\s*union\s+(all\s+)?select",
    ]
    
    text_lower = text.lower()
    
    for pattern in sql_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    return False

def log_security_event(event_type: str, details: str, client_ip: str, 
                      user: Optional[str] = None, severity: str = 'INFO'):
    """Enhanced security event logging with structured data"""
    timestamp = datetime.now()
    
    log_entry = {
        'timestamp': timestamp.isoformat(),
        'event_type': event_type,
        'client_ip': client_ip,
        'user': user or 'anonymous',
        'details': details,
        'severity': severity,
        'environment': ENVIRONMENT
    }
    
    # Store security event
    security_events[client_ip].append(log_entry)
    
    # Keep only recent events (memory management)
    cutoff = timestamp - timedelta(hours=24)
    security_events[client_ip] = [
        event for event in security_events[client_ip]
        if datetime.fromisoformat(event['timestamp']) > cutoff
    ]
    
    # Log to appropriate logger
    log_message = f"Security Event [{severity}]: {event_type} | IP: {client_ip} | User: {user or 'anonymous'} | {details}"
    
    if severity == 'ERROR':
        security_logger.error(log_message)
    elif severity == 'WARNING':
        security_logger.warning(log_message)
    else:
        security_logger.info(log_message)
    
    # Auto-block IPs with too many security violations
    if severity in ['ERROR', 'WARNING']:
        suspicious_patterns[client_ip] += 1
        
        if suspicious_patterns[client_ip] >= SUSPICIOUS_THRESHOLD:
            block_ip_temporarily(
                client_ip, 
                BLOCK_DURATION_MINUTES * 2,  # Longer block for repeated violations
                f"Multiple security violations ({suspicious_patterns[client_ip]})"
            )
    
    return log_entry

def get_security_summary(client_ip: str) -> Dict[str, Any]:
    """Get security summary for an IP address"""
    events = security_events.get(client_ip, [])
    
    return {
        'ip': client_ip,
        'total_events': len(events),
        'suspicious_score': suspicious_patterns.get(client_ip, 0),
        'is_blocked': is_ip_blocked(client_ip)[0],
        'recent_events': events[-5:] if events else [],
        'event_types': list(set(event['event_type'] for event in events))
    }

def cleanup_security_storage():
    """Periodic cleanup of security storage (call this regularly)"""
    now = time.time()
    cutoff = now - (24 * 60 * 60)  # 24 hours
    
    # Clean rate limiting storage
    for key in list(rate_limit_storage.keys()):
        rate_limit_storage[key] = [
            req_time for req_time in rate_limit_storage[key]
            if now - req_time < 3600  # Keep last hour
        ]
        if not rate_limit_storage[key]:
            del rate_limit_storage[key]
    
    # Clean expired blocks
    for ip in list(blocked_ips.keys()):
        if now >= blocked_ips[ip]['until']:
            del blocked_ips[ip]
    
    # Reduce suspicious pattern scores over time
    for ip in list(suspicious_patterns.keys()):
        suspicious_patterns[ip] = max(0, suspicious_patterns[ip] - 1)
        if suspicious_patterns[ip] == 0:
            del suspicious_patterns[ip]
    
    logger.info("Security storage cleanup completed")

class SecurityMiddleware:
    """Security middleware for request processing"""
    
    def __init__(self):
        self.last_cleanup = time.time()
    
    def process_request(self, handler) -> Tuple[bool, Optional[str]]:
        """Process incoming request for security violations"""
        client_ip = get_client_ip(handler.headers)
        
        # Periodic cleanup
        if time.time() - self.last_cleanup > 3600:  # Every hour
            cleanup_security_storage()
            self.last_cleanup = time.time()
        
        # Check IP validity
        is_suspicious, reason = is_suspicious_ip(client_ip)
        if is_suspicious:
            log_security_event(
                'suspicious_ip',
                f"Suspicious IP blocked: {reason}",
                client_ip,
                severity='WARNING'
            )
            return False, f"Request blocked: {reason}"
        
        # Check if IP is blocked
        is_blocked, remaining = is_ip_blocked(client_ip)
        if is_blocked:
            return False, f"IP temporarily blocked. Try again in {remaining} seconds"
        
        # Check general rate limiting
        endpoint = handler.path
        if not check_rate_limit(client_ip, endpoint):
            return False, "Too many requests. Please slow down."
        
        return True, None

# Create global security middleware instance
security_middleware = SecurityMiddleware()

# Export key functions
__all__ = [
    'get_client_ip', 'check_rate_limit', 'is_ip_blocked', 'block_ip_temporarily',
    'get_safe_origin', 'send_secure_response', 'send_secure_error',
    'validate_content_length', 'validate_json_input', 'validate_user_input',
    'detect_xss_patterns', 'log_security_event', 'get_security_summary',
    'security_middleware', 'cleanup_security_storage'
]