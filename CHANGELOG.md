# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Changelog process with git-cliff automation
- Conventional commits enforcement via gitlint
- Architecture Decision Records (ADRs) for capturing design decisions
- CONTRIBUTING.md with development guidelines

## [0.1.0] - 2025-01-15

### Added
- Initial MCP server implementation for Taskwarrior
- Core task management tools:
  - `taskwarrior_list` - Search and filter tasks
  - `taskwarrior_add` - Create new tasks
  - `taskwarrior_complete` - Mark tasks as completed
  - `taskwarrior_modify` - Modify task attributes
  - `taskwarrior_delete` - Delete tasks
  - `taskwarrior_get` - Get detailed task info
  - `taskwarrior_bulk_get` - Get multiple tasks at once
  - `taskwarrior_annotate` - Add notes to tasks
  - `taskwarrior_start` / `taskwarrior_stop` - Time tracking
  - `taskwarrior_projects` - List all projects
  - `taskwarrior_project_summary` - Detailed project analytics
  - `taskwarrior_tags` - List all tags
  - `taskwarrior_undo` - Undo last operation
  - `taskwarrior_summary` - Task statistics
- Agent intelligence tools:
  - `taskwarrior_suggest` - Smart task recommendations
  - `taskwarrior_ready` - List unblocked tasks
  - `taskwarrior_blocked` - List blocked tasks
  - `taskwarrior_dependencies` - Dependency analysis
  - `taskwarrior_triage` - Find stale/forgotten tasks
  - `taskwarrior_context` - Rich task context
- Multiple response formats (Markdown, JSON, Concise)
- Pydantic models with strict type checking
- Comprehensive test suite with pytest
- CI workflow with Python 3.10, 3.11, 3.12 matrix
- Pre-commit hooks with Ruff for linting and formatting

[Unreleased]: https://github.com/yourusername/taskwarrior-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/taskwarrior-mcp/releases/tag/v0.1.0
