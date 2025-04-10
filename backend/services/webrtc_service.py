from typing import Dict
import asyncio
from pipecat.transports.network.webrtc_connection import SmallWebRTCConnection
from pipecat.transports.network.small_webrtc import SmallWebRTCTransport
from pipecat.transports.base_transport import TransportParams
from pipecat.audio.vad.silero import SileroVADAnalyzer

from config.settings import WEBRTC_AUDIO_CHUNK_SIZE
from utils.logging import setup_logging

logger = setup_logging()

class WebRTCService:
    def __init__(self):
        self.connections: Dict[str, SmallWebRTCConnection] = {}
    
    async def handle_offer(self, sdp: str, sdp_type: str, pc_id: str = None) -> dict:
        if pc_id and pc_id in self.connections:
            connection = self.connections[pc_id]
            logger.info(f"Reusing existing connection for pc_id: {pc_id}")
            await connection.renegotiate(sdp=sdp, type=sdp_type)
        else:
            connection = SmallWebRTCConnection()
            await connection.initialize(sdp=sdp, type=sdp_type)
            
            @connection.event_handler("closed")
            async def handle_disconnected(webrtc_connection: SmallWebRTCConnection):
                logger.info(f"Discarding peer connection for pc_id: {webrtc_connection.pc_id}")
                self.connections.pop(webrtc_connection.pc_id, None)
        
        answer = connection.get_answer()
        self.connections[answer["pc_id"]] = connection
        return answer
    
    def create_transport(self, connection: SmallWebRTCConnection) -> SmallWebRTCTransport:
        return SmallWebRTCTransport(
            webrtc_connection=connection,
            params=TransportParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                vad_enabled=True,
                vad_analyzer=SileroVADAnalyzer(),
                vad_audio_passthrough=True,
                audio_out_10ms_chunks=WEBRTC_AUDIO_CHUNK_SIZE
            ),
        )
    
    async def cleanup(self):
        coros = [pc.close() for pc in self.connections.values()]
        await asyncio.gather(*coros)
        self.connections.clear() 