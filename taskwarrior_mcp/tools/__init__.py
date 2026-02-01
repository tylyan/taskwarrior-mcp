"""MCP tool definitions for Taskwarrior."""

# Import all tools to register them with the MCP server
from taskwarrior_mcp.tools.core import (
    taskwarrior_add,
    taskwarrior_annotate,
    taskwarrior_bulk_get,
    taskwarrior_complete,
    taskwarrior_delete,
    taskwarrior_get,
    taskwarrior_list,
    taskwarrior_modify,
    taskwarrior_overview,
    taskwarrior_project_summary,
    taskwarrior_projects,
    taskwarrior_start,
    taskwarrior_stop,
    taskwarrior_summary,
    taskwarrior_tags,
    taskwarrior_undo,
)
from taskwarrior_mcp.tools.intelligence import (
    taskwarrior_blocked,
    taskwarrior_context,
    taskwarrior_dependencies,
    taskwarrior_ready,
    taskwarrior_suggest,
    taskwarrior_triage,
)

__all__ = [
    # Core tools
    "taskwarrior_list",
    "taskwarrior_add",
    "taskwarrior_complete",
    "taskwarrior_modify",
    "taskwarrior_delete",
    "taskwarrior_get",
    "taskwarrior_bulk_get",
    "taskwarrior_annotate",
    "taskwarrior_start",
    "taskwarrior_stop",
    "taskwarrior_projects",
    "taskwarrior_project_summary",
    "taskwarrior_tags",
    "taskwarrior_undo",
    "taskwarrior_summary",
    "taskwarrior_overview",
    # Intelligence tools
    "taskwarrior_suggest",
    "taskwarrior_ready",
    "taskwarrior_blocked",
    "taskwarrior_dependencies",
    "taskwarrior_triage",
    "taskwarrior_context",
]
