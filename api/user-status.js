// api/user-status.js - Vercel Serverless Function
// Tracks online users without needing a persistent Flask server

let users = {}; // { userId: { displayName, status, timestamp, bio, theme, etc } }

const STATUS_ALLOWED = ["online", "away", "busy", "offline"];
const TIMEOUT_MS = 3 * 60 * 1000; // 3 minutes

// Clean up inactive users
function cleanup() {
  const now = Date.now();
  Object.keys(users).forEach((userId) => {
    const user = users[userId];
    if (now - user.timestamp > TIMEOUT_MS || user.status === "offline") {
      console.log(`Cleaning up inactive user: ${user.displayName}`);
      delete users[userId];
    }
  });
}

// Set CORS headers
function setCorsHeaders(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
}

export default function handler(req, res) {
  // Set CORS headers for all requests
  setCorsHeaders(res);
  
  // Handle preflight OPTIONS request
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  // Clean up old users on every request
  cleanup();
  
  try {
    if (req.method === 'POST') {
      // Register or update user profile
      const {
        userId,
        displayName,
        status = 'online',
        bio = '',
        theme = 'light',
        notifications = true,
        soundEnabled = true,
        photoURL = ''
      } = req.body;
      
      // Validation
      if (!userId || !displayName || !STATUS_ALLOWED.includes(status)) {
        return res.status(400).json({
          error: 'Invalid data. userId, displayName and valid status required.'
        });
      }
      
      // Update/create user
      users[userId] = {
        uid: userId,
        displayName: displayName,
        status: status,
        timestamp: Date.now(),
        lastSeen: new Date().toISOString(),
        bio: bio,
        theme: theme,
        notifications: notifications,
        soundEnabled: soundEnabled,
        photoURL: photoURL
      };
      
      console.log(`User registered/updated: ${displayName} -> ${status}`);
      console.log(`Total online users: ${Object.keys(users).length}`);
      
      return res.status(201).json({
        uid: userId,
        displayName: displayName,
        status: status,
        lastSeen: users[userId].lastSeen
      });
      
    } else if (req.method === 'PUT') {
      // Update user status only
      const { userId, status } = req.body;
      
      // Validation
      if (!userId || !STATUS_ALLOWED.includes(status)) {
        return res.status(400).json({
          error: 'Invalid data. userId and valid status required.'
        });
      }
      
      // Check if user exists
      if (!users[userId]) {
        return res.status(404).json({
          error: 'User not found'
        });
      }
      
      // Update status and timestamp
      users[userId].status = status;
      users[userId].timestamp = Date.now();
      users[userId].lastSeen = new Date().toISOString();
      
      console.log(`User status updated: ${users[userId].displayName} -> ${status}`);
      
      return res.status(200).json({
        uid: userId,
        displayName: users[userId].displayName,
        status: status,
        lastSeen: users[userId].lastSeen
      });
      
    } else if (req.method === 'GET') {
      // Get list of online users
      const onlineUsers = Object.values(users)
        .filter(user => user.status !== 'offline')
        .map(user => ({
          uid: user.uid,
          displayName: user.displayName,
          status: user.status,
          lastSeen: user.lastSeen,
          photoURL: user.photoURL || ''
        }));
      
      console.log(`Returning ${onlineUsers.length} online users`);
      
      return res.status(200).json({
        users: onlineUsers
      });
      
    } else {
      // Method not allowed
      return res.status(405).json({
        error: 'Method not allowed'
      });
    }
    
  } catch (error) {
    console.error('API Error:', error);
    return res.status(500).json({
      error: 'Internal server error'
    });
  }
}