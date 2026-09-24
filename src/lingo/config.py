"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from lingo.tls import primary_lan_ip

load_dotenv(override=False)

VALID_BOT_MODES = frozenset({"conversation", "echo_utterance", "echo_live"})
VALID_TRANSPORTS = frozenset({"whatsapp", "web"})


def resolve_bind_host(transport: str, raw_host: str | None) -> str:
    """Pick the listen address.

    For ``TRANSPORT=web``, default to the laptop LAN IP so phones can open that
    address directly. Use ``HOST=0.0.0.0`` (or Docker) to listen on all interfaces.
    ``HOST=auto`` always resolves to the LAN IP when detectable.
    """
    if raw_host is None:
        host = ""
    else:
        host = raw_host.strip()

    if not host:
        if transport == "web":
            return primary_lan_ip() or "0.0.0.0"
        return "0.0.0.0"

    if host.lower() == "auto":
        return primary_lan_ip() or "0.0.0.0"

    return host


@dataclass(frozen=True)
class Settings:
    transport: str
    whatsapp_token: str
    whatsapp_phone_number_id: str
    whatsapp_webhook_verification_token: str
    whatsapp_app_secret: str | None
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    openai_api_key: str
    openai_model: str
    database_url: str
    learner_id_secret: str
    bot_mode: str
    host: str
    port: int
    web_https: bool
    web_cert_dir: Path

    @classmethod
    def from_env(
        cls,
        *,
        require_whatsapp: bool | None = None,
        require_ai: bool | None = None,
    ) -> Settings:
        transport = os.getenv("TRANSPORT", "whatsapp").strip().lower()
        if transport not in VALID_TRANSPORTS:
            raise ValueError("TRANSPORT must be 'whatsapp' or 'web'")

        if require_whatsapp is None:
            require_whatsapp = transport == "whatsapp"

        token = os.getenv("WHATSAPP_TOKEN", "").strip()
        phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
        verify_token = os.getenv("WHATSAPP_WEBHOOK_VERIFICATION_TOKEN", "").strip()
        app_secret = os.getenv("WHATSAPP_APP_SECRET", "").strip() or None

        elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM").strip()
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        openai_model = os.getenv("OPENAI_MODEL", "gpt-6-luna").strip()
        database_url = os.getenv("DATABASE_URL", "").strip()
        learner_id_secret = os.getenv("LEARNER_ID_SECRET", "").strip()

        bot_mode = os.getenv("BOT_MODE", "conversation").strip().lower()
        # None vs "" matters: unset → transport default; empty → same as unset.
        host = resolve_bind_host(transport, os.getenv("HOST"))
        port = int(os.getenv("PORT", "7860"))

        # Phones on LAN need HTTPS for getUserMedia; default on for web transport.
        https_default = "true" if transport == "web" else "false"
        web_https = os.getenv("WEB_HTTPS", https_default).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        web_cert_dir = Path(
            os.getenv("WEB_CERT_DIR", str(Path.cwd() / ".lingo-certs"))
        ).expanduser()

        if bot_mode not in VALID_BOT_MODES:
            raise ValueError("BOT_MODE must be 'conversation', 'echo_utterance', or 'echo_live'")

        if require_ai is None:
            require_ai = bot_mode == "conversation"

        if require_whatsapp:
            missing = [
                name
                for name, value in [
                    ("WHATSAPP_TOKEN", token),
                    ("WHATSAPP_PHONE_NUMBER_ID", phone_number_id),
                    ("WHATSAPP_WEBHOOK_VERIFICATION_TOKEN", verify_token),
                ]
                if not value
            ]
            if missing:
                raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        if require_ai:
            missing = [
                name
                for name, value in [
                    ("ELEVENLABS_API_KEY", elevenlabs_api_key),
                    ("OPENAI_API_KEY", openai_api_key),
                ]
                if not value
            ]
            if missing:
                names = ", ".join(missing)
                raise ValueError(f"Missing required environment variables for AI features: {names}")

        if require_whatsapp and require_ai:
            missing = [
                name
                for name, value in [
                    ("DATABASE_URL", database_url),
                    ("LEARNER_ID_SECRET", learner_id_secret),
                ]
                if not value
            ]
            if missing:
                raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(
            transport=transport,
            whatsapp_token=token,
            whatsapp_phone_number_id=phone_number_id,
            whatsapp_webhook_verification_token=verify_token,
            whatsapp_app_secret=app_secret,
            elevenlabs_api_key=elevenlabs_api_key,
            elevenlabs_voice_id=elevenlabs_voice_id,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            database_url=database_url,
            learner_id_secret=learner_id_secret,
            bot_mode=bot_mode,
            host=host,
            port=port,
            web_https=web_https,
            web_cert_dir=web_cert_dir,
        )
