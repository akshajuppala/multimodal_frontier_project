import asyncio
import logging
import base64
from contextlib import asynccontextmanager

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.agent.context import SharedContext
from src.agent.graph import MainAgent
from src.config import settings
from src.logging.logger import AgentLogger
from src.observer.buffer import FrameBuffer
from src.observer.observer import observe_frames

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Shared state — initialized at module level
shared_context = SharedContext(max_observations=100)
agent_logger = AgentLogger("data/agent_log.jsonl")
main_agent = MainAgent(shared_context=shared_context, agent_logger=agent_logger)
frame_buffer = FrameBuffer(
    window_seconds=settings.observer_window_seconds,
    sample_rate=settings.frame_sample_rate,
)


class SpeechRequest(BaseModel):
    text: str


class SpeechResponse(BaseModel):
    response: str


async def process_observer_window(frames: list[tuple[str, bytes]]) -> None:
    """Run an observer job on a window of frames and update shared context."""
    try:
        observation = await observe_frames(frames)
        await shared_context.add_observation_async(observation)
        logger.info(f"Observation: {observation.actions}, urgency={observation.urgency}")

        if observation.is_urgent:
            summary = "; ".join(observation.safety_concerns or observation.actions)
            logger.warning(f"Urgent observation detected: {summary}")
            asyncio.create_task(main_agent.handle_proactive(summary))

    except Exception as e:
        logger.error(f"Observer job failed: {e}")


async def dispatch_loop() -> None:
    """Background loop that checks the buffer and dispatches observer jobs.
    Runs sequentially so a slow/retrying API call naturally throttles the next."""
    while True:
        if frame_buffer.should_dispatch():
            frames = frame_buffer.snapshot()
            if frames:
                await process_observer_window(frames)
        await asyncio.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(dispatch_loop())
    logger.info("Caregiver assistant started")
    yield


app = FastAPI(title="Alzheimer's Caregiver Assistant", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/video/stream")
async def video_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("Video stream connected")
    try:
        while True:
            data = await websocket.receive_text()
            img_data = base64.b64decode(data)
            frame_buffer.add_frame(img_data)
    except WebSocketDisconnect:
        logger.info("Video stream disconnected")


@app.post("/speech", response_model=SpeechResponse)
async def speech(request: SpeechRequest):
    try:
        response_text = await main_agent.handle_speech(request.text)
        return SpeechResponse(response=response_text)
    except Exception as e:
        logger.error(f"Speech handler failed: {e}")
        return SpeechResponse(response="I'm sorry, I'm having trouble right now. Please try again in a moment.")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "observations": len(shared_context.recent_observations),
        "items_tracked": len(shared_context.last_seen),
    }
