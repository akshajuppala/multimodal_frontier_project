import base64
import json
import logging

import anthropic

from src.agent.prompts import OBSERVER_SYSTEM_PROMPT
from src.models import Observation

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


async def observe_frames(frames: list[tuple[str, bytes]]) -> Observation:
    """Send a window of JPEG frames to Claude vision and return an Observation."""
    client = get_client()

    content_blocks: list[dict] = []
    for _timestamp, jpeg_bytes in frames:
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
            f"These are {len(frames)} sequential frames from a home camera, "
            f"spanning from {frames[0][0]} to {frames[-1][0]}. "
            "Analyze the scene and respond with the JSON observation."
        ),
    })

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=OBSERVER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content_blocks}],
    )

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
