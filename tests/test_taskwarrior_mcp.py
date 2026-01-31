"""Tests for the Taskwarrior MCP server."""

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock

from taskwarrior_mcp import (
    # Input models
    ListTasksInput,
    AddTaskInput,
    CompleteTaskInput,
    ModifyTaskInput,
    DeleteTaskInput,
    GetTaskInput,
    AnnotateTaskInput,
    StartTaskInput,
    StopTaskInput,
    ListProjectsInput,
    ListTagsInput,
    UndoInput,
    # Enums
    ResponseFormat,
    TaskStatus,
    Priority,
    # Private functions (for testing)
    _run_task_command as run_task_command,
    _format_task_markdown as format_task_markdown,
    _format_tasks_markdown as format_tasks_markdown,
    _get_tasks_json as get_tasks_json,
    # Tool functions
    taskwarrior_list,
    taskwarrior_add,
    taskwarrior_complete,
    taskwarrior_modify,
    taskwarrior_delete,
    taskwarrior_get,
    taskwarrior_annotate,
    taskwarrior_start,
    taskwarrior_stop,
    taskwarrior_projects,
    taskwarrior_tags,
    taskwarrior_undo,
    taskwarrior_summary,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_task():
    """A single sample task."""
    return {
        "id": 1,
        "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "description": "Test task",
        "status": "pending",
        "urgency": 5.0,
        "project": "test-project",
        "priority": "H",
        "tags": ["tag1", "tag2"],
        "due": "20250201T120000Z",
    }


@pytest.fixture
def sample_tasks():
    """A list of sample tasks."""
    return [
        {
            "id": 1,
            "description": "Task one",
            "status": "pending",
            "urgency": 8.0,
            "project": "work",
            "priority": "H",
            "tags": ["urgent"],
        },
        {
            "id": 2,
            "description": "Task two",
            "status": "pending",
            "urgency": 3.0,
            "project": "personal",
        },
        {
            "id": 3,
            "description": "Task three",
            "status": "pending",
            "urgency": 5.0,
            "project": "work",
            "tags": ["review"],
        },
    ]


# ============================================================================
# Input Model Tests
# ============================================================================

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

    def test_list_tasks_input_limit_validation(self):
        """Test ListTasksInput limit bounds."""
        # Valid limits
        assert ListTasksInput(limit=1).limit == 1
        assert ListTasksInput(limit=500).limit == 500

        # Invalid limits should raise validation error
        with pytest.raises(ValueError):
            ListTasksInput(limit=0)
        with pytest.raises(ValueError):
            ListTasksInput(limit=501)

    def test_add_task_input_required(self):
        """Test AddTaskInput with only required fields."""
        input_model = AddTaskInput(description="Test task")
        assert input_model.description == "Test task"
        assert input_model.project is None
        assert input_model.priority is None
        assert input_model.due is None
        assert input_model.tags is None
        assert input_model.depends is None

    def test_add_task_input_full(self):
        """Test AddTaskInput with all fields."""
        input_model = AddTaskInput(
            description="Test task",
            project="work",
            priority=Priority.HIGH,
            due="tomorrow",
            tags=["urgent", "review"],
            depends="1,2"
        )
        assert input_model.description == "Test task"
        assert input_model.project == "work"
        assert input_model.priority == Priority.HIGH
        assert input_model.due == "tomorrow"
        assert input_model.tags == ["urgent", "review"]
        assert input_model.depends == "1,2"

    def test_add_task_input_strips_whitespace(self):
        """Test that whitespace is stripped from string fields."""
        input_model = AddTaskInput(description="  Test task  ")
        assert input_model.description == "Test task"

    def test_add_task_input_empty_description_fails(self):
        """Test that empty description raises validation error."""
        with pytest.raises(ValueError):
            AddTaskInput(description="")
        with pytest.raises(ValueError):
            AddTaskInput(description="   ")

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

    def test_delete_task_input(self):
        """Test DeleteTaskInput validation."""
        input_model = DeleteTaskInput(task_id="10")
        assert input_model.task_id == "10"

    def test_get_task_input(self):
        """Test GetTaskInput with response format."""
        input_model = GetTaskInput(task_id="5", response_format=ResponseFormat.JSON)
        assert input_model.task_id == "5"
        assert input_model.response_format == ResponseFormat.JSON

    def test_annotate_task_input(self):
        """Test AnnotateTaskInput validation."""
        input_model = AnnotateTaskInput(task_id="5", annotation="This is a note")
        assert input_model.task_id == "5"
        assert input_model.annotation == "This is a note"

    def test_start_stop_task_input(self):
        """Test StartTaskInput and StopTaskInput."""
        start = StartTaskInput(task_id="5")
        stop = StopTaskInput(task_id="5")
        assert start.task_id == "5"
        assert stop.task_id == "5"

    def test_list_projects_tags_input(self):
        """Test ListProjectsInput and ListTagsInput."""
        projects = ListProjectsInput(response_format=ResponseFormat.JSON)
        tags = ListTagsInput(response_format=ResponseFormat.MARKDOWN)
        assert projects.response_format == ResponseFormat.JSON
        assert tags.response_format == ResponseFormat.MARKDOWN

    def test_undo_input(self):
        """Test UndoInput (no params needed)."""
        undo = UndoInput()
        assert undo is not None


# ============================================================================
# Enum Tests
# ============================================================================

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


# ============================================================================
# Utility Function Tests
# ============================================================================

class TestRunTaskCommand:
    """Tests for the run_task_command utility function."""

    def test_run_task_command_success(self):
        """Test successful command execution."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Created task 1.",
                stderr=""
            )
            success, output = run_task_command(["add", "Test"])
            assert success is True
            assert output == "Created task 1."
            mock_run.assert_called_once()

    def test_run_task_command_error(self):
        """Test command execution with error."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Task not found."
            )
            success, output = run_task_command(["complete", "999"])
            assert success is False
            assert "Task not found" in output

    def test_run_task_command_timeout(self):
        """Test command execution timeout."""
        import subprocess
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="task", timeout=30)
            success, output = run_task_command(["list"])
            assert success is False
            assert "timed out" in output.lower()

    def test_run_task_command_not_found(self):
        """Test when Taskwarrior is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            success, output = run_task_command(["list"])
            assert success is False
            assert "not installed" in output.lower()

    def test_run_task_command_unexpected_error(self):
        """Test handling of unexpected errors."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("Unexpected")
            success, output = run_task_command(["list"])
            assert success is False
            assert "RuntimeError" in output


