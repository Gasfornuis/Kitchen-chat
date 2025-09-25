#!/usr/bin/env python3
"""Seed Admin Users Script - Secure UID-based RBAC

This script creates initial admin roles in the UserRoles collection.
Use this ONCE after deploying the RBAC system to seed your admin users.

Usage:
    # Set environment variable with Firebase service account JSON
    export FIREBASE_SERVICE_ACCOUNT='{"type":"service_account",...}'
    
    # Run script with admin UIDs (get these from Firebase Auth console)
    python scripts/seed_admins.py --uids "admin_uid_1" "admin_uid_2"
    
    # Or with usernames (script will look up UIDs)
    python scripts/seed_admins.py --usernames "daan25" "gasfornuis"

IMPORTANT: Only run this script ONCE and keep it secure!
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from typing import List, Optional

# Add the api directory to the path so we can import rbac
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'api'))

try:
    import firebase_admin
    from firebase_admin import credentials, firestore as fb_firestore
except ImportError:
    print("Error: firebase-admin package not installed.")
    print("Install with: pip install firebase-admin")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    if firebase_admin._apps:
        return fb_firestore.client()
    
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if not sa_json:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT environment variable is required")
    
    try:
        cred = credentials.Certificate(json.loads(sa_json))
        firebase_admin.initialize_app(cred, name="seed_admins")
        logger.info("Firebase initialized for admin seeding")
        return fb_firestore.client(app=firebase_admin.get_app("seed_admins"))
    except Exception as e:
        raise ValueError(f"Failed to initialize Firebase: {e}")

def find_uid_by_username(db, username: str) -> Optional[str]:
    """Find UID by username in Users collection
    
    This assumes your Users collection has documents with username field.
    Adjust the query based on your actual user storage structure.
    """
    try:
        # Try to find user by username
        users = db.collection("Users").where("username", "==", username.lower()).limit(1).get()
        
        if users:
            user_doc = users[0]
            user_data = user_doc.to_dict()
            
            # Check if UID is stored in the document
            uid = user_data.get('uid') or user_data.get('userId') or user_doc.id
            
            if uid:
                logger.info(f"Found UID for username '{username}': {uid[:8]}...")
                return uid
        
        # If not found, try document ID approach (if usernames are used as doc IDs)
        user_doc = db.collection("Users").document(username.lower()).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            uid = user_data.get('uid') or user_data.get('userId') or user_doc.id
            if uid:
                logger.info(f"Found UID for username '{username}': {uid[:8]}...")
                return uid
        
        logger.warning(f"No UID found for username: {username}")
        return None
        
    except Exception as e:
        logger.error(f"Error finding UID for username {username}: {e}")
        return None

def create_admin_role(db, uid: str, username: Optional[str] = None) -> bool:
    """Create admin role for a user UID"""
    try:
        # Check if role already exists
        existing_doc = db.collection("UserRoles").document(uid).get()
        if existing_doc.exists:
            existing_data = existing_doc.to_dict()
            if existing_data.get('isActive', False) and 'admin' in existing_data.get('roles', []):
                logger.info(f"Admin role already exists for UID: {uid[:8]}...")
                return True
        
        # Create admin role data
        admin_role_data = {
            "uid": uid,
            "roles": ["admin"],
            "permissions": [
                "announcements",
                "moderation",
                "users",
                "audit"
            ],
            "isActive": True,
            "createdBy": "system_seed",
            "createdAt": fb_firestore.SERVER_TIMESTAMP,
            "seededAt": datetime.utcnow().isoformat() + "Z",
            "seededUsername": username  # For reference only
        }
        
        # Set the role document
        db.collection("UserRoles").document(uid).set(admin_role_data, merge=True)
        
        logger.info(f"✅ Created admin role for UID: {uid[:8]}... (username: {username or 'unknown'})")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create admin role for UID {uid}: {e}")
        return False

def seed_admins_by_uids(db, uids: List[str]) -> int:
    """Seed admin roles by UIDs"""
    success_count = 0
    
    for uid in uids:
        if not uid or not isinstance(uid, str):
            logger.warning(f"Invalid UID: {uid}")
            continue
        
        if create_admin_role(db, uid):
            success_count += 1
    
    return success_count

def seed_admins_by_usernames(db, usernames: List[str]) -> int:
    """Seed admin roles by usernames (look up UIDs first)"""
    success_count = 0
    
    for username in usernames:
        if not username or not isinstance(username, str):
            logger.warning(f"Invalid username: {username}")
            continue
        
        # Find UID for this username
        uid = find_uid_by_username(db, username)
        if not uid:
            logger.error(f"❌ Cannot seed admin for username '{username}' - UID not found")
            continue
        
        if create_admin_role(db, uid, username):
            success_count += 1
    
    return success_count

def verify_admin_setup(db, uids: List[str]) -> bool:
    """Verify that admin roles were created correctly"""
    logger.info("\n🔍 Verifying admin setup...")
    
    all_verified = True
    
    for uid in uids:
        try:
            doc = db.collection("UserRoles").document(uid).get()
            if not doc.exists:
                logger.error(f"❌ Admin role not found for UID: {uid[:8]}...")
                all_verified = False
                continue
            
            data = doc.to_dict()
            is_active = data.get('isActive', False)
            roles = data.get('roles', [])
            has_admin = 'admin' in roles
            
            if is_active and has_admin:
                logger.info(f"✅ Admin role verified for UID: {uid[:8]}...")
            else:
                logger.error(f"❌ Admin role invalid for UID: {uid[:8]}... (active: {is_active}, admin: {has_admin})")
                all_verified = False
                
        except Exception as e:
            logger.error(f"❌ Verification failed for UID {uid[:8]}...: {e}")
            all_verified = False
    
    return all_verified

def main():
    parser = argparse.ArgumentParser(
        description="Seed admin users for Kitchen Chat RBAC system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Seed by UIDs (recommended)
  python scripts/seed_admins.py --uids "abc123def456" "xyz789uvw012"
  
  # Seed by usernames (will look up UIDs)
  python scripts/seed_admins.py --usernames "daan25" "gasfornuis"
  
  # Verify existing admin setup
  python scripts/seed_admins.py --verify --uids "abc123def456"
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--uids", 
        nargs="+", 
        help="Admin UIDs to seed (recommended - more secure)"
    )
    group.add_argument(
        "--usernames", 
        nargs="+", 
        help="Admin usernames to seed (will look up UIDs)"
    )
    
    parser.add_argument(
        "--verify", 
        action="store_true", 
        help="Verify admin setup after seeding"
    )
    
    parser.add_argument(
        "--permissions", 
        nargs="*", 
        default=["announcements", "moderation", "users", "audit"],
        help="Custom permissions to grant (default: announcements moderation users audit)"
    )
    
    args = parser.parse_args()
    
    # Initialize Firebase
    try:
        db = initialize_firebase()
    except Exception as e:
        logger.error(f"❌ Firebase initialization failed: {e}")
        logger.error("Make sure FIREBASE_SERVICE_ACCOUNT environment variable is set")
        sys.exit(1)
    
    success_count = 0
    uids_to_verify = []
    
    # Seed admins
    if args.uids:
        logger.info(f"🌱 Seeding {len(args.uids)} admin(s) by UID...")
        success_count = seed_admins_by_uids(db, args.uids)
        uids_to_verify = args.uids
        
    elif args.usernames:
        logger.info(f"🌱 Seeding {len(args.usernames)} admin(s) by username...")
        success_count = seed_admins_by_usernames(db, args.usernames)
        # Collect UIDs for verification
        for username in args.usernames:
            uid = find_uid_by_username(db, username)
            if uid:
                uids_to_verify.append(uid)
    
    # Report results
    logger.info(f"\n📊 Seeding completed: {success_count} admin(s) created successfully")
    
    if success_count == 0:
        logger.error("❌ No admin roles were created. Check the logs above for errors.")
        sys.exit(1)
    
    # Verify if requested
    if args.verify and uids_to_verify:
        if verify_admin_setup(db, uids_to_verify):
            logger.info("\n✅ All admin roles verified successfully!")
        else:
            logger.error("\n❌ Some admin roles failed verification")
            sys.exit(1)
    
    logger.info("\n🎉 Admin seeding completed successfully!")
    logger.info("\n📋 Next steps:")
    logger.info("1. Deploy the updated code with RBAC system")
    logger.info("2. Test admin functionality with your seeded admin accounts")
    logger.info("3. Revoke or update roles as needed using the RBAC API")
    logger.info("4. Monitor admin actions in the AdminAuditLog collection")

if __name__ == "__main__":
    main()