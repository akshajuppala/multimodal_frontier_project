# Expo Frontend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an Expo mobile app that streams camera frames to the backend and provides a push-to-talk voice interface for the Alzheimer's caregiver assistant.

**Architecture:** Single-screen Expo app using `expo-camera` for JPEG snapshots at 2 FPS over websocket, `expo-av` for push-to-talk recording, OpenAI Whisper API for STT, backend POST `/speech` for agent responses, and `expo-speech` for TTS playback.

**Tech Stack:** Expo (React Native), TypeScript, expo-camera, expo-av, expo-speech, OpenAI Whisper API

---

### Task 1: Expo Project Scaffolding

**Files:**
- Create: `mobile/` directory via `create-expo-app`
- Modify: `mobile/app.json` for camera/microphone permissions
- Create: `mobile/.env`
- Create: `mobile/src/` directory structure

**Step 1: Create the Expo project**

Run from the project root:
```bash
cd /Users/aidenco/Projects/multimodal_frontier_project
npx create-expo-app@latest mobile --template blank-typescript
```

**Step 2: Install dependencies**

```bash
cd mobile
npx expo install expo-camera expo-av expo-speech
```

**Step 3: Create `.env`**

```
EXPO_PUBLIC_OPENAI_API_KEY=
EXPO_PUBLIC_BACKEND_URL=http://localhost:8000
EXPO_PUBLIC_FRAME_SAMPLE_RATE=2
```

Note: Expo requires `EXPO_PUBLIC_` prefix for env vars accessible in the app.

**Step 4: Update `app.json` with permissions plugins**

Add to the `expo` object in `app.json`:

```json
{
  "expo": {
    "plugins": [
      [
        "expo-camera",
        {
          "cameraPermission": "Allow the caregiver assistant to observe your environment"
        }
      ],
      [
        "expo-av",
        {
          "microphonePermission": "Allow the caregiver assistant to hear your voice"
        }
      ]
    ]
  }
}
```

**Step 5: Create directory structure**

```bash
mkdir -p src/screens src/hooks src/services
```

**Step 6: Commit**

```bash
git add mobile/
git commit -m "feat: expo project scaffolding with camera, av, and speech deps"
```

---

### Task 2: API Service & Whisper Service

**Files:**
- Create: `mobile/src/services/api.ts`
- Create: `mobile/src/services/whisper.ts`

**Step 1: Write `mobile/src/services/api.ts`**

```typescript
const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || "http://localhost:8000";

export interface SpeechResponse {
  response: string;
}

export async function postSpeech(text: string): Promise<string> {
  const res = await fetch(`${BACKEND_URL}/speech`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    throw new Error(`Speech API error: ${res.status}`);
  }

  const data: SpeechResponse = await res.json();
  return data.response;
}

export async function getHealth(): Promise<{ status: string; observations: number; items_tracked: number }> {
  const res = await fetch(`${BACKEND_URL}/health`);
  if (!res.ok) {
    throw new Error(`Health API error: ${res.status}`);
  }
  return res.json();
}
```

**Step 2: Write `mobile/src/services/whisper.ts`**

```typescript
const OPENAI_API_KEY = process.env.EXPO_PUBLIC_OPENAI_API_KEY || "";

export async function transcribeAudio(audioUri: string): Promise<string> {
  const formData = new FormData();

  formData.append("file", {
    uri: audioUri,
    type: "audio/m4a",
    name: "recording.m4a",
  } as any);

  formData.append("model", "whisper-1");
  formData.append("language", "en");

  const response = await fetch(
    "https://api.openai.com/v1/audio/transcriptions",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENAI_API_KEY}`,
      },
      body: formData,
    }
  );

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Whisper API error (${response.status}): ${errorBody}`);
  }

  const data = await response.json();
  return data.text;
}
```

**Step 3: Commit**

```bash
git add mobile/src/services/
git commit -m "feat: api and whisper service clients"
```

---

### Task 3: useWebSocket Hook

**Files:**
- Create: `mobile/src/hooks/useWebSocket.ts`

**Step 1: Write `mobile/src/hooks/useWebSocket.ts`**

```typescript
import { useEffect, useRef, useState, useCallback } from "react";

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || "http://localhost:8000";

type ConnectionStatus = "connecting" | "connected" | "disconnected";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    const wsUrl = BACKEND_URL.replace(/^http/, "ws") + "/video/stream";
    setStatus("connecting");

    const ws = new WebSocket(wsUrl);
    ws.binaryType = "blob";

    ws.onopen = () => {
      setStatus("connected");
    };

    ws.onclose = () => {
      setStatus("disconnected");
      wsRef.current = null;
      // Reconnect after 3 seconds
      reconnectTimeout.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendFrame = useCallback((base64Jpeg: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      // Convert base64 to binary and send
      const binaryString = atob(base64Jpeg);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      wsRef.current.send(bytes.buffer);
    }
  }, []);

  return { status, sendFrame };
}
```

