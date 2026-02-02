"""FastMCP server initialization for Taskwarrior MCP."""

from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("taskwarrior_mcp")


def run() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    run()
