"""Tests for the Taskwarrior MCP server."""

import json
from unittest.mock import MagicMock, patch

import pytest

from taskwarrior_mcp import (
    AddTaskInput,
    AnnotateTaskInput,
    BlockedTaskInfo,
    BottleneckInfo,
    BulkGetTasksInput,
    CompleteTaskInput,
    ComputedInsights,
    DeleteTaskInput,
    GetTaskInput,
    ListProjectsInput,
    ListTagsInput,
    # Input models
    ListTasksInput,
    ModifyTaskInput,
    Priority,
    # Enums
    ResponseFormat,
    ScoredTask,
    StartTaskInput,
    StopTaskInput,
    # Internal models
    TaskAnnotation,
    TaskModel,
    TaskStatus,
    UndoInput,
    # Parser helpers
    _parse_task,
    _parse_tasks,
    taskwarrior_add,
    taskwarrior_annotate,
    taskwarrior_bulk_get,
    taskwarrior_complete,
    taskwarrior_delete,
    taskwarrior_get,
    # Tool functions
    taskwarrior_list,
    taskwarrior_modify,
    taskwarrior_projects,
    taskwarrior_start,
    taskwarrior_stop,
    taskwarrior_summary,
    taskwarrior_tags,
    taskwarrior_undo,
)
from taskwarrior_mcp import (
    _format_task_concise as format_task_concise,
)
from taskwarrior_mcp import (
    _format_task_markdown as format_task_markdown,
)
from taskwarrior_mcp import (
    _format_tasks_concise as format_tasks_concise,
)
from taskwarrior_mcp import (
    _format_tasks_markdown as format_tasks_markdown,
)
from taskwarrior_mcp import (
    _get_tasks_json as get_tasks_json,
)
from taskwarrior_mcp import (
    # Private functions (for testing)
    _run_task_command as run_task_command,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_task():
    """A single sample task as dict (for tool tests that mock subprocess)."""
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
def sample_task_model():
    """A single sample task as TaskModel instance."""
    return TaskModel(
        id=1,
        uuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        description="Test task",
        status="pending",
        urgency=5.0,
        project="test-project",
        priority="H",
        tags=["tag1", "tag2"],
        due="20250201T120000Z",
    )


@pytest.fixture
def sample_tasks():
    """A list of sample tasks as dicts (for tool tests that mock subprocess)."""
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


@pytest.fixture
def sample_task_models():
    """A list of sample tasks as TaskModel instances."""
    return [
        TaskModel(
            id=1,
            description="Task one",
            status="pending",
            urgency=8.0,
            project="work",
            priority="H",
            tags=["urgent"],
        ),
        TaskModel(
            id=2,
            description="Task two",
            status="pending",
            urgency=3.0,
            project="personal",
        ),
        TaskModel(
            id=3,
            description="Task three",
            status="pending",
            urgency=5.0,
            project="work",
            tags=["review"],
        ),
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
            response_format=ResponseFormat.JSON,
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
            depends="1,2",
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
            remove_tags=["old-tag"],
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
        assert ResponseFormat.CONCISE.value == "concise"
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
            mock_run.return_value = MagicMock(returncode=0, stdout="Created task 1.", stderr="")
            success, output = run_task_command(["add", "Test"])
            assert success is True
            assert output == "Created task 1."
            mock_run.assert_called_once()

    def test_run_task_command_error(self):
        """Test command execution with error."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Task not found.")
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
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")
            success, tasks = get_tasks_json()
            assert success is True
            assert len(tasks) == 3

    def test_get_tasks_json_empty(self):
        """Test empty task list."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            success, tasks = get_tasks_json()
            assert success is True
            assert tasks == []

    def test_get_tasks_json_with_filter(self, sample_tasks):
        """Test with filter expression."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks[:1]), stderr="")
            success, tasks = get_tasks_json(filter_expr="project:work")
            assert success is True
            # Verify filter was passed to command
            call_args = mock_run.call_args[0][0]
            assert "project:work" in call_args

    def test_get_tasks_json_status_filters(self, sample_tasks):
        """Test different status filters."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")

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
            mock_run.return_value = MagicMock(returncode=0, stdout="not valid json", stderr="")
            success, result = get_tasks_json()
            assert success is False
            assert "Failed to parse" in result


class TestFormatTaskMarkdown:
    """Tests for the format_task_markdown function."""

    def test_format_basic_task(self):
        """Test formatting a basic task."""
        task = _parse_task({"id": 1, "description": "Test task", "status": "pending", "urgency": 5.0})
        result = format_task_markdown(task)
        assert "[1]" in result
        assert "Test task" in result

    def test_format_task_with_project(self):
        """Test formatting a task with project."""
        task = _parse_task(
            {
                "id": 1,
                "description": "Test task",
                "project": "work",
                "status": "pending",
                "urgency": 5.0,
            }
        )
        result = format_task_markdown(task)
        assert "work" in result
        assert "Project" in result

    def test_format_task_with_priority(self):
        """Test formatting a task with priority."""
        task = _parse_task(
            {
                "id": 1,
                "description": "Test task",
                "priority": "H",
                "status": "pending",
                "urgency": 8.0,
            }
        )
        result = format_task_markdown(task)
        assert "High" in result

    def test_format_task_with_all_priorities(self):
        """Test all priority levels format correctly."""
        for priority, expected in [("H", "High"), ("M", "Medium"), ("L", "Low")]:
            task = _parse_task({"id": 1, "description": "Test", "priority": priority})
            result = format_task_markdown(task)
            assert expected in result

    def test_format_task_with_tags(self):
        """Test formatting a task with tags."""
        task = _parse_task(
            {
                "id": 1,
                "description": "Test task",
                "tags": ["urgent", "review"],
                "status": "pending",
                "urgency": 5.0,
            }
        )
        result = format_task_markdown(task)
        assert "urgent" in result
        assert "review" in result

    def test_format_task_with_due_date(self):
        """Test formatting a task with due date."""
        task = _parse_task(
            {
                "id": 1,
                "description": "Test task",
                "due": "20250201T120000Z",
                "status": "pending",
                "urgency": 10.0,
            }
        )
        result = format_task_markdown(task)
        assert "Due" in result

    def test_format_task_with_annotations(self):
        """Test formatting a task with annotations."""
        task = _parse_task(
            {
                "id": 1,
                "description": "Test task",
                "annotations": [
                    {"entry": "20250130T100000Z", "description": "First note"},
                    {"entry": "20250130T110000Z", "description": "Second note"},
                ],
            }
        )
        result = format_task_markdown(task)
        assert "Notes" in result
        assert "First note" in result
        assert "Second note" in result

    def test_format_task_status_icons(self):
        """Test status icons in formatting."""
        for status in ["pending", "completed", "deleted"]:
            task = _parse_task({"id": 1, "description": "Test", "status": status})
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
        result = format_tasks_markdown(_parse_tasks(sample_tasks))
        assert "3 task(s)" in result
        assert "Task one" in result
        assert "Task two" in result
        assert "Task three" in result

    def test_format_with_custom_title(self, sample_tasks):
        """Test formatting with custom title."""
        result = format_tasks_markdown(_parse_tasks(sample_tasks), title="Work Tasks")
        assert "Work Tasks" in result


class TestFormatTaskConcise:
    """Tests for the concise task formatter."""

    def test_format_task_concise_basic(self, sample_task_models):
        """Test concise formatting of a basic task."""
        task = sample_task_models[0]
        result = format_task_concise(task)
        assert "#1:" in result
        assert "Task one" in result

    def test_format_task_concise_with_metadata(self, sample_task_models):
        """Test concise formatting includes priority, due, project."""
        task = sample_task_models[0]  # Has priority H
        result = format_task_concise(task)
        assert "H" in result

    def test_format_tasks_concise_empty(self):
        """Test concise formatting of empty list."""
        result = format_tasks_concise([])
        assert "0 tasks" in result

    def test_format_tasks_concise_multiple(self, sample_task_models):
        """Test concise formatting of multiple tasks."""
        result = format_tasks_concise(sample_task_models)
        assert "3 task(s)" in result
        assert "#1:" in result
        assert "#2:" in result

    def test_format_tasks_concise_with_title(self, sample_task_models):
        """Test concise formatting with title."""
        result = format_tasks_concise(sample_task_models, "project:work")
        assert "project:work" in result

    def test_format_task_concise_blocked_indicator(self):
        """Test concise formatting shows BLOCKED indicator when blocked."""
        from taskwarrior_mcp import ResolvedDependency

        dep = ResolvedDependency(id=1, uuid="uuid-1", description="Blocker", status="pending")
        task = TaskModel(
            id=2,
            description="Blocked task",
            depends_on=[dep],
            blocked_by_pending=1,
        )
        result = format_task_concise(task)
        assert "BLOCKED(1)" in result

    def test_format_task_concise_no_blocked_when_deps_complete(self):
        """Test concise formatting hides BLOCKED when deps are complete."""
        from taskwarrior_mcp import ResolvedDependency

        dep = ResolvedDependency(id=1, uuid="uuid-1", description="Done blocker", status="completed")
        task = TaskModel(
            id=2,
            description="Was blocked task",
            depends_on=[dep],
            blocked_by_pending=0,
        )
        result = format_task_concise(task)
        assert "BLOCKED" not in result


class TestFormatTaskMarkdownDependencies:
    """Tests for markdown formatter dependency display."""

    def test_format_task_markdown_with_pending_deps(self):
        """Test markdown formatting shows blocked by section."""
        from taskwarrior_mcp import ResolvedDependency

        dep1 = ResolvedDependency(id=1, uuid="uuid-1", description="Blocker one", status="pending")
        dep2 = ResolvedDependency(id=2, uuid="uuid-2", description="Blocker two", status="pending")
        task = TaskModel(
            id=3,
            description="Blocked task",
            depends_on=[dep1, dep2],
            blocked_by_pending=2,
        )
        result = format_task_markdown(task)
        assert "**Blocked by**" in result
        assert "2 pending" in result
        assert "#1: Blocker one" in result
        assert "#2: Blocker two" in result

    def test_format_task_markdown_with_completed_deps(self):
        """Test markdown formatting shows dependencies resolved."""
        from taskwarrior_mcp import ResolvedDependency

        dep = ResolvedDependency(id=1, uuid="uuid-1", description="Done blocker", status="completed")
        task = TaskModel(
            id=2,
            description="Was blocked",
            depends_on=[dep],
            blocked_by_pending=0,
        )
        result = format_task_markdown(task)
        assert "**Dependencies** (all resolved)" in result
        assert "#1: Done blocker" in result

    def test_format_task_markdown_no_deps_section_when_empty(self):
        """Test markdown formatting hides deps section when none."""
        task = TaskModel(id=1, description="No deps task")
        result = format_task_markdown(task)
        assert "Blocked by" not in result
        assert "Dependencies" not in result


# ============================================================================
# Tool Function Tests
# ============================================================================


class TestTaskwarriorList:
    """Tests for the taskwarrior_list tool."""

    @pytest.mark.asyncio
    async def test_list_tasks_markdown(self, sample_tasks):
        """Test listing tasks in markdown format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")
            params = ListTasksInput()
            result = await taskwarrior_list(params)
            assert "Task one" in result
            assert "Task two" in result

    @pytest.mark.asyncio
    async def test_list_tasks_json(self, sample_tasks):
        """Test listing tasks in JSON format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")
            params = ListTasksInput(response_format=ResponseFormat.JSON)
            result = await taskwarrior_list(params)
            data = json.loads(result)
            assert data["total"] == 3
            assert data["count"] == 3
            assert len(data["tasks"]) == 3

    @pytest.mark.asyncio
    async def test_list_tasks_concise(self, sample_tasks):
        """Test listing tasks in concise format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")
            params = ListTasksInput(response_format=ResponseFormat.CONCISE)
            result = await taskwarrior_list(params)
            assert "3 task(s)" in result
            assert "#1:" in result
            # Concise format should be shorter than markdown
            markdown_params = ListTasksInput(response_format=ResponseFormat.MARKDOWN)
            markdown_result = await taskwarrior_list(markdown_params)
            assert len(result) < len(markdown_result)

    @pytest.mark.asyncio
    async def test_list_tasks_with_limit(self, sample_tasks):
        """Test listing tasks with limit."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")
            params = ListTasksInput(limit=2, response_format=ResponseFormat.JSON)
            result = await taskwarrior_list(params)
            data = json.loads(result)
            assert data["total"] == 3
            assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_list_tasks_with_filter(self, sample_tasks):
        """Test listing tasks with filter."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks[:1]), stderr="")
            params = ListTasksInput(filter="project:work")
            result = await taskwarrior_list(params)
            assert "project:work" in result

    @pytest.mark.asyncio
    async def test_list_tasks_error(self):
        """Test handling errors in list."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Database error")
            params = ListTasksInput()
            result = await taskwarrior_list(params)
            assert "Error" in result


