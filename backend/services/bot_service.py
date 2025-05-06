import datetime
import io
import os
import sys
import wave
import asyncio
import json
import aiofiles
from dotenv import load_dotenv
from fastapi import WebSocket
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.services.gladia.stt import GladiaSTTService
from pipecat.services.gladia.config import (GladiaInputParams,
    LanguageConfig,
    RealtimeProcessingConfig)
from pipecat.services.together.llm import TogetherLLMService
from pipecat.transcriptions.language import Language
from services.plivo_frame_serializer import PlivoFrameSerializer
from pipecat.frames.frames import CancelFrame


from config.env import (
    OPENAI_API_KEY, 
    SARVAM_API_KEY, 
    CARTESIA_API_KEY, 
    GROQ_API_KEY,
    GLADIA_API_KEY, 
    TOGETHER_API_KEY,
    PLIVO_AUTH_ID,
    PLIVO_AUTH_TOKEN
)
from utils.constants import SYSTEM_INSTRUCTION, INITIAL_BOT_MESSAGE
from services.sarvam.tts import SarvamTTSService

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")



async def save_audio(server_name: str, audio: bytes, sample_rate: int, num_channels: int):
    if len(audio) > 0:
        filename = (
            f"{server_name}_recording_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        )
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wf:
                wf.setsampwidth(2)
                wf.setnchannels(num_channels)
                wf.setframerate(sample_rate)
                wf.writeframes(audio)
            async with aiofiles.open(filename, "wb") as file:
                await file.write(buffer.getvalue())
        logger.info(f"Merged audio saved to {filename}")
    else:
        logger.info("No audio data to save")


async def run_bot(websocket_client: WebSocket, stream_sid: str, call_id: str, testing: bool):
   
    serializer = PlivoFrameSerializer(stream_sid=stream_sid, call_id=call_id)

    transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_analyzer=SileroVADAnalyzer(),
            serializer=serializer,
        ),
    )

    # Use our LLM service
    llm = TogetherLLMService(
        api_key=TOGETHER_API_KEY,
        model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
    )

    # Use our STT service
    stt = GladiaSTTService(
        api_key=GLADIA_API_KEY,
        model="solaria-1",
        params=GladiaInputParams(
            language_config=LanguageConfig(
                languages=[Language.EN, Language.FR],
                code_switching=True
            ),
        )
    )

    # Use our TTS service - assuming English for Twilio
    tts = CartesiaTTSService(
        api_key=CARTESIA_API_KEY,
        voice_id="0c8ed86e-6c64-40f0-b252-b773911de6bb",
        model="sonic-2",
        push_silence_after_stop=testing,
    )

    # Use our system instruction and initial message
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        INITIAL_BOT_MESSAGE
    ]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    # NOTE: Watch out! This will save all the conversation in memory. You can
    # pass `buffer_size` to get periodic callbacks.
    audiobuffer = AudioBufferProcessor(user_continuous_stream=not testing)

    pipeline = Pipeline(
        [
            transport.input(),  # Websocket input from client
            stt,  # Speech-To-Text
            context_aggregator.user(),
            llm,  # LLM
            tts,  # Text-To-Speech
            transport.output(),  # Websocket output to client
            audiobuffer,  # Used to buffer the audio in the pipeline
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            allow_interruptions=True,
        ),
    )


    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # Start recording.
        logger.debug("[Handler] on_client_connected fired")
        await audiobuffer.start_recording()
        
        # Kick off the conversation.
        messages.append({"role": "system", "content": "Please introduce yourself to the user."})
        await task.queue_frames([context_aggregator.user().get_context_frame()])

        # await asyncio.sleep(5.0)
        # logger.debug("[Test] queuing CancelFrame()")
        # await task.queue_frames([CancelFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await task.cancel()

    @audiobuffer.event_handler("on_audio_data")
    async def on_audio_data(buffer, audio, sample_rate, num_channels):
        server_name = f"plivo_{stream_sid}"
        await save_audio(server_name, audio, sample_rate, num_channels)

    runner = PipelineRunner(handle_sigint=False, force_gc=True)

    await runner.run(task)