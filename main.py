"""CLI shim kept for compatibility; prefer `uv run lingo` or the Docker image."""

from lingo.server import main

if __name__ == "__main__":
    main()