class TestTaskwarriorAdd:
    """Tests for the taskwarrior_add tool."""

    @pytest.mark.asyncio
    async def test_add_simple_task(self):
        """Test adding a simple task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Created task 1.", stderr="")
            params = AddTaskInput(description="Buy groceries")
            result = await taskwarrior_add(params)
            assert "Task created successfully" in result
            assert "Created task 1" in result

    @pytest.mark.asyncio
    async def test_add_task_with_project(self):
        """Test adding a task with project."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Created task 1.", stderr="")
            params = AddTaskInput(description="Review PR", project="work")
            await taskwarrior_add(params)
            # Verify project was included in command
            call_args = mock_run.call_args[0][0]
            assert any("project:" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_add_task_with_priority(self):
        """Test adding a task with priority."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Created task 1.", stderr="")
            params = AddTaskInput(description="Fix bug", priority=Priority.HIGH)
            await taskwarrior_add(params)
            call_args = mock_run.call_args[0][0]
            assert any("priority:H" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_add_task_with_due_date(self):
        """Test adding a task with due date."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Created task 1.", stderr="")
            params = AddTaskInput(description="Submit report", due="friday")
            await taskwarrior_add(params)
            call_args = mock_run.call_args[0][0]
            assert any("due:" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_add_task_with_tags(self):
        """Test adding a task with tags."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Created task 1.", stderr="")
            params = AddTaskInput(description="Call mom", tags=["personal", "important"])
            await taskwarrior_add(params)
            call_args = mock_run.call_args[0][0]
            assert any("+personal" in arg or "+important" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_add_task_with_depends(self):
        """Test adding a task with dependencies."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Created task 2.", stderr="")
            params = AddTaskInput(description="Deploy", depends="1")
            await taskwarrior_add(params)
            call_args = mock_run.call_args[0][0]
            assert any("depends:" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_add_task_error(self):
        """Test handling errors when adding task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Invalid date format")
            params = AddTaskInput(description="Test", due="invalid")
            result = await taskwarrior_add(params)
            assert "Error" in result


class TestTaskwarriorComplete:
    """Tests for the taskwarrior_complete tool."""

    @pytest.mark.asyncio
    async def test_complete_task(self):
        """Test completing a task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Completed task 5.", stderr="")
            params = CompleteTaskInput(task_id="5")
            result = await taskwarrior_complete(params)
            assert "marked as complete" in result
            assert "5" in result

    @pytest.mark.asyncio
    async def test_complete_task_not_found(self):
        """Test completing non-existent task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="No matches.")
            params = CompleteTaskInput(task_id="999")
            result = await taskwarrior_complete(params)
            assert "Error" in result


class TestTaskwarriorModify:
    """Tests for the taskwarrior_modify tool."""

    @pytest.mark.asyncio
    async def test_modify_description(self):
        """Test modifying task description."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Modified 1 task.", stderr="")
            params = ModifyTaskInput(task_id="5", description="New description")
            result = await taskwarrior_modify(params)
            assert "modified successfully" in result

    @pytest.mark.asyncio
    async def test_modify_project(self):
        """Test modifying task project."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Modified 1 task.", stderr="")
            params = ModifyTaskInput(task_id="5", project="new-project")
            await taskwarrior_modify(params)
            call_args = mock_run.call_args[0][0]
            assert any("project:" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_modify_remove_project(self):
        """Test removing task project."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Modified 1 task.", stderr="")
            params = ModifyTaskInput(task_id="5", project="")
            await taskwarrior_modify(params)
            call_args = mock_run.call_args[0][0]
            assert "project:" in call_args

    @pytest.mark.asyncio
    async def test_modify_add_tags(self):
        """Test adding tags to task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Modified 1 task.", stderr="")
            params = ModifyTaskInput(task_id="5", add_tags=["urgent", "review"])
            await taskwarrior_modify(params)
            call_args = mock_run.call_args[0][0]
            assert any("+urgent" in arg or "+review" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_modify_remove_tags(self):
        """Test removing tags from task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Modified 1 task.", stderr="")
            params = ModifyTaskInput(task_id="5", remove_tags=["old-tag"])
            await taskwarrior_modify(params)
            call_args = mock_run.call_args[0][0]
            assert any("-old-tag" in arg for arg in call_args)


