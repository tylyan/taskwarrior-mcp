"""Core MCP tool definitions for Taskwarrior."""

import json
import shlex

from mcp.types import ToolAnnotations

from taskwarrior_mcp.enums import ResponseFormat, TaskStatus
from taskwarrior_mcp.models.inputs import (
    AddTaskInput,
    AnnotateTaskInput,
    BulkGetTasksInput,
    CompleteTaskInput,
    DeleteTaskInput,
    GetTaskInput,
    ListProjectsInput,
    ListTagsInput,
    ListTasksInput,
    ModifyTaskInput,
    OverviewInput,
    ProjectSummaryInput,
    StartTaskInput,
    StopTaskInput,
    UndoInput,
)
from taskwarrior_mcp.server import mcp
from taskwarrior_mcp.utils.cli import _get_tasks_json, _run_task_command
from taskwarrior_mcp.utils.formatters import (
    _format_task_concise,
    _format_task_markdown,
    _format_tasks_concise,
    _format_tasks_markdown,
)
from taskwarrior_mcp.utils.parsers import (
    _enrich_tasks_dependencies,
    _parse_task,
    _parse_tasks,
)


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
    Search and filter tasks using Taskwarrior query expressions.

    USE THIS WHEN:
    - Searching for tasks matching criteria (project, tags, due date, etc.)
    - Getting a filtered subset of tasks
    - Exploring tasks you don't know the IDs of

    DO NOT USE WHEN:
    - You have a specific task ID → use taskwarrior_get instead
    - You have multiple known task IDs → use taskwarrior_bulk_get instead
    - You want prioritized suggestions → use taskwarrior_suggest instead
    - You want to see blocked/ready tasks → use taskwarrior_blocked or taskwarrior_ready

    FILTER SYNTAX (Taskwarrior expressions):
    - Project: "project:work" or "project.is:work"
    - Tags: "+urgent" (has tag) or "-completed" (excludes tag)
    - Due: "due:today", "due:tomorrow", "due:eow" (end of week), "due.before:2024-12-31"
    - Priority: "priority:H", "priority:M", "priority:L"
    - Description: "description.contains:meeting"
    - Combined: "project:work +urgent due.before:eow"

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
    tasks = _enrich_tasks_dependencies(tasks)  # Resolve dependency UUIDs
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

    if params.response_format == ResponseFormat.CONCISE:
        return _format_tasks_concise(tasks, params.filter)

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

    USE THIS WHEN:
    - Adding a new task to track
    - Creating tasks with metadata (project, priority, due date, tags)

    DO NOT USE WHEN:
    - Updating an existing task → use taskwarrior_modify instead
    - Adding notes to a task → use taskwarrior_annotate instead

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
    Update an existing task's attributes.

    USE THIS WHEN:
    - Changing task description, project, priority, due date, or tags
    - Organizing tasks (moving between projects, updating priorities)
    - Adding or removing tags

    DO NOT USE WHEN:
    - Creating a new task → use taskwarrior_add instead
    - Adding notes/comments → use taskwarrior_annotate instead
    - Marking task complete → use taskwarrior_complete instead
    - Starting/stopping work → use taskwarrior_start or taskwarrior_stop

    CLEARING VALUES: Use empty string to clear a field (e.g., due="" removes due date)

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
    Retrieve full details for a single task by ID or UUID.

    USE THIS WHEN:
    - You have a specific task ID (e.g., from a previous list call)
    - You need all task attributes including annotations
    - You want to inspect a task before modifying it

    DO NOT USE WHEN:
    - You want multiple tasks → use taskwarrior_bulk_get for known IDs
    - You want to search/filter tasks → use taskwarrior_list
    - You want context with related tasks and insights → use taskwarrior_context

    ACCEPTS: Task ID (numeric, e.g., "5") or UUID (e.g., "a1b2c3d4...")

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
            return (
                f"Error: Task '{params.task_id}' not found.\n"
                f"Tip: Use taskwarrior_list to find valid task IDs, "
                f"or check if the task was completed/deleted."
            )

        task = _parse_task(tasks[0])

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(task.model_dump(), indent=2)

        if params.response_format == ResponseFormat.CONCISE:
            return _format_task_concise(task)

        return _format_task_markdown(task)

    except json.JSONDecodeError as e:
        return (
            f"Error: Failed to parse task data - {str(e)}\n"
            f"Tip: This may indicate a Taskwarrior configuration issue."
        )


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
    Retrieve full details for multiple tasks by their IDs.

    USE THIS WHEN:
    - You have a list of specific task IDs to retrieve
    - You need details for multiple tasks from a previous search
    - More efficient than calling taskwarrior_get multiple times

    DO NOT USE WHEN:
    - You only need one task → use taskwarrior_get instead
    - You want to search/filter tasks → use taskwarrior_list instead
    - You don't know the task IDs → use taskwarrior_list to find them first

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
            return (
                f"Error: No tasks found for IDs: {', '.join(params.task_ids)}\n"
                f"Tip: Use taskwarrior_list to find valid task IDs. "
                f"These tasks may have been completed or deleted."
            )

        tasks = _parse_tasks(raw_tasks)
        tasks = _enrich_tasks_dependencies(tasks)  # Resolve dependency UUIDs

        if params.response_format == ResponseFormat.JSON:
            return json.dumps([t.model_dump() for t in tasks], indent=2)

        if params.response_format == ResponseFormat.CONCISE:
            return _format_tasks_concise(tasks)

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
        return (
            f"Error: Failed to parse task data - {str(e)}\n"
            f"Tip: This may indicate a Taskwarrior configuration issue."
        )


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
    List all projects and their task counts.

    USE THIS WHEN:
    - Getting a quick overview of project names
    - Seeing how tasks are distributed across projects

    DO NOT USE WHEN:
    - You want detailed project analytics → use taskwarrior_project_summary instead
    - You want to see tasks in a project → use taskwarrior_list with filter="project:name"

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
            {"projects": [{"name": name, "task_count": count} for name, count in sorted(project_counts.items())]},
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
    name="taskwarrior_project_summary",
    annotations=ToolAnnotations(
        title="Project Summary",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_project_summary(params: ProjectSummaryInput) -> str:
    """
    Get detailed analytics for projects including priority breakdown and due dates.

    USE THIS WHEN:
    - You want comprehensive project insights (overdue, due today, priority breakdown)
    - Analyzing workload distribution across projects
    - Getting a detailed status report for a specific project

    DO NOT USE WHEN:
    - You just need a list of project names → use taskwarrior_projects instead
    - You want task-level details → use taskwarrior_list with project filter
    - You want overall task summary → use taskwarrior_summary

    Args:
        params: ProjectSummaryInput with optional project filter and include_completed flag

    Returns:
        Detailed project summary (markdown or JSON)

    Examples:
        - Summarize all projects: params with default values
        - Summarize specific project: params with project="work"
        - Include completed stats: params with include_completed=True
    """
    from datetime import datetime, timezone

    # Get pending tasks
    success, result = _get_tasks_json(status=TaskStatus.PENDING)
    if not success:
        return str(result)

    raw_tasks = result if isinstance(result, list) else []
    pending_tasks = _parse_tasks(raw_tasks)

    # Get completed tasks if requested
    completed_tasks = []
    if params.include_completed:
        success, result = _get_tasks_json(status=TaskStatus.COMPLETED)
        if success and isinstance(result, list):
            completed_tasks = _parse_tasks(result)

    # Filter by project if specified
    if params.project:
        pending_tasks = [t for t in pending_tasks if t.project == params.project]
        completed_tasks = [t for t in completed_tasks if t.project == params.project]

        if not pending_tasks and not completed_tasks:
            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"error": f"Project '{params.project}' not found or has no tasks"})
            return f"Project '{params.project}' not found or has no tasks."

    # Group tasks by project
    project_data: dict[str, dict[str, int]] = {}
    now = datetime.now(timezone.utc)

    for task in pending_tasks:
        project_name = task.project or "(none)"
        if project_name not in project_data:
            project_data[project_name] = {
                "pending": 0,
                "completed": 0,
                "active": 0,
                "overdue": 0,
                "due_today": 0,
                "due_this_week": 0,
                "priority_h": 0,
                "priority_m": 0,
                "priority_l": 0,
                "no_priority": 0,
            }

        data = project_data[project_name]
        data["pending"] += 1

        # Priority breakdown
        if task.priority == "H":
            data["priority_h"] += 1
        elif task.priority == "M":
            data["priority_m"] += 1
        elif task.priority == "L":
            data["priority_l"] += 1
        else:
            data["no_priority"] += 1

        # Active tasks
        if task.start:
            data["active"] += 1

        # Due date analysis
        if task.due:
            try:
                # Parse Taskwarrior date format (ISO 8601)
                due_str = task.due.replace("Z", "+00:00")
                due_date = datetime.fromisoformat(due_str)
                days_until_due = (due_date - now).days

                if days_until_due < 0:
                    data["overdue"] += 1
                elif days_until_due == 0:
                    data["due_today"] += 1
                elif days_until_due <= 7:
                    data["due_this_week"] += 1
            except (ValueError, AttributeError):
                pass

    # Add completed counts
    for task in completed_tasks:
        project_name = task.project or "(none)"
        if project_name not in project_data:
            project_data[project_name] = {
                "pending": 0,
                "completed": 0,
                "active": 0,
                "overdue": 0,
                "due_today": 0,
                "due_this_week": 0,
                "priority_h": 0,
                "priority_m": 0,
                "priority_l": 0,
                "no_priority": 0,
            }
        project_data[project_name]["completed"] += 1

    if not project_data:
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"projects": [], "message": "No projects found"})
        return "# Project Summary\n\nNo projects found."

    # Format output
    if params.response_format == ResponseFormat.JSON:
        projects_list = []
        for name, data in sorted(project_data.items()):
            projects_list.append(
                {
                    "name": name,
                    "pending": data["pending"],
                    "completed": data["completed"],
                    "active": data["active"],
                    "overdue": data["overdue"],
                    "due_today": data["due_today"],
                    "due_this_week": data["due_this_week"],
                    "priority": {
                        "high": data["priority_h"],
                        "medium": data["priority_m"],
                        "low": data["priority_l"],
                        "none": data["no_priority"],
                    },
                }
            )
        return json.dumps({"projects": projects_list}, indent=2)

    # Markdown format
    lines = ["# Project Summary", ""]

    for name, data in sorted(project_data.items()):
        lines.append(f"## {name}")
        lines.append("")
        lines.append(f"**Pending Tasks**: {data['pending']}")

        if params.include_completed:
            lines.append(f"**Completed Tasks**: {data['completed']}")

        if data["active"] > 0:
            lines.append(f"**Active (in progress)**: {data['active']}")

        # Due dates
        if data["overdue"] > 0 or data["due_today"] > 0 or data["due_this_week"] > 0:
            lines.append("")
            lines.append("**Due Dates**:")
            if data["overdue"] > 0:
                lines.append(f"- ⚠️ Overdue: {data['overdue']}")
            if data["due_today"] > 0:
                lines.append(f"- 📅 Due today: {data['due_today']}")
            if data["due_this_week"] > 0:
                lines.append(f"- 📆 Due this week: {data['due_this_week']}")

        # Priority breakdown
        lines.append("")
        lines.append("**Priority**:")
        lines.append(f"- High: {data['priority_h']}")
        lines.append(f"- Medium: {data['priority_m']}")
        lines.append(f"- Low: {data['priority_l']}")
        lines.append(f"- None: {data['no_priority']}")
        lines.append("")

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
    List all tags and their usage counts.

    USE THIS WHEN:
    - Discovering what tags exist in the system
    - Seeing tag usage distribution

    DO NOT USE WHEN:
    - You want tasks with a specific tag → use taskwarrior_list with filter="+tagname"

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
            {"tags": [{"name": name, "task_count": count} for name, count in sorted(tag_counts.items())]},
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
    Get a high-level overview of task statistics.

    USE THIS WHEN:
    - You want a quick snapshot of all pending tasks
    - Getting counts by priority and top projects
    - Answering "how many tasks do I have?"

    DO NOT USE WHEN:
    - You want detailed per-project analytics → use taskwarrior_project_summary
    - You want to see actual tasks → use taskwarrior_list
    - You want suggestions on what to work on → use taskwarrior_suggest

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
    active = 0

    for task in tasks:
        priority = task.priority or ""
        by_priority[priority] = by_priority.get(priority, 0) + 1

        project = task.project or "(none)"
        by_project[project] = by_project.get(project, 0) + 1

        if task.start:
            active += 1

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


