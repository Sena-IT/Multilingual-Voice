from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.groq.stt import GroqSTTService
from pipecat.transcriptions.language import Language
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.gladia.stt import GladiaSTTService
from pipecat.services.gladia.config import (GladiaInputParams,
    LanguageConfig,
    RealtimeProcessingConfig)
from pipecat.services.together.llm import TogetherLLMService
from pipecat.transports.network.small_webrtc import SmallWebRTCTransport
# from pipecat.utils.text.simple_text_aggregator import SimpleTextAggregator
# from pipecat.frames.frames import Frame, TextFrame, LLMFullResponseEndFrame
# from pipecat.processors.frame_processor import FrameDirection



from config.env import OPENAI_API_KEY, SARVAM_API_KEY, CARTESIA_API_KEY, GROQ_API_KEY, GLADIA_API_KEY, GOOGLE_API_KEY, TOGETHER_API_KEY
from utils.constants import SYSTEM_INSTRUCTION, INITIAL_BOT_MESSAGE
from utils.logging import setup_logging
from services.sarvam.tts import SarvamTTSService
# from services.sarvam.translation import SarvamTranslationService

logger = setup_logging()

class BotService:
    def __init__(self, transport: SmallWebRTCTransport, language: str):
        self.transport = transport
        self.stt = self._create_stt(language)
        self.llm = self._create_llm()
        # self.translation = self._create_translation()
        self.tts = self._create_tts(language)
        self.context = self._create_context()
        self.context_aggregator = self.llm.create_context_aggregator(self.context)
        # self.text_aggregator = SimpleTextAggregator()  # Add aggregator for LLM text
        self.pipeline = self._create_pipeline()
        self.task = self._create_task()
        self.runner = PipelineRunner(handle_sigint=False)
        
        self.transport.event_handler("on_client_connected")(self.on_client_connected)
        self.transport.event_handler("on_client_disconnected")(self.on_client_disconnected)
        self.transport.event_handler("on_client_closed")(self.on_client_closed)
    
    def _create_stt(self, language: str) -> OpenAISTTService:
        return GladiaSTTService(
            api_key=GLADIA_API_KEY,
            model="solaria-1",
            params=GladiaInputParams(
                language_config=LanguageConfig(
                    languages=[Language.EN, Language.FR],
                    code_switching=True
                ),
            )
        )
        #     return GroqSTTService(
        #         model="whisper-large-v3-turbo",
        #         api_key=GROQ_API_KEY,
        #         language=Language.EN,
        #         prompt="Understand very clearly what the user is saying. transcribe it accurately to english. Do not miss any words or phrases.",
        #         temperature=0.0
        # )
        # else:
        #     return OpenAISTTService(
        #         api_key=OPENAI_API_KEY,
        #         model="whisper-1",
        #         prompt="Understand very clearly what the user is saying. transcribe it accurately to english. Do not miss any words or phrases.",
        #         temperature=0.0
        #     )
    
    def _create_llm(self) -> OpenAILLMService:
        return TogetherLLMService(
            api_key=TOGETHER_API_KEY,
            model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
        )
        
        # return GoogleLLMService(api_key=GOOGLE_API_KEY, model="gemini-2.0-flash-lite")
        
        
        
        # return OpenAILLMService(
        #     api_key=OPENAI_API_KEY,
        #     model="gpt-4o-mini",
        #     prompt="You will receive a transcript of the user's query in English. Respond with a clear and concise answer in English.",
        #     system_instruction=SYSTEM_INSTRUCTION,
        # )
    
    # def _create_translation(self) -> SarvamTranslationService:
    #     translation = SarvamTranslationService(api_key=SARVAM_API_KEY)
    #     print(f"DEBUG: Created translation service: {translation}")
    #     return translation
    

    def _create_tts(self, language: str):
        if language == "ta":
            return self._create_sarvam_tts()
        else:
            return self._create_cartesia_tts()
    
    def _create_sarvam_tts(self) -> SarvamTTSService:
        return SarvamTTSService(
            api_key=SARVAM_API_KEY,
            voice="anushka",
            model="bulbul:v2",
            sample_rate=24000,
            target_language_code="ta-IN"
        )
    def _create_cartesia_tts(self) -> CartesiaTTSService:
        return CartesiaTTSService(
            api_key=CARTESIA_API_KEY,
            voice_id="0c8ed86e-6c64-40f0-b252-b773911de6bb",
            model="sonic-2",
        )
    
    def _create_context(self) -> OpenAILLMContext:
        return OpenAILLMContext([
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            INITIAL_BOT_MESSAGE
        ])
    
    def _create_pipeline(self) -> Pipeline:
        return Pipeline([
            self.transport.input(),
            self.stt,
            self.context_aggregator.user(),
            self.llm,
            self.tts,
            self.transport.output(),
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
    
    async def run(self):
        await self.runner.run(self.task)

    # async def process_frame(self, frame: Frame, direction: FrameDirection):
    #     if isinstance(frame, TextFrame):
    #         self.text_aggregator.aggregate(frame.text)
    #         logger.debug(f"Aggregated text chunk: '{frame.text}', full text: '{self.text_aggregator.text}'")
    #     elif isinstance(frame, LLMFullResponseEndFrame):
    #         full_text = self.text_aggregator.text
    #         if full_text:
    #             logger.debug(f"Full LLM response for TTS: '{full_text}'")
    #             async for tts_frame in self.tts.run_tts(full_text):
    #                 await self.push_frame(tts_frame, direction)
    #         self.text_aggregator.reset()
    #     else:
    #         await self.push_frame(frame, direction)