class TestTaskwarriorDelete:
    """Tests for the taskwarrior_delete tool."""

    @pytest.mark.asyncio
    async def test_delete_task(self):
        """Test deleting a task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Deleted task 5.", stderr="")
            params = DeleteTaskInput(task_id="5")
            result = await taskwarrior_delete(params)
            assert "deleted" in result.lower()
            assert "5" in result

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self):
        """Test deleting non-existent task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="No matches.")
            params = DeleteTaskInput(task_id="999")
            result = await taskwarrior_delete(params)
            assert "Error" in result


class TestTaskwarriorGet:
    """Tests for the taskwarrior_get tool."""

    @pytest.mark.asyncio
    async def test_get_task_markdown(self, sample_task):
        """Test getting task in markdown format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps([sample_task]), stderr="")
            params = GetTaskInput(task_id="1")
            result = await taskwarrior_get(params)
            assert "Test task" in result
            assert "test-project" in result

    @pytest.mark.asyncio
    async def test_get_task_json(self, sample_task):
        """Test getting task in JSON format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps([sample_task]), stderr="")
            params = GetTaskInput(task_id="1", response_format=ResponseFormat.JSON)
            result = await taskwarrior_get(params)
            data = json.loads(result)
            assert data["description"] == "Test task"

    @pytest.mark.asyncio
    async def test_get_task_not_found(self):
        """Test getting non-existent task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
            params = GetTaskInput(task_id="999")
            result = await taskwarrior_get(params)
            assert "not found" in result.lower()


class TestBulkGetTasksInput:
    """Tests for BulkGetTasksInput model."""

    def test_valid_task_ids(self):
        """Test valid list of task IDs."""
        input_model = BulkGetTasksInput(task_ids=["1", "2", "3"])
        assert input_model.task_ids == ["1", "2", "3"]

    def test_default_response_format(self):
        """Test default response format is markdown."""
        input_model = BulkGetTasksInput(task_ids=["1"])
        assert input_model.response_format == ResponseFormat.MARKDOWN

    def test_json_response_format(self):
        """Test setting JSON response format."""
        input_model = BulkGetTasksInput(task_ids=["1"], response_format=ResponseFormat.JSON)
        assert input_model.response_format == ResponseFormat.JSON

    def test_empty_task_ids_fails(self):
        """Test that empty task_ids list raises validation error."""
        with pytest.raises(ValueError):
            BulkGetTasksInput(task_ids=[])

    def test_whitespace_task_ids_stripped(self):
        """Test that whitespace is stripped from task IDs."""
        input_model = BulkGetTasksInput(task_ids=["  1  ", "  2  "])
        assert input_model.task_ids == ["1", "2"]

    def test_whitespace_only_task_ids_rejected(self):
        """Test that whitespace-only task IDs are filtered out."""
        input_model = BulkGetTasksInput(task_ids=["1", "   ", "2"])
        assert input_model.task_ids == ["1", "2"]

    def test_all_whitespace_task_ids_fails(self):
        """Test that all whitespace-only task IDs raises validation error."""
        with pytest.raises(ValueError):
            BulkGetTasksInput(task_ids=["   ", "  "])


class TestTaskwarriorBulkGet:
    """Tests for the taskwarrior_bulk_get tool."""

    @pytest.mark.asyncio
    async def test_bulk_get_markdown(self, sample_tasks):
        """Test getting multiple tasks in markdown format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks[:2]), stderr="")
            params = BulkGetTasksInput(task_ids=["1", "2"])
            result = await taskwarrior_bulk_get(params)
            assert "Task one" in result
            assert "Task two" in result
            assert "2 tasks found" in result

    @pytest.mark.asyncio
    async def test_bulk_get_json(self, sample_tasks):
        """Test getting multiple tasks in JSON format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks[:2]), stderr="")
            params = BulkGetTasksInput(task_ids=["1", "2"], response_format=ResponseFormat.JSON)
            result = await taskwarrior_bulk_get(params)
            parsed = json.loads(result)
            assert len(parsed) == 2
            assert parsed[0]["description"] == "Task one"

    @pytest.mark.asyncio
    async def test_bulk_get_single_task(self, sample_task):
        """Test getting a single task using bulk get."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps([sample_task]), stderr="")
            params = BulkGetTasksInput(task_ids=["1"])
            result = await taskwarrior_bulk_get(params)
            assert "Test task" in result
            assert "1 tasks found" in result

    @pytest.mark.asyncio
    async def test_bulk_get_partial_not_found(self, sample_tasks):
        """Test bulk get when some tasks are not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps([sample_tasks[0]]), stderr="")
            params = BulkGetTasksInput(task_ids=["1", "999"])
            result = await taskwarrior_bulk_get(params)
            assert "Task one" in result
            assert "not found" in result.lower()
            assert "999" in result

    @pytest.mark.asyncio
    async def test_bulk_get_none_found(self):
        """Test bulk get when no tasks are found."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
            params = BulkGetTasksInput(task_ids=["999", "998"])
            result = await taskwarrior_bulk_get(params)
            assert "Error" in result or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_bulk_get_command_error(self):
        """Test handling errors from Taskwarrior command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Database error")
            params = BulkGetTasksInput(task_ids=["1", "2"])
            result = await taskwarrior_bulk_get(params)
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_bulk_get_uses_or_filter(self, sample_tasks):
        """Test that bulk get uses OR filter syntax."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")
            params = BulkGetTasksInput(task_ids=["1", "2", "3"])
            await taskwarrior_bulk_get(params)
            call_args = mock_run.call_args[0][0]
            # Verify OR filter is used
            assert any("or" in arg.lower() for arg in call_args)


class TestTaskwarriorAnnotate:
    """Tests for the taskwarrior_annotate tool."""

    @pytest.mark.asyncio
    async def test_annotate_task(self):
        """Test adding annotation to task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Annotating task 5.", stderr="")
            params = AnnotateTaskInput(task_id="5", annotation="This is a note")
            result = await taskwarrior_annotate(params)
            assert "Annotation added" in result
            assert "5" in result

    @pytest.mark.asyncio
    async def test_annotate_task_not_found(self):
        """Test annotating non-existent task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="No matches.")
            params = AnnotateTaskInput(task_id="999", annotation="Note")
            result = await taskwarrior_annotate(params)
            assert "Error" in result


class TestTaskwarriorStart:
    """Tests for the taskwarrior_start tool."""

    @pytest.mark.asyncio
    async def test_start_task(self):
        """Test starting a task."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Starting task 5.", stderr="")
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
            mock_run.return_value = MagicMock(returncode=0, stdout="Stopping task 5.", stderr="")
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
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")
            params = ListProjectsInput()
            result = await taskwarrior_projects(params)
            assert "Projects" in result
            assert "work" in result
            assert "personal" in result

    @pytest.mark.asyncio
    async def test_list_projects_json(self, sample_tasks):
        """Test listing projects in JSON format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")
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
            mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
            params = ListProjectsInput()
            result = await taskwarrior_projects(params)
            assert "No projects found" in result


class TestTaskwarriorTags:
    """Tests for the taskwarrior_tags tool."""

    @pytest.mark.asyncio
    async def test_list_tags_markdown(self, sample_tasks):
        """Test listing tags in markdown format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")
            params = ListTagsInput()
            result = await taskwarrior_tags(params)
            assert "Tags" in result
            assert "urgent" in result
            assert "review" in result

    @pytest.mark.asyncio
    async def test_list_tags_json(self, sample_tasks):
        """Test listing tags in JSON format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")
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
                returncode=0, stdout=json.dumps([{"id": 1, "description": "No tags"}]), stderr=""
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
            mock_run.return_value = MagicMock(returncode=0, stdout="Reverted change.", stderr="")
            params = UndoInput()
            result = await taskwarrior_undo(params)
            assert "Undo successful" in result

    @pytest.mark.asyncio
    async def test_undo_nothing_to_undo(self):
        """Test undo with nothing to undo."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="No changes to undo.")
            params = UndoInput()
            result = await taskwarrior_undo(params)
            assert "Error" in result


class TestTaskwarriorSummary:
    """Tests for the taskwarrior_summary tool."""

    @pytest.mark.asyncio
    async def test_summary_with_tasks(self, sample_tasks):
        """Test summary with pending tasks."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")
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
            mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
            result = await taskwarrior_summary()
            assert "No pending tasks" in result

    @pytest.mark.asyncio
    async def test_summary_with_active_tasks(self):
        """Test summary counts active tasks."""
        tasks_with_active = [
            {
                "id": 1,
                "description": "Active task",
                "start": "20250130T100000Z",
                "status": "pending",
            },
            {"id": 2, "description": "Normal task", "status": "pending"},
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks_with_active), stderr="")
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
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks_with_priorities), stderr="")
            result = await taskwarrior_summary()
            assert "High: 1" in result
            assert "Medium: 1" in result
            assert "Low: 1" in result
            assert "No priority: 1" in result


