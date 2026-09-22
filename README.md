# Lingo

Inbound WhatsApp voice calls answered by an echo bot. STT, LLM, and TTS are mocked: the bot replays the caller's audio so you can validate WhatsApp Cloud API Calling + WebRTC before wiring real speech services.

## What it does

1. Meta sends a `calls` webhook when someone dials your WhatsApp Business number
2. This service pre-accepts / accepts the call over WebRTC (via Pipecat)
3. Caller audio is either:
   - **utterance** (default): buffered with Silero VAD, then replayed after they stop talking
   - **live**: immediate audio loopback

## Quick start (Docker)

```bash
cp .env.example .env
# fill WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_WEBHOOK_VERIFICATION_TOKEN

docker compose up --build
```

Health check: `GET http://localhost:7860/health`  
Webhook: `https://<public-host>/whatsapp`

### Local tunnel

Meta needs a public HTTPS webhook. With the container on port 7860:

```bash
ngrok http 7860
# or: cloudflared tunnel --url http://localhost:7860
```

In Meta Developer Console → WhatsApp → Configuration → Webhooks:

- Callback URL: `https://<tunnel>/whatsapp`
- Verify token: same as `WHATSAPP_WEBHOOK_VERIFICATION_TOKEN`
- Subscribe field: **`calls`**

Also enable voice calling on the phone number (Calls tab). Register/connect the number if the Calls tab is missing.

## Quick start (uv, no Docker)

```bash
cp .env.example .env
uv sync
uv run lingo
```

## Environment

| Variable | Required | Description |
|---|---|---|
| `WHATSAPP_TOKEN` | yes | Cloud API access token |
| `WHATSAPP_PHONE_NUMBER_ID` | yes | Business phone number ID |
| `WHATSAPP_WEBHOOK_VERIFICATION_TOKEN` | yes | Webhook verify token you choose |
| `WHATSAPP_APP_SECRET` | no | App secret; enables webhook signature checks |
| `ECHO_MODE` | no | `utterance` (default) or `live` |
| `HOST` / `PORT` | no | Bind address (default `0.0.0.0:7860`) |

## Project layout

```
src/lingo/
  server.py   # FastAPI webhooks + health
  bot.py      # Per-call Pipecat pipeline
  echo.py     # Live / utterance echo processors
  config.py   # Env settings
```

## Deploy notes

- Prefer the **Docker image** on a long-running host (Fly.io, Railway, Render, ECS, a VM). WhatsApp Calling needs persistent WebRTC connections; serverless platforms like **Vercel are a poor fit** even if the FastAPI entrypoint builds.
- Same image runs locally and in production; inject secrets via env
- Webhook path stays `/whatsapp`
- Media is WebRTC to Meta (not through the tunnel); the tunnel only carries HTTPS signaling
- Inbound (user-initiated) WhatsApp calls are free on Meta's Calling API
- Swap `UtteranceEchoProcessor` for STT → LLM → TTS later without changing the WhatsApp layer

## Test call

1. Start the service and tunnel
2. Verify the webhook in Meta
3. From WhatsApp, call your business / test number
4. Speak, pause — you should hear yourself replayed
