# 🚀 Kitchen Chat API Setup

## User Status API Setup

To enable **real online users tracking** instead of demo data, you need to run the Flask API separately.

### 🔧 **Installation & Setup**

1. **Install Dependencies**
   ```bash
   pip install flask flask-cors
   ```

2. **Run the User Status API**
   ```bash
   cd api/
   python user-status-simple.py
   ```
   
   The API will start on `http://localhost:5001`

3. **Configure Frontend**
   - The frontend automatically tries to connect to `/api/user-status-simple`
   - If running locally, make sure your API is accessible at this endpoint
   - For production, update the API URLs in `index.html`

### 📡 **API Endpoints**

#### **POST /api/user-status-simple**
Register or update a user profile:
```json
{
  "userId": "user_abc123",
  "displayName": "John Doe",
  "status": "online",
  "bio": "Hello world",
  "theme": "light",
  "notifications": true,
  "soundEnabled": true
}
```

#### **PUT /api/user-status-simple**
Update user status only:
```json
{
  "userId": "user_abc123",
  "status": "away"
}
```

#### **GET /api/user-status-simple**
Get list of online users:
```json
{
  "users": [
    {
      "uid": "user_abc123",
      "displayName": "John Doe",
      "status": "online",
      "lastSeen": "2025-09-22T23:45:00.000Z",
      "photoURL": ""
    }
  ]
}
```

### ✅ **Testing Multiple Users**

1. **Open two different browsers** (Chrome & Firefox)
2. **Go to your Kitchen Chat URL** in both
3. **Create different profiles** in each browser:
   - Browser 1: "Alice" → status "online"
   - Browser 2: "Bob" → status "away"
4. **Check the users list** - you should now see both users!

### 🔍 **Debug Endpoints**

- **GET /api/user-status-simple/health** - Check if API is running
- **GET /api/user-status-simple/debug** - See all stored users (development only)

### 🎯 **How It Works**

1. **User Registration**: When someone saves their profile → registered in API
2. **Heartbeat System**: Every 60 seconds → status update to stay online
3. **Auto Cleanup**: Users inactive for 3+ minutes → automatically removed
4. **Real-time Updates**: Frontend polls every 15 seconds for new users
5. **Status Changes**: Immediately synced when users change status

### 🚨 **Troubleshooting**

**Problem**: Still seeing only yourself?
- Check browser console (F12) for API errors
- Verify the Flask API is running on port 5001
- Test with `/api/user-status-simple/health` endpoint
- Make sure CORS is enabled (included in the Flask code)

**Problem**: Users disappearing?
- Check the 3-minute timeout in the API
- Verify heartbeat system is working (check console logs)
- Make sure users aren't setting status to "offline"

### 🎉 **Production Deployment**

For production (Vercel/etc.):
1. Replace `user-status-simple.py` with a Vercel-compatible serverless function
2. Use a proper database instead of in-memory storage
3. Add authentication if needed
4. Update API URLs in frontend to match your deployment