class TestTaskwarriorProjectSummary:
    """Tests for the taskwarrior_project_summary tool."""

    @pytest.mark.asyncio
    async def test_project_summary_all_projects_markdown(self, sample_tasks):
        """Test project summary for all projects in markdown format."""
        from taskwarrior_mcp import ProjectSummaryInput, taskwarrior_project_summary

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")
            params = ProjectSummaryInput()
            result = await taskwarrior_project_summary(params)
            assert "Project Summary" in result
            assert "work" in result
            assert "personal" in result
            # work has 2 tasks, personal has 1
            assert "2" in result
            assert "1" in result

    @pytest.mark.asyncio
    async def test_project_summary_single_project(self):
        """Test project summary for a specific project."""
        from taskwarrior_mcp import ProjectSummaryInput, taskwarrior_project_summary

        tasks = [
            {"id": 1, "description": "Task 1", "status": "pending", "project": "work", "priority": "H"},
            {"id": 2, "description": "Task 2", "status": "pending", "project": "work", "priority": "M"},
            {"id": 3, "description": "Task 3", "status": "pending", "project": "work"},
            {"id": 4, "description": "Other task", "status": "pending", "project": "personal"},
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks), stderr="")
            params = ProjectSummaryInput(project="work")
            result = await taskwarrior_project_summary(params)
            assert "work" in result
            assert "personal" not in result
            assert "3" in result  # 3 tasks in work project

    @pytest.mark.asyncio
    async def test_project_summary_json_format(self, sample_tasks):
        """Test project summary in JSON format."""
        from taskwarrior_mcp import ProjectSummaryInput, taskwarrior_project_summary

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")
            params = ProjectSummaryInput(response_format=ResponseFormat.JSON)
            result = await taskwarrior_project_summary(params)
            data = json.loads(result)
            assert "projects" in data
            project_names = [p["name"] for p in data["projects"]]
            assert "work" in project_names
            assert "personal" in project_names

    @pytest.mark.asyncio
    async def test_project_summary_priority_breakdown(self):
        """Test project summary includes priority breakdown."""
        from taskwarrior_mcp import ProjectSummaryInput, taskwarrior_project_summary

        tasks = [
            {"id": 1, "description": "High", "status": "pending", "project": "work", "priority": "H"},
            {"id": 2, "description": "Medium", "status": "pending", "project": "work", "priority": "M"},
            {"id": 3, "description": "Low", "status": "pending", "project": "work", "priority": "L"},
            {"id": 4, "description": "None", "status": "pending", "project": "work"},
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks), stderr="")
            params = ProjectSummaryInput(project="work")
            result = await taskwarrior_project_summary(params)
            assert "High" in result or "H:" in result
            assert "4" in result  # Total tasks

    @pytest.mark.asyncio
    async def test_project_summary_with_overdue_tasks(self):
        """Test project summary shows overdue tasks."""
        from taskwarrior_mcp import ProjectSummaryInput, taskwarrior_project_summary

        tasks = [
            {"id": 1, "description": "Overdue", "status": "pending", "project": "work", "due": "20240101T000000Z"},
            {"id": 2, "description": "Future", "status": "pending", "project": "work", "due": "20991231T000000Z"},
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks), stderr="")
            params = ProjectSummaryInput(project="work")
            result = await taskwarrior_project_summary(params)
            assert "overdue" in result.lower() or "Overdue" in result

    @pytest.mark.asyncio
    async def test_project_summary_with_active_tasks(self):
        """Test project summary shows active tasks."""
        from taskwarrior_mcp import ProjectSummaryInput, taskwarrior_project_summary

        tasks = [
            {"id": 1, "description": "Active", "status": "pending", "project": "work", "start": "20250130T100000Z"},
            {"id": 2, "description": "Not active", "status": "pending", "project": "work"},
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks), stderr="")
            params = ProjectSummaryInput(project="work")
            result = await taskwarrior_project_summary(params)
            assert "active" in result.lower() or "Active" in result

    @pytest.mark.asyncio
    async def test_project_summary_empty(self):
        """Test project summary with no tasks."""
        from taskwarrior_mcp import ProjectSummaryInput, taskwarrior_project_summary

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
            params = ProjectSummaryInput()
            result = await taskwarrior_project_summary(params)
            assert "No projects" in result or "no tasks" in result.lower()

    @pytest.mark.asyncio
    async def test_project_summary_nonexistent_project(self):
        """Test project summary for a project that doesn't exist."""
        from taskwarrior_mcp import ProjectSummaryInput, taskwarrior_project_summary

        tasks = [
            {"id": 1, "description": "Task", "status": "pending", "project": "work"},
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks), stderr="")
            params = ProjectSummaryInput(project="nonexistent")
            result = await taskwarrior_project_summary(params)
            assert "not found" in result.lower() or "no tasks" in result.lower()

    @pytest.mark.asyncio
    async def test_project_summary_include_completed(self):
        """Test project summary with completed tasks included."""
        from taskwarrior_mcp import ProjectSummaryInput, taskwarrior_project_summary

        pending_tasks = [
            {"id": 1, "description": "Pending", "status": "pending", "project": "work"},
        ]
        completed_tasks = [
            {"id": 2, "description": "Done", "status": "completed", "project": "work"},
        ]
        with patch("subprocess.run") as mock_run:
            # First call for pending, second for completed
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout=json.dumps(pending_tasks), stderr=""),
                MagicMock(returncode=0, stdout=json.dumps(completed_tasks), stderr=""),
            ]
            params = ProjectSummaryInput(project="work", include_completed=True)
            result = await taskwarrior_project_summary(params)
            assert "completed" in result.lower() or "Completed" in result


class TestProjectSummaryInput:
    """Tests for ProjectSummaryInput model."""

    def test_project_summary_input_defaults(self):
        """Test ProjectSummaryInput with default values."""
        from taskwarrior_mcp import ProjectSummaryInput

        input_model = ProjectSummaryInput()
        assert input_model.project is None
        assert input_model.include_completed is False
        assert input_model.response_format == ResponseFormat.MARKDOWN

    def test_project_summary_input_with_project(self):
        """Test ProjectSummaryInput with specific project."""
        from taskwarrior_mcp import ProjectSummaryInput

        input_model = ProjectSummaryInput(project="work")
        assert input_model.project == "work"

    def test_project_summary_input_json_format(self):
        """Test ProjectSummaryInput with JSON format."""
        from taskwarrior_mcp import ProjectSummaryInput

        input_model = ProjectSummaryInput(response_format=ResponseFormat.JSON)
        assert input_model.response_format == ResponseFormat.JSON


# ============================================================================
# Agent Intelligence Tools Tests
# ============================================================================


class TestSuggestInput:
    """Tests for SuggestInput model."""

    def test_suggest_input_defaults(self):
        """Test SuggestInput with default values."""
        from taskwarrior_mcp import SuggestInput

        input_model = SuggestInput()
        assert input_model.limit == 5
        assert input_model.context is None
        assert input_model.project is None
        assert input_model.response_format == ResponseFormat.MARKDOWN

    def test_suggest_input_custom(self):
        """Test SuggestInput with custom values."""
        from taskwarrior_mcp import SuggestInput

        input_model = SuggestInput(limit=10, context="quick_wins", project="work", response_format=ResponseFormat.JSON)
        assert input_model.limit == 10
        assert input_model.context == "quick_wins"
        assert input_model.project == "work"

    def test_suggest_input_limit_bounds(self):
        """Test SuggestInput limit validation."""
        from taskwarrior_mcp import SuggestInput

        assert SuggestInput(limit=1).limit == 1
        assert SuggestInput(limit=20).limit == 20
        with pytest.raises(ValueError):
            SuggestInput(limit=0)
        with pytest.raises(ValueError):
            SuggestInput(limit=21)