class TestGetTasksJson:
    """Tests for the get_tasks_json utility function."""

    def test_get_tasks_json_success(self, sample_tasks):
        """Test successful JSON parsing."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_tasks),
                stderr=""
            )
            success, tasks = get_tasks_json()
            assert success is True
            assert len(tasks) == 3

    def test_get_tasks_json_empty(self):
        """Test empty task list."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr=""
            )
            success, tasks = get_tasks_json()
            assert success is True
            assert tasks == []

    def test_get_tasks_json_with_filter(self, sample_tasks):
        """Test with filter expression."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_tasks[:1]),
                stderr=""
            )
            success, tasks = get_tasks_json(filter_expr="project:work")
            assert success is True
            # Verify filter was passed to command
            call_args = mock_run.call_args[0][0]
            assert "project:work" in call_args

    def test_get_tasks_json_status_filters(self, sample_tasks):
        """Test different status filters."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_tasks),
                stderr=""
            )

            # Test pending status
            get_tasks_json(status=TaskStatus.PENDING)
            assert "status:pending" in mock_run.call_args[0][0]

            # Test completed status
            get_tasks_json(status=TaskStatus.COMPLETED)
            assert "status:completed" in mock_run.call_args[0][0]

            # Test deleted status
            get_tasks_json(status=TaskStatus.DELETED)
            assert "status:deleted" in mock_run.call_args[0][0]

    def test_get_tasks_json_parse_error(self):
        """Test handling of invalid JSON."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="not valid json",
                stderr=""
            )
            success, result = get_tasks_json()
            assert success is False
            assert "Failed to parse" in result


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
        assert "Project" in result

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

    def test_format_task_with_all_priorities(self):
        """Test all priority levels format correctly."""
        for priority, expected in [("H", "High"), ("M", "Medium"), ("L", "Low")]:
            task = {"id": 1, "description": "Test", "priority": priority}
            result = format_task_markdown(task)
            assert expected in result

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

    def test_format_task_with_annotations(self):
        """Test formatting a task with annotations."""
        task = {
            "id": 1,
            "description": "Test task",
            "annotations": [
                {"entry": "20250130T100000Z", "description": "First note"},
                {"entry": "20250130T110000Z", "description": "Second note"}
            ]
        }
        result = format_task_markdown(task)
        assert "Notes" in result
        assert "First note" in result
        assert "Second note" in result

    def test_format_task_status_icons(self):
        """Test status icons in formatting."""
        for status in ["pending", "completed", "deleted"]:
            task = {"id": 1, "description": "Test", "status": status}
            result = format_task_markdown(task)
            assert "Test" in result  # Just verify it doesn't crash


class TestFormatTasksMarkdown:
    """Tests for the format_tasks_markdown function."""

    def test_format_empty_list(self):
        """Test formatting empty task list."""
        result = format_tasks_markdown([])
        assert "No tasks found" in result

    def test_format_multiple_tasks(self, sample_tasks):
        """Test formatting multiple tasks."""
        result = format_tasks_markdown(sample_tasks)
        assert "3 task(s)" in result
        assert "Task one" in result
        assert "Task two" in result
        assert "Task three" in result

    def test_format_with_custom_title(self, sample_tasks):
        """Test formatting with custom title."""
        result = format_tasks_markdown(sample_tasks, title="Work Tasks")
        assert "Work Tasks" in result


# ============================================================================
# Tool Function Tests
# ============================================================================

class TestTaskwarriorList:
    """Tests for the taskwarrior_list tool."""

    @pytest.mark.asyncio
    async def test_list_tasks_markdown(self, sample_tasks):
        """Test listing tasks in markdown format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_tasks),
                stderr=""
            )
            params = ListTasksInput()
            result = await taskwarrior_list(params)
            assert "Task one" in result
            assert "Task two" in result

    @pytest.mark.asyncio
    async def test_list_tasks_json(self, sample_tasks):
        """Test listing tasks in JSON format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_tasks),
                stderr=""
            )
            params = ListTasksInput(response_format=ResponseFormat.JSON)
            result = await taskwarrior_list(params)
            data = json.loads(result)
            assert data["total"] == 3
            assert data["count"] == 3
            assert len(data["tasks"]) == 3

    @pytest.mark.asyncio
    async def test_list_tasks_with_limit(self, sample_tasks):
        """Test listing tasks with limit."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_tasks),
                stderr=""
            )
            params = ListTasksInput(limit=2, response_format=ResponseFormat.JSON)
            result = await taskwarrior_list(params)
            data = json.loads(result)
            assert data["total"] == 3
            assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_list_tasks_with_filter(self, sample_tasks):
        """Test listing tasks with filter."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_tasks[:1]),
                stderr=""
            )
            params = ListTasksInput(filter="project:work")
            result = await taskwarrior_list(params)
            assert "project:work" in result

    @pytest.mark.asyncio
    async def test_list_tasks_error(self):
        """Test handling errors in list."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Database error"
            )
            params = ListTasksInput()
            result = await taskwarrior_list(params)
            assert "Error" in result


