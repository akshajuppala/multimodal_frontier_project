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