class TestTaskwarriorSuggest:
    """Tests for the taskwarrior_suggest tool."""

    @pytest.fixture
    def tasks_for_suggestions(self):
        """Tasks with varying priorities and attributes for testing suggestions."""
        return [
            {
                "id": 1,
                "description": "Overdue task",
                "status": "pending",
                "urgency": 15.0,  # High urgency indicates overdue
                "due": "20250101T120000Z",
                "priority": "H",
            },
            {
                "id": 2,
                "description": "Due tomorrow",
                "status": "pending",
                "urgency": 8.0,
                "due": "20250201T120000Z",  # Assuming today is Jan 31
            },
            {
                "id": 3,
                "description": "Active task",
                "status": "pending",
                "urgency": 5.0,
                "start": "20250130T100000Z",
            },
            {
                "id": 4,
                "description": "Low priority task",
                "status": "pending",
                "urgency": 2.0,
                "priority": "L",
            },
            {
                "id": 5,
                "description": "Tagged next",
                "status": "pending",
                "urgency": 4.0,
                "tags": ["next"],
            },
            {
                "id": 6,
                "description": "Blocks others",
                "status": "pending",
                "urgency": 6.0,
            },
        ]

    @pytest.mark.asyncio
    async def test_suggest_returns_prioritized_list(self, tasks_for_suggestions):
        """Test that suggest returns tasks in priority order."""
        from taskwarrior_mcp import SuggestInput, taskwarrior_suggest

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks_for_suggestions), stderr="")
            params = SuggestInput()
            result = await taskwarrior_suggest(params)
            assert "Suggested" in result or "Suggest" in result
            # Overdue task should appear (high urgency)
            assert "Overdue task" in result

    @pytest.mark.asyncio
    async def test_suggest_respects_limit(self, tasks_for_suggestions):
        """Test that suggest respects the limit parameter."""
        from taskwarrior_mcp import SuggestInput, taskwarrior_suggest

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks_for_suggestions), stderr="")
            params = SuggestInput(limit=2, response_format=ResponseFormat.JSON)
            result = await taskwarrior_suggest(params)
            data = json.loads(result)
            assert len(data["suggestions"]) <= 2

    @pytest.mark.asyncio
    async def test_suggest_filters_by_project(self, tasks_for_suggestions):
        """Test that suggest can filter by project."""
        from taskwarrior_mcp import SuggestInput, taskwarrior_suggest

        tasks_with_project = [
            {
                "id": 1,
                "description": "Work task",
                "project": "work",
                "urgency": 5.0,
                "status": "pending",
            },
            {
                "id": 2,
                "description": "Personal task",
                "project": "personal",
                "urgency": 5.0,
                "status": "pending",
            },
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks_with_project), stderr="")
            params = SuggestInput(project="work")
            result = await taskwarrior_suggest(params)
            assert "Work task" in result
            # Personal task should be filtered out or ranked lower

    @pytest.mark.asyncio
    async def test_suggest_includes_reasons(self, tasks_for_suggestions):
        """Test that suggestions include reasoning."""
        from taskwarrior_mcp import SuggestInput, taskwarrior_suggest

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks_for_suggestions), stderr="")
            params = SuggestInput()
            result = await taskwarrior_suggest(params)
            # Should have some reasoning indicator
            assert "Reason" in result or "→" in result or "reason" in result.lower()

    @pytest.mark.asyncio
    async def test_suggest_empty_tasks(self):
        """Test suggest with no tasks."""
        from taskwarrior_mcp import SuggestInput, taskwarrior_suggest

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
            params = SuggestInput()
            result = await taskwarrior_suggest(params)
            assert "no tasks" in result.lower() or "nothing" in result.lower()

    @pytest.mark.asyncio
    async def test_suggest_json_format(self, tasks_for_suggestions):
        """Test suggest returns valid JSON."""
        from taskwarrior_mcp import SuggestInput, taskwarrior_suggest

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks_for_suggestions), stderr="")
            params = SuggestInput(response_format=ResponseFormat.JSON)
            result = await taskwarrior_suggest(params)
            data = json.loads(result)
            assert "suggestions" in data
            for suggestion in data["suggestions"]:
                assert "task" in suggestion
                assert "score" in suggestion
                assert "reasons" in suggestion


class TestReadyInput:
    """Tests for ReadyInput model."""

    def test_ready_input_defaults(self):
        """Test ReadyInput with default values."""
        from taskwarrior_mcp import ReadyInput

        input_model = ReadyInput()
        assert input_model.limit == 10
        assert input_model.project is None
        assert input_model.priority is None
        assert input_model.include_active is True


class TestTaskwarriorReady:
    """Tests for the taskwarrior_ready tool."""

    @pytest.fixture
    def tasks_with_dependencies(self):
        """Tasks with dependency relationships."""
        return [
            {
                "id": 1,
                "description": "Ready task",
                "status": "pending",
                "urgency": 5.0,
            },
            {
                "id": 2,
                "description": "Blocked task",
                "status": "pending",
                "urgency": 5.0,
                "depends": "a1b2c3d4",  # Depends on task 1
            },
            {
                "id": 3,
                "description": "Another ready task",
                "status": "pending",
                "urgency": 8.0,
            },
        ]

    @pytest.mark.asyncio
    async def test_ready_returns_unblocked_tasks(self, tasks_with_dependencies):
        """Test that ready returns only unblocked tasks."""
        from taskwarrior_mcp import ReadyInput, taskwarrior_ready

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks_with_dependencies), stderr="")
            params = ReadyInput()
            result = await taskwarrior_ready(params)
            assert "Ready" in result
            # Task 2 is blocked, should not appear or be marked
            assert "Ready task" in result or "Another ready task" in result

    @pytest.mark.asyncio
    async def test_ready_filters_by_project(self):
        """Test ready can filter by project."""
        from taskwarrior_mcp import ReadyInput, taskwarrior_ready

        tasks = [
            {
                "id": 1,
                "description": "Work task",
                "project": "work",
                "urgency": 5.0,
                "status": "pending",
            },
            {
                "id": 2,
                "description": "Personal task",
                "project": "personal",
                "urgency": 5.0,
                "status": "pending",
            },
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks), stderr="")
            params = ReadyInput(project="work")
            result = await taskwarrior_ready(params)
            assert "Work task" in result

    @pytest.mark.asyncio
    async def test_ready_json_format(self, tasks_with_dependencies):
        """Test ready returns valid JSON."""
        from taskwarrior_mcp import ReadyInput, taskwarrior_ready

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks_with_dependencies), stderr="")
            params = ReadyInput(response_format=ResponseFormat.JSON)
            result = await taskwarrior_ready(params)
            data = json.loads(result)
            assert "tasks" in data
            assert "count" in data


class TestBlockedInput:
    """Tests for BlockedInput model."""

    def test_blocked_input_defaults(self):
        """Test BlockedInput with default values."""
        from taskwarrior_mcp import BlockedInput

        input_model = BlockedInput()
        assert input_model.limit == 10
        assert input_model.show_blockers is True


class TestTaskwarriorBlocked:
    """Tests for the taskwarrior_blocked tool."""

    @pytest.mark.asyncio
    async def test_blocked_returns_blocked_tasks(self):
        """Test that blocked returns tasks with dependencies."""
        from taskwarrior_mcp import BlockedInput, taskwarrior_blocked

        tasks = [
            {
                "id": 1,
                "uuid": "uuid1",
                "description": "Blocker task",
                "status": "pending",
                "urgency": 5.0,
            },
            {
                "id": 2,
                "description": "Blocked task",
                "status": "pending",
                "urgency": 5.0,
                "depends": "uuid1",
            },
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks), stderr="")
            params = BlockedInput()
            result = await taskwarrior_blocked(params)
            assert "Blocked" in result
            assert "Blocked task" in result

    @pytest.mark.asyncio
    async def test_blocked_shows_blockers(self):
        """Test that blocked shows what's blocking each task."""
        from taskwarrior_mcp import BlockedInput, taskwarrior_blocked

        tasks = [
            {"id": 1, "uuid": "uuid1", "description": "Blocker task", "status": "pending"},
            {"id": 2, "description": "Blocked task", "status": "pending", "depends": "uuid1"},
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks), stderr="")
            params = BlockedInput(show_blockers=True)
            result = await taskwarrior_blocked(params)
            # Should show the blocker information
            assert "Blocker" in result or "blocked by" in result.lower()

    @pytest.mark.asyncio
    async def test_blocked_empty_when_no_blocked_tasks(self):
        """Test blocked with no blocked tasks."""
        from taskwarrior_mcp import BlockedInput, taskwarrior_blocked

        tasks = [
            {"id": 1, "description": "Ready task", "status": "pending"},
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks), stderr="")
            params = BlockedInput()
            result = await taskwarrior_blocked(params)
            assert "no blocked" in result.lower() or "0" in result


