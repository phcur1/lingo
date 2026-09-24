"""FastAPI server for WhatsApp Calling or local browser WebRTC."""

from __future__ import annotations

import argparse
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import aiohttp
import uvicorn
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from loguru import logger
from pipecat.transports.smallwebrtc.connection import IceServer, SmallWebRTCConnection
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)
from pipecat.transports.whatsapp.api import WhatsAppConnectCall, WhatsAppWebhookRequest
from pipecat.transports.whatsapp.client import WhatsAppClient

from lingo.bot import run_bot
from lingo.config import Settings
from lingo.tls import discover_lan_ips, ensure_self_signed_cert

STATIC_DIR = Path(__file__).resolve().parent / "static"

whatsapp_client: WhatsAppClient | None = None
small_webrtc_handler: SmallWebRTCRequestHandler | None = None
settings: Settings | None = None


def _log_access_urls(cfg: Settings) -> None:
    scheme = "https" if cfg.web_https and cfg.transport == "web" else "http"
    logger.info("Local: {}://127.0.0.1:{}", scheme, cfg.port)
    for ip in discover_lan_ips():
        logger.info("Phone on same Wi-Fi: {}://{}:{}", scheme, ip, cfg.port)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global whatsapp_client, small_webrtc_handler, settings

    bot_mode = os.getenv("BOT_MODE", "conversation").strip().lower()
    transport = os.getenv("TRANSPORT", "whatsapp").strip().lower()
    require_ai = bot_mode == "conversation"
    require_whatsapp = transport == "whatsapp"
    settings = Settings.from_env(require_whatsapp=require_whatsapp, require_ai=require_ai)

    logger.info(
        "Starting Lingo server (transport={}, mode={})",
        settings.transport,
        settings.bot_mode,
    )

    if settings.transport == "web":
        ice_servers = [IceServer(urls="stun:stun.l.google.com:19302")]
        small_webrtc_handler = SmallWebRTCRequestHandler(ice_servers=ice_servers)
        _log_access_urls(settings)
        if settings.web_https:
            logger.info(
                "Using HTTPS so phones can access the microphone. "
                "Accept the self-signed certificate warning once in the browser."
            )
        try:
            yield
        finally:
            if small_webrtc_handler is not None:
                await small_webrtc_handler.close()
                small_webrtc_handler = None
            logger.info("Shutdown complete")
        return

    logger.info("WhatsApp phone_number_id={}", settings.whatsapp_phone_number_id)
    async with aiohttp.ClientSession() as session:
        whatsapp_client = WhatsAppClient(
            whatsapp_token=settings.whatsapp_token,
            phone_number_id=settings.whatsapp_phone_number_id,
            session=session,
            whatsapp_secret=settings.whatsapp_app_secret,
        )
        try:
            yield
        finally:
            logger.info("Terminating active WhatsApp calls...")
            await whatsapp_client.terminate_all_calls()
            whatsapp_client = None
            logger.info("Shutdown complete")


app = FastAPI(
    title="Lingo Voice Bot",
    description=(
        "Voice bot with ElevenLabs STT/TTS and OpenAI LLM. "
        "Supports WhatsApp Cloud API Calling or a local browser WebRTC UI."
    ),
    version="0.3.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "transport": settings.transport if settings else "unknown",
        "mode": settings.bot_mode if settings else "unknown",
    }


@app.get("/")
async def index():
    """Serve the local browser call UI (web transport)."""
    if settings is None or settings.transport != "web":
        raise HTTPException(
            status_code=404,
            detail="Web UI is available when TRANSPORT=web",
        )
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=500, detail="Web UI assets missing")
    return FileResponse(index_path)


@app.post("/api/offer")
async def offer(request: SmallWebRTCRequest, background_tasks: BackgroundTasks):
    """Browser WebRTC offer/answer signaling."""
    if settings is None or settings.transport != "web" or small_webrtc_handler is None:
        raise HTTPException(status_code=404, detail="Web transport is not enabled")

    async def webrtc_connection_callback(connection: SmallWebRTCConnection) -> None:
        logger.info("Accepted browser WebRTC call pc_id={}", connection.pc_id)
        background_tasks.add_task(run_bot, connection, settings, None)

    answer = await small_webrtc_handler.handle_web_request(
        request=request,
        webrtc_connection_callback=webrtc_connection_callback,
    )
    return answer


