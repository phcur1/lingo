# Lingo

Voice bot with **ElevenLabs STT/TTS** and **OpenAI LLM**, powered by Pipecat.

Two ways to talk to it:

1. **Web (local)** — run on your laptop, open a simple page on your phone over the same Wi‑Fi, tap Call. No WhatsApp.
2. **WhatsApp** — Meta Cloud API Calling webhooks + WebRTC.

Echo modes are still available for testing the audio path without AI costs.

## What it does

### Web transport (`TRANSPORT=web`)

1. This service serves a mobile-friendly page at `/` (HTTPS by default)
2. Your phone connects over WebRTC to the laptop
3. Same bot pipeline as WhatsApp: STT → LLM → TTS (or echo)

### WhatsApp transport (`TRANSPORT=whatsapp`, default)

1. Meta sends a `calls` webhook when someone dials your WhatsApp Business number
2. This service accepts the call over WebRTC (via Pipecat)
3. In **conversation mode** (default):
   - Caller audio → ElevenLabs STT → OpenAI LLM → ElevenLabs TTS → Response audio
   - LinGo keeps the conversation moving and selects up to two useful corrections
   - Completed turns and post-call learning memory are stored in PostgreSQL
4. In **echo modes** (for testing):
   - **echo_utterance**: buffers with Silero VAD, replays after silence
   - **echo_live**: immediate audio loopback

## Quick start — phone on same Wi‑Fi (no WhatsApp)

```bash
cp .env.example .env
# Required for conversation mode:
#   ELEVENLABS_API_KEY, OPENAI_API_KEY
# Optional: skip WhatsApp vars entirely

# In .env:
TRANSPORT=web
BOT_MODE=conversation

uv sync
uv run lingo
# or: uv run lingo --transport web
```

On startup the server prints a URL like `https://192.168.x.x:7860`. Open that on your phone (same Wi‑Fi), accept the self-signed certificate warning once, tap **Call**, allow the microphone.

Phones only expose the mic on HTTPS (except `localhost`), so web mode generates a local certificate under `.lingo-certs/` by default.

Echo test without AI keys:

```bash
TRANSPORT=web BOT_MODE=echo_live uv run lingo
```

Docker:

```bash
TRANSPORT=web BOT_MODE=conversation docker compose up --build
```

Then open `https://<laptop-lan-ip>:7860` from the phone.

## Quick start — WhatsApp (Docker)

```bash
cp .env.example .env
# Fill required credentials:
#   - WhatsApp: WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, etc.
#   - ElevenLabs: ELEVENLABS_API_KEY
#   - OpenAI: OPENAI_API_KEY
#   - Storage: DATABASE_URL, LEARNER_ID_SECRET
# TRANSPORT=whatsapp  (default)

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

## Testing Without WhatsApp Setup

### Browser UI (recommended)

Use `TRANSPORT=web` as above — real mic conversation on LAN.

### CLI Tool for Local Testing

Test the STT/LLM/TTS pipeline with audio files **without** needing WhatsApp or Meta infrastructure:

```bash
# Set API keys
export ELEVENLABS_API_KEY=your-key
export OPENAI_API_KEY=your-key

# Process an audio file
uv run lingo-cli input.mp3

# Save bot response to file
uv run lingo-cli input.mp3 -o response.wav

# Or pass keys directly
uv run lingo-cli input.mp3 \
  --elevenlabs-api-key=your-key \
  --openai-api-key=your-key \
  -o response.wav
