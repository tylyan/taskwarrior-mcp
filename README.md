# Taskwarrior MCP Server

An MCP (Model Context Protocol) server that enables AI assistants to interact with [Taskwarrior](https://taskwarrior.org/), the powerful command-line task management tool.

## Features

- **Full Taskwarrior Integration**: List, create, modify, complete, and delete tasks
- **Project & Tag Management**: Organize tasks with projects and tags
- **Annotations**: Add notes and context to tasks
- **Filtering**: Use Taskwarrior's powerful filter expressions
- **Multiple Output Formats**: Get responses in Markdown or JSON

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

| Tool | Description |
|------|-------------|
| `taskwarrior_list` | List tasks with optional filtering |
| `taskwarrior_add` | Create a new task |
| `taskwarrior_complete` | Mark a task as completed |
| `taskwarrior_modify` | Modify task attributes |
| `taskwarrior_delete` | Delete a task |
| `taskwarrior_get` | Get detailed info about a task |
| `taskwarrior_annotate` | Add a note to a task |
| `taskwarrior_start` | Start working on a task |
| `taskwarrior_stop` | Stop working on a task |
| `taskwarrior_projects` | List all projects |
| `taskwarrior_tags` | List all tags |
| `taskwarrior_undo` | Undo the last operation |
| `taskwarrior_summary` | Get task statistics |

## Usage Examples

Once configured, you can interact with Taskwarrior through your AI assistant:

- "What tasks do I have?"
- "Add a task to review the quarterly report with high priority"
- "Show me all tasks in the work project"
- "Complete task 5"
- "What's due this week?"

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
