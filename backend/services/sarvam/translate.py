import requests
from typing import Optional

from loguru import logger
from pipecat.frames.frames import Frame, TextFrame, ErrorFrame, LLMFullResponseEndFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.ai_service import AIService
from pipecat.utils.text.simple_text_aggregator import SimpleTextAggregator

class SarvamTranslationService(AIService):
    def __init__(
        self,
        *,
        api_key: str,
        source_language_code: str = "en-IN",
        target_language_code: str = "ta-IN",
        speaker_gender: str = "Female",
        mode: str = "modern-colloquial",
        numerals_format: str = "international",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._api_key = api_key
        self._source_language_code = source_language_code
        self._target_language_code = target_language_code
        self._speaker_gender = speaker_gender
        self._mode = mode
        self._numerals_format = numerals_format
        self._endpoint = "https://api.sarvam.ai/translate"
        self._text_aggregator = SimpleTextAggregator()
        self._full_text = ""  # Store full text separately
        self._validate_params()

    def _validate_params(self):
        valid_genders = ["Male", "Female"]
        valid_modes = ["formal", "modern-colloquial"]
        valid_numerals = ["international", "native"]
        if self._speaker_gender not in valid_genders:
            raise ValueError(f"speaker_gender must be one of {valid_genders}")
        if self._mode not in valid_modes:
            raise ValueError(f"mode must be one of {valid_modes}")
        if self._numerals_format not in valid_numerals:
            raise ValueError(f"numerals_format must be one of {valid_numerals}")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        logger.debug(f"{self}: Received frame {frame.__class__.__name__}")
        
        if isinstance(frame, TextFrame):
            aggregated_text = self._text_aggregator.aggregate(frame.text)
            self._full_text += frame.text  # Append to full text
            logger.debug(f"{self}: Aggregated text chunk '{frame.text}', current buffer: '{self._text_aggregator.text}', full text: '{self._full_text}'")
            if aggregated_text:
                logger.debug(f"{self}: Partial aggregation result: '{aggregated_text}'")
        elif isinstance(frame, LLMFullResponseEndFrame):
            full_text = self._full_text.strip()  # Use stored full text
            logger.debug(f"{self}: LLM response complete, full text: '{full_text}'")
            if full_text:
                translated_text = await self._translate(full_text)
                if translated_text:
                    logger.debug(f"{self}: Translated text: '{translated_text}'")
                    await self.push_frame(TextFrame(translated_text))
                else:
                    logger.error(f"{self}: Translation failed for '{full_text}'")
                    await self.push_frame(ErrorFrame("Translation failed"))
            else:
                logger.warning(f"{self}: No text to translate")
            self._full_text = ""  # Reset full text
            self._text_aggregator.reset()  # Reset aggregator
        else:
            logger.debug(f"{self}: Passing through frame {frame.__class__.__name__}")
            await self.push_frame(frame, direction)

    async def _translate(self, text: str) -> Optional[str]:
        logger.debug(
            f"{self}: Translating text [{text}] from {self._source_language_code} to "
            f"{self._target_language_code} (gender: {self._speaker_gender}, mode: {self._mode}, "
            f"numerals: {self._numerals_format})"
        )
        
        payload = {
            "input": text,
            "source_language_code": self._source_language_code,
            "target_language_code": self._target_language_code,
            "speaker_gender": self._speaker_gender,
            "mode": self._mode,
            "numerals_format": self._numerals_format
        }
        headers = {
            "api-subscription-key": self._api_key,
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(self._endpoint, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result["translated_text"]
        except Exception as e:
            logger.exception(f"{self} error translating text: {e}")
            return None