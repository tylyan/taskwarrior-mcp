# Contributing to Taskwarrior MCP

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

```bash
git clone https://github.com/yourusername/taskwarrior-mcp.git
cd taskwarrior-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## Commit Messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/). All commits must follow this format:

```
<type>(<scope>): <subject>

[optional body]

[optional footer(s)]
```

### Types

| Type       | Description                                        |
|------------|---------------------------------------------------|
| `feat`     | New feature                                        |
| `fix`      | Bug fix                                            |
| `docs`     | Documentation only changes                         |
| `style`    | Code style (formatting, no logic change)           |
| `refactor` | Code change that neither fixes nor adds feature    |
| `perf`     | Performance improvement                            |
| `test`     | Adding or fixing tests                             |
| `chore`    | Maintenance tasks, dependencies                    |
| `ci`       | CI/CD changes                                      |
| `build`    | Build system changes                               |
| `revert`   | Revert a previous commit                           |

### Scopes (Optional)

Use scopes to indicate which part of the codebase is affected:

- `tools` - MCP tool implementations
- `models` - Pydantic models
- `utils` - Utility functions (formatters, parsers)
- `deps` - Dependencies
- `ci` - CI/CD workflows

### Examples

```bash
# Feature
feat(tools): add bulk task modification support

# Bug fix
fix(utils): handle empty task list in formatter

# Documentation
docs: update README with new configuration options

# Breaking change (use ! after type/scope)
feat(tools)!: rename taskwarrior_get to taskwarrior_task

BREAKING CHANGE: The tool `taskwarrior_get` has been renamed to
`taskwarrior_task` for consistency.
```

### Commit Message Validation

Commits are validated locally via gitlint (pre-commit hook) and in CI.

## Pull Request Process

1. Create a feature branch from `develop`
2. Make your changes following the commit conventions
3. Ensure tests pass: `pytest`
4. Ensure linting passes: `ruff check . && ruff format --check .`
5. Update documentation if needed
6. Submit a PR to `develop`

## Architecture Decision Records (ADRs)

Significant architectural decisions are documented in `docs/adr/`. If your contribution involves a significant design decision, please create an ADR.

See `docs/adr/0000-template.md` for the format.

## Code Style

- Python 3.10+ with type hints
- Formatting: Ruff (auto-applied via pre-commit)
- Line length: 120 characters
- Strict mypy compliance

## Testing

- Write tests for new features
- Follow test-driven development when appropriate
- Run tests: `pytest` or `uv run pytest`
- Coverage reports: `pytest --cov=taskwarrior_mcp`

## Versioning

This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html):

- **MAJOR** version for incompatible API changes
- **MINOR** version for new functionality in a backwards compatible manner
- **PATCH** version for backwards compatible bug fixes

### Version Bumping

The version is defined in `pyproject.toml` and is accessible in code via:

```python
from taskwarrior_mcp import __version__
print(__version__)  # e.g., "0.2.0"
```

### How Conventional Commits Drive Versioning

Your commit messages determine the next version:

| Commit Type | Version Bump | Example |
|-------------|--------------|---------|
| `fix:` | PATCH (0.1.0 → 0.1.1) | `fix: handle empty task list` |
| `feat:` | MINOR (0.1.0 → 0.2.0) | `feat: add bulk modify tool` |
| `feat!:` or `BREAKING CHANGE:` | MAJOR (0.1.0 → 1.0.0) | `feat!: rename tools` |

### Release Process

1. Ensure all changes are merged to `main`
2. Determine version bump from commits since last release
3. Update version in `pyproject.toml`
4. Regenerate changelog: `git-cliff -o CHANGELOG.md`
5. Commit: `git commit -am "chore(release): prepare X.Y.Z"`
6. Tag: `git tag vX.Y.Z`
7. Push: `git push && git push --tags`

The GitHub Actions release workflow will automatically publish to PyPI when a tag is pushed.

## Changelog

The changelog is generated using git-cliff from conventional commits. You don't need to manually edit CHANGELOG.md - it will be regenerated at release time.

To preview unreleased changes:

```bash
git-cliff --unreleased
```

To regenerate the full changelog:

```bash
git-cliff -o CHANGELOG.md
```

## Questions?

Open an issue for questions or discussion.
