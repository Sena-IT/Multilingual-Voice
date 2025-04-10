from fastapi import APIRouter, BackgroundTasks
from typing import Dict

from services.webrtc_service import WebRTCService
from services.bot_service import BotService
from utils.logging import setup_logging

logger = setup_logging()
router = APIRouter()
webrtc_service = WebRTCService()

@router.post("/offer")
async def handle_offer(request: dict, background_tasks: BackgroundTasks):
    pc_id = request.get("pc_id")
    sdp = request["sdp"]
    sdp_type = request["type"]
    
    answer = await webrtc_service.handle_offer(sdp, sdp_type, pc_id)
    connection = webrtc_service.connections[answer["pc_id"]]
    
    transport = webrtc_service.create_transport(connection)
    bot_service = BotService(transport)
    background_tasks.add_task(bot_service.run)
    
    return answer 