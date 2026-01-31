#!/usr/bin/env python3
"""
MCP Server for Taskwarrior.

This server provides tools to interact with Taskwarrior CLI, enabling task
management operations including listing, creating, completing, modifying,
and organizing tasks with projects and tags.
"""

import json
import shlex
import subprocess
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Initialize the MCP server
mcp = FastMCP("taskwarrior_mcp")


# ============================================================================
# Enums
# ============================================================================


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


# ============================================================================
# Pydantic Input Models
# ============================================================================


class ListTasksInput(BaseModel):
    """Input model for listing tasks."""

    model_config = ConfigDict(str_strip_whitespace=True)

    filter: str | None = Field(
        default=None,
        description="Taskwarrior filter expression (e.g., 'project:work', '+urgent', 'due:today')",
    )
    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        description="Filter by task status: pending, completed, deleted, or all",
    )
    limit: int | None = Field(
        default=50, description="Maximum number of tasks to return", ge=1, le=500
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable",
    )


class AddTaskInput(BaseModel):
    """Input model for adding a new task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    description: str = Field(
        ..., description="Task description (required)", min_length=1, max_length=1000
    )
    project: str | None = Field(default=None, description="Project name to assign the task to")
    priority: Priority | None = Field(
        default=None, description="Task priority: H (high), M (medium), L (low)"
    )
    due: str | None = Field(
        default=None,
        description="Due date (e.g., 'today', 'tomorrow', '2024-12-31', 'eow' for end of week)",
    )
    tags: list[str] | None = Field(
        default=None, description="List of tags to apply (without '+' prefix)", max_length=20
    )
    depends: str | None = Field(
        default=None, description="Task ID(s) this task depends on (comma-separated)"
    )

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Description cannot be empty")
        return v.strip()


class CompleteTaskInput(BaseModel):
    """Input model for completing a task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(..., description="Task ID or UUID to complete", min_length=1)


class ModifyTaskInput(BaseModel):
    """Input model for modifying a task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(..., description="Task ID or UUID to modify", min_length=1)
    description: str | None = Field(default=None, description="New task description")
    project: str | None = Field(
        default=None, description="New project name (use empty string to remove)"
    )
    priority: str | None = Field(
        default=None, description="New priority: H, M, L, or empty to remove"
    )
    due: str | None = Field(default=None, description="New due date (use empty string to remove)")
    add_tags: list[str] | None = Field(default=None, description="Tags to add (without '+' prefix)")
    remove_tags: list[str] | None = Field(
        default=None, description="Tags to remove (without '-' prefix)"
    )


class DeleteTaskInput(BaseModel):
    """Input model for deleting a task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(..., description="Task ID or UUID to delete", min_length=1)


class AnnotateTaskInput(BaseModel):
    """Input model for adding an annotation to a task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(..., description="Task ID or UUID to annotate", min_length=1)
    annotation: str = Field(
        ..., description="Annotation text to add", min_length=1, max_length=2000
    )


class GetTaskInput(BaseModel):
    """Input model for getting a single task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(..., description="Task ID or UUID to retrieve", min_length=1)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable",
    )


class BulkGetTasksInput(BaseModel):
    """Input model for getting multiple tasks at once."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_ids: list[str] = Field(
        ..., description="List of task IDs or UUIDs to retrieve", min_length=1, max_length=50
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable",
    )

    @field_validator("task_ids")
    @classmethod
    def validate_task_ids(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one task ID is required")
        cleaned = [tid.strip() for tid in v if tid.strip()]
        if not cleaned:
            raise ValueError("At least one valid task ID is required")
        return cleaned


class ListProjectsInput(BaseModel):
    """Input model for listing projects."""

    model_config = ConfigDict(str_strip_whitespace=True)

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable",
    )


class ListTagsInput(BaseModel):
    """Input model for listing tags."""

    model_config = ConfigDict(str_strip_whitespace=True)

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable",
    )


class StartTaskInput(BaseModel):
    """Input model for starting a task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(..., description="Task ID or UUID to start", min_length=1)


class StopTaskInput(BaseModel):
    """Input model for stopping a task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(..., description="Task ID or UUID to stop", min_length=1)


class UndoInput(BaseModel):
    """Input model for undo operation."""

    model_config = ConfigDict(str_strip_whitespace=True)
    # No parameters needed - undo is a global operation


# ============================================================================
# Agent Intelligence Input Models
# ============================================================================


class SuggestInput(BaseModel):
    """Input model for smart task suggestions."""

    model_config = ConfigDict(str_strip_whitespace=True)

    limit: int = Field(
        default=5, description="Maximum number of suggestions to return", ge=1, le=20
    )
    context: str | None = Field(
        default=None,
        description="Context: 'quick_wins', 'blockers', 'deadlines', or None for balanced",
    )
    project: str | None = Field(
        default=None, description="Filter suggestions to a specific project"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: 'markdown' or 'json'"
    )


class ReadyInput(BaseModel):
    """Input model for listing ready (unblocked) tasks."""

    model_config = ConfigDict(str_strip_whitespace=True)

    limit: int = Field(default=10, description="Maximum number of tasks to return", ge=1, le=50)
    project: str | None = Field(default=None, description="Filter to a specific project")
    priority: str | None = Field(default=None, description="Filter by priority: H, M, or L")
    include_active: bool = Field(default=True, description="Include tasks that are already started")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: 'markdown' or 'json'"
    )


class BlockedInput(BaseModel):
    """Input model for listing blocked tasks."""

    model_config = ConfigDict(str_strip_whitespace=True)

    limit: int = Field(
        default=10, description="Maximum number of blocked tasks to return", ge=1, le=50
    )
    show_blockers: bool = Field(
        default=True, description="Show which tasks are blocking each blocked task"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: 'markdown' or 'json'"
    )


class DependenciesInput(BaseModel):
    """Input model for dependency graph analysis."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str | None = Field(
        default=None, description="Specific task ID to analyze, or None for overview"
    )
    direction: str = Field(
        default="both", description="Direction: 'blocks', 'blocked_by', or 'both'"
    )
    depth: int = Field(
        default=3, description="How deep to traverse the dependency tree", ge=1, le=10
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: 'markdown' or 'json'"
    )


class TriageInput(BaseModel):
    """Input model for task triage/review."""

    model_config = ConfigDict(str_strip_whitespace=True)

    stale_days: int = Field(
        default=14, description="Number of days before a task is considered stale", ge=1, le=365
    )
    include_untagged: bool = Field(default=True, description="Include tasks with no tags")
    include_no_project: bool = Field(
        default=True, description="Include tasks not assigned to a project"
    )
    include_no_due: bool = Field(default=True, description="Include tasks with no due date")
    limit: int = Field(default=20, description="Maximum items per category", ge=1, le=100)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: 'markdown' or 'json'"
    )


