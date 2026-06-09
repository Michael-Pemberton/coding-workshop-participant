"""User role enumeration for RBAC."""
from enum import Enum

class UserRole(str, Enum):
    """Defines the access levels for users in the system."""
    ADMIN = "admin"
    MANAGER = "manager"
    CONTRIBUTOR = "contributor"
    VIEWER = "viewer"