**Step 2: Commit**

```bash
git add mobile/src/hooks/useWebSocket.ts
git commit -m "feat: websocket hook with auto-reconnect for frame streaming"
```

---

### Task 4: useFrameCapture Hook

**Files:**
- Create: `mobile/src/hooks/useFrameCapture.ts`

**Step 1: Write `mobile/src/hooks/useFrameCapture.ts`**

```typescript
import { useEffect, useRef, useCallback } from "react";
import { CameraView } from "expo-camera";

const FRAME_SAMPLE_RATE = Number(process.env.EXPO_PUBLIC_FRAME_SAMPLE_RATE) || 2;
const INTERVAL_MS = 1000 / FRAME_SAMPLE_RATE;

export function useFrameCapture(
  cameraRef: React.RefObject<CameraView | null>,
  sendFrame: (base64Jpeg: string) => void,
  enabled: boolean
) {
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const captureFrame = useCallback(async () => {
    if (!cameraRef.current) return;

    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.5,
        base64: true,
        exif: false,
        shutterSound: false,
      });

      if (photo?.base64) {
        sendFrame(photo.base64);
      }
    } catch {
      // Camera may not be ready yet, silently ignore
    }
  }, [cameraRef, sendFrame]);

  useEffect(() => {
    if (enabled) {
      intervalRef.current = setInterval(captureFrame, INTERVAL_MS);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [enabled, captureFrame]);
}
```

**Step 2: Commit**

```bash
git add mobile/src/hooks/useFrameCapture.ts
git commit -m "feat: frame capture hook with configurable sample rate"
```

---

### Task 5: useVoiceRecorder Hook

**Files:**
- Create: `mobile/src/hooks/useVoiceRecorder.ts`

**Step 1: Write `mobile/src/hooks/useVoiceRecorder.ts`**

```typescript
import { useState, useRef, useCallback } from "react";
import { Audio } from "expo-av";
import type { Recording } from "expo-av/build/Audio";
import { transcribeAudio } from "../services/whisper";

const SPEECH_RECORDING_OPTIONS: Audio.RecordingOptions = {
  isMeteringEnabled: false,
  android: {
    extension: ".m4a",
    outputFormat: Audio.AndroidOutputFormat.MPEG_4,
    audioEncoder: Audio.AndroidAudioEncoder.AAC,
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 64000,
  },
  ios: {
    extension: ".m4a",
    outputFormat: Audio.IOSOutputFormat.MPEG4AAC,
    audioQuality: Audio.IOSAudioQuality.MEDIUM,
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 64000,
    linearPCMBitDepth: 16,
    linearPCMIsBigEndian: false,
    linearPCMIsFloat: false,
  },
  web: {
    mimeType: "audio/webm",
    bitsPerSecond: 64000,
  },
};

export type RecorderState = "idle" | "recording" | "transcribing";

export function useVoiceRecorder() {
  const [state, setState] = useState<RecorderState>("idle");
  const recordingRef = useRef<Recording | null>(null);

  const startRecording = useCallback(async () => {
    const { status } = await Audio.requestPermissionsAsync();
    if (status !== "granted") {
      throw new Error("Microphone permission not granted");
    }

    await Audio.setAudioModeAsync({
      allowsRecordingIOS: true,
      playsInSilentModeIOS: true,
    });

    const { recording } = await Audio.Recording.createAsync(
      SPEECH_RECORDING_OPTIONS
    );

    recordingRef.current = recording;
    setState("recording");
  }, []);

  const stopAndTranscribe = useCallback(async (): Promise<string> => {
    if (!recordingRef.current) {
      throw new Error("No active recording");
    }

    setState("transcribing");

    await recordingRef.current.stopAndUnloadAsync();
    await Audio.setAudioModeAsync({
      allowsRecordingIOS: false,
    });

    const uri = recordingRef.current.getURI();
    recordingRef.current = null;

    if (!uri) {
      setState("idle");
      throw new Error("No recording URI");
    }

    try {
      const text = await transcribeAudio(uri);
      setState("idle");
      return text;
    } catch (error) {
      setState("idle");
      throw error;
    }
  }, []);

  return { state, startRecording, stopAndTranscribe };
}
```

**Step 2: Commit**

