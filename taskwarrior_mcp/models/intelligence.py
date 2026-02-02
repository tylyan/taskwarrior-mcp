"""Output/intermediate models for agent intelligence features."""

from pydantic import BaseModel, Field

from taskwarrior_mcp.models.task import TaskModel


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
