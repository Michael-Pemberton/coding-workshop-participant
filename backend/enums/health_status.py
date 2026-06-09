"""Project health (RAG) status enumeration."""
from enum import Enum

class HealthStatus(str, Enum):
    """RAG (Red/Amber/Green) health indicator for projects."""
    GREEN = "green"
    AMBER = "amber"
    RED = "red"
