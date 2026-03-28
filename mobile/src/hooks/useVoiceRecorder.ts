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
