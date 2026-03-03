from http.server import BaseHTTPRequestHandler
import json
import os
import logging
import traceback
import firebase_admin
from firebase_admin import credentials, firestore as admin_firestore

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import auth
try:
    from .auth import require_authentication
except ImportError:
    try:
        from auth import require_authentication
    except ImportError:
        require_authentication = None

# Firebase setup
db = None
try:
    if not firebase_admin._apps:
        sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if sa_json:
            cred = credentials.Certificate(json.loads(sa_json))
            firebase_admin.initialize_app(cred)
    if firebase_admin._apps:
        db = admin_firestore.client()
except Exception as e:
    logger.error(f"Firebase initialization failed: {e}")

# Gemini setup
genai = None
model = None
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai_module
        genai = genai_module
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash')
        logger.info("Gemini AI initialized successfully")
    except Exception as e:
        logger.error(f"Gemini initialization failed: {e}")
else:
    logger.warning("No GEMINI_API_KEY found - AI will return fallback responses")

FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")

SYSTEM_PROMPT = """You are KitchenAI, a friendly and helpful AI assistant living inside Kitchen Chat.
Rules:
- Keep responses short and conversational (max 200 words)
- Reply in the same language the user writes in
- Be helpful, friendly, and a bit playful
- You can answer questions, tell jokes, help with ideas, translate text, etc.
- If asked who you are: you're KitchenAI, the built-in AI assistant of Kitchen Chat
- Don't use markdown formatting (no ** or ## etc), just plain text
- Use emoji occasionally to be expressive 😊"""

def get_dm_id(user1, user2):
    users = sorted([user1.lower(), user2.lower()])
    return f"dm_{users[0]}_{users[1]}"

def send_response_with_cors(handler, data, status=200):
    try:
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        handler.send_response(status)
        handler.send_header('Content-Type', 'application/json; charset=utf-8')
        handler.send_header('Content-Length', str(len(body)))
        handler.send_header('Access-Control-Allow-Origin', '*')
        handler.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
        handler.end_headers()
        handler.wfile.write(body)
        return True
    except Exception as e:
        logger.error(f"Failed to send response: {e}")
        return False

def get_conversation_context(conversation_id, limit=10):
    """Get recent messages for context"""
    if not db:
        return []
    try:
        msgs = db.collection("DirectMessages") \
            .where("conversationId", "==", conversation_id) \
            .order_by("CreatedAt", direction=admin_firestore.Query.DESCENDING) \
            .limit(limit) \
            .stream()
        
        context = []
        for doc in msgs:
            data = doc.to_dict()
            sender = data.get("sender", "")
            content = data.get("content", "")
            if content:
                role = "model" if sender.lower() == "kitchenai" else "user"
                context.append({"role": role, "parts": [content]})
        
        context.reverse()  # Oldest first
        return context
    except Exception as e:
        logger.error(f"Error getting context: {e}")
        return []

def generate_ai_response(user_message, conversation_id):
    """Generate AI response using Gemini"""
    if not model:
        return "Hey! 👋 I'm KitchenAI, but my AI brain isn't connected yet. Ask the admin to set up the GEMINI_API_KEY! 🔧"
    
    try:
        # Get conversation history for context
        history = get_conversation_context(conversation_id)
        
        # Build the chat with system prompt
        chat = model.start_chat(history=history[:-1] if history else [])
        
        # Send the user's message with system context
        prompt = f"{SYSTEM_PROMPT}\n\nUser message: {user_message}"
        if not history:
            # First message - use full system prompt
            response = chat.send_message(prompt)
        else:
            # Ongoing conversation - just send user message
            response = chat.send_message(user_message)
        
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        logger.error(traceback.format_exc())
        return f"Oops, my brain had a hiccup! 🤯 Try again in a moment."

def save_ai_message(conversation_id, sender_name, content):
    """Save AI response as a DM in Firestore"""
    if not db:
        return None
    
    try:
        doc_data = {
            "content": content,
            "CreatedAt": admin_firestore.SERVER_TIMESTAMP,
            "sender": "KitchenAI",
            "recipient": sender_name,
            "conversationId": conversation_id,
            "messageType": "text",
            "secret": FIREBASE_SECRET
        }
        
        update_time, doc_ref = db.collection("DirectMessages").add(doc_data)
        return doc_ref.id
    except Exception as e:
        logger.error(f"Error saving AI message: {e}")
        return None

class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info(f"HTTP: {format % args}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def do_POST(self):
        try:
            # Auth check
            if require_authentication:
                current_user = require_authentication(self)
                if not current_user:
                    return send_response_with_cors(self, {"error": "Authentication required"}, 401)
                username = current_user.get("displayName", "Anonymous")
            else:
                username = "TestUser"

            # Read body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length <= 0:
                return send_response_with_cors(self, {"error": "No data provided"}, 400)

            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            user_message = data.get("message", "").strip()
            sender = data.get("sender", username)

            if not user_message:
                return send_response_with_cors(self, {"error": "No message provided"}, 400)

            # Generate conversation ID
            conversation_id = get_dm_id(sender, "KitchenAI")

            # Generate AI response
            ai_response = generate_ai_response(user_message, conversation_id)

            # Save AI response as DM
            msg_id = save_ai_message(conversation_id, sender, ai_response)

            logger.info(f"AI response to {sender}: {ai_response[:50]}...")

            return send_response_with_cors(self, {
                "ok": True,
                "response": ai_response,
                "messageId": msg_id
            }, 200)

        except json.JSONDecodeError:
            return send_response_with_cors(self, {"error": "Invalid JSON"}, 400)
        except Exception as e:
            logger.error(f"AI chat error: {e}")
            logger.error(traceback.format_exc())
            return send_response_with_cors(self, {"error": f"AI error: {str(e)}"}, 500)