class TestTaskwarriorAdd:
    """Tests for the taskwarrior_add tool."""

    @pytest.mark.asyncio
    async def test_add_simple_task(self):
        """Test adding a simple task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Created task 1.",
                stderr=""
            )
            params = AddTaskInput(description="Buy groceries")
            result = await taskwarrior_add(params)
            assert "Task created successfully" in result
            assert "Created task 1" in result

    @pytest.mark.asyncio
    async def test_add_task_with_project(self):
        """Test adding a task with project."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Created task 1.",
                stderr=""
            )
            params = AddTaskInput(description="Review PR", project="work")
            result = await taskwarrior_add(params)
            # Verify project was included in command
            call_args = mock_run.call_args[0][0]
            assert any("project:" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_add_task_with_priority(self):
        """Test adding a task with priority."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Created task 1.",
                stderr=""
            )
            params = AddTaskInput(description="Fix bug", priority=Priority.HIGH)
            result = await taskwarrior_add(params)
            call_args = mock_run.call_args[0][0]
            assert any("priority:H" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_add_task_with_due_date(self):
        """Test adding a task with due date."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Created task 1.",
                stderr=""
            )
            params = AddTaskInput(description="Submit report", due="friday")
            result = await taskwarrior_add(params)
            call_args = mock_run.call_args[0][0]
            assert any("due:" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_add_task_with_tags(self):
        """Test adding a task with tags."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Created task 1.",
                stderr=""
            )
            params = AddTaskInput(description="Call mom", tags=["personal", "important"])
            result = await taskwarrior_add(params)
            call_args = mock_run.call_args[0][0]
            assert any("+personal" in arg or "+important" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_add_task_with_depends(self):
        """Test adding a task with dependencies."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Created task 2.",
                stderr=""
            )
            params = AddTaskInput(description="Deploy", depends="1")
            result = await taskwarrior_add(params)
            call_args = mock_run.call_args[0][0]
            assert any("depends:" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_add_task_error(self):
        """Test handling errors when adding task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Invalid date format"
            )
            params = AddTaskInput(description="Test", due="invalid")
            result = await taskwarrior_add(params)
            assert "Error" in result


class TestTaskwarriorComplete:
    """Tests for the taskwarrior_complete tool."""

    @pytest.mark.asyncio
    async def test_complete_task(self):
        """Test completing a task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Completed task 5.",
                stderr=""
            )
            params = CompleteTaskInput(task_id="5")
            result = await taskwarrior_complete(params)
            assert "marked as complete" in result
            assert "5" in result

    @pytest.mark.asyncio
    async def test_complete_task_not_found(self):
        """Test completing non-existent task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="No matches."
            )
            params = CompleteTaskInput(task_id="999")
            result = await taskwarrior_complete(params)
            assert "Error" in result


class TestTaskwarriorModify:
    """Tests for the taskwarrior_modify tool."""

    @pytest.mark.asyncio
    async def test_modify_description(self):
        """Test modifying task description."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Modified 1 task.",
                stderr=""
            )
            params = ModifyTaskInput(task_id="5", description="New description")
            result = await taskwarrior_modify(params)
            assert "modified successfully" in result

    @pytest.mark.asyncio
    async def test_modify_project(self):
        """Test modifying task project."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Modified 1 task.",
                stderr=""
            )
            params = ModifyTaskInput(task_id="5", project="new-project")
            result = await taskwarrior_modify(params)
            call_args = mock_run.call_args[0][0]
            assert any("project:" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_modify_remove_project(self):
        """Test removing task project."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Modified 1 task.",
                stderr=""
            )
            params = ModifyTaskInput(task_id="5", project="")
            result = await taskwarrior_modify(params)
            call_args = mock_run.call_args[0][0]
            assert "project:" in call_args

    @pytest.mark.asyncio
    async def test_modify_add_tags(self):
        """Test adding tags to task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Modified 1 task.",
                stderr=""
            )
            params = ModifyTaskInput(task_id="5", add_tags=["urgent", "review"])
            result = await taskwarrior_modify(params)
            call_args = mock_run.call_args[0][0]
            assert any("+urgent" in arg or "+review" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_modify_remove_tags(self):
        """Test removing tags from task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Modified 1 task.",
                stderr=""
            )
            params = ModifyTaskInput(task_id="5", remove_tags=["old-tag"])
            result = await taskwarrior_modify(params)
            call_args = mock_run.call_args[0][0]
            assert any("-old-tag" in arg for arg in call_args)


