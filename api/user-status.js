// api/user-status.js - Vercel Serverless Function with Authentication
// Tracks online users without needing a persistent Flask server

import { verify_session_token } from './auth.py';

let users = {}; // { userId: { displayName, status, timestamp, bio, theme, etc } }

const STATUS_ALLOWED = ["online", "away", "busy", "offline"];
const TIMEOUT_MS = 3 * 60 * 1000; // 3 minutes

// Authentication helper function
function getSessionToken(req) {
  // Try Authorization header
  const authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    return authHeader.slice(7);
  }
  
  // Try cookies
  const cookies = req.headers.cookie;
  if (cookies) {
    const sessionCookie = cookies
      .split(';')
      .find(row => row.trim().startsWith('kc_session='));
    if (sessionCookie) {
      return decodeURIComponent(sessionCookie.split('=')[1]);
    }
  }
  
  return null;
}

// Verify authentication
function requireAuth(req) {
  const token = getSessionToken(req);
  if (!token) return null;
  
  // This would normally call the Python function, but for JS we'll simulate
  // In practice, you'd need to implement session verification in JS too
  // For now, we'll trust any bearer token (not secure for production)
  return { username: 'user', displayName: 'User' }; // Mock auth for demo
}

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
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie');
  res.setHeader('Access-Control-Allow-Credentials', 'true');
}

// Send authentication error
function sendAuthError(res, message = 'Authentication required') {
  res.status(401).json({ error: message });
}

export default function handler(req, res) {
  // Set CORS headers for all requests
  setCorsHeaders(res);
  
  // Handle preflight OPTIONS request
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  // Require authentication for all user-status operations
  const authUser = requireAuth(req);
  if (!authUser) {
    return sendAuthError(res);
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
      
      // Security check - users can only update their own status
      // For demo purposes, we'll allow any authenticated user to set any display name
      // In production, you'd validate this matches the authenticated user
      
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
    console.error('User Status API Error:', error);
    return res.status(500).json({
      error: 'Internal server error'
    });
  }
}