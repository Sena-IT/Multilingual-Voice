from fastapi import APIRouter, BackgroundTasks, WebSocket
import json

from services.transport import WebRTCService
from services.bot_service import BotService
from utils.logging import setup_logging
from starlette.responses import HTMLResponse

logger = setup_logging()
router = APIRouter()
webrtc_service = WebRTCService()
bot_service = BotService()


@router.post("/")
async def start_call():
    print("POST Plivo ML")
    return HTMLResponse(content=open("backend\plivo\senabot.xml").read(), media_type="application/xml")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    start_data = websocket.iter_text()
    await start_data.__anext__()
    call_data = json.loads(await start_data.__anext__())
    print(call_data, flush=True)
    stream_sid = call_data["start"]["streamSid"]
    call_sid = call_data["start"]["callSid"]
    print("WebSocket connection accepted")
    await bot_service.run_bot(websocket, stream_sid, call_sid, router.state.testing)



@router.post("/offer")
async def handle_offer(request: dict, background_tasks: BackgroundTasks):
    pc_id = request.get("pc_id")
    sdp = request["sdp"]
    sdp_type = request["type"]
    language = request["language"]
    
    answer = await webrtc_service.handle_offer(sdp, sdp_type, pc_id)
    connection = webrtc_service.connections[answer["pc_id"]]
    
    transport = webrtc_service.create_transport(connection)
    bot_service = BotService(transport,language)
    background_tasks.add_task(bot_service.run)
    
    return answer 