class TestDependenciesInput:
    """Tests for DependenciesInput model."""

    def test_dependencies_input_defaults(self):
        """Test DependenciesInput with default values."""
        from taskwarrior_mcp import DependenciesInput

        input_model = DependenciesInput()
        assert input_model.task_id is None
        assert input_model.direction == "both"
        assert input_model.depth == 3


class TestTaskwarriorDependencies:
    """Tests for the taskwarrior_dependencies tool."""

    @pytest.mark.asyncio
    async def test_dependencies_overview_mode(self):
        """Test dependencies in overview mode (no task_id)."""
        from taskwarrior_mcp import DependenciesInput, taskwarrior_dependencies

        tasks = [
            {"id": 1, "uuid": "uuid1", "description": "Blocker", "status": "pending"},
            {
                "id": 2,
                "uuid": "uuid2",
                "description": "Blocked",
                "status": "pending",
                "depends": "uuid1",
            },
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks), stderr="")
            params = DependenciesInput()
            result = await taskwarrior_dependencies(params)
            assert "Dependency" in result or "dependency" in result.lower()

    @pytest.mark.asyncio
    async def test_dependencies_specific_task(self):
        """Test dependencies for a specific task."""
        from taskwarrior_mcp import DependenciesInput, taskwarrior_dependencies

        tasks = [
            {"id": 1, "uuid": "uuid1", "description": "Blocker", "status": "pending"},
            {
                "id": 2,
                "uuid": "uuid2",
                "description": "Middle",
                "status": "pending",
                "depends": "uuid1",
            },
            {
                "id": 3,
                "uuid": "uuid3",
                "description": "Blocked",
                "status": "pending",
                "depends": "uuid2",
            },
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks), stderr="")
            params = DependenciesInput(task_id="1")
            result = await taskwarrior_dependencies(params)
            assert "Blocker" in result or "#1" in result

    @pytest.mark.asyncio
    async def test_dependencies_json_format(self):
        """Test dependencies returns valid JSON."""
        from taskwarrior_mcp import DependenciesInput, taskwarrior_dependencies

        tasks = [
            {"id": 1, "uuid": "uuid1", "description": "Task 1", "status": "pending"},
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks), stderr="")
            params = DependenciesInput(response_format=ResponseFormat.JSON)
            result = await taskwarrior_dependencies(params)
            data = json.loads(result)
            assert "bottlenecks" in data or "ready" in data or "blocked" in data


class TestTriageInput:
    """Tests for TriageInput model."""

    def test_triage_input_defaults(self):
        """Test TriageInput with default values."""
        from taskwarrior_mcp import TriageInput

        input_model = TriageInput()
        assert input_model.stale_days == 14
        assert input_model.include_untagged is True
        assert input_model.include_no_project is True
        assert input_model.include_no_due is True
        assert input_model.limit == 20


class TestTaskwarriorTriage:
    """Tests for the taskwarrior_triage tool."""

    @pytest.fixture
    def tasks_for_triage(self):
        """Tasks with various triage conditions."""
        return [
            {
                "id": 1,
                "description": "Stale task",
                "status": "pending",
                "entry": "20250101T120000Z",  # Old entry date
                "modified": "20250101T120000Z",
            },
            {
                "id": 2,
                "description": "No project task",
                "status": "pending",
                "entry": "20250130T120000Z",
            },
            {
                "id": 3,
                "description": "No tags task",
                "status": "pending",
                "project": "work",
                "entry": "20250130T120000Z",
            },
            {
                "id": 4,
                "description": "Good task",
                "status": "pending",
                "project": "work",
                "tags": ["review"],
                "due": "20250215T120000Z",
                "entry": "20250130T120000Z",
            },
        ]

    @pytest.mark.asyncio
    async def test_triage_finds_stale_tasks(self, tasks_for_triage):
        """Test that triage finds stale tasks."""
        from taskwarrior_mcp import TriageInput, taskwarrior_triage

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks_for_triage), stderr="")
            params = TriageInput(stale_days=14)
            result = await taskwarrior_triage(params)
            assert "Triage" in result
            assert "Stale" in result or "stale" in result.lower()

    @pytest.mark.asyncio
    async def test_triage_finds_no_project(self, tasks_for_triage):
        """Test that triage finds tasks without projects."""
        from taskwarrior_mcp import TriageInput, taskwarrior_triage

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks_for_triage), stderr="")
            params = TriageInput(include_no_project=True)
            result = await taskwarrior_triage(params)
            assert "project" in result.lower()

    @pytest.mark.asyncio
    async def test_triage_finds_untagged(self, tasks_for_triage):
        """Test that triage finds untagged tasks."""
        from taskwarrior_mcp import TriageInput, taskwarrior_triage

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks_for_triage), stderr="")
            params = TriageInput(include_untagged=True)
            result = await taskwarrior_triage(params)
            assert "tag" in result.lower()

    @pytest.mark.asyncio
    async def test_triage_json_format(self, tasks_for_triage):
        """Test triage returns valid JSON."""
        from taskwarrior_mcp import TriageInput, taskwarrior_triage

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(tasks_for_triage), stderr="")
            params = TriageInput(response_format=ResponseFormat.JSON)
            result = await taskwarrior_triage(params)
            data = json.loads(result)
            assert "stale" in data or "no_project" in data or "untagged" in data

    @pytest.mark.asyncio
    async def test_triage_empty_when_all_good(self):
        """Test triage when all tasks are well-organized."""
        from taskwarrior_mcp import TriageInput, taskwarrior_triage

        good_tasks = [
            {
                "id": 1,
                "description": "Good task",
                "status": "pending",
                "project": "work",
                "tags": ["review"],
                "due": "20250215T120000Z",
                "entry": "20250130T120000Z",
                "modified": "20250130T120000Z",
            },
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(good_tasks), stderr="")
            params = TriageInput()
            result = await taskwarrior_triage(params)
            # Should indicate no issues or empty categories
            assert "0" in result or "no items" in result.lower() or "looking good" in result.lower()


class TestContextInput:
    """Tests for ContextInput model."""

    def test_context_input_required(self):
        """Test ContextInput with required task_id."""
        from taskwarrior_mcp import ContextInput

        input_model = ContextInput(task_id="5")
        assert input_model.task_id == "5"
        assert input_model.include_related is True
        assert input_model.include_activity is True


class TestTaskwarriorContext:
    """Tests for the taskwarrior_context tool."""

    @pytest.mark.asyncio
    async def test_context_returns_rich_details(self, sample_task):
        """Test that context returns rich task details."""
        from taskwarrior_mcp import ContextInput, taskwarrior_context

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps([sample_task]), stderr="")
            params = ContextInput(task_id="1")
            result = await taskwarrior_context(params)
            assert "Test task" in result
            # Should have computed fields
            assert "age" in result.lower() or "created" in result.lower()

    @pytest.mark.asyncio
    async def test_context_includes_related_tasks(self, sample_tasks):
        """Test that context shows related tasks."""
        from taskwarrior_mcp import ContextInput, taskwarrior_context

        # First call gets main task, second gets all for related
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(sample_tasks), stderr="")
            params = ContextInput(task_id="1", include_related=True)
            result = await taskwarrior_context(params)
            # Should mention related tasks or project
            assert "work" in result.lower() or "related" in result.lower()

    @pytest.mark.asyncio
    async def test_context_json_format(self, sample_task):
        """Test context returns valid JSON."""
        from taskwarrior_mcp import ContextInput, taskwarrior_context

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps([sample_task]), stderr="")
            params = ContextInput(task_id="1", response_format=ResponseFormat.JSON)
            result = await taskwarrior_context(params)
            data = json.loads(result)
            assert "task" in data
            assert "computed" in data or "age" in data

    @pytest.mark.asyncio
    async def test_context_task_not_found(self):
        """Test context when task doesn't exist."""
        from taskwarrior_mcp import ContextInput, taskwarrior_context

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
            params = ContextInput(task_id="999")
            result = await taskwarrior_context(params)
            assert "not found" in result.lower() or "error" in result.lower()


# ============================================================================
# Internal Pydantic Model Tests
# ============================================================================


