# Configuration Examples

This directory contains example configurations for using the Taskwarrior MCP server with various clients.

## Quick Start

Choose the configuration that matches your setup:

| File | Use Case |
|------|----------|
| [claude-desktop-macos.json](claude-desktop-macos.json) | Claude Desktop on macOS |
| [claude-desktop-windows.json](claude-desktop-windows.json) | Claude Desktop on Windows |
| [claude-code-cli.json](claude-code-cli.json) | Claude Code CLI |
| [uvx-config.json](uvx-config.json) | Any client using uvx (no install required) |

## Installation Methods

### Option 1: uvx (Recommended - No Installation)

Use `uvx` to run directly without installing:

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

### Option 2: pip Install

```bash
pip install taskwarrior-mcp
```

Then use:

```json
{
  "mcpServers": {
    "taskwarrior": {
      "command": "taskwarrior-mcp"
    }
  }
}
```

### Option 3: From Source

```bash
git clone https://github.com/yourusername/taskwarrior-mcp.git
cd taskwarrior-mcp
pip install -e .
```

## Configuration Locations

| Client | Config File Location |
|--------|---------------------|
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude Desktop (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Claude Code CLI | `~/.claude/settings.json` |

## Environment Variables

You can customize Taskwarrior behavior using environment variables:

```json
{
  "mcpServers": {
    "taskwarrior": {
      "command": "taskwarrior-mcp",
      "env": {
        "TASKRC": "/path/to/custom/.taskrc",
        "TASKDATA": "/path/to/custom/.task"
      }
    }
  }
}
```

## Troubleshooting

### Taskwarrior not found

Ensure Taskwarrior is installed and in your PATH:

```bash
# Verify installation
task --version

# If not installed:
# macOS
brew install task

# Ubuntu/Debian
sudo apt install taskwarrior

# Windows (via Chocolatey)
choco install taskwarrior
```

### Permission Issues

If you get permission errors, ensure the MCP server can access your Taskwarrior data directory (default: `~/.task`).

### Multiple Taskwarrior Databases

Use different `TASKDATA` paths to manage separate task databases:

```json
{
  "mcpServers": {
    "taskwarrior-work": {
      "command": "taskwarrior-mcp",
      "env": {
        "TASKDATA": "~/.task-work"
      }
    },
    "taskwarrior-personal": {
      "command": "taskwarrior-mcp",
      "env": {
        "TASKDATA": "~/.task-personal"
      }
    }
  }
}
```
