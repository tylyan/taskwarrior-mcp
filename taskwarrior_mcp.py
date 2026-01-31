#!/usr/bin/env python3
"""
MCP Server for Taskwarrior.

This server provides tools to interact with Taskwarrior CLI, enabling task
management operations including listing, creating, completing, modifying,
and organizing tasks with projects and tags.
"""

import json
import subprocess
import shlex
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP

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

    filter: Optional[str] = Field(
        default=None,
        description="Taskwarrior filter expression (e.g., 'project:work', '+urgent', 'due:today')"
    )
    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        description="Filter by task status: pending, completed, deleted, or all"
    )
    limit: Optional[int] = Field(
        default=50,
        description="Maximum number of tasks to return",
        ge=1,
        le=500
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class AddTaskInput(BaseModel):
    """Input model for adding a new task."""
    model_config = ConfigDict(str_strip_whitespace=True)

    description: str = Field(
        ...,
        description="Task description (required)",
        min_length=1,
        max_length=1000
    )
    project: Optional[str] = Field(
        default=None,
        description="Project name to assign the task to"
    )
    priority: Optional[Priority] = Field(
        default=None,
        description="Task priority: H (high), M (medium), L (low)"
    )
    due: Optional[str] = Field(
        default=None,
        description="Due date (e.g., 'today', 'tomorrow', '2024-12-31', 'eow' for end of week)"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="List of tags to apply (without '+' prefix)",
        max_length=20
    )
    depends: Optional[str] = Field(
        default=None,
        description="Task ID(s) this task depends on (comma-separated)"
    )

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Description cannot be empty")
        return v.strip()


class CompleteTaskInput(BaseModel):
    """Input model for completing a task."""
    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(
        ...,
        description="Task ID or UUID to complete",
        min_length=1
    )


class ModifyTaskInput(BaseModel):
    """Input model for modifying a task."""
    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(
        ...,
        description="Task ID or UUID to modify",
        min_length=1
    )
    description: Optional[str] = Field(
        default=None,
        description="New task description"
    )
    project: Optional[str] = Field(
        default=None,
        description="New project name (use empty string to remove)"
    )
    priority: Optional[str] = Field(
        default=None,
        description="New priority: H, M, L, or empty to remove"
    )
    due: Optional[str] = Field(
        default=None,
        description="New due date (use empty string to remove)"
    )
    add_tags: Optional[List[str]] = Field(
        default=None,
        description="Tags to add (without '+' prefix)"
    )
    remove_tags: Optional[List[str]] = Field(
        default=None,
        description="Tags to remove (without '-' prefix)"
    )


class DeleteTaskInput(BaseModel):
    """Input model for deleting a task."""
    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(
        ...,
        description="Task ID or UUID to delete",
        min_length=1
    )


class AnnotateTaskInput(BaseModel):
    """Input model for adding an annotation to a task."""
    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(
        ...,
        description="Task ID or UUID to annotate",
        min_length=1
    )
    annotation: str = Field(
        ...,
        description="Annotation text to add",
        min_length=1,
        max_length=2000
    )


class GetTaskInput(BaseModel):
    """Input model for getting a single task."""
    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(
        ...,
        description="Task ID or UUID to retrieve",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class ListProjectsInput(BaseModel):
    """Input model for listing projects."""
    model_config = ConfigDict(str_strip_whitespace=True)

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class ListTagsInput(BaseModel):
    """Input model for listing tags."""
    model_config = ConfigDict(str_strip_whitespace=True)

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class StartTaskInput(BaseModel):
    """Input model for starting a task."""
    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(
        ...,
        description="Task ID or UUID to start",
        min_length=1
    )


class StopTaskInput(BaseModel):
    """Input model for stopping a task."""
    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(
        ...,
        description="Task ID or UUID to stop",
        min_length=1
    )


class UndoInput(BaseModel):
    """Input model for undo operation."""
    model_config = ConfigDict(str_strip_whitespace=True)
    # No parameters needed - undo is a global operation


# ============================================================================
# Shared Utilities
# ============================================================================

def _run_task_command(args: List[str], input_text: Optional[str] = None) -> tuple[bool, str]:
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
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            input=input_text
        )

        output = result.stdout.strip()
        if result.returncode != 0:
            error = result.stderr.strip() or output
            return False, f"Error: {error}"

        return True, output

    except subprocess.TimeoutExpired:
        return False, "Error: Command timed out after 30 seconds"
    except FileNotFoundError:
        return False, "Error: Taskwarrior is not installed or not in PATH. Install it with 'brew install task' or equivalent."
    except Exception as e:
        return False, f"Error: Unexpected error - {type(e).__name__}: {str(e)}"


def _get_tasks_json(filter_expr: Optional[str] = None, status: TaskStatus = TaskStatus.PENDING) -> tuple[bool, List[dict] | str]:
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


def _format_task_markdown(task: dict) -> str:
    """Format a single task as markdown."""
    lines = []

    # Header with ID and description
    task_id = task.get("id", task.get("uuid", "?")[:8])
    desc = task.get("description", "No description")
    status = task.get("status", "pending")

    status_icon = {"pending": "", "completed": "", "deleted": ""}
    icon = status_icon.get(status, "")

    lines.append(f"### {icon} [{task_id}] {desc}")

    # Details
    details = []
    if task.get("project"):
        details.append(f"**Project**: {task['project']}")
    if task.get("priority"):
        priority_map = {"H": "High", "M": "Medium", "L": "Low"}
        details.append(f"**Priority**: {priority_map.get(task['priority'], task['priority'])}")
    if task.get("due"):
        details.append(f"**Due**: {task['due']}")
    if task.get("tags"):
        details.append(f"**Tags**: {', '.join(task['tags'])}")
    if task.get("urgency"):
        details.append(f"**Urgency**: {task['urgency']:.2f}")

    if details:
        lines.append(" | ".join(details))

    # Annotations
    if task.get("annotations"):
        lines.append("**Notes:**")
        for ann in task["annotations"]:
            entry = ann.get("entry", "")[:10] if ann.get("entry") else ""
            desc = ann.get("description", "")
            lines.append(f"  - [{entry}] {desc}")

    return "\n".join(lines)


def _format_tasks_markdown(tasks: List[dict], title: str = "Tasks") -> str:
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
    annotations={
        "title": "List Tasks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
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
        return result

    tasks = result
    if params.limit and len(tasks) > params.limit:
        tasks = tasks[:params.limit]

    if params.response_format == ResponseFormat.JSON:
        return json.dumps({
            "total": len(result),
            "count": len(tasks),
            "tasks": tasks
        }, indent=2)

    title = "Tasks"
    if params.filter:
        title = f"Tasks matching '{params.filter}'"
    if params.status != TaskStatus.PENDING:
        title += f" ({params.status.value})"

    return _format_tasks_markdown(tasks, title)


@mcp.tool(
    name="taskwarrior_add",
    annotations={
        "title": "Add Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False
    }
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
    annotations={
        "title": "Complete Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
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
    annotations={
        "title": "Modify Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
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
    annotations={
        "title": "Delete Task",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False
    }
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
    annotations={
        "title": "Get Task Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
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

        task = tasks[0]

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(task, indent=2)

        return _format_task_markdown(task)

    except json.JSONDecodeError as e:
        return f"Error: Failed to parse task data - {str(e)}"


@mcp.tool(
    name="taskwarrior_annotate",
    annotations={
        "title": "Annotate Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False
    }
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
    annotations={
        "title": "Start Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
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
    annotations={
        "title": "Stop Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
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
    annotations={
        "title": "List Projects",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
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
    success, tasks = _get_tasks_json(status=TaskStatus.PENDING)

    if not success:
        return tasks

    # Count tasks per project
    project_counts: dict[str, int] = {}
    for task in tasks:
        project = task.get("project", "(none)")
        project_counts[project] = project_counts.get(project, 0) + 1

    if params.response_format == ResponseFormat.JSON:
        return json.dumps({
            "projects": [
                {"name": name, "task_count": count}
                for name, count in sorted(project_counts.items())
            ]
        }, indent=2)

    lines = ["# Projects", ""]
    if not project_counts:
        lines.append("No projects found.")
    else:
        for name, count in sorted(project_counts.items()):
            lines.append(f"- **{name}**: {count} task(s)")

    return "\n".join(lines)


@mcp.tool(
    name="taskwarrior_tags",
    annotations={
        "title": "List Tags",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
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
    success, tasks = _get_tasks_json(status=TaskStatus.PENDING)

    if not success:
        return tasks

    # Count tasks per tag
    tag_counts: dict[str, int] = {}
    for task in tasks:
        for tag in task.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if params.response_format == ResponseFormat.JSON:
        return json.dumps({
            "tags": [
                {"name": name, "task_count": count}
                for name, count in sorted(tag_counts.items())
            ]
        }, indent=2)

    lines = ["# Tags", ""]
    if not tag_counts:
        lines.append("No tags found.")
    else:
        for name, count in sorted(tag_counts.items()):
            lines.append(f"- **+{name}**: {count} task(s)")

    return "\n".join(lines)


@mcp.tool(
    name="taskwarrior_undo",
    annotations={
        "title": "Undo Last Change",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False
    }
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
    annotations={
        "title": "Task Summary",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def taskwarrior_summary() -> str:
    """
    Get a summary of task statistics.

    Use this tool to get an overview of pending tasks, including counts by
    project, priority, and urgency.

    Returns:
        Summary statistics of tasks
    """
    success, tasks = _get_tasks_json(status=TaskStatus.PENDING)

    if not success:
        return tasks

    if not tasks:
        return "# Task Summary\n\nNo pending tasks."

    # Calculate statistics
    total = len(tasks)
    by_priority = {"H": 0, "M": 0, "L": 0, "": 0}
    by_project: dict[str, int] = {}
    overdue = 0
    due_today = 0
    active = 0

    for task in tasks:
        priority = task.get("priority", "")
        by_priority[priority] = by_priority.get(priority, 0) + 1

        project = task.get("project", "(none)")
        by_project[project] = by_project.get(project, 0) + 1

        if task.get("start"):
            active += 1

        # Simple due date checking (Taskwarrior handles the complex logic)
        due = task.get("due", "")
        if due:
            # Check if urgency suggests overdue (urgency > 12 typically means overdue)
            urgency = task.get("urgency", 0)
            if urgency > 12:
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
        "## Top Projects"
    ]

    # Show top 5 projects by task count
    sorted_projects = sorted(by_project.items(), key=lambda x: x[1], reverse=True)[:5]
    for project, count in sorted_projects:
        lines.append(f"- {project}: {count}")

    return "\n".join(lines)


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    mcp.run()