class TestTaskwarriorDelete:
    """Tests for the taskwarrior_delete tool."""

    @pytest.mark.asyncio
    async def test_delete_task(self):
        """Test deleting a task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Deleted task 5.",
                stderr=""
            )
            params = DeleteTaskInput(task_id="5")
            result = await taskwarrior_delete(params)
            assert "deleted" in result.lower()
            assert "5" in result

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self):
        """Test deleting non-existent task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="No matches."
            )
            params = DeleteTaskInput(task_id="999")
            result = await taskwarrior_delete(params)
            assert "Error" in result


class TestTaskwarriorGet:
    """Tests for the taskwarrior_get tool."""

    @pytest.mark.asyncio
    async def test_get_task_markdown(self, sample_task):
        """Test getting task in markdown format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps([sample_task]),
                stderr=""
            )
            params = GetTaskInput(task_id="1")
            result = await taskwarrior_get(params)
            assert "Test task" in result
            assert "test-project" in result

    @pytest.mark.asyncio
    async def test_get_task_json(self, sample_task):
        """Test getting task in JSON format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps([sample_task]),
                stderr=""
            )
            params = GetTaskInput(task_id="1", response_format=ResponseFormat.JSON)
            result = await taskwarrior_get(params)
            data = json.loads(result)
            assert data["description"] == "Test task"

    @pytest.mark.asyncio
    async def test_get_task_not_found(self):
        """Test getting non-existent task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="[]",
                stderr=""
            )
            params = GetTaskInput(task_id="999")
            result = await taskwarrior_get(params)
            assert "not found" in result.lower()


class TestTaskwarriorAnnotate:
    """Tests for the taskwarrior_annotate tool."""

    @pytest.mark.asyncio
    async def test_annotate_task(self):
        """Test adding annotation to task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Annotating task 5.",
                stderr=""
            )
            params = AnnotateTaskInput(task_id="5", annotation="This is a note")
            result = await taskwarrior_annotate(params)
            assert "Annotation added" in result
            assert "5" in result

    @pytest.mark.asyncio
    async def test_annotate_task_not_found(self):
        """Test annotating non-existent task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="No matches."
            )
            params = AnnotateTaskInput(task_id="999", annotation="Note")
            result = await taskwarrior_annotate(params)
            assert "Error" in result


class TestTaskwarriorStart:
    """Tests for the taskwarrior_start tool."""

    @pytest.mark.asyncio
    async def test_start_task(self):
        """Test starting a task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Starting task 5.",
                stderr=""
            )
            params = StartTaskInput(task_id="5")
            result = await taskwarrior_start(params)
            assert "started" in result.lower()
            assert "5" in result


