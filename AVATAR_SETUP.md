# Custom Profile Pictures Setup Guide

This guide explains how to implement and deploy the custom profile pictures feature in Kitchen Chat.

## 🚀 Overview

The avatar system allows users to:
- Upload custom profile pictures (JPG, PNG, GIF)
- Automatic image processing (resize to 200x200px, crop to square)
- Fallback to text initials when no avatar is uploaded
- Support for both Firebase Storage and local storage

## 📋 Prerequisites

1. **Python Dependencies** (already added to requirements.txt):
   ```
   Pillow>=9.0.0
   python-multipart>=0.0.5
   ```

2. **Storage Solution** (choose one):
   - **Firebase Storage** (recommended for production)
   - **Local Storage** (for development/testing)

## 🔧 Installation Steps

### Step 1: Install Dependencies

```bash
# Install new Python packages
pip install Pillow>=9.0.0 python-multipart>=0.0.5

# Or install all requirements
pip install -r requirements.txt
```

### Step 2: Storage Configuration

#### Option A: Firebase Storage (Recommended)

1. **Enable Firebase Storage** in your Firebase Console:
   - Go to your Firebase project
   - Navigate to Storage → Get Started
   - Choose production mode or test mode

2. **Configure Storage Rules** (in Firebase Console → Storage → Rules):
   ```javascript
   rules_version = '2';
   service firebase.storage {
     match /b/{bucket}/o {
       // Allow authenticated users to upload avatars
       match /avatars/{userId}_{timestamp} {
         allow read: if true; // Public read access for avatars
         allow write: if request.auth != null 
                     && request.resource.size < 5 * 1024 * 1024 // 5MB limit
                     && request.resource.contentType.matches('image/.*');
       }
     }
   }
   ```

3. **Update Firebase Service Account** (if needed):
   - Ensure your `FIREBASE_SERVICE_ACCOUNT` environment variable includes Storage permissions

#### Option B: Local Storage (Development)

1. **Create avatars directory**:
   ```bash
   mkdir -p static/avatars
   ```

2. **Configure web server** to serve static files:
   - For Vercel: Add `vercel.json` configuration
   - For local development: Ensure `/static/` route serves files

### Step 3: Deploy API Endpoint

1. **Verify avatar-upload.py** is in your `/api/` directory
2. **Deploy to Vercel** (or your hosting platform):
   ```bash
   vercel --prod
   ```

### Step 4: Update Frontend

#### Option A: Replace index.html
```bash
# Backup current file
cp index.html index-backup.html

# Use new version with avatar support
cp index-with-avatars.html index.html
```

#### Option B: Manual Integration
Add avatar functionality to your existing `index.html`:

1. **Add avatar upload section** to profile modal
2. **Update CSS** with avatar styles
3. **Add JavaScript functions** for avatar handling
4. **Update message/user displays** to show avatars

### Step 5: Test the Implementation

1. **Open your Kitchen Chat application**
2. **Login and go to Profile settings**
3. **Test avatar upload**:
   - Select an image file (JPG, PNG, or GIF)
   - Verify preview shows correctly
   - Save profile and check if avatar appears in chat

## 🔍 Testing Checklist

- [ ] **File Upload**: Can select and preview images
- [ ] **Size Validation**: Rejects files over 5MB
- [ ] **Format Validation**: Only accepts JPG/PNG/GIF
- [ ] **Image Processing**: Resizes and crops to square
- [ ] **Storage**: Successfully uploads to Firebase/local
- [ ] **Display**: Avatar shows in messages and user list
- [ ] **Fallback**: Shows initials when no avatar
- [ ] **Removal**: Can remove avatar and return to initials
- [ ] **Mobile**: Works on mobile devices

## 🐛 Troubleshooting

### Common Issues

1. **"Pillow not installed" error**:
   ```bash
   pip install Pillow
   ```

2. **Firebase upload fails**:
   - Check Firebase Storage is enabled
   - Verify service account permissions
   - Check storage rules allow uploads

3. **"No module named 'PIL'" error**:
   ```bash
   pip uninstall PIL Pillow
   pip install Pillow
   ```

4. **File upload doesn't work**:
   - Check browser console for JavaScript errors
   - Verify `/api/avatar-upload` endpoint is accessible
   - Check Content-Type headers for multipart/form-data

5. **Images too large after processing**:
   - Adjust `avatar_size` in `avatar-upload.py`
   - Modify JPEG quality setting (currently 85)

### Debug Mode

Add debug logging to `avatar-upload.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📁 File Structure

After implementation, your project should have:

```
kitchen-chat/
├── api/
│   ├── avatar-upload.py          # New: Avatar upload handler
│   ├── user-profile.py           # Updated: Avatar URL support
│   └── ...
├── static/                       # New: For local storage
│   └── avatars/                  # New: Avatar files directory
├── index.html                    # Updated: With avatar support
├── index-with-avatars.html       # New: Test page
├── requirements.txt              # Updated: New dependencies
├── AVATAR_SETUP.md              # New: This guide
└── ...
```

## 🔒 Security Considerations

1. **File Size Limits**: 5MB maximum per file
2. **File Type Validation**: Only JPG, PNG, GIF allowed
3. **Image Processing**: Prevents malicious file uploads
4. **Authentication**: Only logged-in users can upload
5. **Storage Access**: Public read, authenticated write

## 🚀 Production Deployment

### Vercel Deployment

1. **Update vercel.json** (if needed):
   ```json
   {
     "functions": {
       "api/avatar-upload.py": {
         "maxDuration": 30
       }
     }
   }
   ```

2. **Set Environment Variables**:
   ```bash
   vercel env add FIREBASE_SERVICE_ACCOUNT
   vercel env add FIREBASE_SECRET
   ```

3. **Deploy**:
   ```bash
   vercel --prod
   ```

### Performance Optimization

1. **CDN**: Use Firebase Storage's built-in CDN
2. **Caching**: Set appropriate cache headers
3. **Compression**: Images are automatically optimized
4. **Lazy Loading**: Consider lazy loading for user lists

## 📚 API Reference

### POST /api/avatar-upload

**Purpose**: Upload and process user avatar

**Content-Type**: `multipart/form-data`

**Parameters**:
- `avatar` (file): Image file (JPG/PNG/GIF, max 5MB)
- `userId` (string): User identifier

**Response**:
```json
{
  "success": true,
  "avatarUrl": "https://storage.googleapis.com/...",
  "message": "Avatar uploaded successfully"
}
```

**Error Response**:
```json
{
  "error": "File too large (max 5MB)",
  "success": false
}
```

### PUT /api/user-profile

**Updated**: Now accepts `avatarUrl` field

**New Field**:
- `avatarUrl` (string|null): URL to user's avatar image

## 🎨 Customization

### Adjust Avatar Size

In `avatar-upload.py`, modify:
```python
self.avatar_size = 200  # Change to desired size
```

### Change Image Quality

In `avatar-upload.py`, modify:
```python
image.save(output, format='JPEG', optimize=True, quality=85)  # Adjust quality
```

### Custom Storage Location

For local storage, modify:
```python
avatar_dir = 'static/avatars'  # Change directory
```

## 🆘 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review browser console for JavaScript errors
3. Check server logs for Python errors
4. Verify all dependencies are installed
5. Test with a simple image file first

## ✅ Success!

Once implemented, users will be able to:
- Upload custom profile pictures
- See avatars in chat messages
- View avatars in online users list
- Enjoy a more personalized chat experience

The feature enhances user identity and makes the chat feel more modern and engaging!