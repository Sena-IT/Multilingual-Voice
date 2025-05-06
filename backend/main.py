import argparse
import asyncio
from contextlib import asynccontextmanager
import sys
from uuid import uuid4
import json
import uvicorn
from fastapi import FastAPI, WebSocket
from loguru import logger

from services.bot_service import run_bot
from starlette.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from services.plivo_frame_serializer import PlivoFrameSerializer


logger.add(sys.stderr, level="DEBUG")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/")
async def start_call():
    print("POST Plivo ML")
    return HTMLResponse(content=open("plivo/senabot.xml").read(), media_type="application/xml")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        # For Plivo, the first message should be a "start" event
        # We need to get the stream_sid and call_id from this message
        start_data = await websocket.receive_text()
        start_message = json.loads(start_data)
        
        print(f"Received start message: {start_message}", flush=True)
        
        # Extract stream_sid and call_id from Plivo format
        stream_sid = start_message.get("start", {}).get("streamId", "")
        call_id = start_message.get("start", {}).get("callId", "")
        
        print(f"WebSocket connection accepted - StreamID: {stream_sid}, CallID: {call_id}")
        
        
        temp_serializer = PlivoFrameSerializer(stream_sid, call_id)
        
        # Deserialize the start message to create a StartFrame
        start_frame = temp_serializer.deserialize(start_data)
        
        # Send the start_data back to the bot pipeline to process
        # We'll handle this in the run_bot function
        await run_bot(websocket, stream_sid, call_id, app.state.testing)
        
    except Exception as e:
        print(f"WebSocket error: {e}", flush=True)
        logger.exception("WebSocket error")
        await websocket.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipecat Bot Server")
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host"
    )
    parser.add_argument("--port", type=int, default=7860, help="Port")
    parser.add_argument("--testing", action="store_true", help="Enable testing mode")
    args = parser.parse_args()

    app.state.testing = args.testing

    uvicorn.run(app, host=args.host, port=args.port)