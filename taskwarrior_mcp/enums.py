"""Enums for Taskwarrior MCP."""

from enum import Enum


class ResponseFormat(str, Enum):
    """Output format for tool responses."""

    MARKDOWN = "markdown"
    JSON = "json"


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
