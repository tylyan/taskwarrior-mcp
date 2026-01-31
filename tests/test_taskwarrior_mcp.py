"""Tests for the Taskwarrior MCP server."""

import pytest
import json
from unittest.mock import patch, MagicMock

from taskwarrior_mcp import (
    ListTasksInput,
    AddTaskInput,
    CompleteTaskInput,
    ModifyTaskInput,
    DeleteTaskInput,
    GetTaskInput,
    AnnotateTaskInput,
    StartTaskInput,
    StopTaskInput,
    ResponseFormat,
    TaskStatus,
    Priority,
    _run_task_command as run_task_command,
    _format_task_markdown as format_task_markdown,
)


class TestInputModels:
    """Tests for Pydantic input models."""

    def test_list_tasks_input_defaults(self):
        """Test ListTasksInput with default values."""
        input_model = ListTasksInput()
        assert input_model.filter is None
        assert input_model.status == TaskStatus.PENDING
        assert input_model.limit == 50
        assert input_model.response_format == ResponseFormat.MARKDOWN

    def test_list_tasks_input_custom(self):
        """Test ListTasksInput with custom values."""
        input_model = ListTasksInput(
            filter="project:work",
            status=TaskStatus.COMPLETED,
            limit=10,
            response_format=ResponseFormat.JSON
        )
        assert input_model.filter == "project:work"
        assert input_model.status == TaskStatus.COMPLETED
        assert input_model.limit == 10
        assert input_model.response_format == ResponseFormat.JSON

    def test_add_task_input_required(self):
        """Test AddTaskInput with only required fields."""
        input_model = AddTaskInput(description="Test task")
        assert input_model.description == "Test task"
        assert input_model.project is None
        assert input_model.priority is None
        assert input_model.due is None
        assert input_model.tags is None

    def test_add_task_input_full(self):
        """Test AddTaskInput with all fields."""
        input_model = AddTaskInput(
            description="Test task",
            project="work",
            priority=Priority.HIGH,
            due="tomorrow",
            tags=["urgent", "review"]
        )
        assert input_model.description == "Test task"
        assert input_model.project == "work"
        assert input_model.priority == Priority.HIGH
        assert input_model.due == "tomorrow"
        assert input_model.tags == ["urgent", "review"]

    def test_add_task_input_strips_whitespace(self):
        """Test that whitespace is stripped from string fields."""
        input_model = AddTaskInput(description="  Test task  ")
        assert input_model.description == "Test task"

    def test_complete_task_input(self):
        """Test CompleteTaskInput validation."""
        input_model = CompleteTaskInput(task_id="5")
        assert input_model.task_id == "5"

    def test_modify_task_input(self):
        """Test ModifyTaskInput with various modifications."""
        input_model = ModifyTaskInput(
            task_id="3",
            description="Updated description",
            priority="H",
            add_tags=["new-tag"],
            remove_tags=["old-tag"]
        )
        assert input_model.task_id == "3"
        assert input_model.description == "Updated description"
        assert input_model.priority == "H"
        assert input_model.add_tags == ["new-tag"]
        assert input_model.remove_tags == ["old-tag"]


class TestRunTaskCommand:
    """Tests for the run_task_command utility function."""

    def test_run_task_command_success(self, mock_subprocess_success):
        """Test successful command execution."""
        success, output = run_task_command(["list"])
        assert success is True
        mock_subprocess_success.assert_called_once()

    def test_run_task_command_error(self, mock_subprocess_error):
        """Test command execution with error."""
        success, output = run_task_command(["complete", "999"])
        assert success is False
        assert "Task not found" in output

    def test_run_task_command_timeout(self, mock_subprocess_timeout):
        """Test command execution timeout."""
        success, output = run_task_command(["list"])
        assert success is False
        assert "timed out" in output.lower()


class TestFormatTaskMarkdown:
    """Tests for the format_task_markdown function."""

    def test_format_basic_task(self):
        """Test formatting a basic task."""
        task = {
            "id": 1,
            "description": "Test task",
            "status": "pending",
            "urgency": 5.0
        }
        result = format_task_markdown(task)
        assert "[1]" in result
        assert "Test task" in result

    def test_format_task_with_project(self):
        """Test formatting a task with project."""
        task = {
            "id": 1,
            "description": "Test task",
            "project": "work",
            "status": "pending",
            "urgency": 5.0
        }
        result = format_task_markdown(task)
        assert "work" in result

    def test_format_task_with_priority(self):
        """Test formatting a task with priority."""
        task = {
            "id": 1,
            "description": "Test task",
            "priority": "H",
            "status": "pending",
            "urgency": 8.0
        }
        result = format_task_markdown(task)
        assert "High" in result

    def test_format_task_with_tags(self):
        """Test formatting a task with tags."""
        task = {
            "id": 1,
            "description": "Test task",
            "tags": ["urgent", "review"],
            "status": "pending",
            "urgency": 5.0
        }
        result = format_task_markdown(task)
        assert "urgent" in result
        assert "review" in result

    def test_format_task_with_due_date(self):
        """Test formatting a task with due date."""
        task = {
            "id": 1,
            "description": "Test task",
            "due": "20250201T120000Z",
            "status": "pending",
            "urgency": 10.0
        }
        result = format_task_markdown(task)
        assert "Due" in result


class TestEnums:
    """Tests for enum values."""

    def test_response_format_values(self):
        """Test ResponseFormat enum values."""
        assert ResponseFormat.MARKDOWN.value == "markdown"
        assert ResponseFormat.JSON.value == "json"

    def test_task_status_values(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.DELETED.value == "deleted"
        assert TaskStatus.ALL.value == "all"

    def test_priority_values(self):
        """Test Priority enum values."""
        assert Priority.HIGH.value == "H"
        assert Priority.MEDIUM.value == "M"
        assert Priority.LOW.value == "L"
        assert Priority.NONE.value == ""
