import base64
import json
import typing
from loguru import logger

from pipecat.frames.frames import (
    AudioRawFrame,  # Correct import - not AudioFrame
    Frame,
    CancelFrame,
    StartFrame,
    TransportMessageUrgentFrame,
    TransportMessageFrame,
    EndFrame,
)
from pipecat.serializers.base_serializer import FrameSerializer  # Correct import - not abstract_serializer


class PlivoFrameSerializer(FrameSerializer):
    """Plivo-specific frame serializer for WebSocket communication"""
    
    def __init__(self, stream_sid: str = "", call_id: str = ""):
        """
        Initialize the Plivo frame serializer.
        
        Args:
            stream_sid: The stream ID from Plivo's start event
            call_id: The call ID from Plivo's start event
        """
        self._stream_sid = stream_sid
        self._call_id = call_id
        self._initialized = False
    
    @property
    def type(self) -> str:
        """
        Required abstract property for FrameSerializer.
        Returns the type of serializer.
        """
        return "plivo"
    
    def set_stream_info(self, stream_sid: str, call_id: str):
        """Update stream info after connection"""
        self._stream_sid = stream_sid
        self._call_id = call_id
        self._initialized = True
        logger.debug(f"Plivo serializer initialized with stream_sid: {stream_sid}, call_id: {call_id}")
    
    async def serialize(self, frame: Frame) -> typing.Optional[str]:
        """
        Serialize a Frame to Plivo WebSocket format
        
        Args:
            frame: Frame to serialize
            
        Returns:
            JSON string for WebSocket message or None
        """
        result = None
        
        if isinstance(frame, AudioRawFrame):
            # Convert audio frame to Plivo format
            audio_bytes = frame.audio
            if hasattr(audio_bytes, 'tobytes'):
                audio_bytes = audio_bytes.tobytes()
            
            # Encode to base64
            payload = base64.b64encode(audio_bytes).decode('utf-8')
            
            # Plivo expects playAudio event for outgoing audio
            message = {
                "event": "playAudio",
                "media": {
                    "contentType": "audio/x-l16",  # Plivo supports audio/x-l16
                    "sampleRate": frame.sample_rate,
                    "payload": payload
                }
            }
            
            result = json.dumps(message)
            logger.debug(f"Serialized audio frame: sample_rate={frame.sample_rate}, payload_length={len(payload)}")
            
        elif isinstance(frame, TransportMessageFrame) or isinstance(frame, TransportMessageUrgentFrame):
            # Handle transport messages
            if isinstance(frame.message, dict):
                result = json.dumps(frame.message)
            elif isinstance(frame.message, str):
                result = frame.message
            else:
                logger.error(f"Unsupported transport message type: {type(frame.message)}")
                
        elif isinstance(frame, (EndFrame, CancelFrame)):
            # Plivo doesn't have explicit hangup messages like Twilio
            # The call ends when the WebSocket connection is closed
            logger.debug(f"Frame type {type(frame).__name__} - connection will close")
            result = None
            
        else:
            logger.debug(f"Skipping serialization for unsupported frame type: {type(frame)}")
        
        return result
    
    async def deserialize(self, data: str) -> typing.Optional[Frame]:
        """
        Deserialize Plivo WebSocket message to Frame
        
        Args:
            data: JSON string from Plivo WebSocket
            
        Returns:
            Frame object or None
        """
        try:
            message = json.loads(data)
            event = message.get("event")
            
            logger.debug(f"Deserializing Plivo event: {event}")
            
            if event == "media":
                # Extract audio data from Plivo format
                media = message.get("media", {})
                payload = media.get("payload", "")
                
                # Decode base64 audio
                audio_data = base64.b64decode(payload)
                
                # Extract metadata
                sample_rate = media.get("sampleRate", 8000)
                track = media.get("track", "inbound")
                timestamp = media.get("timestamp", "0")
                chunk = media.get("chunk", 0)
                
                # Create AudioRawFrame
                frame = AudioRawFrame(
                    audio=audio_data,
                    sample_rate=sample_rate,
                    num_channels=1  # Plivo uses mono audio
                )
                
                # Add metadata
                frame.pts = int(timestamp) if timestamp else None
                
                logger.debug(f"Deserialized audio frame: track={track}, chunk={chunk}, "
                           f"sample_rate={sample_rate}, size={len(audio_data)}")
                
                return frame
                
            elif event == "start":
                # just pull out Plivo’s IDs and stash them—
                # Pipecat will emit its own StartFrame for the pipeline.
                sd  = message.get("start", {})
                sid = sd.get("streamId")
                cid = sd.get("callId")
                if sid and cid:
                    self.set_stream_info(sid, cid)
                logger.info(f"Plivo stream initialized: {sd}")
                return None
                
            elif event == "stop":
                # Let on_client_disconnected handle pipeline teardown
                logger.info("Plivo stream stopped")
                return None
                
            elif event == "checkpoint":
                # Handle checkpoint events (Plivo-specific)
                checkpoint_data = {
                    "streamId": message.get("streamId", ""),
                    "name": message.get("name", "")
                }
                return TransportMessageFrame(message=checkpoint_data)
                
            elif event == "playedStream":
                # Handle playedStream events (Plivo-specific)
                played_data = {
                    "streamId": message.get("streamId", ""),
                    "name": message.get("name", "")
                }
                return TransportMessageFrame(message=played_data)
                
            else:
                logger.debug(f"Unknown Plivo event: {event}")
                
            return None
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error deserializing Plivo message: {e}")
            return None
    
    def get_stream_id(self) -> str:
        """Get the current stream ID"""
        return self._stream_sid
    
    def get_call_id(self) -> str:
        """Get the current call ID"""
        return self._call_id
    
    def is_initialized(self) -> bool:
        """Check if the serializer has been initialized with stream info"""
        return self._initialized