```bash
git add mobile/src/hooks/useVoiceRecorder.ts
git commit -m "feat: voice recorder hook with Whisper STT integration"
```

---

### Task 6: useSpeechAgent Hook

**Files:**
- Create: `mobile/src/hooks/useSpeechAgent.ts`

**Step 1: Write `mobile/src/hooks/useSpeechAgent.ts`**

```typescript
import { useState, useCallback } from "react";
import * as Speech from "expo-speech";
import { postSpeech } from "../services/api";

export type AgentState = "idle" | "thinking" | "speaking";

export function useSpeechAgent() {
  const [agentState, setAgentState] = useState<AgentState>("idle");
  const [lastResponse, setLastResponse] = useState<string>("");

  const askAgent = useCallback(async (text: string): Promise<void> => {
    setAgentState("thinking");

    try {
      const response = await postSpeech(text);
      setLastResponse(response);
      setAgentState("speaking");

      await new Promise<void>((resolve, reject) => {
        Speech.speak(response, {
          language: "en-US",
          pitch: 1.0,
          rate: 0.9,
          onDone: () => {
            setAgentState("idle");
            resolve();
          },
          onStopped: () => {
            setAgentState("idle");
            resolve();
          },
          onError: (error) => {
            setAgentState("idle");
            reject(error);
          },
        });
      });
    } catch (error) {
      setAgentState("idle");
      throw error;
    }
  }, []);

  const stopSpeaking = useCallback(() => {
    Speech.stop();
    setAgentState("idle");
  }, []);

  return { agentState, lastResponse, askAgent, stopSpeaking };
}
```

**Step 2: Commit**

```bash
git add mobile/src/hooks/useSpeechAgent.ts
git commit -m "feat: speech agent hook with TTS playback"
```

---

### Task 7: CameraScreen

**Files:**
- Create: `mobile/src/screens/CameraScreen.tsx`

**Step 1: Write `mobile/src/screens/CameraScreen.tsx`**

```typescript
import React, { useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
} from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import { useWebSocket } from "../hooks/useWebSocket";
import { useFrameCapture } from "../hooks/useFrameCapture";
import { useVoiceRecorder } from "../hooks/useVoiceRecorder";
import { useSpeechAgent } from "../hooks/useSpeechAgent";

export default function CameraScreen() {
  const cameraRef = useRef<CameraView>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [cameraReady, setCameraReady] = useState(false);

  const { status: wsStatus, sendFrame } = useWebSocket();
  useFrameCapture(cameraRef, sendFrame, cameraReady && wsStatus === "connected");

  const { state: recorderState, startRecording, stopAndTranscribe } =
    useVoiceRecorder();
  const { agentState, lastResponse, askAgent } = useSpeechAgent();

  const isProcessing =
    recorderState === "transcribing" || agentState === "thinking";
  const isBusy =
    recorderState !== "idle" || agentState !== "idle";

  const handlePressIn = async () => {
    if (isBusy) return;
    try {
      await startRecording();
    } catch (error) {
      console.error("Failed to start recording:", error);
    }
  };

  const handlePressOut = async () => {
    if (recorderState !== "recording") return;
    try {
      const text = await stopAndTranscribe();
      if (text) {
        await askAgent(text);
      }
    } catch (error) {
      console.error("Voice interaction failed:", error);
    }
  };

  // Permissions not loaded yet
  if (!permission) {
    return <View style={styles.container} />;
  }

  // Permissions not granted
  if (!permission.granted) {
    return (
      <View style={styles.permissionContainer}>
        <Text style={styles.permissionText}>
          Camera access is needed for the caregiver assistant.
        </Text>
        <Pressable style={styles.permissionButton} onPress={requestPermission}>
          <Text style={styles.permissionButtonText}>Grant Access</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView
        ref={cameraRef}
        style={styles.camera}
        facing="back"
        onCameraReady={() => setCameraReady(true)}
      />

      {/* Connection status indicator */}
      <View style={styles.statusBar}>
        <View
          style={[
            styles.statusDot,
            {
              backgroundColor:
                wsStatus === "connected" ? "#4CAF50" : "#F44336",
            },
          ]}
        />
        <Text style={styles.statusText}>
          {wsStatus === "connected" ? "Connected" : "Disconnected"}
        </Text>
      </View>

      {/* Last response text */}
      {lastResponse ? (
        <View style={styles.responseContainer}>
          <Text style={styles.responseText} numberOfLines={3}>
            {lastResponse}
          </Text>
        </View>
      ) : null}

      {/* Push-to-talk button */}
      <View style={styles.buttonContainer}>
        {isProcessing ? (
          <View style={[styles.talkButton, styles.processingButton]}>
            <ActivityIndicator color="#fff" size="large" />
            <Text style={styles.buttonLabel}>
              {recorderState === "transcribing"
                ? "Listening..."
                : "Thinking..."}
            </Text>
          </View>
        ) : (
          <Pressable
            style={({ pressed }) => [
              styles.talkButton,
              recorderState === "recording" && styles.recordingButton,
              pressed && styles.talkButtonPressed,
            ]}
            onPressIn={handlePressIn}
            onPressOut={handlePressOut}
            disabled={isBusy}
          >
            <Text style={styles.buttonIcon}>
              {recorderState === "recording" ? "●" : "🎤"}
            </Text>
            <Text style={styles.buttonLabel}>
              {recorderState === "recording"
                ? "Release to send"
                : agentState === "speaking"
                ? "Speaking..."
                : "Hold to talk"}
            </Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#000",
  },
  camera: {
    flex: 1,
  },
  permissionContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#000",
    padding: 20,
  },
  permissionText: {
    color: "#fff",
    fontSize: 18,
    textAlign: "center",
    marginBottom: 20,
  },
  permissionButton: {
    backgroundColor: "#007AFF",
    paddingHorizontal: 32,
    paddingVertical: 16,
    borderRadius: 12,
  },
  permissionButtonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  statusBar: {
    position: "absolute",
    top: 60,
    left: 20,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(0,0,0,0.5)",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 8,
  },
  statusText: {
    color: "#fff",
    fontSize: 14,
  },
  responseContainer: {
    position: "absolute",
    bottom: 160,
    left: 20,
    right: 20,
    backgroundColor: "rgba(0,0,0,0.7)",
    padding: 16,
    borderRadius: 12,
  },
  responseText: {
    color: "#fff",
    fontSize: 16,
    textAlign: "center",
  },
  buttonContainer: {
    position: "absolute",
    bottom: 40,
    left: 0,
    right: 0,
    alignItems: "center",
  },
  talkButton: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: "#007AFF",
    justifyContent: "center",
    alignItems: "center",
    elevation: 5,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
  },
  talkButtonPressed: {
    opacity: 0.8,
  },
  recordingButton: {
    backgroundColor: "#FF3B30",
  },
  processingButton: {
    backgroundColor: "#FF9500",
  },
  buttonIcon: {
    fontSize: 32,
  },
  buttonLabel: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "600",
    marginTop: 4,
  },
});
```

