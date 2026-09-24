import pytest

from lingo.config import Settings, resolve_bind_host


def test_echo_mode_does_not_require_ai_or_database(monkeypatch):
    monkeypatch.setenv("BOT_MODE", "echo_live")
    monkeypatch.setenv("WHATSAPP_TOKEN", "token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "phone-id")
    monkeypatch.setenv("WHATSAPP_WEBHOOK_VERIFICATION_TOKEN", "verify")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("LEARNER_ID_SECRET", raising=False)
    settings = Settings.from_env(require_whatsapp=True, require_ai=False)
    assert settings.bot_mode == "echo_live"


def test_conversation_mode_requires_database(monkeypatch):
    monkeypatch.setenv("WHATSAPP_TOKEN", "token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "phone-id")
    monkeypatch.setenv("WHATSAPP_WEBHOOK_VERIFICATION_TOKEN", "verify")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "eleven")
    monkeypatch.setenv("OPENAI_API_KEY", "openai")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("LEARNER_ID_SECRET", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings.from_env(require_whatsapp=True, require_ai=True)


def test_web_transport_defaults_to_lan_ip(monkeypatch):
    monkeypatch.setenv("TRANSPORT", "web")
    monkeypatch.setenv("BOT_MODE", "echo_live")
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.setattr("lingo.config.primary_lan_ip", lambda: "192.168.1.42")
    settings = Settings.from_env(require_whatsapp=False, require_ai=False)
    assert settings.host == "192.168.1.42"


def test_host_auto_and_explicit(monkeypatch):
    monkeypatch.setattr("lingo.config.primary_lan_ip", lambda: "10.0.0.5")
    assert resolve_bind_host("web", "auto") == "10.0.0.5"
    assert resolve_bind_host("web", "0.0.0.0") == "0.0.0.0"
    assert resolve_bind_host("whatsapp", None) == "0.0.0.0"
