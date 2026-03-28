# Expo Frontend Design

## Overview

Single-screen Expo mobile app that streams camera frames to the backend via websocket and provides a push-to-talk voice interface for the Alzheimer's caregiver assistant.

## Architecture

Expo managed workflow with `expo-camera`, `expo-av`, `expo-speech`. Two parallel data streams:

1. **Continuous**: Camera JPEG snapshots at 2 FPS sent over WS `/video/stream`
2. **On-demand**: Push-to-talk records audio → Whisper API (STT) → POST `/speech` → `expo-speech` (TTS)

```
Camera Preview (full screen)
        │
        ├── Timer (500ms) ──► WS /video/stream (JPEG binary)
        │
        └── Push-to-Talk Button
              │ (press & hold)
              ▼
         expo-av Recording
              │ (release)
              ▼
         Whisper API (STT) → text
              │
              ▼
         POST /speech {text} → {response}
              │
              ▼
         expo-speech (TTS) → audio playback
```

## Screen Layout

- Camera preview fills entire screen
- Large push-to-talk button centered at bottom
- Button states: default (mic icon), recording (pulsing red), processing (spinner)
- Connection status dot in corner (green/red)

## File Structure

```
mobile/
├── app.json
├── package.json
├── tsconfig.json
├── .env                        # OPENAI_API_KEY, BACKEND_URL, FRAME_SAMPLE_RATE
├── App.tsx
├── src/
│   ├── screens/
│   │   └── CameraScreen.tsx
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   ├── useFrameCapture.ts
│   │   ├── useVoiceRecorder.ts
│   │   └── useSpeechAgent.ts
│   └── services/
│       ├── whisper.ts
│       └── api.ts
└── assets/
```

## Dependencies

- `expo-camera` — camera preview + JPEG snapshots
- `expo-av` — audio recording
- `expo-speech` — TTS playback
- OpenAI Whisper API via fetch — STT

## Backend Integration

No backend changes needed. Existing endpoints:
- WS `/video/stream` — accepts binary JPEG frames
- POST `/speech` — accepts `{"text": "..."}`, returns `{"response": "..."}`
- GET `/health` — status check

## Shared Config

`FRAME_SAMPLE_RATE` used by both backend and mobile `.env` to keep capture rate in sync.