@mcp.tool(
    name="taskwarrior_overview",
    annotations=ToolAnnotations(
        title="Task Overview",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_overview(params: OverviewInput) -> str:
    """
    Get a comprehensive overview of tasks, projects, and tags in one call.

    USE THIS WHEN:
    - Starting a session and need to understand the task landscape
    - Getting summary stats, projects, AND tags efficiently
    - Answering "give me an overview of my tasks"

    DO NOT USE WHEN:
    - You only need task list → use taskwarrior_list
    - You need detailed project analytics → use taskwarrior_project_summary
    - You need task suggestions → use taskwarrior_suggest

    Args:
        params: OverviewInput with include_projects, include_tags, and response_format

    Returns:
        Consolidated overview with summary stats, projects, and tags

    Examples:
        - Full overview: params with defaults
        - Summary only: params with include_projects=False, include_tags=False
        - JSON format: params with response_format="json"
    """
    success, result = _get_tasks_json(status=TaskStatus.PENDING)

    if not success:
        return str(result)

    raw_tasks = result if isinstance(result, list) else []
    tasks = _parse_tasks(raw_tasks)

    # Compute all aggregations in a single pass
    total = len(tasks)
    by_priority: dict[str, int] = {"H": 0, "M": 0, "L": 0, "": 0}
    by_project: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    active = 0

    for task in tasks:
        by_priority[task.priority or ""] += 1
        project = task.project or "(none)"
        by_project[project] = by_project.get(project, 0) + 1
        for tag in task.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        if task.start:
            active += 1

    if params.response_format == ResponseFormat.JSON:
        data: dict[str, object] = {
            "summary": {
                "total": total,
                "active": active,
                "by_priority": by_priority,
            },
        }
        if params.include_projects:
            data["projects"] = [{"name": n, "count": c} for n, c in sorted(by_project.items())]
        if params.include_tags:
            data["tags"] = [{"name": n, "count": c} for n, c in sorted(tag_counts.items())]
        return json.dumps(data, indent=2)

    # Markdown format
    lines = [
        "# Task Overview",
        "",
        f"**Total Pending**: {total} | **Active**: {active}",
        f"**Priority**: H:{by_priority['H']} M:{by_priority['M']} L:{by_priority['L']}",
    ]

    if params.include_projects and by_project:
        lines.extend(["", "## Projects"])
        for name, count in sorted(by_project.items(), key=lambda x: -x[1]):
            lines.append(f"- {name}: {count}")

    if params.include_tags and tag_counts:
        lines.extend(["", "## Tags"])
        for name, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- +{name}: {count}")

    return "\n".join(lines)