**Step 2: Commit**

```bash
git add mobile/src/screens/CameraScreen.tsx
git commit -m "feat: camera screen with push-to-talk voice interaction"
```

---

### Task 8: App Entry Point

**Files:**
- Modify: `mobile/App.tsx`

**Step 1: Update `mobile/App.tsx`**

Replace the contents of `App.tsx` with:

```typescript
import CameraScreen from "./src/screens/CameraScreen";

export default function App() {
  return <CameraScreen />;
}
```

**Step 2: Verify the app compiles**

Run:
```bash
cd mobile && npx expo start
```

Expected: Metro bundler starts without errors. App renders camera screen on a device/emulator.

**Step 3: Commit**

```bash
git add mobile/App.tsx
git commit -m "feat: app entry point wired to camera screen"
```

---

### Task 9: Final Verification

**Step 1: Verify project structure**

```bash
ls mobile/src/screens/ mobile/src/hooks/ mobile/src/services/
```

Expected:
- `screens/CameraScreen.tsx`
- `hooks/useWebSocket.ts`, `useFrameCapture.ts`, `useVoiceRecorder.ts`, `useSpeechAgent.ts`
- `services/api.ts`, `whisper.ts`

**Step 2: Run TypeScript type check**

```bash
cd mobile && npx tsc --noEmit
```

Expected: No type errors.

**Step 3: Start the backend**

From the project root:
```bash
python -m uvicorn src.server:app --host 0.0.0.0 --port 8000
```

**Step 4: Start the Expo app**

```bash
cd mobile && npx expo start
```

**Step 5: Manual test checklist**

1. App opens showing camera preview — ✅
2. Green status dot shows "Connected" when backend is running — ✅
3. Red dot shows "Disconnected" when backend is off — ✅
4. Hold the talk button → recording state (red button) — ✅
5. Release → transcribing → thinking → speaking (TTS plays response) — ✅
6. Backend `data/agent_log.jsonl` shows the interaction logged — ✅

**Step 6: Commit any remaining files**

```bash
git add -A
git commit -m "feat: expo frontend complete with camera streaming and voice interface"
```
