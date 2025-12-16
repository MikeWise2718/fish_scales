"""CLI entry point for the Fish Scale MCP Server."""

import argparse
import sys


def main():
    """Main entry point for fish-scale-mcp command."""
    parser = argparse.ArgumentParser(
        description="Fish Scale MCP Server - Expose fish-scale-ui as MCP tools"
    )
    parser.add_argument(
        "--ui-url",
        default="http://localhost:5010",
        help="Base URL of fish-scale-ui (default: http://localhost:5010)"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)"
    )

    args = parser.parse_args()

    # Import here to avoid loading everything just to show help
    from fish_scale_mcp.server import create_server

    server = create_server(ui_base_url=args.ui_url)

    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        server.run(transport="sse")


if __name__ == "__main__":
    main()
