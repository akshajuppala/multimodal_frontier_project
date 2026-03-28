"""
Vision analysis tool — sends a camera frame to a multimodal LLM
and returns structured observations about the scene.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from server.state.models import FrameObservation
from server.state.store import StateStore

OBSERVER_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "observer_system.md"
_observer_prompt: Optional[str] = None


def _load_observer_prompt() -> str:
    global _observer_prompt
    if _observer_prompt is None:
        _observer_prompt = OBSERVER_PROMPT_PATH.read_text()
    return _observer_prompt


def _build_previous_state_summary(store: StateStore) -> str:
    objects = store.get_all_objects()
    people = store.get_present_people()
    recent = store.get_observations(limit=3)

    parts = []
    if objects:
        obj_lines = [f"- {o.item}: {o.location} (confidence {o.confidence:.0%})" for o in objects[:15]]
        parts.append("Known objects:\n" + "\n".join(obj_lines))
    if people:
        parts.append("People present: " + ", ".join(p.name for p in people))
    if recent:
        parts.append("Recent activity:\n" + "\n".join(f"- [{r['timestamp']}] {r['summary']}" for r in recent))
    return "\n\n".join(parts) if parts else "No previous state available."


@tool
def analyze_frame(frame_base64: str) -> dict:
    """Analyze a camera frame to detect objects, people, activities, and dangers.

    Args:
        frame_base64: Base64-encoded JPEG image from the camera.

    Returns:
        Structured observation with objects, people, activity, danger signals.
    """
    store = StateStore()
    try:
        previous_state = _build_previous_state_summary(store)
        system_prompt = _load_observer_prompt()

        vision_llm = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=1500)

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Previous state:\n{previous_state}\n\nAnalyze this frame:"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{frame_base64}", "detail": "low"},
                    },
                ],
            },
        ]

        response = vision_llm.invoke(messages)
        content = response.content

        # Parse the JSON from the LLM response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        observation_data = json.loads(content.strip())
        observation = FrameObservation(**observation_data)

        if observation.changed:
            if observation.timestamp is None:
                observation.timestamp = datetime.utcnow()
            store.save_observation(observation)

        return observation.model_dump(mode="json")
    finally:
        store.close()