class TestTaskwarriorStop:
    """Tests for the taskwarrior_stop tool."""

    @pytest.mark.asyncio
    async def test_stop_task(self):
        """Test stopping a task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Stopping task 5.",
                stderr=""
            )
            params = StopTaskInput(task_id="5")
            result = await taskwarrior_stop(params)
            assert "stopped" in result.lower()
            assert "5" in result


class TestTaskwarriorProjects:
    """Tests for the taskwarrior_projects tool."""

    @pytest.mark.asyncio
    async def test_list_projects_markdown(self, sample_tasks):
        """Test listing projects in markdown format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_tasks),
                stderr=""
            )
            params = ListProjectsInput()
            result = await taskwarrior_projects(params)
            assert "Projects" in result
            assert "work" in result
            assert "personal" in result

    @pytest.mark.asyncio
    async def test_list_projects_json(self, sample_tasks):
        """Test listing projects in JSON format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_tasks),
                stderr=""
            )
            params = ListProjectsInput(response_format=ResponseFormat.JSON)
            result = await taskwarrior_projects(params)
            data = json.loads(result)
            assert "projects" in data
            project_names = [p["name"] for p in data["projects"]]
            assert "work" in project_names

    @pytest.mark.asyncio
    async def test_list_projects_empty(self):
        """Test listing projects with no tasks."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="[]",
                stderr=""
            )
            params = ListProjectsInput()
            result = await taskwarrior_projects(params)
            assert "No projects found" in result