class TestTaskAnnotation:
    """Tests for the TaskAnnotation model."""

    def test_task_annotation_defaults(self):
        """Test TaskAnnotation with default values."""
        annotation = TaskAnnotation(description="Test note")
        assert annotation.description == "Test note"
        assert annotation.entry is None

    def test_task_annotation_with_entry(self):
        """Test TaskAnnotation with entry timestamp."""
        annotation = TaskAnnotation(entry="20250130T100000Z", description="Test note")
        assert annotation.entry == "20250130T100000Z"
        assert annotation.description == "Test note"

    def test_task_annotation_from_dict(self):
        """Test creating TaskAnnotation from dict."""
        data = {"entry": "20250130T100000Z", "description": "Note from dict"}
        annotation = TaskAnnotation.model_validate(data)
        assert annotation.entry == "20250130T100000Z"
        assert annotation.description == "Note from dict"


class TestTaskModel:
    """Tests for the TaskModel model."""

    def test_task_model_minimal(self):
        """Test TaskModel with minimal data."""
        task = TaskModel()
        assert task.id is None
        assert task.uuid is None
        assert task.description == ""
        assert task.status == "pending"
        assert task.urgency == 0.0
        assert task.tags == []
        assert task.annotations == []

    def test_task_model_full(self):
        """Test TaskModel with all fields."""
        task = TaskModel(
            id=1,
            uuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            description="Test task",
            status="pending",
            urgency=5.0,
            project="work",
            priority="H",
            tags=["urgent", "review"],
            due="20250201T120000Z",
            entry="20250130T100000Z",
            modified="20250130T110000Z",
            start="20250130T105000Z",
            depends="uuid1,uuid2",
            annotations=[TaskAnnotation(entry="20250130T100000Z", description="Note")],
        )
        assert task.id == 1
        assert task.uuid == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert task.description == "Test task"
        assert task.status == "pending"
        assert task.urgency == 5.0
        assert task.project == "work"
        assert task.priority == "H"
        assert task.tags == ["urgent", "review"]
        assert task.due == "20250201T120000Z"
        assert task.entry == "20250130T100000Z"
        assert task.modified == "20250130T110000Z"
        assert task.start == "20250130T105000Z"
        assert task.depends == "uuid1,uuid2"
        assert len(task.annotations) == 1

    def test_task_model_from_dict(self):
        """Test creating TaskModel from dict (like Taskwarrior JSON output)."""
        data = {
            "id": 1,
            "uuid": "test-uuid",
            "description": "Test task",
            "status": "pending",
            "urgency": 8.0,
            "project": "work",
            "priority": "H",
            "tags": ["urgent"],
            "due": "20250201T120000Z",
        }
        task = TaskModel.model_validate(data)
        assert task.id == 1
        assert task.uuid == "test-uuid"
        assert task.description == "Test task"
        assert task.priority == "H"
        assert task.tags == ["urgent"]

    def test_task_model_with_annotations_dict(self):
        """Test TaskModel with annotations as list of dicts."""
        data = {
            "id": 1,
            "description": "Task with notes",
            "annotations": [
                {"entry": "20250130T100000Z", "description": "First note"},
                {"entry": "20250130T110000Z", "description": "Second note"},
            ],
        }
        task = TaskModel.model_validate(data)
        assert len(task.annotations) == 2
        assert task.annotations[0].description == "First note"
        assert task.annotations[1].description == "Second note"

    def test_task_model_allows_extra_fields(self):
        """Test that TaskModel allows extra fields from Taskwarrior."""
        data = {
            "id": 1,
            "description": "Test",
            "custom_field": "custom_value",
            "another_field": 123,
        }
        task = TaskModel.model_validate(data)
        assert task.id == 1
        assert task.description == "Test"
        # Extra fields should be preserved
        assert task.model_extra.get("custom_field") == "custom_value"
        assert task.model_extra.get("another_field") == 123

    def test_task_model_to_dict(self):
        """Test converting TaskModel back to dict."""
        task = TaskModel(id=1, description="Test task", status="pending", urgency=5.0, tags=["urgent"])
        data = task.model_dump()
        assert data["id"] == 1
        assert data["description"] == "Test task"
        assert data["tags"] == ["urgent"]

    def test_task_model_with_resolved_dependencies(self):
        """Test TaskModel with resolved dependency fields."""
        from taskwarrior_mcp import ResolvedDependency

        dep1 = ResolvedDependency(id=1, uuid="uuid-1", description="Blocking task 1", status="pending")
        dep2 = ResolvedDependency(id=2, uuid="uuid-2", description="Blocking task 2", status="completed")

        task = TaskModel(
            id=3,
            description="Blocked task",
            depends="uuid-1,uuid-2",
            depends_on=[dep1, dep2],
            blocked_by_pending=1,
        )
        assert task.depends == "uuid-1,uuid-2"
        assert len(task.depends_on) == 2
        assert task.depends_on[0].description == "Blocking task 1"
        assert task.depends_on[1].status == "completed"
        assert task.blocked_by_pending == 1

    def test_task_model_depends_on_defaults_empty(self):
        """Test that depends_on defaults to empty list."""
        task = TaskModel(id=1, description="Task without deps")
        assert task.depends_on == []
        assert task.blocked_by_pending == 0

    def test_task_model_depends_on_serializes_to_json(self):
        """Test that resolved deps serialize properly to JSON."""
        from taskwarrior_mcp import ResolvedDependency

        dep = ResolvedDependency(id=1, uuid="uuid-1", description="Blocker", status="pending")
        task = TaskModel(id=2, description="Task", depends_on=[dep], blocked_by_pending=1)

        data = task.model_dump()
        assert "depends_on" in data
        assert len(data["depends_on"]) == 1
        assert data["depends_on"][0]["uuid"] == "uuid-1"
        assert data["blocked_by_pending"] == 1


class TestResolvedDependency:
    """Tests for the ResolvedDependency model."""

    def test_resolved_dependency_minimal(self):
        """Test ResolvedDependency with required fields only."""
        from taskwarrior_mcp import ResolvedDependency

        dep = ResolvedDependency(uuid="uuid-123", description="A task")
        assert dep.uuid == "uuid-123"
        assert dep.description == "A task"
        assert dep.id is None
        assert dep.status == "pending"

    def test_resolved_dependency_full(self):
        """Test ResolvedDependency with all fields."""
        from taskwarrior_mcp import ResolvedDependency

        dep = ResolvedDependency(id=5, uuid="uuid-456", description="Blocker task", status="completed")
        assert dep.id == 5
        assert dep.uuid == "uuid-456"
        assert dep.description == "Blocker task"
        assert dep.status == "completed"

    def test_resolved_dependency_from_dict(self):
        """Test creating ResolvedDependency from dict."""
        from taskwarrior_mcp import ResolvedDependency

        data = {"id": 1, "uuid": "abc-123", "description": "Task", "status": "pending"}
        dep = ResolvedDependency.model_validate(data)
        assert dep.id == 1
        assert dep.uuid == "abc-123"