class ContextInput(BaseModel):
    """Input model for rich task context."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(..., description="Task ID or UUID to get context for", min_length=1)
    include_related: bool = Field(
        default=True, description="Include related tasks from the same project"
    )
    include_activity: bool = Field(default=True, description="Include recent activity information")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: 'markdown' or 'json'"
    )


# ============================================================================
# Internal Data Models
# ============================================================================


class TaskAnnotation(BaseModel):
    """Model for task annotations (notes)."""

    entry: str | None = None
    description: str = ""


class TaskModel(BaseModel):
    """Model representing a Taskwarrior task with all its attributes."""

    model_config = ConfigDict(extra="allow")

    id: int | None = None
    uuid: str | None = None
    description: str = ""
    status: str = "pending"
    urgency: float = 0.0
    project: str | None = None
    priority: str | None = None
    tags: list[str] = Field(default_factory=list)
    due: str | None = None
    entry: str | None = None
    modified: str | None = None
    start: str | None = None
    depends: str | None = None
    annotations: list[TaskAnnotation] = Field(default_factory=list)


class ScoredTask(BaseModel):
    """A task with its suggestion score and reasons."""

    task: TaskModel
    score: float
    reasons: list[str]


class BlockedTaskInfo(BaseModel):
    """Information about a blocked task and what blocks it."""

    task: TaskModel
    blockers: list[TaskModel] = Field(default_factory=list)


class BottleneckInfo(BaseModel):
    """Information about a bottleneck task and how many tasks it blocks."""

    task: TaskModel
    blocks_count: int


class ComputedInsights(BaseModel):
    """Computed insights about a task."""

    age: str
    last_activity: str
    dependency_status: str
    related_pending: int
    annotations_count: int


# ============================================================================
# Parser Helpers
# ============================================================================


def _parse_task(task_dict: dict[str, Any]) -> TaskModel:
    """
    Parse a task dictionary into a TaskModel.

    Args:
        task_dict: Dictionary from Taskwarrior JSON export

    Returns:
        TaskModel instance with validated data
    """
    return TaskModel.model_validate(task_dict)


def _parse_tasks(tasks: list[dict[str, Any]]) -> list[TaskModel]:
    """
    Parse a list of task dictionaries into TaskModel instances.

    Args:
        tasks: List of dictionaries from Taskwarrior JSON export

    Returns:
        List of TaskModel instances
    """
    return [TaskModel.model_validate(t) for t in tasks]


# ============================================================================
# Shared Utilities
# ============================================================================


def _run_task_command(args: list[str], input_text: str | None = None) -> tuple[bool, str]:
    """
    Execute a Taskwarrior command and return the result.

    Args:
        args: List of command arguments (without 'task' prefix)
        input_text: Optional input to send to stdin (for confirmations)

    Returns:
        Tuple of (success: bool, output: str)
    """
    try:
        cmd = ["task"] + args
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, input=input_text)

        output = result.stdout.strip()
        if result.returncode != 0:
            error = result.stderr.strip() or output
            return False, f"Error: {error}"

        return True, output

    except subprocess.TimeoutExpired:
        return False, "Error: Command timed out after 30 seconds"
    except FileNotFoundError:
        return False, (
            "Error: Taskwarrior is not installed or not in PATH. "
            "Install it with 'brew install task' or equivalent."
        )
    except Exception as e:
        return False, f"Error: Unexpected error - {type(e).__name__}: {str(e)}"


def _get_tasks_json(
    filter_expr: str | None = None,
    status: TaskStatus = TaskStatus.PENDING,
) -> tuple[bool, list[dict[str, Any]] | str]:
    """
    Get tasks as JSON from Taskwarrior.

    Args:
        filter_expr: Optional filter expression
        status: Task status to filter

    Returns:
        Tuple of (success: bool, tasks: List[dict] | error: str)
    """
    args = []

    # Add status filter
    if status == TaskStatus.PENDING:
        args.append("status:pending")
    elif status == TaskStatus.COMPLETED:
        args.append("status:completed")
    elif status == TaskStatus.DELETED:
        args.append("status:deleted")
    # ALL means no status filter

    # Add custom filter
    if filter_expr:
        args.append(filter_expr)

    args.append("export")

    success, output = _run_task_command(args)
    if not success:
        return False, output

    try:
        tasks = json.loads(output) if output else []
        return True, tasks
    except json.JSONDecodeError as e:
        return False, f"Error: Failed to parse task output - {str(e)}"


def _format_task_markdown(task: TaskModel) -> str:
    """Format a single task as markdown."""
    lines = []

    # Header with ID and description
    task_id = task.id if task.id else (task.uuid[:8] if task.uuid else "?")
    desc = task.description or "No description"
    status = task.status

    status_icon = {"pending": "", "completed": "", "deleted": ""}
    icon = status_icon.get(status, "")

    lines.append(f"### {icon} [{task_id}] {desc}")

    # Details
    details = []
    if task.project:
        details.append(f"**Project**: {task.project}")
    if task.priority:
        priority_map = {"H": "High", "M": "Medium", "L": "Low"}
        details.append(f"**Priority**: {priority_map.get(task.priority, task.priority)}")
    if task.due:
        details.append(f"**Due**: {task.due}")
    if task.tags:
        details.append(f"**Tags**: {', '.join(task.tags)}")
    if task.urgency:
        details.append(f"**Urgency**: {task.urgency:.2f}")

    if details:
        lines.append(" | ".join(details))

    # Annotations
    if task.annotations:
        lines.append("**Notes:**")
        for ann in task.annotations:
            entry = ann.entry[:10] if ann.entry else ""
            lines.append(f"  - [{entry}] {ann.description}")

    return "\n".join(lines)


def _format_tasks_markdown(tasks: list[TaskModel], title: str = "Tasks") -> str:
    """Format a list of tasks as markdown."""
    if not tasks:
        return f"# {title}\n\nNo tasks found."

    lines = [f"# {title}", f"*{len(tasks)} task(s)*", ""]

    for task in tasks:
        lines.append(_format_task_markdown(task))
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# Tool Definitions
# ============================================================================


@mcp.tool(
    name="taskwarrior_list",
    annotations=ToolAnnotations(
        title="List Tasks",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_list(params: ListTasksInput) -> str:
    """
    List tasks from Taskwarrior with optional filtering.

    Use this tool to view tasks, search for specific tasks, or get an overview
    of pending work. Supports Taskwarrior filter expressions for powerful querying.

    Args:
        params: ListTasksInput containing filter, status, limit, and response_format

    Returns:
        Formatted list of tasks (markdown or JSON based on response_format)

    Examples:
        - List all pending tasks: params with status="pending"
        - List tasks for a project: params with filter="project:work"
        - List urgent tasks: params with filter="+urgent"
        - List tasks due today: params with filter="due:today"
        - List completed tasks: params with status="completed"
    """
    success, result = _get_tasks_json(params.filter, params.status)

    if not success:
        return str(result)

    raw_tasks = result if isinstance(result, list) else []
    tasks = _parse_tasks(raw_tasks)
    total_count = len(tasks)

    if params.limit and len(tasks) > params.limit:
        tasks = tasks[: params.limit]

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {"total": total_count, "count": len(tasks), "tasks": [t.model_dump() for t in tasks]},
            indent=2,
        )

    title = "Tasks"
    if params.filter:
        title = f"Tasks matching '{params.filter}'"
    if params.status != TaskStatus.PENDING:
        title += f" ({params.status.value})"

    return _format_tasks_markdown(tasks, title)


@mcp.tool(
    name="taskwarrior_add",
    annotations=ToolAnnotations(
        title="Add Task",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
async def taskwarrior_add(params: AddTaskInput) -> str:
    """
    Create a new task in Taskwarrior.

    Use this tool to add new tasks with optional project, priority, due date, and tags.

    Args:
        params: AddTaskInput containing description and optional attributes

    Returns:
        Confirmation message with the created task ID

    Examples:
        - Simple task: params with description="Buy groceries"
        - Task with project: params with description="Review PR", project="work"
        - High priority task: params with description="Fix bug", priority="H"
        - Task with due date: params with description="Submit report", due="friday"
        - Task with tags: params with description="Call mom", tags=["personal", "important"]
    """
    args = [shlex.quote(params.description)]

    if params.project:
        args.append(f"project:{shlex.quote(params.project)}")

    if params.priority and params.priority.value:
        args.append(f"priority:{params.priority.value}")

    if params.due:
        args.append(f"due:{shlex.quote(params.due)}")

    if params.tags:
        for tag in params.tags:
            args.append(f"+{shlex.quote(tag)}")

    if params.depends:
        args.append(f"depends:{shlex.quote(params.depends)}")

    args.append("rc.confirmation=off")

    success, output = _run_task_command(["add"] + args)

    if success:
        return f"Task created successfully.\n{output}"
    return output


@mcp.tool(
    name="taskwarrior_complete",
    annotations=ToolAnnotations(
        title="Complete Task",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_complete(params: CompleteTaskInput) -> str:
    """
    Mark a task as completed.

    Use this tool when a task has been finished and should be marked as done.

    Args:
        params: CompleteTaskInput containing the task_id to complete

    Returns:
        Confirmation message

    Examples:
        - Complete task #5: params with task_id="5"
        - Complete by UUID: params with task_id="a1b2c3d4"
    """
    args = [params.task_id, "done", "rc.confirmation=off"]
    success, output = _run_task_command(args)

    if success:
        return f"Task {params.task_id} marked as complete.\n{output}"
    return output


@mcp.tool(
    name="taskwarrior_modify",
    annotations=ToolAnnotations(
        title="Modify Task",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_modify(params: ModifyTaskInput) -> str:
    """
    Modify an existing task's attributes.

    Use this tool to update task description, project, priority, due date, or tags.

    Args:
        params: ModifyTaskInput containing task_id and attributes to modify

    Returns:
        Confirmation message with updated task info

    Examples:
        - Change description: params with task_id="5", description="Updated task name"
        - Change project: params with task_id="5", project="personal"
        - Set priority: params with task_id="5", priority="H"
        - Add tags: params with task_id="5", add_tags=["urgent"]
        - Remove due date: params with task_id="5", due=""
    """
    args = [params.task_id, "modify"]

    if params.description is not None:
        args.append(shlex.quote(params.description))

    if params.project is not None:
        if params.project == "":
            args.append("project:")
        else:
            args.append(f"project:{shlex.quote(params.project)}")

    if params.priority is not None:
        if params.priority == "":
            args.append("priority:")
        else:
            args.append(f"priority:{params.priority}")

    if params.due is not None:
        if params.due == "":
            args.append("due:")
        else:
            args.append(f"due:{shlex.quote(params.due)}")

    if params.add_tags:
        for tag in params.add_tags:
            args.append(f"+{shlex.quote(tag)}")

    if params.remove_tags:
        for tag in params.remove_tags:
            args.append(f"-{shlex.quote(tag)}")

    args.append("rc.confirmation=off")

    success, output = _run_task_command(args)

    if success:
        return f"Task {params.task_id} modified successfully.\n{output}"
    return output


@mcp.tool(
    name="taskwarrior_delete",
    annotations=ToolAnnotations(
        title="Delete Task",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_delete(params: DeleteTaskInput) -> str:
    """
    Delete a task from Taskwarrior.

    Use this tool to remove a task. The task is marked as deleted but can be
    recovered with 'undo' if needed.

    Args:
        params: DeleteTaskInput containing the task_id to delete

    Returns:
        Confirmation message

    Examples:
        - Delete task #5: params with task_id="5"
    """
    args = [params.task_id, "delete", "rc.confirmation=off"]
    success, output = _run_task_command(args)

    if success:
        return f"Task {params.task_id} deleted.\n{output}"
    return output


@mcp.tool(
    name="taskwarrior_get",
    annotations=ToolAnnotations(
        title="Get Task Details",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_get(params: GetTaskInput) -> str:
    """
    Get detailed information about a specific task.

    Use this tool to view all attributes and annotations of a single task.

    Args:
        params: GetTaskInput containing task_id and response_format

    Returns:
        Detailed task information (markdown or JSON)

    Examples:
        - Get task #5: params with task_id="5"
        - Get task as JSON: params with task_id="5", response_format="json"
    """
    success, output = _run_task_command([params.task_id, "export"])

    if not success:
        return output

    try:
        tasks = json.loads(output) if output else []
        if not tasks:
            return f"Error: Task {params.task_id} not found."

        task = _parse_task(tasks[0])

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(task.model_dump(), indent=2)

        return _format_task_markdown(task)

    except json.JSONDecodeError as e:
        return f"Error: Failed to parse task data - {str(e)}"


@mcp.tool(
    name="taskwarrior_bulk_get",
    annotations=ToolAnnotations(
        title="Get Multiple Task Details",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_bulk_get(params: BulkGetTasksInput) -> str:
    """
    Get detailed information about multiple tasks at once.

    Use this tool to view all attributes and annotations of multiple tasks
    in a single request, which is more efficient than calling taskwarrior_get
    multiple times.

    Args:
        params: BulkGetTasksInput containing task_ids and response_format

    Returns:
        Detailed task information (markdown or JSON)

    Examples:
        - Get tasks #1, #2, #3: params with task_ids=["1", "2", "3"]
        - Get tasks as JSON: params with task_ids=["1", "2"], response_format="json"
    """
    # Build filter for multiple task IDs using Taskwarrior OR syntax
    filter_expr = " or ".join(f"id:{tid}" for tid in params.task_ids)
    success, output = _run_task_command([f"({filter_expr})", "export"])

    if not success:
        return output

    try:
        raw_tasks = json.loads(output) if output else []

        if not raw_tasks:
            return f"Error: No tasks found for IDs: {', '.join(params.task_ids)}"

        tasks = _parse_tasks(raw_tasks)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps([t.model_dump() for t in tasks], indent=2)

        # Format as markdown
        lines = [f"# Task Details ({len(tasks)} tasks found)\n"]
        for task in tasks:
            lines.append(_format_task_markdown(task))
            lines.append("")  # Blank line between tasks

        # Note any missing tasks
        found_ids = {str(t.id) for t in tasks if t.id is not None}
        found_ids.update({t.uuid[:8] for t in tasks if t.uuid})
        missing = [tid for tid in params.task_ids if tid not in found_ids]
        if missing:
            lines.append(f"\n**Note:** Tasks not found: {', '.join(missing)}")

        return "\n".join(lines)

    except json.JSONDecodeError as e:
        return f"Error: Failed to parse task data - {str(e)}"


@mcp.tool(
    name="taskwarrior_annotate",
    annotations=ToolAnnotations(
        title="Annotate Task",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
async def taskwarrior_annotate(params: AnnotateTaskInput) -> str:
    """
    Add an annotation (note) to a task.

    Use this tool to add notes, comments, or additional context to a task.

    Args:
        params: AnnotateTaskInput containing task_id and annotation text

    Returns:
        Confirmation message

    Examples:
        - Add note: params with task_id="5", annotation="Discussed with John, needs review"
    """
    args = [params.task_id, "annotate", shlex.quote(params.annotation), "rc.confirmation=off"]
    success, output = _run_task_command(args)

    if success:
        return f"Annotation added to task {params.task_id}.\n{output}"
    return output


@mcp.tool(
    name="taskwarrior_start",
    annotations=ToolAnnotations(
        title="Start Task",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_start(params: StartTaskInput) -> str:
    """
    Start working on a task.

    Use this tool to indicate you're actively working on a task. This adds the
    'active' state to the task.

    Args:
        params: StartTaskInput containing the task_id to start

    Returns:
        Confirmation message

    Examples:
        - Start task #5: params with task_id="5"
    """
    args = [params.task_id, "start", "rc.confirmation=off"]
    success, output = _run_task_command(args)

    if success:
        return f"Task {params.task_id} started.\n{output}"
    return output


@mcp.tool(
    name="taskwarrior_stop",
    annotations=ToolAnnotations(
        title="Stop Task",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_stop(params: StopTaskInput) -> str:
    """
    Stop working on a task.

    Use this tool to indicate you've paused work on a task.

    Args:
        params: StopTaskInput containing the task_id to stop

    Returns:
        Confirmation message

    Examples:
        - Stop task #5: params with task_id="5"
    """
    args = [params.task_id, "stop", "rc.confirmation=off"]
    success, output = _run_task_command(args)

    if success:
        return f"Task {params.task_id} stopped.\n{output}"
    return output


@mcp.tool(
    name="taskwarrior_projects",
    annotations=ToolAnnotations(
        title="List Projects",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_projects(params: ListProjectsInput) -> str:
    """
    List all projects in Taskwarrior.

    Use this tool to see all projects and the number of tasks in each.

    Args:
        params: ListProjectsInput with response_format

    Returns:
        List of projects with task counts

    Examples:
        - List projects: params with response_format="markdown"
    """
    success, result = _get_tasks_json(status=TaskStatus.PENDING)

    if not success:
        return str(result)

    # Count tasks per project
    raw_tasks = result if isinstance(result, list) else []
    tasks = _parse_tasks(raw_tasks)
    project_counts: dict[str, int] = {}
    for task in tasks:
        project = task.project or "(none)"
        project_counts[project] = project_counts.get(project, 0) + 1

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "projects": [
                    {"name": name, "task_count": count}
                    for name, count in sorted(project_counts.items())
                ]
            },
            indent=2,
        )

    lines = ["# Projects", ""]
    if not project_counts:
        lines.append("No projects found.")
    else:
        for name, count in sorted(project_counts.items()):
            lines.append(f"- **{name}**: {count} task(s)")

    return "\n".join(lines)


@mcp.tool(
    name="taskwarrior_tags",
    annotations=ToolAnnotations(
        title="List Tags",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_tags(params: ListTagsInput) -> str:
    """
    List all tags used in Taskwarrior.

    Use this tool to see all tags and how many tasks use each tag.

    Args:
        params: ListTagsInput with response_format

    Returns:
        List of tags with usage counts

    Examples:
        - List tags: params with response_format="markdown"
    """
    success, result = _get_tasks_json(status=TaskStatus.PENDING)

    if not success:
        return str(result)

    # Count tasks per tag
    raw_tasks = result if isinstance(result, list) else []
    tasks = _parse_tasks(raw_tasks)
    tag_counts: dict[str, int] = {}
    for task in tasks:
        for tag in task.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "tags": [
                    {"name": name, "task_count": count}
                    for name, count in sorted(tag_counts.items())
                ]
            },
            indent=2,
        )

    lines = ["# Tags", ""]
    if not tag_counts:
        lines.append("No tags found.")
    else:
        for name, count in sorted(tag_counts.items()):
            lines.append(f"- **+{name}**: {count} task(s)")

    return "\n".join(lines)


@mcp.tool(
    name="taskwarrior_undo",
    annotations=ToolAnnotations(
        title="Undo Last Change",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
async def taskwarrior_undo(params: UndoInput) -> str:
    """
    Undo the last Taskwarrior operation.

    Use this tool to revert the most recent change to tasks.

    Args:
        params: UndoInput (no parameters needed)

    Returns:
        Confirmation message

    Examples:
        - Undo last action: params with no special values
    """
    success, output = _run_task_command(["undo", "rc.confirmation=off"])

    if success:
        return f"Undo successful.\n{output}"
    return output


@mcp.tool(
    name="taskwarrior_summary",
    annotations=ToolAnnotations(
        title="Task Summary",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_summary() -> str:
    """
    Get a summary of task statistics.

    Use this tool to get an overview of pending tasks, including counts by
    project, priority, and urgency.

    Returns:
        Summary statistics of tasks
    """
    success, result = _get_tasks_json(status=TaskStatus.PENDING)

    if not success:
        return str(result)

    raw_tasks = result if isinstance(result, list) else []
    tasks = _parse_tasks(raw_tasks)
    if not tasks:
        return "# Task Summary\n\nNo pending tasks."

    # Calculate statistics
    total = len(tasks)
    by_priority = {"H": 0, "M": 0, "L": 0, "": 0}
    by_project: dict[str, int] = {}
    overdue = 0
    active = 0

    for task in tasks:
        priority = task.priority or ""
        by_priority[priority] = by_priority.get(priority, 0) + 1

        project = task.project or "(none)"
        by_project[project] = by_project.get(project, 0) + 1

        if task.start:
            active += 1

        # Simple due date checking (Taskwarrior handles the complex logic)
        if task.due:
            # Check if urgency suggests overdue (urgency > 12 typically means overdue)
            if task.urgency > 12:
                overdue += 1

    lines = [
        "# Task Summary",
        "",
        f"**Total Pending Tasks**: {total}",
        f"**Active (in progress)**: {active}",
        "",
        "## By Priority",
        f"- High: {by_priority['H']}",
        f"- Medium: {by_priority['M']}",
        f"- Low: {by_priority['L']}",
        f"- No priority: {by_priority['']}",
        "",
        "## Top Projects",
    ]

    # Show top 5 projects by task count
    sorted_projects = sorted(by_project.items(), key=lambda x: x[1], reverse=True)[:5]
    for project, count in sorted_projects:
        lines.append(f"- {project}: {count}")

    return "\n".join(lines)


# ============================================================================
# Agent Intelligence Helper Functions
# ============================================================================


def _calculate_suggestion_score(
    task: TaskModel, all_tasks: list[TaskModel]
) -> tuple[float, list[str]]:
    """
    Calculate suggestion score for a task and return reasons.

    Returns:
        Tuple of (score, list_of_reasons)
    """
    score = 0.0
    reasons: list[str] = []

    # Base urgency from Taskwarrior
    urgency = task.urgency

    # Overdue: urgency > 12 typically indicates overdue
    if urgency > 12:
        score += 100
        reasons.append("Overdue")
    elif urgency > 8:
        score += 50
        reasons.append("Due soon")

    # High priority
    if task.priority == "H":
        score += 30
        reasons.append("High priority")
    elif task.priority == "M":
        score += 15

    # Currently active (started)
    if task.start:
        score += 15
        reasons.append("Currently active")

    # Tagged +next
    if "next" in task.tags:
        score += 25
        reasons.append("Tagged +next")

    # Quick wins (tagged quick or low urgency with no dependencies)
    if "quick" in task.tags:
        score += 10
        reasons.append("Quick win")

    # Blocks other tasks
    task_uuid = task.uuid or ""
    blocked_count = 0
    for t in all_tasks:
        if t.depends and task_uuid in t.depends:
            blocked_count += 1

    if blocked_count > 0:
        score += 20 * blocked_count
        reasons.append(f"Blocks {blocked_count} task(s)")

    # Add base urgency
    score += urgency

    return score, reasons


def _get_blocked_tasks(tasks: list[TaskModel]) -> list[TaskModel]:
    """Get tasks that have unresolved dependencies."""
    # Build a set of pending task UUIDs
    pending_uuids = {t.uuid for t in tasks if t.status == "pending" and t.uuid}

    blocked: list[TaskModel] = []
    for task in tasks:
        if task.status != "pending":
            continue
        if task.depends:
            # Check if any dependency is still pending
            dep_uuids = [d.strip() for d in task.depends.split(",") if d.strip()]
            has_pending_dep = any(d in pending_uuids for d in dep_uuids)
            if has_pending_dep:
                blocked.append(task)

    return blocked


def _get_ready_tasks(tasks: list[TaskModel]) -> list[TaskModel]:
    """Get tasks that have no pending dependencies."""
    pending_uuids = {t.uuid for t in tasks if t.status == "pending" and t.uuid}

    ready: list[TaskModel] = []
    for task in tasks:
        if task.status != "pending":
            continue
        if not task.depends:
            ready.append(task)
        else:
            # Check if all dependencies are completed
            dep_uuids = [d.strip() for d in task.depends.split(",") if d.strip()]
            has_pending_dep = any(d in pending_uuids for d in dep_uuids)
            if not has_pending_dep:
                ready.append(task)

    return ready


def _get_task_age_str(task: TaskModel) -> str:
    """Get human-readable age of a task."""
    if not task.entry:
        return "Unknown"

    try:
        # Taskwarrior uses ISO format: 20250130T100000Z
        entry_dt = datetime.strptime(task.entry[:15], "%Y%m%dT%H%M%S")
        entry_dt = entry_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - entry_dt

        days = delta.days
        if days == 0:
            return "Today"
        elif days == 1:
            return "Yesterday"
        elif days < 7:
            return f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            return f"{weeks} week(s) ago"
        else:
            months = days // 30
            return f"{months} month(s) ago"
    except (ValueError, TypeError):
        return "Unknown"


def _is_task_stale(task: TaskModel, stale_days: int) -> bool:
    """Check if a task is stale (not modified recently)."""
    modified = task.modified or task.entry
    if not modified:
        return True

    try:
        mod_dt = datetime.strptime(modified[:15], "%Y%m%dT%H%M%S")
        mod_dt = mod_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - mod_dt
        return delta.days >= stale_days
    except (ValueError, TypeError):
        return False


# ============================================================================
# Agent Intelligence Tool Definitions
# ============================================================================


@mcp.tool(
    name="taskwarrior_suggest",
    annotations=ToolAnnotations(
        title="Suggest Tasks",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_suggest(params: SuggestInput) -> str:
    """
    Get smart task suggestions based on urgency, priority, and dependencies.

    Use this tool to help decide what to work on next. Returns a prioritized
    list of tasks with reasoning for why each is suggested.

    Args:
        params: SuggestInput with limit, context, project filter, and format

    Returns:
        Prioritized list of task suggestions with reasons

    Examples:
        - Get top 5 suggestions: params with default values
        - Focus on blockers: params with context="blockers"
        - Filter to project: params with project="work"
    """
    # Get all pending tasks
    filter_expr = f"project:{params.project}" if params.project else None
    success, result = _get_tasks_json(filter_expr, TaskStatus.PENDING)

    if not success:
        return str(result)

    raw_tasks = result if isinstance(result, list) else []
    tasks = _parse_tasks(raw_tasks)
    if not tasks:
        return "# Suggestions\n\nNo pending tasks found. Nothing to suggest!"

    # Score each task
    scored_tasks: list[ScoredTask] = []
    for task in tasks:
        score, reasons = _calculate_suggestion_score(task, tasks)
        scored_tasks.append(ScoredTask(task=task, score=score, reasons=reasons))

    # Sort by score descending
    scored_tasks.sort(key=lambda x: x.score, reverse=True)

    # Apply context filter if specified
    if params.context == "quick_wins":
        scored_tasks = [
            s for s in scored_tasks if "Quick win" in s.reasons or s.task.urgency < 5
        ]
    elif params.context == "blockers":
        scored_tasks = [s for s in scored_tasks if any("Blocks" in r for r in s.reasons)]
    elif params.context == "deadlines":
        scored_tasks = [
            s for s in scored_tasks if "Overdue" in s.reasons or "Due soon" in s.reasons
        ]

    # Limit results
    scored_tasks = scored_tasks[: params.limit]

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "suggestions": [s.model_dump() for s in scored_tasks],
                "total_pending": len(tasks),
            },
            indent=2,
        )

    # Markdown format
    if not scored_tasks:
        return "# Suggestions\n\nNo tasks match your criteria."

    lines = ["# Suggested: What to Work On", ""]

    for i, s in enumerate(scored_tasks, 1):
        task = s.task
        task_id = task.id if task.id else "?"
        desc = task.description or "No description"
        reasons = s.reasons

        # Add status indicator
        indicator = ""
        if "Overdue" in reasons:
            indicator = "⚠️ OVERDUE"
        elif "Due soon" in reasons:
            indicator = "📅 DUE SOON"
        elif "Quick win" in reasons:
            indicator = "⚡ QUICK WIN"
        elif "Currently active" in reasons:
            indicator = "🔄 ACTIVE"

        lines.append(f"{i}. **[#{task_id}] {desc}** {indicator}")

        # Details line
        details = []
        if task.due:
            details.append(f"Due: {task.due[:10]}")
        if task.priority:
            details.append(f"Priority: {task.priority}")
        if task.project:
            details.append(f"Project: {task.project}")

        if details:
            lines.append(f"   {' | '.join(details)}")

        # Reason line
        if reasons:
            lines.append(f"   → Reason: {', '.join(reasons)}")

        lines.append("")

    return "\n".join(lines)


@mcp.tool(
    name="taskwarrior_ready",
    annotations=ToolAnnotations(
        title="Ready Tasks",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_ready(params: ReadyInput) -> str:
    """
    List tasks that are ready to work on (no pending dependencies).

    Use this tool to see which tasks can be started immediately without
    waiting for other tasks to complete first.

    Args:
        params: ReadyInput with limit, project, priority, and format options

    Returns:
        List of unblocked tasks ready to start

    Examples:
        - Get ready tasks: params with default values
        - Filter by project: params with project="work"
        - High priority only: params with priority="H"
    """
    # Get all pending tasks (need all to check dependencies)
    success, result = _get_tasks_json(status=TaskStatus.PENDING)

    if not success:
        return str(result)

    raw_tasks = result if isinstance(result, list) else []
    all_tasks = _parse_tasks(raw_tasks)
    ready_tasks = _get_ready_tasks(all_tasks)

    # Apply filters
    if params.project:
        ready_tasks = [t for t in ready_tasks if t.project == params.project]

    if params.priority:
        ready_tasks = [t for t in ready_tasks if t.priority == params.priority]

    if not params.include_active:
        ready_tasks = [t for t in ready_tasks if not t.start]

    # Sort by urgency descending
    ready_tasks.sort(key=lambda t: t.urgency, reverse=True)

    # Limit
    ready_tasks = ready_tasks[: params.limit]

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "tasks": [t.model_dump() for t in ready_tasks],
                "count": len(ready_tasks),
                "total_pending": len(all_tasks),
            },
            indent=2,
        )

    # Markdown format
    if not ready_tasks:
        return "# Ready to Work\n\nNo unblocked tasks found."

    lines = [f"# Ready to Work ({len(ready_tasks)} tasks)", ""]
    lines.append("| ID | Task | Priority | Due | Project |")
    lines.append("|----|------|----------|-----|---------|")

    for task in ready_tasks:
        task_id = task.id if task.id else "?"
        desc = task.description[:40] if task.description else ""
        priority = task.priority or "-"
        due = task.due[:10] if task.due else "-"
        project = task.project or "-"

        # Mark overdue
        if task.urgency > 12:
            due = f"**{due}** ⚠️"

        lines.append(f"| {task_id} | {desc} | {priority} | {due} | {project} |")

    return "\n".join(lines)


@mcp.tool(
    name="taskwarrior_blocked",
    annotations=ToolAnnotations(
        title="Blocked Tasks",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_blocked(params: BlockedInput) -> str:
    """
    List tasks that are blocked by dependencies.

    Use this tool to see which tasks are waiting on other tasks to complete.

    Args:
        params: BlockedInput with limit, show_blockers option, and format

    Returns:
        List of blocked tasks with their blockers

    Examples:
        - Get blocked tasks: params with default values
        - Without blocker details: params with show_blockers=False
    """
    # Get all pending tasks
    success, result = _get_tasks_json(status=TaskStatus.PENDING)

    if not success:
        return str(result)

    raw_tasks = result if isinstance(result, list) else []
    all_tasks = _parse_tasks(raw_tasks)
    blocked_tasks = _get_blocked_tasks(all_tasks)

    # Limit
    blocked_tasks = blocked_tasks[: params.limit]

    # Build UUID to task mapping for showing blockers
    uuid_to_task = {t.uuid: t for t in all_tasks if t.uuid}

    if params.response_format == ResponseFormat.JSON:
        blocked_info: list[BlockedTaskInfo] = []
        for task in blocked_tasks:
            info = BlockedTaskInfo(task=task, blockers=[])
            if params.show_blockers and task.depends:
                dep_uuids = [d.strip() for d in task.depends.split(",") if d.strip()]
                for dep_uuid in dep_uuids:
                    blocker = uuid_to_task.get(dep_uuid)
                    if blocker and blocker.status == "pending":
                        info.blockers.append(blocker)
            blocked_info.append(info)

        return json.dumps(
            {
                "blocked": [b.model_dump() for b in blocked_info],
                "count": len(blocked_tasks),
                "total_pending": len(all_tasks),
            },
            indent=2,
        )

    # Markdown format
    if not blocked_tasks:
        return "# Blocked Tasks\n\nNo blocked tasks found. All tasks are ready to work on!"

    lines = [f"# Blocked Tasks ({len(blocked_tasks)} waiting)", ""]

    for i, task in enumerate(blocked_tasks, 1):
        task_id = task.id if task.id else "?"
        desc = task.description or "No description"

        lines.append(f"{i}. **[#{task_id}] {desc}**")

        if params.show_blockers and task.depends:
            dep_uuids = [d.strip() for d in task.depends.split(",") if d.strip()]
            blockers_list = []
            for dep_uuid in dep_uuids:
                blocker = uuid_to_task.get(dep_uuid)
                if blocker and blocker.status == "pending":
                    blocker_id = blocker.id if blocker.id else "?"
                    blocker_desc = blocker.description[:30] if blocker.description else ""
                    blockers_list.append(f"#{blocker_id} ({blocker_desc})")

            if blockers_list:
                lines.append(f"   Blocked by: {', '.join(blockers_list)}")

        lines.append("")

    return "\n".join(lines)


@mcp.tool(
    name="taskwarrior_dependencies",
    annotations=ToolAnnotations(
        title="Task Dependencies",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_dependencies(params: DependenciesInput) -> str:
    """
    Analyze task dependencies and find bottlenecks.

    Use this tool to understand dependency relationships between tasks,
    find critical bottlenecks, and see what's blocking progress.

    Args:
        params: DependenciesInput with optional task_id, direction, depth

    Returns:
        Dependency graph analysis (overview or specific task)

    Examples:
        - Get overview: params with task_id=None
        - Specific task: params with task_id="5"
        - Only what task blocks: params with task_id="5", direction="blocks"
    """
    # Get all tasks (pending and completed for full picture)
    success, result = _get_tasks_json(status=TaskStatus.ALL)

    if not success:
        return str(result)

    raw_tasks = result if isinstance(result, list) else []
    all_tasks = _parse_tasks(raw_tasks)
    pending_tasks = [t for t in all_tasks if t.status == "pending"]

    # Build UUID to task mapping
    uuid_to_task = {t.uuid: t for t in all_tasks if t.uuid}

    # Build "blocks" relationships (what each task blocks)
    blocks_map: dict[str, list[TaskModel]] = {}  # uuid -> list of tasks it blocks
    for task in pending_tasks:
        if task.depends:
            dep_uuids = [d.strip() for d in task.depends.split(",") if d.strip()]
            for dep_uuid in dep_uuids:
                if dep_uuid not in blocks_map:
                    blocks_map[dep_uuid] = []
                blocks_map[dep_uuid].append(task)

    if params.task_id:
        # Specific task analysis
        success, output = _run_task_command([params.task_id, "export"])
        if not success:
            return output

        try:
            task_list = json.loads(output) if output else []
            if not task_list:
                return f"Error: Task {params.task_id} not found."
            task = _parse_task(task_list[0])
        except json.JSONDecodeError:
            return f"Error: Could not parse task {params.task_id}"

        task_uuid = task.uuid or ""
        task_id = task.id if task.id else params.task_id
        desc = task.description or "No description"

        # What this task blocks
        blocks = blocks_map.get(task_uuid, [])

        # What blocks this task
        blocked_by: list[TaskModel] = []
        if task.depends:
            dep_uuids = [d.strip() for d in task.depends.split(",") if d.strip()]
            for dep_uuid in dep_uuids:
                blocker = uuid_to_task.get(dep_uuid)
                if blocker:
                    blocked_by.append(blocker)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {
                    "task": task.model_dump(),
                    "blocks": [b.model_dump() for b in blocks]
                    if params.direction in ["both", "blocks"]
                    else [],
                    "blocked_by": [b.model_dump() for b in blocked_by]
                    if params.direction in ["both", "blocked_by"]
                    else [],
                    "ready": len([b for b in blocked_by if b.status == "pending"]) == 0,
                },
                indent=2,
            )

        # Markdown format
        lines = [f"# Dependencies for #{task_id}: {desc}", ""]

        if params.direction in ["both", "blocks"]:
            lines.append(f"### ⬇️ Blocks ({len(blocks)} task(s) waiting)")
            if blocks:
                for b in blocks:
                    status = "✓ COMPLETED" if b.status == "completed" else ""
                    b_id = b.id if b.id else "?"
                    lines.append(f"├── #{b_id}: {b.description} {status}")
            else:
                lines.append("(None)")
            lines.append("")

        if params.direction in ["both", "blocked_by"]:
            lines.append(f"### ⬆️ Blocked By ({len(blocked_by)} task(s) required)")
            if blocked_by:
                for b in blocked_by:
                    status = "✓ COMPLETED" if b.status == "completed" else ""
                    b_id = b.id if b.id else "?"
                    lines.append(f"└── #{b_id}: {b.description} {status}")
            else:
                lines.append("(None)")
            lines.append("")

        # Assessment
        pending_blockers = [b for b in blocked_by if b.status == "pending"]
        ready = len(pending_blockers) == 0
        impact = "HIGH" if len(blocks) >= 2 else "MEDIUM" if len(blocks) == 1 else "LOW"

        lines.append("### Assessment")
        status_text = "READY TO START" if ready else f"BLOCKED by {len(pending_blockers)} task(s)"
        lines.append(f"- Status: {status_text}")
        lines.append(f"- Impact: {impact} (unblocks {len(blocks)} task(s))")

        return "\n".join(lines)

    else:
        # Overview mode
        # Find bottlenecks (tasks that block the most others)
        bottlenecks: list[BottleneckInfo] = []
        for uuid, blocked_list in blocks_map.items():
            bottleneck_task = uuid_to_task.get(uuid)
            if bottleneck_task is not None and bottleneck_task.status == "pending":
                bottlenecks.append(
                    BottleneckInfo(task=bottleneck_task, blocks_count=len(blocked_list))
                )

        bottlenecks.sort(key=lambda x: x.blocks_count, reverse=True)

        blocked_tasks = _get_blocked_tasks(pending_tasks)
        ready_tasks = _get_ready_tasks(pending_tasks)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {
                    "bottlenecks": [b.model_dump() for b in bottlenecks[:10]],
                    "blocked": [t.id for t in blocked_tasks[:10]],
                    "ready": [t.id for t in ready_tasks[:10]],
                    "stats": {
                        "total_pending": len(pending_tasks),
                        "blocked_count": len(blocked_tasks),
                        "ready_count": len(ready_tasks),
                    },
                },
                indent=2,
            )

        # Markdown format
        lines = ["# Dependency Overview", ""]

        lines.append("### Critical Bottlenecks")
        if bottlenecks[:5]:
            for bottleneck in bottlenecks[:5]:
                t_id = bottleneck.task.id if bottleneck.task.id else "?"
                lines.append(f"- #{t_id} blocks {bottleneck.blocks_count} downstream task(s)")
        else:
            lines.append("(No bottlenecks)")
        lines.append("")

        lines.append(f"### Blocked Tasks ({len(blocked_tasks)} cannot start)")
        if blocked_tasks[:5]:
            for t in blocked_tasks[:5]:
                t_id = t.id if t.id else "?"
                desc = t.description[:40] if t.description else ""
                lines.append(f"- #{t_id}: {desc}")
        else:
            lines.append("(None)")
        lines.append("")

        lines.append(f"### Ready to Work ({len(ready_tasks)} unblocked)")
        if ready_tasks[:5]:
            lines.append(", ".join([f"#{t.id}" for t in ready_tasks[:5] if t.id]))
        else:
            lines.append("(None)")

        return "\n".join(lines)


@mcp.tool(
    name="taskwarrior_triage",
    annotations=ToolAnnotations(
        title="Triage Tasks",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_triage(params: TriageInput) -> str:
    """
    Surface tasks that need attention: stale, unorganized, or forgotten.

    Use this tool for weekly reviews to find tasks that have fallen through
    the cracks or need better organization.

    Args:
        params: TriageInput with stale_days, filter options, and format

    Returns:
        Categorized list of tasks needing attention

    Examples:
        - Default triage: params with default values
        - Only stale tasks: params with include_untagged=False, include_no_project=False
        - More aggressive: params with stale_days=7
    """
    success, result = _get_tasks_json(status=TaskStatus.PENDING)

    if not success:
        return str(result)

    raw_tasks = result if isinstance(result, list) else []
    all_tasks = _parse_tasks(raw_tasks)

    # Categorize tasks
    stale: list[TaskModel] = []
    no_project: list[TaskModel] = []
    untagged: list[TaskModel] = []
    no_due: list[TaskModel] = []

    for task in all_tasks:
        if params.include_untagged and not task.tags:
            untagged.append(task)

        if params.include_no_project and not task.project:
            no_project.append(task)

        if params.include_no_due and not task.due:
            no_due.append(task)

        if _is_task_stale(task, params.stale_days):
            stale.append(task)

    # Limit each category
    stale = stale[: params.limit]
    no_project = no_project[: params.limit]
    untagged = untagged[: params.limit]
    no_due = no_due[: params.limit]

    total_items = len(stale) + len(no_project) + len(untagged) + len(no_due)

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "stale": [t.model_dump() for t in stale],
                "no_project": [t.model_dump() for t in no_project],
                "untagged": [t.model_dump() for t in untagged],
                "no_due": [t.model_dump() for t in no_due],
                "total_items": total_items,
                "total_pending": len(all_tasks),
            },
            indent=2,
        )

    # Markdown format
    if total_items == 0:
        return "# Task Triage\n\nLooking good! No items need attention."

    lines = [f"# Task Triage - {total_items} items need attention", ""]

    if stale:
        stale_header = f"### 🕸️ Stale Tasks (>{params.stale_days} days) - {len(stale)} items"
        lines.append(stale_header)
        lines.append("| ID | Task | Age | Last Modified |")
        lines.append("|----|------|-----|---------------|")
        for task in stale:
            task_id = task.id if task.id else "?"
            desc = task.description[:30] if task.description else ""
            age = _get_task_age_str(task)
            modified = (task.modified or task.entry or "")[:10]
            lines.append(f"| {task_id} | {desc} | {age} | {modified} |")
        lines.append("")

    if no_project:
        lines.append(f"### 📁 No Project Assigned - {len(no_project)} items")
        lines.append("| ID | Task | Created |")
        lines.append("|----|------|---------|")
        for task in no_project:
            task_id = task.id if task.id else "?"
            desc = task.description[:40] if task.description else ""
            created = task.entry[:10] if task.entry else ""
            lines.append(f"| {task_id} | {desc} | {created} |")
        lines.append("")

    if untagged:
        lines.append(f"### 🏷️ Untagged Tasks - {len(untagged)} items")
        lines.append("| ID | Task | Project |")
        lines.append("|----|------|---------|")
        for task in untagged:
            task_id = task.id if task.id else "?"
            desc = task.description[:40] if task.description else ""
            project = task.project or "-"
            lines.append(f"| {task_id} | {desc} | {project} |")
        lines.append("")

    if no_due:
        lines.append(f"### 📅 No Due Date - {len(no_due)} items")
        lines.append("| ID | Task | Priority | Project |")
        lines.append("|----|------|----------|---------|")
        for task in no_due:
            task_id = task.id if task.id else "?"
            desc = task.description[:30] if task.description else ""
            priority = task.priority or "-"
            project = task.project or "-"
            lines.append(f"| {task_id} | {desc} | {priority} | {project} |")
        lines.append("")

    lines.append("### Triage Actions")
    lines.append("- Consider: archive, delete, set due date, assign project, or add to +next")

    return "\n".join(lines)


@mcp.tool(
    name="taskwarrior_context",
    annotations=ToolAnnotations(
        title="Task Context",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_context(params: ContextInput) -> str:
    """
    Get rich context for a task including computed insights.

    Use this tool to deeply understand a task with its age, dependencies,
    related tasks, and activity history.

    Args:
        params: ContextInput with task_id and options for related/activity info

    Returns:
        Rich task details with computed insights

    Examples:
        - Get full context: params with task_id="5"
        - Task only: params with task_id="5", include_related=False
    """
    # Get the specific task
    success, output = _run_task_command([params.task_id, "export"])

    if not success:
        return output

    try:
        task_list = json.loads(output) if output else []
        if not task_list:
            return f"Error: Task {params.task_id} not found."
        task = _parse_task(task_list[0])
    except json.JSONDecodeError as e:
        return f"Error: Failed to parse task data - {str(e)}"

    # Get all tasks for dependency and related analysis
    success, all_result = _get_tasks_json(status=TaskStatus.ALL)
    raw_all_tasks = all_result if success and isinstance(all_result, list) else []
    all_tasks = _parse_tasks(raw_all_tasks)
    pending_tasks = [t for t in all_tasks if t.status == "pending"]

    # Compute additional fields
    task_uuid = task.uuid or ""
    age = _get_task_age_str(task)

    # Dependency status
    blocking_count = 0
    blocked_by_count = 0

    if task.depends:
        dep_uuids = [d.strip() for d in task.depends.split(",") if d.strip()]
        uuid_to_task = {t.uuid: t for t in all_tasks if t.uuid}
        blocked_by_count = sum(
            1 for d in dep_uuids if uuid_to_task.get(d) and uuid_to_task[d].status == "pending"
        )

    for t in pending_tasks:
        if t.depends and task_uuid in t.depends:
            blocking_count += 1

    if blocked_by_count > 0:
        dep_status = f"Blocked by {blocked_by_count} task(s)"
    elif blocking_count > 0:
        dep_status = f"Blocks {blocking_count} task(s)"
    else:
        dep_status = "Ready"

    # Related tasks (same project)
    related: list[TaskModel] = []
    if params.include_related and task.project:
        related = [t for t in pending_tasks if t.project == task.project and t.uuid != task_uuid][
            :5
        ]

    # Last modified
    last_activity = "Unknown"
    if task.modified:
        try:
            mod_dt = datetime.strptime(task.modified[:15], "%Y%m%dT%H%M%S")
            now = datetime.now(timezone.utc)
            mod_dt = mod_dt.replace(tzinfo=timezone.utc)
            delta = now - mod_dt
            if delta.days == 0:
                hours = delta.seconds // 3600
                last_activity = f"{hours} hour(s) ago" if hours > 0 else "Recently"
            elif delta.days == 1:
                last_activity = "Yesterday"
            else:
                last_activity = f"{delta.days} days ago"
        except (ValueError, TypeError):
            pass

    computed = ComputedInsights(
        age=age,
        last_activity=last_activity,
        dependency_status=dep_status,
        related_pending=len(related),
        annotations_count=len(task.annotations),
    )

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "task": task.model_dump(),
                "computed": computed.model_dump(),
                "related_tasks": [t.model_dump() for t in related]
                if params.include_related
                else [],
            },
            indent=2,
        )

    # Markdown format
    task_id = task.id if task.id else params.task_id
    desc = task.description or "No description"
    status = task.status

    lines = [f"# Task Context: #{task_id}", ""]
    lines.append(f"**{desc}**")
    lines.append("")

    # Basic info
    lines.append("### Details")
    if task.project:
        lines.append(f"- **Project**: {task.project}")
    if task.priority:
        priority_map = {"H": "High", "M": "Medium", "L": "Low"}
        lines.append(f"- **Priority**: {priority_map.get(task.priority, task.priority)}")
    if task.due:
        lines.append(f"- **Due**: {task.due}")
    if task.tags:
        lines.append(f"- **Tags**: {', '.join(task.tags)}")
    lines.append(f"- **Status**: {status}")
    lines.append(f"- **Urgency**: {task.urgency:.2f}")
    lines.append("")

    # Computed insights
    lines.append("### Insights")
    lines.append(f"- **Age**: Created {age}")
    lines.append(f"- **Last Activity**: {last_activity}")
    lines.append(f"- **Dependencies**: {dep_status}")
    if computed.annotations_count > 0:
        lines.append(f"- **Notes**: {computed.annotations_count} annotation(s)")
    lines.append("")

    # Annotations
    if task.annotations:
        lines.append("### Notes")
        for ann in task.annotations:
            entry = ann.entry[:10] if ann.entry else ""
            lines.append(f"- [{entry}] {ann.description}")
        lines.append("")

    # Related tasks
    if params.include_related and related:
        lines.append(f"### Related Tasks ({len(related)} in same project)")
        for r in related:
            r_id = r.id if r.id else "?"
            r_desc = r.description[:40] if r.description else ""
            lines.append(f"- #{r_id}: {r_desc}")

    return "\n".join(lines)


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    mcp.run()
