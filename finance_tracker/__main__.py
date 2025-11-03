"""Entry point for running the finance tracker MCP server."""
from .mcp_server import app


def main() -> None:  # pragma: no cover - CLI entry point
    app.run()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
