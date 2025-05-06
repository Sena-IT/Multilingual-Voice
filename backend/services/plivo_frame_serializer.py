import base64
import json
from typing import Optional
from loguru import logger
from pipecat.serializers.base_serializer import FrameSerializer

# ---- Pipecat frame imports ---------------------------------------------------
from pipecat.frames.frames import (
    Frame,
    AudioRawFrame,
    BotStoppedSpeakingFrame,
    CancelFrame,
    StartInterruptionFrame,
    TransportMessageFrame,
    TransportMessageUrgentFrame,
    EndFrame,
)

# -----------------------------------------------------------------------------


class PlivoFrameSerializer(FrameSerializer):
    """Serialize Pipecat frames to/from Plivo WebSocket messages."""

    def __init__(self, stream_sid: str = "", call_id: str = ""):
        """
        Args:
            stream_sid: Stream ID from Plivo's <Stream> start event.
            call_id:    Call ID from Plivo's <Stream> start event.
        """
        self._stream_sid = stream_sid
        self._call_id = call_id
        self._initialized = False

        # True while the caller is talking; drop bot-audio until bot actually stops.
        self._mute_until_bot_stops = False

    # -------------------------------------------------------------------------
    # Required property
    # -------------------------------------------------------------------------
    @property
    def type(self) -> str:
        return "plivo"

    # -------------------------------------------------------------------------
    # Helper to set IDs after we receive Plivo's “start” event
    # -------------------------------------------------------------------------
    def set_stream_info(self, stream_sid: str, call_id: str):
        self._stream_sid = stream_sid
        self._call_id = call_id
        self._initialized = True
        logger.debug(
            f"Plivo serializer initialized with stream_sid={stream_sid}, call_id={call_id}"
        )

    # -------------------------------------------------------------------------
    # SERIALIZE  (Pipecat → Plivo WebSocket)
    # -------------------------------------------------------------------------
    async def serialize(self, frame: Frame) -> Optional[str]:
        """
        Map Pipecat frames to Plivo WebSocket JSON strings.

        * StartInterruptionFrame / CancelFrame → clearAudio + begin muting
        * While muted → drop any AudioRawFrame from TTS
        * BotStoppedSpeakingFrame → lift mute flag
        * AudioRawFrame → playAudio
        """

        # 1️⃣  Interruption detected → flush Plivo & start muting
        if isinstance(frame, (StartInterruptionFrame, CancelFrame)):
            self._mute_until_bot_stops = True
            message = {"event": "clearAudio", "streamId": self._stream_sid}
            logger.debug(f"[Serializer] clearAudio → {message}")
            return json.dumps(message)

        # 2️⃣  While muted, discard any bot audio frames
        if self._mute_until_bot_stops and isinstance(frame, AudioRawFrame):
            logger.debug("[Serializer] Dropping bot audio during interruption")
            return None

        # 3️⃣  Bot finished speaking → un-mute
        if isinstance(frame, BotStoppedSpeakingFrame):
            self._mute_until_bot_stops = False
            logger.debug("[Serializer] Bot stopped → un-mute")
            return None  # control frame, nothing to send

        # 4️⃣  Normal outbound audio → playAudio
        if isinstance(frame, AudioRawFrame):
            audio_bytes = (
                frame.audio.tobytes() if hasattr(frame.audio, "tobytes") else frame.audio
            )
            payload = base64.b64encode(audio_bytes).decode("utf-8")
            return json.dumps(
                {
                    "event": "playAudio",
                    "media": {
                        "contentType": "audio/x-l16",
                        "sampleRate": frame.sample_rate,
                        "payload": payload,
                    },
                }
            )

        # 5️⃣  Transport-level JSON frames — pass straight through
        if isinstance(frame, (TransportMessageFrame, TransportMessageUrgentFrame)):
            msg = frame.message
            return json.dumps(msg) if isinstance(msg, dict) else msg

        # 6️⃣  End of call — just close socket, no JSON needed
        if isinstance(frame, EndFrame):
            logger.debug("[Serializer] EndFrame → socket will close")
            return None

        # 7️⃣  Anything else is ignored
        logger.debug(f"[Serializer] skipping unsupported frame type: {type(frame)}")
        return None

    # -------------------------------------------------------------------------
    # DESERIALIZE  (Plivo WebSocket → Pipecat)
    # -------------------------------------------------------------------------
    async def deserialize(self, data: str) -> Optional[Frame]:
        """
        Convert Plivo WebSocket JSON messages to Pipecat frames.
        Only 'media', 'start', 'stop', 'checkpoint', 'playedStream',
        and 'clearedAudio' are handled; others are logged and ignored.
        """
        try:
            message = json.loads(data)
            event = message.get("event")

            # -- Inbound audio -------------------------------------------------
            if event == "media":
                media = message.get("media", {})
                payload = media.get("payload", "")
                audio_data = base64.b64decode(payload)
                sample_rate = media.get("sampleRate", 8000)
                from pipecat.frames.frames import AudioRawFrame  # local import to avoid cycles

                frame = AudioRawFrame(
                    audio=audio_data,
                    sample_rate=sample_rate,
                    num_channels=1,
                )
                # Optional timestamp
                timestamp = media.get("timestamp", "0")
                frame.pts = int(timestamp) if timestamp else None
                return frame

            # -- Stream start --------------------------------------------------
            if event == "start":
                sd = message.get("start", {})
                self.set_stream_info(sd.get("streamId", ""), sd.get("callId", ""))
                logger.info(f"Plivo stream initialized: {sd}")
                return None

            # -- Stream stop ---------------------------------------------------
            if event == "stop":
                logger.info("Plivo stream stopped")
                return None

            # -- Plivo control callbacks --------------------------------------
            if event in {"checkpoint", "playedStream", "clearedAudio"}:
                return TransportMessageFrame(message=message)

            logger.debug(f"Unknown Plivo event: {event}")
            return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode Plivo JSON: {e}")
        except Exception as e:
            logger.error(f"Error deserializing Plivo message: {e}")

        return None

    # -------------------------------------------------------------------------
    # Helper accessors
    # -------------------------------------------------------------------------
    def get_stream_id(self) -> str:
        return self._stream_sid

    def get_call_id(self) -> str:
        return self._call_id

    def is_initialized(self) -> bool:
        return self._initialized
