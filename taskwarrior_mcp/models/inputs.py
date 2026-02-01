"""Input models for Taskwarrior MCP tools."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from taskwarrior_mcp.enums import Priority, ResponseFormat, TaskStatus

# ============================================================================
# Core Tool Input Models
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
    limit: int | None = Field(default=50, description="Maximum number of tasks to return", ge=1, le=500)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable",
    )


class AddTaskInput(BaseModel):
    """Input model for adding a new task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    description: str = Field(..., description="Task description (required)", min_length=1, max_length=1000)
    project: str | None = Field(default=None, description="Project name to assign the task to")
    priority: Priority | None = Field(default=None, description="Task priority: H (high), M (medium), L (low)")
    due: str | None = Field(
        default=None,
        description="Due date (e.g., 'today', 'tomorrow', '2024-12-31', 'eow' for end of week)",
    )
    tags: list[str] | None = Field(
        default=None, description="List of tags to apply (without '+' prefix)", max_length=20
    )
    depends: str | None = Field(default=None, description="Task ID(s) this task depends on (comma-separated)")

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
    project: str | None = Field(default=None, description="New project name (use empty string to remove)")
    priority: str | None = Field(default=None, description="New priority: H, M, L, or empty to remove")
    due: str | None = Field(default=None, description="New due date (use empty string to remove)")
    add_tags: list[str] | None = Field(default=None, description="Tags to add (without '+' prefix)")
    remove_tags: list[str] | None = Field(default=None, description="Tags to remove (without '-' prefix)")


class DeleteTaskInput(BaseModel):
    """Input model for deleting a task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(..., description="Task ID or UUID to delete", min_length=1)


class AnnotateTaskInput(BaseModel):
    """Input model for adding an annotation to a task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(..., description="Task ID or UUID to annotate", min_length=1)
    annotation: str = Field(..., description="Annotation text to add", min_length=1, max_length=2000)


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

    task_ids: list[str] = Field(..., description="List of task IDs or UUIDs to retrieve", min_length=1, max_length=50)
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


class ProjectSummaryInput(BaseModel):
    """Input model for project summary."""

    model_config = ConfigDict(str_strip_whitespace=True)

    project: str | None = Field(
        default=None,
        description="Specific project to summarize, or None for all projects",
    )
    include_completed: bool = Field(
        default=False,
        description="Include completed task statistics",
    )
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

    limit: int = Field(default=5, description="Maximum number of suggestions to return", ge=1, le=20)
    context: str | None = Field(
        default=None,
        description="Context: 'quick_wins', 'blockers', 'deadlines', or None for balanced",
    )
    project: str | None = Field(default=None, description="Filter suggestions to a specific project")
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

    limit: int = Field(default=10, description="Maximum number of blocked tasks to return", ge=1, le=50)
    show_blockers: bool = Field(default=True, description="Show which tasks are blocking each blocked task")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: 'markdown' or 'json'"
    )


class DependenciesInput(BaseModel):
    """Input model for dependency graph analysis."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str | None = Field(default=None, description="Specific task ID to analyze, or None for overview")
    direction: str = Field(default="both", description="Direction: 'blocks', 'blocked_by', or 'both'")
    depth: int = Field(default=3, description="How deep to traverse the dependency tree", ge=1, le=10)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: 'markdown' or 'json'"
    )


class TriageInput(BaseModel):
    """Input model for task triage/review."""

    model_config = ConfigDict(str_strip_whitespace=True)

    stale_days: int = Field(default=14, description="Number of days before a task is considered stale", ge=1, le=365)
    include_untagged: bool = Field(default=True, description="Include tasks with no tags")
    include_no_project: bool = Field(default=True, description="Include tasks not assigned to a project")
    include_no_due: bool = Field(default=True, description="Include tasks with no due date")
    limit: int = Field(default=20, description="Maximum items per category", ge=1, le=100)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: 'markdown' or 'json'"
    )


class ContextInput(BaseModel):
    """Input model for rich task context."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(..., description="Task ID or UUID to get context for", min_length=1)
    include_related: bool = Field(default=True, description="Include related tasks from the same project")
    include_activity: bool = Field(default=True, description="Include recent activity information")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: 'markdown' or 'json'"
    )
