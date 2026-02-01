"""Pydantic models for Taskwarrior MCP."""

from taskwarrior_mcp.models.inputs import (
    AddTaskInput,
    AnnotateTaskInput,
    BlockedInput,
    BulkGetTasksInput,
    CompleteTaskInput,
    ContextInput,
    DeleteTaskInput,
    DependenciesInput,
    GetTaskInput,
    ListProjectsInput,
    ListTagsInput,
    ListTasksInput,
    ModifyTaskInput,
    ProjectSummaryInput,
    ReadyInput,
    StartTaskInput,
    StopTaskInput,
    SuggestInput,
    TriageInput,
    UndoInput,
)
from taskwarrior_mcp.models.intelligence import (
    BlockedTaskInfo,
    BottleneckInfo,
    ComputedInsights,
    ScoredTask,
)
from taskwarrior_mcp.models.task import ResolvedDependency, TaskAnnotation, TaskModel

__all__ = [
    # Task models
    "TaskAnnotation",
    "TaskModel",
    "ResolvedDependency",
    # Core input models
    "ListTasksInput",
    "AddTaskInput",
    "CompleteTaskInput",
    "ModifyTaskInput",
    "DeleteTaskInput",
    "AnnotateTaskInput",
    "GetTaskInput",
    "BulkGetTasksInput",
    "ListProjectsInput",
    "ProjectSummaryInput",
    "ListTagsInput",
    "StartTaskInput",
    "StopTaskInput",
    "UndoInput",
    # Agent intelligence input models
    "SuggestInput",
    "ReadyInput",
    "BlockedInput",
    "DependenciesInput",
    "TriageInput",
    "ContextInput",
    # Intelligence output models
    "ScoredTask",
    "BlockedTaskInfo",
    "BottleneckInfo",
    "ComputedInsights",
]
