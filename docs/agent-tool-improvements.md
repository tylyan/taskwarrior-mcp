# Taskwarrior MCP Server Improvements

Based on Anthropic's [Writing Tools for AI Agents](https://www.anthropic.com/engineering/writing-tools-for-agents) best practices.

## Summary

Apply 5 key principles to improve agent tool selection and reduce token usage:
1. **Choose Tools Strategically** - Consolidate overlapping metadata tools
2. **Clear Namespacing** - Already good ✓
3. **Return Meaningful Context** - Add resolved dependency fields
4. **Token Efficiency** - Add concise response format
5. **Engineer Descriptions** - Add "when NOT to use" guidance

---

## Phase 1: Tool Description Improvements (High Impact, Low Risk)

### 1.1 Update docstrings with "when NOT to use" guidance

**File:** `taskwarrior_mcp/tools/core.py`

Add to each tool docstring:
- **USE THIS WHEN:** Clear scenarios
- **DO NOT USE WHEN:** Redirect to correct tool
- **Filter syntax examples** (for `taskwarrior_list`)

Example for `taskwarrior_list`:
```python
"""
Search and filter tasks using Taskwarrior query expressions.

USE THIS WHEN:
- Searching for tasks matching criteria (project, tags, due date)
- Getting a filtered subset of tasks

DO NOT USE WHEN:
- You have a specific task ID → use taskwarrior_get
- You have multiple known task IDs → use taskwarrior_bulk_get
- You want prioritized suggestions → use taskwarrior_suggest

FILTER SYNTAX:
- Project: "project:work"
- Tags: "+urgent" or "-completed"
- Due: "due:today", "due:eow", "due.before:2024-12-31"
- Priority: "priority:H", "priority:M", "priority:L"
- Combined: "project:work +urgent due:today"
"""
```

**File:** `taskwarrior_mcp/tools/intelligence.py` - Same pattern for intelligence tools

### 1.2 Improve error messages with actionable guidance

**File:** `taskwarrior_mcp/tools/core.py`

Before:
```python
return f"Error: Task {task_id} not found."
```

After:
```python
return (
    f"Error: Task '{task_id}' not found.\n"
    f"Tip: Use taskwarrior_list to find valid task IDs."
)
```

---

## Phase 2: Add Concise Response Format (Token Efficiency)

### 2.1 Add CONCISE enum value

**File:** `taskwarrior_mcp/enums.py`

```python
class ResponseFormat(str, Enum):
    CONCISE = "concise"   # Minimal output for chaining
    MARKDOWN = "markdown" # Human-readable (default)
    JSON = "json"         # Machine-readable
```

### 2.2 Implement concise formatters

**File:** `taskwarrior_mcp/utils/formatters.py`

Add `_format_task_concise()` and `_format_tasks_concise()`:
```
5 tasks | project:work
#1: Review PR (H, due:today)
#2: Deploy fix (M)
#3: Update docs (L)
```

### 2.3 Update tools to handle concise format

**File:** `taskwarrior_mcp/tools/core.py` - Add concise branch to list/get/bulk_get

---

## Phase 3: Add Computed Fields (Meaningful Context)

### 3.1 Add resolved fields to TaskModel

**File:** `taskwarrior_mcp/models/task.py`

```python
class TaskModel(BaseModel):
    # ... existing fields ...

    # Computed fields (populated during formatting)
    depends_resolved: list[str] | None = Field(
        default=None,
        description="Human-readable: ['#3: Setup env', '#4: Run tests']"
    )
    blocks_resolved: list[str] | None = Field(
        default=None,
        description="Tasks that depend on this one"
    )
    age_human: str | None = Field(
        default=None,
        description="e.g., '3 days ago'"
    )
    due_human: str | None = Field(
        default=None,
        description="e.g., 'Tomorrow', 'Overdue by 2 days'"
    )
    is_blocked: bool = False
    is_blocking: bool = False
```

### 3.2 Resolve UUIDs during parsing

**File:** `taskwarrior_mcp/utils/parsers.py`

Update `_parse_task()` to accept optional `all_tasks` parameter for resolving UUID dependencies to human-readable `#ID: Description` format.

### 3.3 Update formatters to display resolved fields

**File:** `taskwarrior_mcp/utils/formatters.py`

Show "Depends on: #3, #4" instead of UUIDs.

---

## Phase 4: Tool Consolidation

### 4.1 Create unified `taskwarrior_overview` tool

**File:** `taskwarrior_mcp/tools/core.py`

Consolidates: `taskwarrior_summary`, `taskwarrior_projects`, `taskwarrior_tags`

```python
class OverviewInput(BaseModel):
    include_projects: bool = True
    include_tags: bool = True
    include_priority_breakdown: bool = True
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
```

Single call returns complete task landscape instead of 3 separate calls.

---

## Files to Modify

| File | Changes |
|------|---------|
| `taskwarrior_mcp/enums.py` | Add `CONCISE` to ResponseFormat |
| `taskwarrior_mcp/models/task.py` | Add computed fields |
| `taskwarrior_mcp/models/inputs.py` | Add OverviewInput (Phase 4) |
| `taskwarrior_mcp/tools/core.py` | Update docstrings, error messages, add concise handling |
| `taskwarrior_mcp/tools/intelligence.py` | Update docstrings |
| `taskwarrior_mcp/utils/formatters.py` | Add concise formatters, use resolved fields |
| `taskwarrior_mcp/utils/parsers.py` | Add dependency resolution |

---

## Verification

1. **Unit tests:** Update `tests/test_taskwarrior_mcp.py` for new response formats
2. **Manual testing:** Test tools via MCP to verify improved descriptions appear
3. **Agent evaluation:** Test with Claude to verify improved tool selection

```bash
# Run existing tests
pytest tests/

# Test MCP server manually
uv run python -m taskwarrior_mcp
```
