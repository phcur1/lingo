"""Per-call Pipecat pipeline for the WhatsApp echo bot."""

from __future__ import annotations

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.whatsapp.api import WhatsAppConnectCall
from pipecat.workers.runner import WorkerRunner

from lingo.echo import LiveEchoProcessor, UtteranceEchoProcessor


async def run_bot(
    webrtc_connection: SmallWebRTCConnection,
    call: WhatsAppConnectCall | None = None,
    *,
    echo_mode: str = "utterance",
) -> None:
    """Answer one WhatsApp call and echo the caller's voice."""

    caller = call.from_ if call else None
    call_id = call.id if call else None
    logger.info(
        "Starting echo bot mode={} call_id={} caller={}",
        echo_mode,
        call_id,
        caller,
    )

    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_out_10ms_chunks=2,
        ),
    )

    processors: list = [transport.input()]

    if echo_mode == "live":
        processors.append(LiveEchoProcessor())
    else:
        processors.extend(
            [
                VADProcessor(vad_analyzer=SileroVADAnalyzer()),
                UtteranceEchoProcessor(),
            ]
        )

    processors.append(transport.output())

    pipeline = Pipeline(processors)
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=False,
        ),
        idle_timeout_secs=None,
    )
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_transport, _client):
        logger.info("WebRTC connected for call_id={}", call_id)

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client):
        logger.info("WebRTC disconnected for call_id={}", call_id)
        await runner.cancel()

    await runner.run()
    logger.info("Echo bot finished for call_id={}", call_id)
