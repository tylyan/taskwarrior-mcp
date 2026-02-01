"""
MCP Server for Taskwarrior.

This server provides tools to interact with Taskwarrior CLI, enabling task
management operations including listing, creating, completing, modifying,
and organizing tasks with projects and tags.
"""

# Re-export enums
from taskwarrior_mcp.enums import Priority, ResponseFormat, TaskStatus

# Re-export models
from taskwarrior_mcp.models import (
    AddTaskInput,
    AnnotateTaskInput,
    BlockedInput,
    BlockedTaskInfo,
    BottleneckInfo,
    BulkGetTasksInput,
    CompleteTaskInput,
    ComputedInsights,
    ContextInput,
    DeleteTaskInput,
    DependenciesInput,
    GetTaskInput,
    ListProjectsInput,
    ListTagsInput,
    ListTasksInput,
    ModifyTaskInput,
    ProjectSummaryInput,
    ReadyInput,
    ScoredTask,
    StartTaskInput,
    StopTaskInput,
    SuggestInput,
    TaskAnnotation,
    TaskModel,
    TriageInput,
    UndoInput,
)

# Re-export MCP server instance
from taskwarrior_mcp.server import mcp

# Re-export tools
from taskwarrior_mcp.tools import (
    taskwarrior_add,
    taskwarrior_annotate,
    taskwarrior_blocked,
    taskwarrior_bulk_get,
    taskwarrior_complete,
    taskwarrior_context,
    taskwarrior_delete,
    taskwarrior_dependencies,
    taskwarrior_get,
    taskwarrior_list,
    taskwarrior_modify,
    taskwarrior_project_summary,
    taskwarrior_projects,
    taskwarrior_ready,
    taskwarrior_start,
    taskwarrior_stop,
    taskwarrior_suggest,
    taskwarrior_summary,
    taskwarrior_tags,
    taskwarrior_triage,
    taskwarrior_undo,
)

# Re-export utilities (including private functions used by tests)
from taskwarrior_mcp.utils import (
    _format_task_concise,
    _format_task_markdown,
    _format_tasks_concise,
    _format_tasks_markdown,
    _get_tasks_json,
    _parse_task,
    _parse_tasks,
    _run_task_command,
)

__all__ = [
    # Enums
    "ResponseFormat",
    "TaskStatus",
    "Priority",
    # Task models
    "TaskAnnotation",
    "TaskModel",
    # Core input models
    "ListTasksInput",
    "AddTaskInput",
    "CompleteTaskInput",
    "ModifyTaskInput",
    "DeleteTaskInput",
    "AnnotateTaskInput",
    "GetTaskInput",
    "BulkGetTasksInput",
    "ListProjectsInput",
    "ProjectSummaryInput",
    "ListTagsInput",
    "StartTaskInput",
    "StopTaskInput",
    "UndoInput",
    # Agent intelligence input models
    "SuggestInput",
    "ReadyInput",
    "BlockedInput",
    "DependenciesInput",
    "TriageInput",
    "ContextInput",
    # Intelligence output models
    "ScoredTask",
    "BlockedTaskInfo",
    "BottleneckInfo",
    "ComputedInsights",
    # Utility functions
    "_run_task_command",
    "_get_tasks_json",
    "_parse_task",
    "_parse_tasks",
    "_format_task_concise",
    "_format_task_markdown",
    "_format_tasks_concise",
    "_format_tasks_markdown",
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
    # Intelligence tools
    "taskwarrior_suggest",
    "taskwarrior_ready",
    "taskwarrior_blocked",
    "taskwarrior_dependencies",
    "taskwarrior_triage",
    "taskwarrior_context",
    # MCP server instance
    "mcp",
]
