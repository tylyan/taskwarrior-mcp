# Taskwarrior MCP Server

An MCP (Model Context Protocol) server that enables AI assistants to interact with [Taskwarrior](https://taskwarrior.org/), the powerful command-line task management tool.

## Features

- **Full Taskwarrior Integration**: List, create, modify, complete, and delete tasks
- **Project & Tag Management**: Organize tasks with projects and tags
- **Annotations**: Add notes and context to tasks
- **Filtering**: Use Taskwarrior's powerful filter expressions
- **Multiple Output Formats**: Get responses in Markdown or JSON
- **Agent Intelligence**: Smart suggestions, dependency analysis, triage tools

## Prerequisites

- Python 3.10 or higher
- [Taskwarrior](https://taskwarrior.org/) installed and available in your PATH

### Installing Taskwarrior

```bash
# macOS
brew install task

# Ubuntu/Debian
sudo apt install taskwarrior

# Fedora
sudo dnf install task

# Arch Linux
sudo pacman -S task
```

## Installation

### From PyPI (recommended)

```bash
pip install taskwarrior-mcp
```

### From Source

```bash
git clone https://github.com/yourusername/taskwarrior-mcp.git
cd taskwarrior-mcp
pip install -e .
```

## Configuration

### Claude Desktop

Add to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "taskwarrior": {
      "command": "taskwarrior-mcp"
    }
  }
}
```

### Claude Code CLI

Add to your `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "taskwarrior": {
      "command": "taskwarrior-mcp"
    }
  }
}
```

### Using uvx (no installation required)

```json
{
  "mcpServers": {
    "taskwarrior": {
      "command": "uvx",
      "args": ["taskwarrior-mcp"]
    }
  }
}
```

## Available Tools

### Core Task Management

| Tool | Description |
|------|-------------|
| `taskwarrior_list` | List tasks with optional filtering |
| `taskwarrior_add` | Create a new task |
| `taskwarrior_complete` | Mark a task as completed |
| `taskwarrior_modify` | Modify task attributes |
| `taskwarrior_delete` | Delete a task |
| `taskwarrior_get` | Get detailed info about a task |
| `taskwarrior_bulk_get` | Get detailed info about multiple tasks at once |
| `taskwarrior_annotate` | Add a note to a task |
| `taskwarrior_start` | Start working on a task |
| `taskwarrior_stop` | Stop working on a task |
| `taskwarrior_projects` | List all projects |
| `taskwarrior_project_summary` | Get detailed project summaries with priority breakdown, due dates, and active tasks |
| `taskwarrior_tags` | List all tags |
| `taskwarrior_undo` | Undo the last operation |
| `taskwarrior_summary` | Get task statistics |

### Agent Intelligence Tools

| Tool | Description |
|------|-------------|
| `taskwarrior_suggest` | Get smart task recommendations with scoring and reasoning |
| `taskwarrior_ready` | List tasks that are ready to work on (no pending dependencies) |
| `taskwarrior_blocked` | List tasks that are blocked by dependencies |
| `taskwarrior_dependencies` | Analyze dependency graphs and find bottlenecks |
| `taskwarrior_triage` | Find forgotten/stale tasks that need attention |
| `taskwarrior_context` | Get rich task context with computed insights |

## Usage Examples

Once configured, you can interact with Taskwarrior through your AI assistant:

### Basic Task Management
- "What tasks do I have?"
- "Add a task to review the quarterly report with high priority"
- "Show me all tasks in the work project"
- "Complete task 5"
- "What's due this week?"

### Agent Intelligence
- "What should I work on next?" - Uses `taskwarrior_suggest` for smart recommendations
- "What tasks are ready to start?" - Uses `taskwarrior_ready` for unblocked tasks
- "What's blocking my progress?" - Uses `taskwarrior_blocked` and `taskwarrior_dependencies`
- "Any tasks I've forgotten about?" - Uses `taskwarrior_triage` for stale/orphaned tasks
- "Give me context on task 5" - Uses `taskwarrior_context` for rich task details

## Development

### Setup

```bash
git clone https://github.com/yourusername/taskwarrior-mcp.git
cd taskwarrior-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Format code
black .
ruff check --fix .

# Type checking
mypy taskwarrior_mcp.py
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
