from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.together.llm import TogetherLLMService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.gladia.stt import GladiaSTTService
from pipecat.services.gladia.config import GladiaInputParams, LanguageConfig, RealtimeProcessingConfig
from pipecat.services.cartesia.tts import CartesiaTTSService
from services.sarvam.tts import SarvamTTSService
from pipecat.transcriptions.language import Language
from pipecat.transports.network.small_webrtc import SmallWebRTCTransport
from pipecat.pipeline.task import PipelineParams, PipelineTask
from config.env import OPENAI_API_KEY, SARVAM_API_KEY, CARTESIA_API_KEY, GLADIA_API_KEY, TOGETHER_API_KEY
from utils.constants import SYSTEM_INSTRUCTION, INITIAL_BOT_MESSAGE, SYSTEM_INSTRUCTION_TA
from utils.logging import setup_logging
from services.zoho.zoho_llm import get_lead_data_with_llm  # ✅ Newly imported

import openai
import asyncio
import json

logger = setup_logging()


class BotService:
    def __init__(self, transport: SmallWebRTCTransport, language: str):
        self.transport = transport
        self.full_transcript = []

        # Initialize components
        self.stt = self._create_stt(language)
        self.llm = self._create_llm(language)
        self.tts = self._create_tts(language)
        self.context = self._create_context(language)
        self.context_aggregator = self.llm.create_context_aggregator(self.context)

        # Transcript processor
        self.transcript = TranscriptProcessor()
        self._setup_transcript_handler()

        # Build pipeline and task
        self.pipeline = self._create_pipeline()
        self.task = self._create_task()
        self.runner = PipelineRunner(handle_sigint=False)

        # Event handlers
        self.transport.event_handler("on_client_connected")(self.on_client_connected)
        self.transport.event_handler("on_client_disconnected")(self.on_client_disconnected)
        self.transport.event_handler("on_client_closed")(self.on_client_closed)

    def _setup_transcript_handler(self):
        @self.transcript.event_handler("on_transcript_update")
        async def on_transcript_update(processor, frame):
            for message in frame.messages:
                self.full_transcript.append({
                    "timestamp": message.timestamp,
                    "role": message.role,
                    "content": message.content
                })
            print("Transcript Update =====================", self.full_transcript)

    def _create_stt(self, language: str):
        if language == "ta":
            transcript_ta = OpenAISTTService(
                api_key=OPENAI_API_KEY,
                model="whisper-1",
                prompt="""Listen carefully to Tamil speech. Transcribe it accurately into clear and correct English. 
                Do not miss any words or important context. The user is speaking in Tamil clearly. Listen carefully.""",
                temperature=0.0
            )
            print("Transcript TA =====================", transcript_ta)
            return transcript_ta
        else:
            transcript = GladiaSTTService(
                api_key=GLADIA_API_KEY,
                model="solaria-1",
                language="en",
                code_switching=True
            )
            print("Transcript =====================", transcript)
            return transcript

    def _create_llm(self, language: str) -> TogetherLLMService:
        print("Language ================", language)
        if language == "ta":
            return TogetherLLMService(
                api_key=TOGETHER_API_KEY,
                model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                system_instruction=SYSTEM_INSTRUCTION_TA
            )
        else:
            return TogetherLLMService(
                api_key=TOGETHER_API_KEY,
                model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                system_instruction=SYSTEM_INSTRUCTION
            )

    def _create_tts(self, language: str):
        if language == "ta":
            return SarvamTTSService(
                api_key=SARVAM_API_KEY,
                voice="anushka",
                model="bulbul:v2",
                sample_rate=24000,
                target_language_code="ta-IN"
            )
        else:
            return CartesiaTTSService(
                api_key=CARTESIA_API_KEY,
                voice_id="0c8ed86e-6c64-40f0-b252-b773911de6bb",
                model="sonic-2",
            )

    def _create_context(self, language: str) -> OpenAILLMContext:
        if language == "ta":
            return OpenAILLMContext([{"role": "system", "content": SYSTEM_INSTRUCTION_TA}, INITIAL_BOT_MESSAGE])
        else:
            return OpenAILLMContext([{"role": "system", "content": SYSTEM_INSTRUCTION}, INITIAL_BOT_MESSAGE])

    def _create_pipeline(self) -> Pipeline:
        return Pipeline([
            self.transport.input(),         # Audio input
            self.stt,                       # Speech-to-text
            self.transcript.user(),         # <== Already present
            self.context_aggregator.user(),
            self.llm,                       # LLM processing
            self.tts,                       # TTS
            self.transport.output(),        # Output audio
            self.transcript.assistant(),    # <== Already present
            self.context_aggregator.assistant(),
        ])

    def _create_task(self) -> PipelineTask:
        return PipelineTask(
            self.pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
                enable_usage_metrics=True,
                report_only_initial_ttfb=True,
            ),
        )

    async def on_client_connected(self, transport, client):
        logger.info("Pipecat Client connected")
        context_frame = self.context_aggregator.user().get_context_frame()
        await self.task.queue_frames([context_frame])

    async def on_client_disconnected(self, transport, client):
        logger.info("Pipecat Client disconnected")

    async def on_client_closed(self, transport, client):
        logger.info("Pipecat Client closed")
        await self.task.cancel()

        # Print final transcript
        logger.info("Full Conversation Transcript:")
        for entry in self.full_transcript:
            logger.info(f"[{entry['timestamp']}] {entry['role'].capitalize()}: {entry['content']}")

        # Optional: Save to file
        import json
        with open("latest_conversation.json", "w") as f:
            json.dump(self.full_transcript, f, indent=2)

        # ✅ NEW: Extract and send lead data after conversation ends
        try:
            await self.process_lead_data()
        except Exception as e:
            logger.error("Failed to process lead data:", exc_info=True)

        # Clear for next session
        self.full_transcript.clear()

    async def process_lead_data(self):
        """Trigger LLM-based lead extraction and submit to Zoho"""
        logger.info("Processing lead data from full transcript...")
        if not self.full_transcript:
            logger.warning("No transcript available for lead processing.")
            return

        # Call the external LLM function
        lead_data = await asyncio.get_event_loop().run_in_executor(None, get_lead_data_with_llm, self.full_transcript)
        logger.info("Lead Data Extracted:", lead_data)

    async def run(self):
        await self.runner.run(self.task)