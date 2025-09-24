# 🔒 Kitchen Chat - Enhanced Security Deployment Guide v2.0

## ✅ **KRITIEKE BEVEILIGINGSVERBETERINGEN GEIMPLEMENTEERD**

### 🆕 **Nieuwe Beveiligingsfeatures**

#### 1. **Bcrypt Password Hashing** ✅
- **OPGELOST**: SHA-256 vervangen door bcrypt met cost factor 12
- **Automatische migratie** van oude SHA-256 passwords bij login
- **Secure salt generation** voor elke password

#### 2. **Enhanced Brute Force Protection** ✅
- **Exponential backoff**: 5 attempts = 5min, 10 = 30min, 15+ = 2hr
- **IP-based blocking** met automatische unblocking
- **Suspicious pattern detection** met auto-blocking

#### 3. **Advanced Input Validation** ✅
- **XSS detection** met 20+ pattern checks
- **SQL injection protection** met comprehensive patterns
- **JSON injection prevention** met depth limiting
- **Content sanitization** voor alle user input

#### 4. **Production-Ready CORS** ✅
- **NO WILDCARDS**: Expliciete origin whitelist
- **Environment-based configuration**: Dev vs Production origins
- **Security headers**: CSP, HSTS, X-Frame-Options, etc.

---

## 🚀 **PRODUCTIE DEPLOYMENT CHECKLIST**

### 🔴 **STAP 1: Environment Configuration**

```bash
# Verplichte environment variables
export ENVIRONMENT="production"
export FIREBASE_SERVICE_ACCOUNT='{"type": "service_account", ...}'
export FIREBASE_SECRET="$(openssl rand -hex 32)"
export ALLOWED_ORIGINS="https://kitchenchat.live,https://www.kitchenchat.live"

# Redis voor production rate limiting (aanbevolen)
export REDIS_URL="redis://localhost:6379/0"

# Security configuratie
export MAX_LOGIN_ATTEMPTS="5"
export BLOCK_DURATION_MINUTES="15"
export SESSION_DURATION="28800"  # 8 uur
export BCRYPT_ROUNDS="12"
```

### 🔴 **STAP 2: Dependency Installation**

```bash
# Installeer secure dependencies
pip install -r requirements-secure.txt

# Security audit
safety check
bandit -r api/

# Test installatie
python -c "import bcrypt; print('Bcrypt ready:', bcrypt.checkpw(b'test', bcrypt.hashpw(b'test', bcrypt.gensalt())))"
```

### 🔴 **STAP 3: Database Migration Script**

```python
# migrate_passwords.py - Voer éénmalig uit!
import bcrypt
from google.cloud import firestore
import os
import json

def migrate_sha256_to_bcrypt():
    # Initialize Firestore
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if not sa_json:
        print("ERROR: FIREBASE_SERVICE_ACCOUNT not set")
        return
    
    cred = credentials.Certificate(json.loads(sa_json))
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    users_ref = db.collection('Users')
    migrated_count = 0
    
    for doc in users_ref.stream():
        user_data = doc.to_dict()
        password_hash = user_data.get('passwordHash', '')
        
        # Check if it's old SHA-256 format (contains ':')
        if ':' in password_hash:
            print(f"User {doc.id} needs password reset (old SHA-256 format)")
            
            # Mark for password reset
            doc.reference.update({
                'requiresPasswordReset': True,
                'oldPasswordHash': password_hash,
                'migrationRequired': True,
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
            
            migrated_count += 1
    
    print(f"Migration complete. {migrated_count} users marked for password migration.")
    print("Users will be automatically migrated to bcrypt on next login.")

if __name__ == "__main__":
    migrate_sha256_to_bcrypt()
```

