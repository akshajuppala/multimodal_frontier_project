import React, { useEffect, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
} from "react-native";
import {
  Camera,
  useCameraDevice,
  useCameraPermission,
} from "react-native-vision-camera";
import { File as ExpoFile } from "expo-file-system";
import { useWebSocket } from "../hooks/useWebSocket";
import { useFrameCapture } from "../hooks/useFrameCapture";
import { useVoiceRecorder } from "../hooks/useVoiceRecorder";
import { useSpeechAgent } from "../hooks/useSpeechAgent";

const FRAME_SAMPLE_RATE = Number(process.env.EXPO_PUBLIC_FRAME_SAMPLE_RATE) || 2;
const INTERVAL_MS = 1000 / FRAME_SAMPLE_RATE;

export default function CameraScreen() {
  const cameraRef = useRef<Camera>(null);
  const { hasPermission, requestPermission } = useCameraPermission();
  const device = useCameraDevice("back");
  const { status: wsStatus, sendFrame } = useWebSocket();

  const enabled = wsStatus === "connected";
  const onFrame = useFrameCapture(sendFrame, enabled);

  // Snapshot-based capture loop running off the JS thread's timer.
  // takePhoto() on vision-camera does NOT freeze the preview.
  const activeRef = useRef(false);
  useEffect(() => {
    if (!enabled || !device) {
      activeRef.current = false;
      return;
    }
    activeRef.current = true;

    async function loop() {
      while (activeRef.current) {
        if (cameraRef.current) {
          try {
            const photo = await cameraRef.current.takePhoto({
              flash: "off",
              enableShutterSound: false,
            });
            if (activeRef.current && photo.path) {
              const uri = photo.path.startsWith("file://")
                ? photo.path
                : `file://${photo.path}`;
              const file = new ExpoFile(uri);
              const buffer = await file.arrayBuffer();
              const bytes = new Uint8Array(buffer);
              const chunks: string[] = [];
              for (let i = 0; i < bytes.length; i += 8192) {
                chunks.push(String.fromCharCode(...bytes.subarray(i, i + 8192)));
              }
              onFrame(btoa(chunks.join("")));
            }
          } catch (e) {
            console.error("Frame capture error:", e);
          }
        }
        if (activeRef.current) {
          await new Promise((r) => setTimeout(r, INTERVAL_MS));
        }
      }
    }

    loop();
    return () => {
      activeRef.current = false;
    };
  }, [enabled, device, onFrame]);

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
  if (!hasPermission) {
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

  if (!device) {
    return (
      <View style={styles.container}>
        <Text style={styles.statusText}>No camera device found</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Camera
        ref={cameraRef}
        style={styles.camera}
        device={device}
        isActive={true}
        photo={true}
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
