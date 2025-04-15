from typing import AsyncGenerator
import aiohttp

from pipecat.frames.frames import Frame, ErrorFrame, TextFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.ai_service import AIService

class SarvamTranslationService(AIService):
    def __init__(self, api_key: str, source_language_code: str = "en-IN", target_language_code: str = "ta-IN"):
        super().__init__()
        self._api_key = api_key
        self._source_language_code = source_language_code
        self._target_language_code = target_language_code
        self._endpoint = "https://api.sarvam.ai/translate"
        self._session = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session:
            await self._session.close()
            self._session = None

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> AsyncGenerator[Frame, None]:
        print(f"DEBUG: SarvamTranslationService.process_frame called with frame={frame}, direction={direction}")
        if isinstance(frame, TextFrame):
            text = frame.text
            payload = {
                "input": text,
                "source_language_code": self._source_language_code,
                "target_language_code": self._target_language_code,
                "speaker_gender": "female",
                "mode": "modern-colloquial"
            }
            headers = {"api-subscription-key": self._api_key}

            try:
                if self._session is None:
                    self._session = aiohttp.ClientSession()
                async with self._session.post(self._endpoint, json=payload, headers=headers) as response:
                    if response.status != 200:
                        yield ErrorFrame(f"Translation error (status: {response.status})")
                        return
                    data = await response.json()
                    translated_text = data["translated_text"]
                    yield TextFrame(text=translated_text)
            except Exception as e:
                yield ErrorFrame(f"Error during translation: {str(e)}")
        else:
            print(f"DEBUG: Yielding frame={frame}")
            yield frame

    async def cleanup(self):
        if self._session:
            await self._session.close()
            self._session = None