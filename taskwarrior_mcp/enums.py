"""Enums for Taskwarrior MCP."""

from enum import Enum


class ResponseFormat(str, Enum):
    """Output format for tool responses."""

    CONCISE = "concise"  # Minimal output for chaining (~50% smaller than markdown)
    MARKDOWN = "markdown"  # Human-readable (default)
    JSON = "json"  # Machine-readable with all fields


class TaskStatus(str, Enum):
    """Task status filter options."""

    PENDING = "pending"
    COMPLETED = "completed"
    DELETED = "deleted"
    ALL = "all"


class Priority(str, Enum):
    """Task priority levels."""

    HIGH = "H"
    MEDIUM = "M"
    LOW = "L"
    NONE = ""
