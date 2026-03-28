import { useEffect, useRef, useState, useCallback } from "react";

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || "http://10.64.19.19:8000";

type ConnectionStatus = "connecting" | "connected" | "disconnected";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    const wsUrl = BACKEND_URL.replace(/^http/, "ws") + "/video/stream";
    setStatus("connecting");

    const ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      setStatus("connected");
    };

    ws.onclose = (event) => {
      setStatus("disconnected");
      wsRef.current = null;
      console.error(`WebSocket Closed. Code: ${event.code}, Reason: ${event.reason}`);
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
      if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const sendFrame = useCallback((base64Jpeg: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      // Convert base64 to binary and send
      wsRef.current.send(base64Jpeg);
    }
  }, []);

  return { status, sendFrame };
}
