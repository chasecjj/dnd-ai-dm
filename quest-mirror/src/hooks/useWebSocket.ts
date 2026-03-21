import { useRef, useEffect, useState, useCallback } from "react";
import { QuestMirrorWS } from "../api/ws";
import type { ServerMsg, ClientMsg } from "../api/types";

type WsStatus =
  | "connecting"
  | "connected"
  | "disconnected"
  | "idle"
  | "session_expired"
  | "connection_lost";

export function useWebSocket(
  sessionId: string | null,
  token: string | null,
  onMessage: (msg: ServerMsg) => void,
): { status: WsStatus; send: (msg: ClientMsg) => void } {
  const [status, setStatus] = useState<WsStatus>("idle");
  const wsRef = useRef<QuestMirrorWS | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!sessionId || !token) {
      setStatus("idle");
      return;
    }

    const ws = new QuestMirrorWS({
      sessionId,
      token,
      onMessage: (msg) => onMessageRef.current(msg),
      onStatus: setStatus,
    });

    ws.connect();
    wsRef.current = ws;

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [sessionId, token]);

  const send = useCallback((msg: ClientMsg) => {
    wsRef.current?.send(msg);
  }, []);

  return { status, send };
}
