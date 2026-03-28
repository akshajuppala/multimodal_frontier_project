import asyncio
import base64
import json
import logging

import anthropic

from src.agent.prompts import OBSERVER_SYSTEM_PROMPT
from src.models import Observation
from src.config import settings

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None

MAX_FRAMES_PER_REQUEST = 3
MAX_RETRIES = 4
INITIAL_BACKOFF = 2.0


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            default_headers={}
        )
    return _client


def _subsample(frames: list[tuple[str, bytes]], n: int) -> list[tuple[str, bytes]]:
    """Pick n evenly-spaced frames from the window (first, middle…, last)."""
    if len(frames) <= n:
        return frames
    indices = [round(i * (len(frames) - 1) / (n - 1)) for i in range(n)]
    return [frames[i] for i in indices]


async def observe_frames(frames: list[tuple[str, bytes]]) -> Observation:
    """Send a window of JPEG frames to Claude vision and return an Observation."""
    client = get_client()
    sampled = _subsample(frames, MAX_FRAMES_PER_REQUEST)

    content_blocks: list[dict] = []
    for _timestamp, jpeg_bytes in sampled:
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.standard_b64encode(jpeg_bytes).decode("utf-8"),
            },
        })

    content_blocks.append({
        "type": "text",
        "text": (
            f"These are {len(sampled)} frames sampled from {len(frames)} total, "
            f"spanning from {frames[0][0]} to {frames[-1][0]}. "
            "Analyze the scene and respond with the JSON observation."
        ),
    })

    # Retry with exponential backoff on rate limits
    backoff = INITIAL_BACKOFF
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=OBSERVER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content_blocks}],
            )
            break
        except anthropic.RateLimitError as e:
            if attempt == MAX_RETRIES:
                raise
            retry_after = float(e.response.headers.get("retry-after", backoff))
            logger.warning(f"Rate limited, retrying in {retry_after:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})")
            await asyncio.sleep(retry_after)
            backoff *= 2

    response_text = response.content[0].text

    try:
        data = json.loads(response_text)
        return Observation(**data)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Failed to parse observer response: {e}\nRaw: {response_text}")
        return Observation(
            timestamp=frames[-1][0],
            actions=["[parse error] " + response_text[:200]],
            objects=[],
            safety_concerns=[],
            urgency="none",
        )
