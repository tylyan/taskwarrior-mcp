"""CLI utilities for Taskwarrior interaction."""

import json
import subprocess
from typing import Any

from taskwarrior_mcp.enums import TaskStatus


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
            "Error: Taskwarrior is not installed or not in PATH. Install it with 'brew install task' or equivalent."
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