class TestDependencyEnrichment:
    """Tests for dependency enrichment functions."""

    def test_enrich_task_dependencies_no_deps(self):
        """Test enrichment with task that has no dependencies."""
        from taskwarrior_mcp import _enrich_task_dependencies

        task = TaskModel(id=1, uuid="task-1", description="Task without deps")
        uuid_map = {}

        enriched = _enrich_task_dependencies(task, uuid_map)
        assert enriched.depends_on == []
        assert enriched.blocked_by_pending == 0

    def test_enrich_task_dependencies_with_pending_dep(self):
        """Test enrichment resolves pending dependency."""
        from taskwarrior_mcp import _enrich_task_dependencies

        blocker = TaskModel(id=1, uuid="blocker-uuid", description="Blocker", status="pending")
        task = TaskModel(id=2, uuid="task-uuid", description="Blocked", depends="blocker-uuid")
        uuid_map = {"blocker-uuid": blocker}

        enriched = _enrich_task_dependencies(task, uuid_map)
        assert len(enriched.depends_on) == 1
        assert enriched.depends_on[0].id == 1
        assert enriched.depends_on[0].description == "Blocker"
        assert enriched.depends_on[0].status == "pending"
        assert enriched.blocked_by_pending == 1

    def test_enrich_task_dependencies_with_completed_dep(self):
        """Test enrichment with completed dependency (not blocking)."""
        from taskwarrior_mcp import _enrich_task_dependencies

        blocker = TaskModel(id=1, uuid="blocker-uuid", description="Done blocker", status="completed")
        task = TaskModel(id=2, uuid="task-uuid", description="Was blocked", depends="blocker-uuid")
        uuid_map = {"blocker-uuid": blocker}

        enriched = _enrich_task_dependencies(task, uuid_map)
        assert len(enriched.depends_on) == 1
        assert enriched.depends_on[0].status == "completed"
        assert enriched.blocked_by_pending == 0  # Completed deps don't block

    def test_enrich_task_dependencies_multiple_deps(self):
        """Test enrichment with multiple dependencies."""
        from taskwarrior_mcp import _enrich_task_dependencies

        blocker1 = TaskModel(id=1, uuid="uuid-1", description="Blocker 1", status="pending")
        blocker2 = TaskModel(id=2, uuid="uuid-2", description="Blocker 2", status="completed")
        blocker3 = TaskModel(id=3, uuid="uuid-3", description="Blocker 3", status="pending")
        task = TaskModel(id=4, uuid="uuid-4", description="Blocked", depends="uuid-1,uuid-2,uuid-3")
        uuid_map = {"uuid-1": blocker1, "uuid-2": blocker2, "uuid-3": blocker3}

        enriched = _enrich_task_dependencies(task, uuid_map)
        assert len(enriched.depends_on) == 3
        assert enriched.blocked_by_pending == 2  # Only pending deps count

    def test_enrich_task_dependencies_missing_uuid(self):
        """Test enrichment handles missing UUID gracefully."""
        from taskwarrior_mcp import _enrich_task_dependencies

        task = TaskModel(id=1, uuid="task-uuid", description="Task", depends="missing-uuid")
        uuid_map = {}

        enriched = _enrich_task_dependencies(task, uuid_map)
        assert len(enriched.depends_on) == 0  # Missing UUID is skipped
        assert enriched.blocked_by_pending == 0

    def test_enrich_tasks_dependencies_batch(self):
        """Test batch enrichment of multiple tasks."""
        from taskwarrior_mcp import _enrich_tasks_dependencies

        task1 = TaskModel(id=1, uuid="uuid-1", description="Independent task")
        task2 = TaskModel(id=2, uuid="uuid-2", description="Depends on task1", depends="uuid-1")
        task3 = TaskModel(id=3, uuid="uuid-3", description="Depends on task2", depends="uuid-2")
        tasks = [task1, task2, task3]

        enriched = _enrich_tasks_dependencies(tasks)

        # Task 1 has no deps
        assert enriched[0].depends_on == []
        assert enriched[0].blocked_by_pending == 0

        # Task 2 depends on task 1
        assert len(enriched[1].depends_on) == 1
        assert enriched[1].depends_on[0].id == 1
        assert enriched[1].blocked_by_pending == 1

        # Task 3 depends on task 2
        assert len(enriched[2].depends_on) == 1
        assert enriched[2].depends_on[0].id == 2
        assert enriched[2].blocked_by_pending == 1


class TestScoredTask:
    """Tests for the ScoredTask model."""

    def test_scored_task(self):
        """Test ScoredTask with task, score, and reasons."""
        task = TaskModel(id=1, description="Test task", urgency=8.0)
        scored = ScoredTask(task=task, score=85.0, reasons=["High priority", "Due soon"])
        assert scored.task.id == 1
        assert scored.score == 85.0
        assert len(scored.reasons) == 2
        assert "High priority" in scored.reasons

    def test_scored_task_from_dict(self):
        """Test ScoredTask from nested dict."""
        data = {
            "task": {"id": 1, "description": "Test", "urgency": 5.0},
            "score": 50.0,
            "reasons": ["Overdue"],
        }
        scored = ScoredTask.model_validate(data)
        assert scored.task.id == 1
        assert scored.score == 50.0
        assert scored.reasons == ["Overdue"]


class TestBlockedTaskInfo:
    """Tests for the BlockedTaskInfo model."""

    def test_blocked_task_info_minimal(self):
        """Test BlockedTaskInfo with minimal data."""
        task = TaskModel(id=1, description="Blocked task")
        info = BlockedTaskInfo(task=task)
        assert info.task.id == 1
        assert info.blockers == []

    def test_blocked_task_info_with_blockers(self):
        """Test BlockedTaskInfo with blocker tasks."""
        blocked = TaskModel(id=2, description="Blocked task")
        blocker1 = TaskModel(id=1, description="Blocker 1")
        blocker2 = TaskModel(id=3, description="Blocker 2")
        info = BlockedTaskInfo(task=blocked, blockers=[blocker1, blocker2])
        assert info.task.id == 2
        assert len(info.blockers) == 2
        assert info.blockers[0].description == "Blocker 1"


class TestBottleneckInfo:
    """Tests for the BottleneckInfo model."""

    def test_bottleneck_info(self):
        """Test BottleneckInfo model."""
        task = TaskModel(id=1, description="Bottleneck task")
        info = BottleneckInfo(task=task, blocks_count=5)
        assert info.task.id == 1
        assert info.blocks_count == 5


class TestComputedInsights:
    """Tests for the ComputedInsights model."""

    def test_computed_insights(self):
        """Test ComputedInsights with all fields."""
        insights = ComputedInsights(
            age="3 days ago",
            last_activity="Yesterday",
            dependency_status="Ready",
            related_pending=5,
            annotations_count=2,
        )
        assert insights.age == "3 days ago"
        assert insights.last_activity == "Yesterday"
        assert insights.dependency_status == "Ready"
        assert insights.related_pending == 5
        assert insights.annotations_count == 2


# ============================================================================
# Parser Helper Tests
# ============================================================================


class TestParseTask:
    """Tests for the _parse_task helper function."""

    def test_parse_task_basic(self):
        """Test parsing a basic task dict."""
        data = {
            "id": 1,
            "description": "Test task",
            "status": "pending",
            "urgency": 5.0,
        }
        task = _parse_task(data)
        assert isinstance(task, TaskModel)
        assert task.id == 1
        assert task.description == "Test task"

    def test_parse_task_with_annotations(self):
        """Test parsing a task with annotations."""
        data = {
            "id": 1,
            "description": "Task with notes",
            "annotations": [
                {"entry": "20250130T100000Z", "description": "Note 1"},
            ],
        }
        task = _parse_task(data)
        assert len(task.annotations) == 1
        assert isinstance(task.annotations[0], TaskAnnotation)

    def test_parse_task_preserves_extra_fields(self):
        """Test that extra Taskwarrior fields are preserved."""
        data = {
            "id": 1,
            "description": "Test",
            "recur": "weekly",
            "imask": 1,
        }
        task = _parse_task(data)
        assert task.model_extra.get("recur") == "weekly"


class TestParseTasks:
    """Tests for the _parse_tasks helper function."""

    def test_parse_tasks_empty(self):
        """Test parsing empty list."""
        tasks = _parse_tasks([])
        assert tasks == []

    def test_parse_tasks_multiple(self):
        """Test parsing multiple tasks."""
        data = [
            {"id": 1, "description": "Task 1", "urgency": 5.0},
            {"id": 2, "description": "Task 2", "urgency": 3.0},
            {"id": 3, "description": "Task 3", "urgency": 8.0},
        ]
        tasks = _parse_tasks(data)
        assert len(tasks) == 3
        assert all(isinstance(t, TaskModel) for t in tasks)
        assert tasks[0].id == 1
        assert tasks[2].urgency == 8.0


# ============================================================================
# Tests verifying TaskModel compatibility with existing functions
# ============================================================================


class TestTaskModelIntegration:
    """Tests verifying TaskModel works with existing format functions."""

    def test_format_task_markdown_with_task_model(self, sample_task_model):
        """Test that TaskModel works with format_task_markdown."""
        result = format_task_markdown(sample_task_model)
        assert "[1]" in result
        assert "Test task" in result
        assert "test-project" in result
        assert "High" in result

    def test_parse_and_format_round_trip(self, sample_task):
        """Test parsing a dict to TaskModel and formatting."""
        task_model = _parse_task(sample_task)
        result = format_task_markdown(task_model)
        assert "[1]" in result
        assert "Test task" in result

    def test_sample_task_models_fixture(self, sample_task_models):
        """Test that sample_task_models fixture works correctly."""
        assert len(sample_task_models) == 3
        assert all(isinstance(t, TaskModel) for t in sample_task_models)
        assert sample_task_models[0].description == "Task one"
        assert sample_task_models[1].project == "personal"
        assert sample_task_models[2].tags == ["review"]
