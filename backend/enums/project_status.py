"""Project lifecycle status enumeration."""
from enum import Enum

class ProjectStatus(str, Enum):
    """Represents the current lifecycle state of a project."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"
