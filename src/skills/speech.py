"""Speech/TTS skill — convert text to speech audio for the user.

Returns base64-encoded audio that the server can push over WebSocket.
"""
from __future__ import annotations

import base64
import logging
import os

import railtracks as rt

logger = logging.getLogger(__name__)

TTS_PROVIDER = os.getenv("TTS_PROVIDER", "openai")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")


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


@rt.function_node
def speech_tool(text: str) -> str:
    """Convert text to speech audio. Use this to speak to the user. Returns confirmation with base64-encoded audio.

    Args:
        text (str): The message to speak to the user. Keep it short and clear.
    """
    audio_b64 = ""

    try:
        if TTS_PROVIDER == "elevenlabs" and ELEVENLABS_API_KEY:
            audio_bytes = _tts_elevenlabs(text)
        elif OPENAI_API_KEY:
            audio_bytes = _tts_openai(text)
        else:
            logger.warning("No TTS API key configured — returning text only")
            return f"[TTS unavailable] {text}"

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return f"[TTS error] {text}"

    return f"SPEECH:{audio_b64}:{text}"
