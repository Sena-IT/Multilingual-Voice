from typing import AsyncGenerator, Optional
import aiohttp
import base64
import io
import os
import re
import time

from loguru import logger
from pydub import AudioSegment

from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    StartFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.services.tts_service import TTSService

class SarvamTTSService(TTSService):
    DEFAULT_SAMPLE_RATE = 24000  # Match WebRTC transport
    SARVAM_API_SAMPLE_RATE = 24000  # Closest Sarvam-supported rate

    def __init__(
        self,
        *,
        api_key: str,
        voice: str = "Maitreyi",
        model: str = "bulbul:v1",
        sample_rate: Optional[int] = None,
        source_language_code: str = "en-IN",
        target_language_code: str = "ta-IN",
        **kwargs,
    ):
        super().__init__(sample_rate=sample_rate or self.DEFAULT_SAMPLE_RATE, **kwargs)
        self._api_key = api_key
        self.set_model_name(model)
        self.set_voice(voice)
        self._source_language_code = source_language_code
        self._target_language_code = target_language_code
        self._tts_endpoint = "https://api.sarvam.ai/text-to-speech"
        # self._translate_endpoint = "https://api.sarvam.ai/translate"
        self._session = None
        self._validate_voice(voice)
        self._validate_model(model)

    def _validate_voice(self, voice: str) -> None:
        supported_voices = [
            "meera", "pavithra", "maitreyi", "arvind", "amol", "amartya",
            "diya", "neel", "misha", "vian", "arjun", "maya", "anushka",
            "abhilash", "manisha", "vidya", "arya", "karun", "hitesh"
        ]
        if voice not in supported_voices:
            raise ValueError(f"Voice '{voice}' is not supported. Choose from: {supported_voices}")

    def _validate_model(self, model: str) -> None:
        supported_models = ["bulbul:v1", "bulbul:v2"]
        if model not in supported_models:
            raise ValueError(f"Model '{model}' is not supported. Choose from: {supported_models}")

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session:
            await self._session.close()
            self._session = None

    async def start(self, frame: StartFrame):
        await super().start(frame)
        logger.info(f"StartFrame audio_out_sample_rate: {frame.audio_out_sample_rate}, TTS sample_rate: {self.sample_rate}")
        if self.sample_rate != frame.audio_out_sample_rate:
            logger.warning(
                f"Sample rate mismatch: TTS ({self.sample_rate} Hz) vs Transport ({frame.audio_out_sample_rate} Hz)"
            )
        if self.SARVAM_API_SAMPLE_RATE not in [8000, 16000, 22050, 24000]:
            logger.error(f"Invalid Sarvam API sample rate: {self.SARVAM_API_SAMPLE_RATE}")

    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        if len(text) > 500:
            yield ErrorFrame("Input text exceeds 500 characters.")
            return

        logger.debug(f"{self}: Processing text [{text}]")
        await self.start_ttfb_metrics()

        # TTS step
        tts_payload = {
            "text": text,  # Use 'text' instead of 'inputs'
            "target_language_code": self._target_language_code,
            "speaker": self._voice_id,
            "model": self.model_name,
            "speech_sample_rate": self.SARVAM_API_SAMPLE_RATE,
            "enable_preprocessing": True
        }

        headers = {"api-subscription-key": self._api_key}

        try:
            if self._session is None:
                self._session = aiohttp.ClientSession()
            async with self._session.post(self._tts_endpoint, json=tts_payload, headers=headers) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error(f"{self} TTS error (status: {response.status}, error: {error})")
                    yield ErrorFrame(f"Error getting audio (status: {response.status}, error: {error})")
                    return
                tts_data = await response.json()
                audio_data = tts_data["audios"][0]
                audio_bytes = base64.b64decode(audio_data)

            # Save raw WAV for debugging
            timestamp = int(time.time() * 1000)
            safe_text = re.sub(r'[^\w\s-]', '', text[:30].replace(" ", "_").replace("\n", "").replace("\t", ""))
            debug_wav_filename = f"debug_audio/sarvam_raw_{timestamp}_{safe_text}.wav"
            os.makedirs("debug_audio", exist_ok=True)
            with open(debug_wav_filename, "wb") as f:
                f.write(audio_bytes)
            logger.info(f"Saved raw Sarvam AI audio to: {debug_wav_filename}")

            # Convert WAV to PCM and upsample
            audio_segment = AudioSegment.from_wav(io.BytesIO(audio_bytes))
            audio_segment = audio_segment.set_channels(1)
            audio_segment = audio_segment.set_sample_width(2)
            if audio_segment.frame_rate != self.sample_rate:
                audio_segment = audio_segment.set_frame_rate(self.sample_rate)
            raw_audio = audio_segment.raw_data

            await self.start_tts_usage_metrics(text)
            yield TTSStartedFrame()

            CHUNK_SIZE = int(self.sample_rate * 0.02 * 2)  # 20 ms at 24000 Hz = 960 bytes
            for i in range(0, len(raw_audio), CHUNK_SIZE):
                chunk = raw_audio[i:i + CHUNK_SIZE]
                await self.stop_ttfb_metrics()
                yield TTSAudioRawFrame(
                    audio=chunk,
                    sample_rate=self.sample_rate,
                    num_channels=1
                )

            yield TTSStoppedFrame()

        except Exception as e:
            logger.exception(f"{self} error generating TTS: {e}")
            yield ErrorFrame(f"Error generating TTS: {str(e)}")

    async def cleanup(self):
        if self._session:
            await self._session.close()
            self._session = None

    def can_generate_metrics(self) -> bool:
        return True

   

def create_sarvam_tts() -> SarvamTTSService:
        return SarvamTTSService(
            api_key=os.getenv("SARVAM_API_KEY"),
            voice="anushka",
            model="bulbul:v2",
            sample_rate=24000,
            target_language_code="ta-IN"
        )    