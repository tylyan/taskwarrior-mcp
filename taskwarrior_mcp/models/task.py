"""Core task models for Taskwarrior MCP."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TaskAnnotation(BaseModel):
    """Model for task annotations (notes)."""

    entry: str | None = None
    description: str = ""


class ResolvedDependency(BaseModel):
    """Lightweight resolved dependency reference.

    Contains just enough info about a dependency task for agents to understand
    blocking relationships without needing additional tool calls.
    """

    id: int | None = None
    uuid: str
    description: str
    status: str = "pending"


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

    # Resolved dependency fields (populated by enrichment)
    depends_on: list[ResolvedDependency] = Field(default_factory=list)
    blocked_by_pending: int = 0