```

**What it does:**
1. Reads your audio file (any format FFmpeg supports)
2. Transcribes it with ElevenLabs STT
3. Sends transcript to OpenAI LLM
4. Generates response audio with ElevenLabs TTS
5. Prints transcript and response text
6. Optionally saves response audio to file

**Requirements:**
- FFmpeg installed (`apt install ffmpeg` or `brew install ffmpeg`)
- ElevenLabs and OpenAI API keys
- No WhatsApp, tunnels, or webhooks needed

## Environment

| Variable | Required | Description |
|---|---|---|
| `TRANSPORT` | no | `whatsapp` (default) or `web` (browser UI) |
| `WHATSAPP_TOKEN` | whatsapp | Cloud API access token |
| `WHATSAPP_PHONE_NUMBER_ID` | whatsapp | Business phone number ID |
| `WHATSAPP_WEBHOOK_VERIFICATION_TOKEN` | whatsapp | Webhook verify token you choose |
| `WHATSAPP_APP_SECRET` | no | App secret; enables webhook signature checks |
| `BOT_MODE` | no | `conversation` (default), `echo_utterance`, or `echo_live` |
| `ELEVENLABS_API_KEY` | yes* | ElevenLabs API key (*required for conversation mode) |
| `ELEVENLABS_VOICE_ID` | no | Voice ID (default: Rachel) |
| `OPENAI_API_KEY` | yes* | OpenAI API key (*required for conversation mode) |
| `OPENAI_MODEL` | no | Model (default: `gpt-6-luna`) |
| `DATABASE_URL` | yes* | SQLAlchemy PostgreSQL URL (*WhatsApp conversation mode) |
| `LEARNER_ID_SECRET` | yes* | Secret for protected learner IDs (*WhatsApp conversation mode) |
| `HOST` / `PORT` | no | Bind address (default `0.0.0.0:7860`) |
| `WEB_HTTPS` | no | HTTPS for web UI (default `true` when `TRANSPORT=web`) |
| `WEB_CERT_DIR` | no | Where to store the self-signed cert (default `.lingo-certs`) |

## Bot Modes

### Conversation Mode (Production)
Real AI voice assistant using:
- **ElevenLabs STT**: Speech-to-text with low latency
- **OpenAI LLM**: configured `gpt-6-luna` model for conversation and post-call analysis
- **ElevenLabs TTS**: Natural voice synthesis

Set `BOT_MODE=conversation` and provide API keys.

### Echo Modes (Testing)
For validating the audio path without AI costs:
- `echo_utterance`: Replays what you said after detecting silence
- `echo_live`: Immediate audio loopback

## Project layout

```
src/lingo/
  server.py      # FastAPI: WhatsApp webhooks or / + /api/offer
  bot.py         # Per-call Pipecat pipeline (STT/LLM/TTS or echo)
  policy.py      # Shared live tutoring policy
  models.py      # SQLAlchemy transcript and learning-memory models
  analysis.py    # Post-call extraction and recurring-pattern updates
  echo.py        # Echo processors for testing
  config.py      # Unified configuration
  tls.py         # Self-signed certs for LAN HTTPS
  static/        # Browser call UI
```

Export the 15-case evaluation set for teacher review without calling external services:

```bash
uv run lingo-eval --output teacher-review.csv
```

Add `--run` to collect responses from the configured OpenAI model before export.

## Deploy notes

- Prefer the **Docker image** on a long-running host (Fly.io, Railway, Render, ECS, a VM). WhatsApp Calling needs persistent WebRTC connections; serverless platforms like **Vercel are a poor fit** even if the FastAPI entrypoint builds.
- Same image runs locally and in production; inject secrets via env
- WhatsApp webhook path stays `/whatsapp`
- Web UI path is `/` with signaling at `/api/offer`
- Media is WebRTC (not through an HTTPS tunnel); tunnels only carry WhatsApp signaling when used
- Inbound (user-initiated) WhatsApp calls are free on Meta's Calling API

## Test call

### Web
1. `TRANSPORT=web uv run lingo`
2. Open the printed `https://<lan-ip>:7860` on your phone
3. Tap Call and talk

### WhatsApp
1. Start the service and tunnel
2. Verify the webhook in Meta
3. From WhatsApp, call your business / test number
4. **Conversation mode**: Talk to the AI assistant naturally
5. **Echo mode**: Speak, pause — you should hear yourself replayed
