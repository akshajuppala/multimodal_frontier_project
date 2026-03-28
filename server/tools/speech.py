"""
Speech tool — converts text to speech and returns audio data.

Supports OpenAI TTS and ElevenLabs. Falls back gracefully.
The audio bytes are intended to be sent back over websocket to the iOS app.
"""
from __future__ import annotations

import base64
import os
from typing import Optional

from langchain_core.tools import tool

TTS_PROVIDER = os.getenv("TTS_PROVIDER", "openai")  # "openai" or "elevenlabs"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel

# Websocket callback — set by the server at runtime
_ws_send_callback = None


def set_ws_callback(callback):
    """Register the websocket send function so speech_tool can push audio to the client."""
    global _ws_send_callback
    _ws_send_callback = callback


def _tts_openai(text: str) -> bytes:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=text,
        response_format="mp3",
    )
    return response.content


def _tts_elevenlabs(text: str) -> bytes:
    import httpx

    response = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
        headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.75, "similarity_boost": 0.75},
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return response.content


@tool
def speech_tool(text: str) -> dict:
    """Speak text aloud to the user via text-to-speech.

    This is the primary way to communicate with the user. Every message
    you want the user to hear must go through this tool.

    Args:
        text: The message to speak to the user. Keep it short and clear.

    Returns:
        Confirmation with the text that was spoken.
    """
    audio_b64: Optional[str] = None

    try:
        if TTS_PROVIDER == "elevenlabs" and ELEVENLABS_API_KEY:
            audio_bytes = _tts_elevenlabs(text)
        elif OPENAI_API_KEY:
            audio_bytes = _tts_openai(text)
        else:
            audio_bytes = None

        if audio_bytes:
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        audio_b64 = None

    # Push to websocket if callback is registered
    if _ws_send_callback:
        import asyncio
        import json

        msg = json.dumps({
            "type": "speech",
            "payload": {"text": text, "audio": audio_b64 or ""},
        })
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(_ws_send_callback(msg))
            else:
                loop.run_until_complete(_ws_send_callback(msg))
        except Exception:
            pass

    return {"spoken": True, "text": text, "has_audio": audio_b64 is not None}
