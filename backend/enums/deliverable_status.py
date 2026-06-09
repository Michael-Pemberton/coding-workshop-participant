"""Deliverable progress status enumeration."""
from enum import Enum

class DeliverableStatus(str, Enum):
    """Tracks the completion state of a project deliverable."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
