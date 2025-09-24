# 🔒 Kitchen Chat - Security & Deployment Guide

## ⚠️ KRITIEK: VEREISTE CONFIGURATIE VOOR PRODUCTIE

### 1. **Environment Variables**

Voeg deze environment variables toe aan je hosting platform:

```bash
# Firebase Configuration
FIREBASE_SERVICE_ACCOUNT={"type": "service_account", "project_id": "...", ...}
FIREBASE_SECRET="your-super-secret-key-here"

# Allowed Origins (VERVANG MET JE EIGEN DOMEINEN!)
ALLOWED_ORIGINS="https://jouwdomein.com,https://www.jouwdomein.com"

# Rate Limiting Configuration
MAX_LOGIN_ATTEMPTS_PER_IP=10
MAX_API_CALLS_PER_MINUTE=60

# Session Configuration  
SESSION_DURATION_HOURS=8
SESSION_COOKIE_SECURE=true
```

### 2. **CORS Configuration Update**

**🚨 BELANGRIJK**: Update `ALLOWED_ORIGINS` in ALLE API files:

```python
# In api/security_utils.py, api/announcements.py, etc.
ALLOWED_ORIGINS = [
    'https://jouw-productie-domein.com',
    'https://www.jouw-productie-domein.com',
    # Verwijder localhost voor productie!
    # 'http://localhost:3000',  # Alleen voor development
]
```

### 3. **Firestore Security Rules**

Voeg deze security rules toe aan je Firestore:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Users collectie - alleen eigen data
    match /Users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    
    // Sessions collectie - server-only toegang
    match /Sessions/{sessionId} {
      allow read, write: if false; // Alleen server kan dit
    }
    
    // Posts - authenticated users kunnen lezen/schrijven
    match /Posts/{postId} {
      allow read: if request.auth != null;
      allow create: if request.auth != null && 
                   request.auth.token.name == resource.data.PostedBy;
    }
    
    // Announcements - alleen lezen voor alle users, admin voor schrijven
    match /announcements/{announcementId} {
      allow read: if request.auth != null;
      allow create, update, delete: if request.auth != null && 
                                       (request.auth.token.name == 'daan25' || 
                                        request.auth.token.name == 'gasfornuis');
    }
    
    // DirectMessages - alleen tussen betrokken users
    match /DirectMessages/{messageId} {
      allow read, create: if request.auth != null && 
                          (request.auth.token.name == resource.data.sender || 
                           request.auth.token.name == resource.data.recipient);
    }
    
    // UserProfiles - lezen voor alle users, schrijven alleen eigen profiel
    match /UserProfiles/{userId} {
      allow read: if request.auth != null;
      allow write: if request.auth != null && request.auth.uid == userId;
    }
  }
}
```

### 4. **Password Migration Script**

**🚨 BELANGRIJK**: Bestaande SHA-256 wachtwoorden moeten worden gemigreerd naar bcrypt:

```python
# password_migration.py
import bcrypt
from google.cloud import firestore

def migrate_passwords():
    db = firestore.Client()
    users_ref = db.collection('Users')
    
    for doc in users_ref.stream():
        user_data = doc.to_dict()
        password_hash = user_data.get('passwordHash', '')
        
        # Check if still using old SHA-256 format
        if ':' in password_hash and len(password_hash.split(':')) == 2:
            print(f"User {doc.id} needs password reset (old hash format)")
            
            # Mark for password reset
            doc.reference.update({
                'requiresPasswordReset': True,
                'oldPasswordHash': password_hash
            })

# Run eenmaal: python password_migration.py
```

### 5. **Nginx/Reverse Proxy Configuration**

Voor productie deployment:

```nginx
server {
    listen 443 ssl http2;
    server_name jouwdomein.com;
    
    # SSL Configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/s;
    
    location /api/auth {
        limit_req zone=auth burst=10 nodelay;
        proxy_pass http://your-backend:8000;
    }
    
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://your-backend:8000;
    }
    
    location / {
        root /var/www/kitchen-chat;
        try_files $uri $uri/ /index.html;
    }
}
```

## 🛡️ Security Checklist voor Productie

### ✅ **VEREIST VOOR GO-LIVE:**

- [ ] **CORS Origins** bijgewerkt naar productie domeinen
- [ ] **Environment Variables** ingesteld
- [ ] **Firestore Security Rules** geactiveerd  
- [ ] **HTTPS** geconfigureerd (SSL certificaat)
- [ ] **Password migration** uitgevoerd
- [ ] **Rate limiting** getest
- [ ] **Admin accounts** gevalideerd
- [ ] **Backup strategie** ingesteld
- [ ] **Monitoring** geconfigureerd
- [ ] **Error logging** getest

### 📊 **Monitoring & Alerting**

Stel alerts in voor:
- Hoge error rates (>5%)
- Failed authentication attempts (>10/min)
- Rate limit violations
- Admin actions (announcements)
- Unusual traffic patterns

### 🚀 **Deployment Commands**

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run password migration (eenmalig)
python password_migration.py

# 3. Deploy to production
# (gebruik je hosting platform's deployment process)

# 4. Test security
curl -H "Origin: https://evil.com" https://jouwapi.com/api/auth
# Moet CORS error geven!
```

### 🔍 **Security Testing**

Test deze scenario's:

1. **CORS Attack**: `curl -H "Origin: https://evil.com"`
2. **Rate Limiting**: Stuur 100 requests snel achter elkaar  
3. **Admin Impersonation**: Probeer admin functies zonder rechten
4. **Session Hijacking**: Probeer invalid tokens
5. **XSS Injection**: Stuur `<script>alert('xss')</script>`
6. **SQL Injection**: Probeer database queries in inputs
7. **Brute Force**: Probeer 20 verkeerde wachtwoorden

### ⚠️ **Bekende Limitaties**

- **Rate limiting** is in-memory (verdwijnt bij restart)
- **Demo mode** heeft beperkte security
- **Base64 images** zijn niet optimaal voor grote files
- **Geen CAPTCHA** tegen bots
- **Geen email verificatie** voor registratie

### 🔄 **Volgende Security Stappen (Medium Prioriteit)**

1. **Redis** voor persistent rate limiting
2. **JWT tokens** in plaats van session cookies  
3. **CAPTCHA** voor registratie/login
4. **Email verificatie** systeem
5. **2FA** voor admin accounts
6. **Content moderation** AI voor berichten
7. **File upload** security (virus scanning)
8. **IP geolocation** blocking

---

## 🆘 **Emergency Security Response**

Bij security incident:

1. **Block IP**: Voeg toe aan `blocked_ips` lijst
2. **Revoke Sessions**: Delete uit Sessions collectie  
3. **Check Logs**: Zoek naar patronen in security_logger
4. **Update Rules**: Firestore Security Rules aanscherpen
5. **Notify Users**: Via announcement systeem

---

**Laatste Update:** September 24, 2025  
**Security Status:** ✅ HOGE PRIORITEIT OPGELOST  
**Next Review:** Oktober 2025