### 🔴 **STAP 4: Firestore Security Rules Update**

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Users collection - enhanced security
    match /Users/{userId} {
      allow read, write: if request.auth != null && 
                        request.auth.uid == userId &&
                        isValidUser(request.auth);
    }
    
    // Sessions collection - server-only toegang
    match /Sessions/{sessionId} {
      allow read, write: if false; // Alleen server toegang via Admin SDK
    }
    
    // Posts - authenticated users met content validation
    match /Posts/{postId} {
      allow read: if request.auth != null;
      allow create: if request.auth != null && 
                   isValidPostContent(resource.data) &&
                   request.auth.token.name == resource.data.PostedBy;
      allow update, delete: if request.auth != null &&
                           request.auth.token.name == resource.data.PostedBy;
    }
    
    // Announcements - admin only
    match /announcements/{announcementId} {
      allow read: if request.auth != null;
      allow create, update, delete: if request.auth != null && 
                                     isAdmin(request.auth.token.name);
    }
    
    // DirectMessages - enhanced privacy
    match /DirectMessages/{messageId} {
      allow read, create: if request.auth != null && 
                          (
                            request.auth.token.name == resource.data.sender || 
                            request.auth.token.name == resource.data.recipient
                          ) &&
                          isValidMessageContent(resource.data);
    }
    
    // Helper functions
    function isValidUser(auth) {
      return auth.token.email_verified == true || 
             auth.token.name != null;
    }
    
    function isValidPostContent(data) {
      return data.Content is string &&
             data.Content.size() <= 2000 &&
             data.PostedBy is string &&
             data.MessageType in ['text', 'announcement'];
    }
    
    function isValidMessageContent(data) {
      return data.content is string &&
             data.content.size() <= 500 &&
             data.sender is string &&
             data.recipient is string;
    }
    
    function isAdmin(username) {
      return username in ['daan25', 'gasfornuis']; // Update met jouw admin usernames
    }
  }
}
```

### 🔴 **STAP 5: Nginx Production Configuration**

```nginx
# /etc/nginx/sites-available/kitchenchat
server {
    listen 443 ssl http2;
    server_name kitchenchat.live www.kitchenchat.live;
    
    # SSL Configuration (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/kitchenchat.live/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/kitchenchat.live/privkey.pem;
    
    # SSL Security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Enhanced Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    
    # CSP
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https:; font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self';" always;
    
    # Rate Limiting Zones
    limit_req_zone $binary_remote_addr zone=api:10m rate=60r/m;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=10r/m;
    limit_req_zone $binary_remote_addr zone=global:10m rate=120r/m;
    
    # Global rate limit
    limit_req zone=global burst=20 nodelay;
    
    # API endpoints met specifieke limits
    location /api/auth {
        limit_req zone=auth burst=5 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /api/ {
        limit_req zone=api burst=10 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Static files
    location / {
        root /var/www/kitchen-chat;
        try_files $uri $uri/ /index.html;
        
        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
            expires 1y;
            add_header Cache-Control "public, no-transform";
        }
    }
    
    # Security - block common attack paths
    location ~ /\. {
        deny all;
        return 404;
    }
    
    location ~ \.(env|log|config)$ {
        deny all;
        return 404;
    }
}

# HTTP to HTTPS redirect
server {
    listen 80;
    server_name kitchenchat.live www.kitchenchat.live;
    return 301 https://$server_name$request_uri;
}
```

### 🔴 **STAP 6: Production Server Configuration**

```bash
# gunicorn_config.py
bind = "127.0.0.1:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 5

# Security
user = "www-data"
group = "www-data"
tmp_upload_dir = None

# Logging
accesslog = "/var/log/kitchen-chat/access.log"
errorlog = "/var/log/kitchen-chat/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Start server
# gunicorn -c gunicorn_config.py api.auth-v2:handler
```

---

## 🔍 **SECURITY TESTING CHECKLIST**

### ✅ **Automated Security Tests**

```bash
# 1. Dependency vulnerability scan
safety check --json

# 2. Code security analysis
bandit -r api/ -f json

# 3. Password hashing test
python -c "
import bcrypt
password = b'test123'
hashed = bcrypt.hashpw(password, bcrypt.gensalt(12))
print('Bcrypt test passed:', bcrypt.checkpw(password, hashed))
"

# 4. Rate limiting test
curl -H "Origin: https://evil.com" https://kitchenchat.live/api/auth
# Should return CORS error

# 5. Brute force protection test
for i in {1..20}; do
  curl -X POST https://kitchenchat.live/api/auth \
    -H "Content-Type: application/json" \
    -d '{"action":"login","username":"test","password":"wrong"}'
done
# Should get blocked after 5 attempts
```

### 🔍 **Manual Security Tests**

1. **XSS Injection Test**:
   ```javascript
   // Test in message input
   <script>alert('xss')</script>
   javascript:alert('xss')
   <iframe src="javascript:alert('xss')"></iframe>
   ```

2. **SQL Injection Test**:
   ```sql
   ' OR '1'='1' --
   '; DROP TABLE Users; --
   ' UNION SELECT * FROM Users --
   ```

3. **CORS Policy Test**:
   ```bash
   curl -H "Origin: https://evil.com" -H "Access-Control-Request-Method: POST" \
        -H "Access-Control-Request-Headers: Content-Type" \
        -X OPTIONS https://kitchenchat.live/api/auth
   ```

4. **Session Security Test**:
   ```bash
   # Test session cookie attributes
   curl -c cookies.txt -X POST https://kitchenchat.live/api/auth \
        -H "Content-Type: application/json" \
        -d '{"action":"login","username":"valid","password":"valid"}'
   
   # Check cookie flags: HttpOnly, Secure, SameSite
   cat cookies.txt
   ```

---

## 📨 **MONITORING & ALERTING**

### 📊 **Security Metrics**

```python
# security_monitor.py
import time
from collections import defaultdict

# Metrics to track
security_metrics = {
    'failed_logins_per_hour': 0,
    'blocked_ips_count': 0,
    'xss_attempts_per_day': 0,
    'sql_injection_attempts_per_day': 0,
    'rate_limit_violations_per_hour': 0,
    'cors_violations_per_day': 0,
    'suspicious_ips_detected': 0
}

# Alert thresholds
ALERT_THRESHOLDS = {
    'failed_logins_per_hour': 100,
    'xss_attempts_per_day': 10,
    'sql_injection_attempts_per_day': 5,
    'cors_violations_per_day': 50
}
```

### 📧 **Alert Configuration**

```bash
# Logwatch configuration for security events
# /etc/logwatch/conf/services/kitchen-chat-security.conf
Title = "Kitchen Chat Security Events"
LogFile = kitchen-chat-auth.log
Service = kitchen-chat-security

# Monitor for:
# - Multiple failed login attempts
# - XSS/SQL injection attempts  
# - CORS violations
# - Blocked IPs
# - Session hijacking attempts
```

---

## 🎯 **PERFORMANCE & SECURITY BALANCE**

### 🚀 **Production Optimizations**

1. **Redis Rate Limiting** (aanbevolen):
   ```python
   # Vervang in-memory storage
   import redis
   r = redis.Redis(host='localhost', port=6379, db=0)
   ```

2. **Session Storage Optimization**:
   ```python
   # Use Redis for session storage
   # More efficient than in-memory voor multiple servers
   ```

3. **Security Event Aggregation**:
   ```python
   # Batch security events to reduce I/O
   # Send to SIEM system (Splunk, ELK, etc.)
   ```

---

## 📝 **SECURITY CHANGELOG**

### v2.0 (September 2025)
- ✅ **CRITICAL**: Upgraded SHA-256 → bcrypt password hashing
- ✅ **HIGH**: Eliminated CORS wildcards
- ✅ **HIGH**: Enhanced brute force protection
- ✅ **MEDIUM**: Advanced XSS/SQL injection detection
- ✅ **MEDIUM**: Comprehensive input validation
- ✅ **LOW**: Improved error message sanitization

### Next Steps (v2.1)
- 🔄 JWT tokens instead of session cookies
- 🔄 Email verification for registration
- 🔄 2FA for admin accounts
- 🔄 CAPTCHA integration
- 🔄 Content moderation AI

---

## 🆆 **SUPPORT & CONTACT**

**Security Issues**: Rapporteer via private channel  
**General Issues**: GitHub Issues  
**Documentation**: Zie README.md  

**Last Updated**: September 24, 2025  
**Security Status**: ✅ **PRODUCTION READY**  
**Next Security Review**: Oktober 2025