"""Parser helpers for Taskwarrior data."""

from typing import Any

from taskwarrior_mcp.models.task import ResolvedDependency, TaskModel


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


def _enrich_task_dependencies(
    task: TaskModel,
    uuid_to_task: dict[str, TaskModel],
) -> TaskModel:
    """
    Resolve dependency UUIDs to task references.

    Populates the `depends_on` field with ResolvedDependency objects
    and sets `blocked_by_pending` to count pending blockers.

    Args:
        task: Task to enrich
        uuid_to_task: Mapping of UUID to TaskModel for lookup

    Returns:
        The same task with resolved dependency fields populated
    """
    if not task.depends:
        return task

    resolved: list[ResolvedDependency] = []
    pending_count = 0

    for uuid in task.depends.split(","):
        uuid = uuid.strip()
        if dep_task := uuid_to_task.get(uuid):
            resolved.append(
                ResolvedDependency(
                    id=dep_task.id,
                    uuid=uuid,
                    description=dep_task.description,
                    status=dep_task.status,
                )
            )
            if dep_task.status == "pending":
                pending_count += 1

    task.depends_on = resolved
    task.blocked_by_pending = pending_count
    return task


def _enrich_tasks_dependencies(tasks: list[TaskModel]) -> list[TaskModel]:
    """
    Batch enrich all tasks with resolved dependencies.

    Builds a UUID→TaskModel mapping and enriches each task.

    Args:
        tasks: List of tasks to enrich

    Returns:
        List of tasks with resolved dependency fields populated
    """
    uuid_to_task = {t.uuid: t for t in tasks if t.uuid}
    return [_enrich_task_dependencies(t, uuid_to_task) for t in tasks]
