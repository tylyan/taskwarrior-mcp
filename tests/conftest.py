"""Pytest configuration and fixtures for taskwarrior-mcp tests."""

import pytest
from unittest.mock import patch, MagicMock
import subprocess


@pytest.fixture
def mock_subprocess_success():
    """Mock subprocess.run to return successful task output."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr=""
        )
        yield mock_run


@pytest.fixture
def mock_subprocess_with_tasks():
    """Mock subprocess.run to return a list of tasks."""
    sample_tasks = [
        {
            "id": 1,
            "description": "Test task 1",
            "status": "pending",
            "urgency": 5.0,
            "project": "test",
            "priority": "H",
            "tags": ["tag1", "tag2"]
        },
        {
            "id": 2,
            "description": "Test task 2",
            "status": "pending",
            "urgency": 3.0
        }
    ]

    with patch("subprocess.run") as mock_run:
        import json
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(sample_tasks),
            stderr=""
        )
        yield mock_run


@pytest.fixture
def mock_subprocess_error():
    """Mock subprocess.run to simulate a Taskwarrior error."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Task not found."
        )
        yield mock_run


@pytest.fixture
def mock_subprocess_timeout():
    """Mock subprocess.run to simulate a timeout."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="task", timeout=30)
        yield mock_run
