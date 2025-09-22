from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

# In-memory storage for demo; use a database for production!
online_users = {}  # { user_id: {"username": str, "status": str, "timestamp": float, "bio": str} }
STATUS_ALLOWED = ["online", "away", "busy", "offline"]

def cleanup_old_users():
    """Remove users who haven't been active for too long"""
    cutoff = time.time() - 180  # 3 minute timeout
    for user_id in list(online_users.keys()):
        user_data = online_users[user_id]
        if user_data["timestamp"] < cutoff or user_data["status"] == "offline":
            print(f"Cleaning up inactive user: {user_data['username']}")
            del online_users[user_id]

@app.route("/api/user-status", methods=["POST"])
def set_status():
    """
    Update or register user status
    Expected JSON:
    {
      "userId": "user_abc123",
      "displayName": "John Doe",
      "status": "online",
      "bio": "Hello world",
      "theme": "light",
      "notifications": true,
      "soundEnabled": true
    }
    """
    try:
        data = request.json
        user_id = data.get("userId")
        username = data.get("displayName")
        status = data.get("status", "online")
        bio = data.get("bio", "")
        theme = data.get("theme", "light")
        notifications = data.get("notifications", True)
        sound_enabled = data.get("soundEnabled", True)
        
        # Basic validation
        if not user_id or not username or status not in STATUS_ALLOWED:
            return jsonify({"error": "Invalid data. userId, displayName and valid status required."}), 400
        
        # Update user info
        online_users[user_id] = {
            "uid": user_id,
            "displayName": username,
            "status": status,
            "timestamp": time.time(),
            "lastSeen": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "bio": bio,
            "theme": theme,
            "notifications": notifications,
            "soundEnabled": sound_enabled,
            "photoURL": ""  # Can be added later
        }
        
        cleanup_old_users()
        
        print(f"User status updated: {username} -> {status}")
        print(f"Currently online users: {len(online_users)}")
        
        return jsonify({
            "uid": user_id,
            "displayName": username,
            "status": status,
            "lastSeen": online_users[user_id]["lastSeen"]
        })
        
    except Exception as e:
        print(f"Error updating user status: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route("/api/user-status", methods=["PUT"])
def update_status_only():
    """
    Update only the status of an existing user
    Expected JSON:
    {
      "userId": "user_abc123",
      "status": "away"
    }
    """
    try:
        data = request.json
        user_id = data.get("userId")
        status = data.get("status")
        
        # Basic validation
        if not user_id or status not in STATUS_ALLOWED:
            return jsonify({"error": "Invalid data. userId and valid status required."}), 400
        
        # Check if user exists
        if user_id not in online_users:
            return jsonify({"error": "User not found"}), 404
        
        # Update status and timestamp
        online_users[user_id]["status"] = status
        online_users[user_id]["timestamp"] = time.time()
        online_users[user_id]["lastSeen"] = time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        cleanup_old_users()
        
        user_data = online_users[user_id]
        print(f"User status updated: {user_data['displayName']} -> {status}")
        
        return jsonify({
            "uid": user_id,
            "displayName": user_data["displayName"],
            "status": status,
            "lastSeen": user_data["lastSeen"]
        })
        
    except Exception as e:
        print(f"Error updating user status: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route("/api/user-status", methods=["GET"])
def get_online_users():
    """
    Get list of currently active users
    Returns JSON like:
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
    """
    try:
        cleanup_old_users()
        
        # Return users that are not offline
        users = [
            {
                "uid": user_data["uid"],
                "displayName": user_data["displayName"],
                "status": user_data["status"],
                "lastSeen": user_data["lastSeen"],
                "photoURL": user_data.get("photoURL", "")
            }
            for user_data in online_users.values()
            if user_data["status"] != "offline"
        ]
        
        print(f"Returning {len(users)} online users")
        return jsonify({"users": users})
        
    except Exception as e:
        print(f"Error getting online users: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route("/api/user-status/health", methods=["GET"])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "online_users_count": len(online_users)
    })

@app.route("/api/user-status/debug", methods=["GET"])
def debug_info():
    """Debug endpoint to see all stored users (for development only)"""
    return jsonify({
        "online_users": online_users,
        "count": len(online_users),
        "timestamp": time.time()
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"Starting User Status API on port {port}")
    print("Endpoints:")
    print("  POST /api/user-status - Register/update user")
    print("  PUT /api/user-status - Update user status only")
    print("  GET /api/user-status - Get online users")
    print("  GET /api/user-status/health - Health check")
    print("  GET /api/user-status/debug - Debug info")
    app.run(host="0.0.0.0", port=port, debug=True)