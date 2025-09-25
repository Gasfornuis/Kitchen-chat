"""Secure Role-Based Access Control (RBAC) System for Kitchen Chat

CRITICAL SECURITY FIX:
- Prevents privilege escalation via displayName manipulation
- Uses immutable UID-based role checking
- Server-side only role validation
- Comprehensive audit logging
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
import firebase_admin
from firebase_admin import credentials, firestore as fb_firestore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security.rbac')

# Initialize Firebase if not already done
if not firebase_admin._apps:
    try:
        sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if sa_json:
            cred = credentials.Certificate(json.loads(sa_json))
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized for RBAC")
        else:
            logger.warning("RBAC running in demo mode - no Firebase credentials")
    except Exception as e:
        logger.error(f"Firebase RBAC initialization failed: {e}")

db = fb_firestore.client() if firebase_admin._apps else None

class RBACError(Exception):
    """RBAC-specific errors"""
    pass

def get_user_roles(uid: str) -> Dict[str, Any]:
    """Get user roles and permissions from database by UID
    
    Args:
        uid: Immutable user identifier (never displayName!)
        
    Returns:
        Dict with roles, permissions, isActive status
    """
    if not uid or not isinstance(uid, str):
        return {"roles": [], "permissions": [], "isActive": False}
    
    if not db:
        # Demo mode - only for testing
        if uid == "demo_admin_uid":
            return {
                "roles": ["admin"],
                "permissions": ["announcements", "moderation", "users"],
                "isActive": True
            }
        return {"roles": [], "permissions": [], "isActive": False}
    
    try:
        doc = db.collection("UserRoles").document(uid).get()
        
        if not doc.exists:
            return {"roles": [], "permissions": [], "isActive": False}
        
        data = doc.to_dict() or {}
        
        return {
            "roles": data.get("roles", []),
            "permissions": data.get("permissions", []),
            "isActive": data.get("isActive", False)
        }
        
    except Exception as e:
        logger.error(f"Error getting user roles for {uid}: {e}")
        return {"roles": [], "permissions": [], "isActive": False}

def is_admin(uid: Optional[str]) -> bool:
    """Check if user is admin by UID (NEVER by displayName!)
    
    Args:
        uid: Immutable user identifier
        
    Returns:
        True if user has admin role and is active
    """
    if not uid:
        return False
    
    try:
        user_data = get_user_roles(uid)
        
        # Must be active and have admin role
        if not user_data.get("isActive", False):
            return False
        
        roles = [role.lower() for role in user_data.get("roles", [])]
        is_admin_user = "admin" in roles
        
        if is_admin_user:
            security_logger.info(f"Admin access granted for UID: {uid}")
        
        return is_admin_user
        
    except Exception as e:
        logger.error(f"Admin check error for {uid}: {e}")
        return False

def has_permission(uid: Optional[str], permission: str) -> bool:
    """Check if user has specific permission
    
    Args:
        uid: Immutable user identifier
        permission: Permission to check (e.g., 'announcements', 'moderation')
        
    Returns:
        True if user has permission or is admin
    """
    if not uid or not permission:
        return False
    
    try:
        user_data = get_user_roles(uid)
        
        # Must be active
        if not user_data.get("isActive", False):
            return False
        
        # Admins have all permissions
        roles = [role.lower() for role in user_data.get("roles", [])]
        if "admin" in roles:
            return True
        
        # Check specific permission
        permissions = [perm.lower() for perm in user_data.get("permissions", [])]
        return permission.lower() in permissions
        
    except Exception as e:
        logger.error(f"Permission check error for {uid}, {permission}: {e}")
        return False

def log_admin_action(action: str, admin_uid: str, target: Optional[str] = None, 
                    client_ip: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
    """Log admin actions for audit trail
    
    Args:
        action: Description of admin action
        admin_uid: UID of admin performing action
        target: Target of action (e.g., username, announcement ID)
        client_ip: IP address of admin
        metadata: Additional context data
    """
    try:
        if not db:
            # Log to console in demo mode
            logger.info(f"ADMIN ACTION: {action} by {admin_uid} on {target}")
            return
        
        audit_entry = {
            "action": action,
            "adminUid": admin_uid,
            "target": target,
            "clientIp": client_ip,
            "metadata": metadata or {},
            "timestamp": fb_firestore.SERVER_TIMESTAMP,
            "isoTimestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        db.collection("AdminAuditLog").add(audit_entry)
        security_logger.info(f"Admin action logged: {action} by {admin_uid}")
        
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}")
        # Don't fail the main operation if logging fails

def require_admin(uid: Optional[str]) -> bool:
    """Require admin role, raise exception if not admin
    
    Args:
        uid: User UID to check
        
    Returns:
        True if admin
        
    Raises:
        RBACError: If user is not admin
    """
    if not is_admin(uid):
        raise RBACError(f"Admin access required")
    return True

def require_permission(uid: Optional[str], permission: str) -> bool:
    """Require specific permission, raise exception if not authorized
    
    Args:
        uid: User UID to check
        permission: Required permission
        
    Returns:
        True if authorized
        
    Raises:
        RBACError: If user doesn't have permission
    """
    if not has_permission(uid, permission):
        raise RBACError(f"Permission '{permission}' required")
    return True

def create_user_role(uid: str, roles: List[str], permissions: List[str], 
                    is_active: bool = True, created_by: Optional[str] = None) -> bool:
    """Create or update user role in database
    
    Args:
        uid: User UID
        roles: List of roles (e.g., ['admin', 'moderator'])
        permissions: List of permissions
        is_active: Whether role is active
        created_by: UID of admin creating this role
        
    Returns:
        True if successful
    """
    if not db:
        logger.warning("Cannot create user role in demo mode")
        return False
    
    try:
        role_data = {
            "uid": uid,
            "roles": roles,
            "permissions": permissions,
            "isActive": is_active,
            "createdBy": created_by,
            "createdAt": fb_firestore.SERVER_TIMESTAMP,
            "updatedAt": fb_firestore.SERVER_TIMESTAMP
        }
        
        db.collection("UserRoles").document(uid).set(role_data, merge=True)
        
        # Log the role creation
        if created_by:
            log_admin_action(
                f"Created role for user",
                created_by,
                target=uid,
                metadata={"roles": roles, "permissions": permissions}
            )
        
        logger.info(f"Created role for UID {uid} with roles: {roles}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create user role: {e}")
        return False

def revoke_user_role(uid: str, revoked_by: Optional[str] = None) -> bool:
    """Revoke user role (set inactive)
    
    Args:
        uid: User UID to revoke
        revoked_by: UID of admin revoking the role
        
    Returns:
        True if successful
    """
    if not db:
        logger.warning("Cannot revoke user role in demo mode")
        return False
    
    try:
        db.collection("UserRoles").document(uid).update({
            "isActive": False,
            "revokedBy": revoked_by,
            "revokedAt": fb_firestore.SERVER_TIMESTAMP
        })
        
        # Log the revocation
        if revoked_by:
            log_admin_action(
                f"Revoked role for user",
                revoked_by,
                target=uid
            )
        
        logger.info(f"Revoked role for UID {uid}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to revoke user role: {e}")
        return False

def get_audit_log(limit: int = 100) -> List[Dict[str, Any]]:
    """Get recent admin audit log entries
    
    Args:
        limit: Maximum number of entries to return
        
    Returns:
        List of audit log entries
    """
    if not db:
        return []
    
    try:
        docs = (db.collection("AdminAuditLog")
                 .order_by("timestamp", direction=fb_firestore.Query.DESCENDING)
                 .limit(limit)
                 .get())
        
        audit_entries = []
        for doc in docs:
            entry = doc.to_dict()
            entry["id"] = doc.id
            audit_entries.append(entry)
        
        return audit_entries
        
    except Exception as e:
        logger.error(f"Failed to get audit log: {e}")
        return []

# Export main functions
__all__ = [
    'is_admin', 'has_permission', 'log_admin_action', 
    'require_admin', 'require_permission', 'create_user_role', 
    'revoke_user_role', 'get_audit_log', 'RBACError'
]