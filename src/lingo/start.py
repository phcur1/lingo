"""Container startup with mode-aware schema migration."""

import os


def main() -> None:
    bot_mode = os.getenv("BOT_MODE", "conversation").strip().lower()
    transport = os.getenv("TRANSPORT", "whatsapp").strip().lower()
    # Learning-memory migrations are for WhatsApp conversation persistence.
    if bot_mode == "conversation" and transport != "web":
        from lingo.migrate import main as migrate

        migrate()

    from lingo.server import main as run_server

    run_server()
