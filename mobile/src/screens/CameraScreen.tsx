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
