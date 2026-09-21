"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv(override=False)


@dataclass(frozen=True)
class Settings:
    whatsapp_token: str
    whatsapp_phone_number_id: str
    whatsapp_webhook_verification_token: str
    whatsapp_app_secret: str | None
    echo_mode: str
    host: str
    port: int

    @classmethod
    def from_env(cls, *, require_whatsapp: bool = True) -> Settings:
        token = os.getenv("WHATSAPP_TOKEN", "").strip()
        phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
        verify_token = os.getenv("WHATSAPP_WEBHOOK_VERIFICATION_TOKEN", "").strip()
        app_secret = os.getenv("WHATSAPP_APP_SECRET", "").strip() or None
        echo_mode = os.getenv("ECHO_MODE", "utterance").strip().lower()
        host = os.getenv("HOST", "0.0.0.0").strip()
        port = int(os.getenv("PORT", "7860"))

        if echo_mode not in {"utterance", "live"}:
            raise ValueError("ECHO_MODE must be 'utterance' or 'live'")

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

        return cls(
            whatsapp_token=token,
            whatsapp_phone_number_id=phone_number_id,
            whatsapp_webhook_verification_token=verify_token,
            whatsapp_app_secret=app_secret,
            echo_mode=echo_mode,
            host=host,
            port=port,
        )