@app.patch("/api/offer")
async def ice_candidate(request: SmallWebRTCPatchRequest):
    if settings is None or settings.transport != "web" or small_webrtc_handler is None:
        raise HTTPException(status_code=404, detail="Web transport is not enabled")
    await small_webrtc_handler.handle_patch_request(request)
    return {"status": "success"}


@app.get("/whatsapp")
async def verify_webhook(request: Request):
    """Meta webhook verification challenge."""
    if whatsapp_client is None or settings is None:
        raise HTTPException(status_code=503, detail="Service unavailable")

    params = dict(request.query_params)
    try:
        challenge = await whatsapp_client.handle_verify_webhook_request(
            params=params,
            expected_verification_token=settings.whatsapp_webhook_verification_token,
        )
        logger.info("WhatsApp webhook verification succeeded")
        return PlainTextResponse(content=str(challenge))
    except ValueError as exc:
        logger.warning("WhatsApp webhook verification failed: {}", exc)
        raise HTTPException(status_code=403, detail="Verification failed") from exc


@app.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
):
    """Handle inbound WhatsApp call connect / terminate webhooks."""
    if whatsapp_client is None or settings is None:
        raise HTTPException(status_code=503, detail="Service unavailable")

    raw_body = await request.body()
    try:
        body = WhatsAppWebhookRequest.model_validate_json(raw_body)
    except Exception as exc:
        logger.warning("Invalid WhatsApp webhook payload: {}", exc)
        raise HTTPException(status_code=400, detail="Invalid request body") from exc

    if body.object != "whatsapp_business_account":
        raise HTTPException(status_code=400, detail="Invalid object type")

    async def connection_callback(
        connection: SmallWebRTCConnection,
        call: WhatsAppConnectCall,
    ) -> None:
        logger.info("Accepted WhatsApp call id={} from={}", call.id, call.from_)
        background_tasks.add_task(run_bot, connection, settings, call)

    try:
        result = await whatsapp_client.handle_webhook_request(
            body,
            connection_callback,
            raw_body=raw_body,
            sha256_signature=x_hub_signature_256,
        )
        return {"status": "success", "handled": result}
    except ValueError as exc:
        logger.warning("Rejected WhatsApp webhook: {}", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Failed to process WhatsApp webhook")
        raise HTTPException(status_code=500, detail="Internal server error") from None


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lingo voice bot server")
    parser.add_argument("--host", default=None, help="Bind host (default: HOST env or 0.0.0.0)")
    parser.add_argument(
        "--port", type=int, default=None, help="Bind port (default: PORT env or 7860)"
    )
    parser.add_argument(
        "--transport",
        choices=["whatsapp", "web"],
        default=None,
        help="Call transport (default: TRANSPORT env or whatsapp)",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = create_parser().parse_args(argv)
    if args.transport:
        os.environ["TRANSPORT"] = args.transport

    transport = os.getenv("TRANSPORT", "whatsapp").strip().lower()
    require_whatsapp = transport == "whatsapp"
    cfg = Settings.from_env(require_whatsapp=require_whatsapp, require_ai=False)

    logger.remove()
    logger.add(sys.stderr, level="TRACE" if args.verbose else "INFO")

    host = args.host or cfg.host
    port = args.port or cfg.port
    ssl_kwargs: dict = {}

    if cfg.transport == "web" and cfg.web_https:
        cert_file, key_file = ensure_self_signed_cert(cfg.web_cert_dir)
        ssl_kwargs = {"ssl_certfile": str(cert_file), "ssl_keyfile": str(key_file)}
        logger.info("TLS cert: {}", cert_file)

    if cfg.transport == "web":
        scheme = "https" if ssl_kwargs else "http"
        logger.info("Listening on {}://{}:{} (open / on your phone)", scheme, host, port)
    else:
        logger.info("Listening on http://{}:{} (webhook path /whatsapp)", host, port)

    uvicorn.run(
        "lingo.server:app",
        host=host,
        port=port,
        log_level="info",
        factory=False,
        **ssl_kwargs,
    )


if __name__ == "__main__":
    main()
