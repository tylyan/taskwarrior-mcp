"""Parser helpers for Taskwarrior data."""

from typing import Any

from taskwarrior_mcp.models.task import TaskModel


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
