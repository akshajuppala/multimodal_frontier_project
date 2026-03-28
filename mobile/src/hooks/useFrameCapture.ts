import { useRef, useCallback } from "react";

const FRAME_SAMPLE_RATE = Number(process.env.EXPO_PUBLIC_FRAME_SAMPLE_RATE) || 2;
const INTERVAL_MS = 1000 / FRAME_SAMPLE_RATE;

/**
 * Returns a frame processor callback for react-native-vision-camera.
 * Throttles frame capture to FRAME_SAMPLE_RATE fps and sends base64 JPEG
 * via the provided sendFrame callback.
 */
export function useFrameCapture(
  sendFrame: (base64Jpeg: string) => void,
  enabled: boolean
) {
  const lastCaptureRef = useRef(0);

  const onFrame = useCallback(
    (base64Jpeg: string) => {
      if (!enabled) return;
      const now = Date.now();
      if (now - lastCaptureRef.current < INTERVAL_MS) return;
      lastCaptureRef.current = now;
      sendFrame(base64Jpeg);
    },
    [enabled, sendFrame]
  );

  return onFrame;
}
