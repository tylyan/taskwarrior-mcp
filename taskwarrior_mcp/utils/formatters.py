"""Formatting utilities for task output."""

from taskwarrior_mcp.models.task import TaskModel


def _format_task_concise(task: TaskModel) -> str:
    """
    Format a single task in concise format for token efficiency.

    Output: "#5: Description (H, due:2024-12-31, project:work)"
    """
    task_id = task.id if task.id else "?"
    desc = task.description[:50] if task.description else "No description"

    # Build compact metadata
    meta = []
    if task.priority:
        meta.append(task.priority)
    if task.due:
        meta.append(f"due:{task.due[:10]}")
    if task.project:
        meta.append(f"proj:{task.project}")

    if meta:
        return f"#{task_id}: {desc} ({', '.join(meta)})"
    return f"#{task_id}: {desc}"


def _format_tasks_concise(tasks: list[TaskModel], title: str | None = None) -> str:
    """
    Format a list of tasks in concise format for token efficiency.

    Output:
    5 tasks | project:work
    #1: Task one (H, due:today)
    #2: Task two (M)
    """
    if not tasks:
        return "0 tasks"

    lines = []

    # Header with count
    header = f"{len(tasks)} task(s)"
    if title:
        header = f"{len(tasks)} task(s) | {title}"
    lines.append(header)

    # Task lines
    for task in tasks:
        lines.append(_format_task_concise(task))

    return "\n".join(lines)


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
