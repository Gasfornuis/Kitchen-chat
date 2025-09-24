from http.server import BaseHTTPRequestHandler
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Debug endpoint to check system status"""
        try:
            debug_info = {
                "timestamp": datetime.now().isoformat(),
                "environment": {
                    "firebase_service_account_configured": bool(os.environ.get("FIREBASE_SERVICE_ACCOUNT")),
                    "firebase_secret_configured": bool(os.environ.get("FIREBASE_SECRET")),
                    "firebase_apps_initialized": len(firebase_admin._apps) > 0
                },
                "database": {
                    "status": "unknown"
                },
                "collections": {}
            }
            
            # Check Firebase connection
            try:
                if firebase_admin._apps:
                    db = firestore.client()
                    debug_info["database"]["status"] = "connected"
                    
                    # Check collections
                    try:
                        # Check Posts collection
                        posts_ref = db.collection("Posts").limit(1)
                        posts_sample = list(posts_ref.stream())
                        debug_info["collections"]["Posts"] = {
                            "accessible": True,
                            "sample_count": len(posts_sample),
                            "sample_document": {
                                "id": posts_sample[0].id if posts_sample else None,
                                "fields": list(posts_sample[0].to_dict().keys()) if posts_sample else []
                            }
                        }
                        
                        # Check Subjects collection
                        subjects_ref = db.collection("Subjects").limit(1)
                        subjects_sample = list(subjects_ref.stream())
                        debug_info["collections"]["Subjects"] = {
                            "accessible": True,
                            "sample_count": len(subjects_sample),
                            "sample_document": {
                                "id": subjects_sample[0].id if subjects_sample else None,
                                "fields": list(subjects_sample[0].to_dict().keys()) if subjects_sample else []
                            }
                        }
                        
                        # Check Users collection
                        users_ref = db.collection("Users").limit(1)
                        users_sample = list(users_ref.stream())
                        debug_info["collections"]["Users"] = {
                            "accessible": True,
                            "sample_count": len(users_sample),
                            "sample_document": {
                                "id": users_sample[0].id if users_sample else None,
                                "fields": list(users_sample[0].to_dict().keys()) if users_sample else []
                            }
                        }
                        
                    except Exception as collection_error:
                        debug_info["collections"]["error"] = str(collection_error)
                        
                else:
                    debug_info["database"]["status"] = "not_initialized"
                    
            except Exception as db_error:
                debug_info["database"]["status"] = "error"
                debug_info["database"]["error"] = str(db_error)
            
            # Set CORS headers
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            self.end_headers()
            
            # Send response
            response = json.dumps(debug_info, indent=2)
            self.wfile.write(response.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Debug endpoint error: {str(e)}")
            
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            error_response = {
                "error": "Debug endpoint failed",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()