import argparse
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from config.env import validate_env
from config.settings import API_HOST, API_PORT, ALLOWED_ORIGINS
from services.webrtc_service import WebRTCService
from utils.logging import setup_logging

logger = setup_logging()

app = FastAPI()
webrtc_service = WebRTCService()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
async def health_check():
    return {"status": "ok", "message": "Service is running"}


# Include API routes
app.include_router(router, prefix="/api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate environment variables on startup
    validate_env()
    yield
    # Cleanup WebRTC connections on shutdown
    await webrtc_service.cleanup()

app.lifespan_context = lifespan

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC demo")
    parser.add_argument(
        "--host", default=API_HOST, help=f"Host for HTTP server (default: {API_HOST})"
    )
    parser.add_argument(
        "--port", type=int, default=API_PORT, help=f"Port for HTTP server (default: {API_PORT})"
    )
    parser.add_argument("--verbose", "-v", action="count")
    args = parser.parse_args()

    

    uvicorn.run(app, host=args.host, port=args.port) 