class TestTaskwarriorTags:
    """Tests for the taskwarrior_tags tool."""

    @pytest.mark.asyncio
    async def test_list_tags_markdown(self, sample_tasks):
        """Test listing tags in markdown format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_tasks),
                stderr=""
            )
            params = ListTagsInput()
            result = await taskwarrior_tags(params)
            assert "Tags" in result
            assert "urgent" in result
            assert "review" in result

    @pytest.mark.asyncio
    async def test_list_tags_json(self, sample_tasks):
        """Test listing tags in JSON format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_tasks),
                stderr=""
            )
            params = ListTagsInput(response_format=ResponseFormat.JSON)
            result = await taskwarrior_tags(params)
            data = json.loads(result)
            assert "tags" in data
            tag_names = [t["name"] for t in data["tags"]]
            assert "urgent" in tag_names

    @pytest.mark.asyncio
    async def test_list_tags_empty(self):
        """Test listing tags with no tagged tasks."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps([{"id": 1, "description": "No tags"}]),
                stderr=""
            )
            params = ListTagsInput()
            result = await taskwarrior_tags(params)
            assert "No tags found" in result


class TestTaskwarriorUndo:
    """Tests for the taskwarrior_undo tool."""

    @pytest.mark.asyncio
    async def test_undo_success(self):
        """Test successful undo."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Reverted change.",
                stderr=""
            )
            params = UndoInput()
            result = await taskwarrior_undo(params)
            assert "Undo successful" in result

    @pytest.mark.asyncio
    async def test_undo_nothing_to_undo(self):
        """Test undo with nothing to undo."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="No changes to undo."
            )
            params = UndoInput()
            result = await taskwarrior_undo(params)
            assert "Error" in result


class TestTaskwarriorSummary:
    """Tests for the taskwarrior_summary tool."""

    @pytest.mark.asyncio
    async def test_summary_with_tasks(self, sample_tasks):
        """Test summary with pending tasks."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_tasks),
                stderr=""
            )
            result = await taskwarrior_summary()
            assert "Task Summary" in result
            assert "Total Pending Tasks" in result
            assert "3" in result
            assert "By Priority" in result
            assert "Top Projects" in result

    @pytest.mark.asyncio
    async def test_summary_empty(self):
        """Test summary with no pending tasks."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="[]",
                stderr=""
            )
            result = await taskwarrior_summary()
            assert "No pending tasks" in result

    @pytest.mark.asyncio
    async def test_summary_with_active_tasks(self):
        """Test summary counts active tasks."""
        tasks_with_active = [
            {"id": 1, "description": "Active task", "start": "20250130T100000Z", "status": "pending"},
            {"id": 2, "description": "Normal task", "status": "pending"},
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(tasks_with_active),
                stderr=""
            )
            result = await taskwarrior_summary()
            assert "Active" in result
            assert "1" in result  # One active task

    @pytest.mark.asyncio
    async def test_summary_priority_breakdown(self):
        """Test summary shows priority breakdown."""
        tasks_with_priorities = [
            {"id": 1, "description": "High", "priority": "H", "status": "pending"},
            {"id": 2, "description": "Medium", "priority": "M", "status": "pending"},
            {"id": 3, "description": "Low", "priority": "L", "status": "pending"},
            {"id": 4, "description": "None", "status": "pending"},
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(tasks_with_priorities),
                stderr=""
            )
            result = await taskwarrior_summary()
            assert "High: 1" in result
            assert "Medium: 1" in result
            assert "Low: 1" in result
            assert "No priority: 1" in result
