import type { ClientMsg, ServerMsg } from "./types";

type MessageHandler = (msg: ServerMsg) => void;
type StatusHandler = (
  status:
    | "connecting"
    | "connected"
    | "disconnected"
    | "session_expired"
    | "connection_lost",
) => void;

interface QuestMirrorWSOptions {
  sessionId: string;
  token: string;
  onMessage: MessageHandler;
  onStatus: StatusHandler;
}

const HEARTBEAT_INTERVAL = 15_000;
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000];
const MAX_RECONNECT_ATTEMPTS = 10;

export class QuestMirrorWS {
  private ws: WebSocket | null = null;
  private readonly sessionId: string;
  private readonly token: string;
  private readonly onMessage: MessageHandler;
  private readonly onStatus: StatusHandler;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectAttempt = 0;
  private intentionallyClosed = false;

  constructor(opts: QuestMirrorWSOptions) {
    this.sessionId = opts.sessionId;
    this.token = opts.token;
    this.onMessage = opts.onMessage;
    this.onStatus = opts.onStatus;
  }

  connect(): void {
    this.onStatus("connecting");
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${location.host}/ws/solo/${this.sessionId}?token=${this.token}`;
    const ws = new WebSocket(url);

    ws.onopen = () => {
      this.reconnectAttempt = 0;
      this.onStatus("connected");
      this.startHeartbeat();
    };

    ws.onmessage = (event: MessageEvent) => {
      const msg = JSON.parse(event.data as string) as ServerMsg;
      this.onMessage(msg);
    };

    ws.onclose = (event: CloseEvent) => {
      this.stopHeartbeat();

      // Close codes 4001 (invalid token) and 4004 (session not found)
      // indicate the session is expired / invalid -- do not reconnect.
      if (event.code === 4001 || event.code === 4004) {
        this.onStatus("session_expired");
        return;
      }

      this.onStatus("disconnected");

      if (!this.intentionallyClosed) {
        this.scheduleReconnect();
      }
    };

    ws.onerror = (event: Event) => {
      console.error("[QuestMirrorWS] WebSocket error:", event);
    };

    this.ws = ws;
  }

  send(msg: ClientMsg): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  close(): void {
    this.intentionallyClosed = true;
    this.stopHeartbeat();
    this.ws?.close();
    this.ws = null;
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: "heartbeat" } as ClientMsg);
    }, HEARTBEAT_INTERVAL);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempt >= MAX_RECONNECT_ATTEMPTS) {
      this.onStatus("connection_lost");
      return;
    }

    const delayIndex = Math.min(
      this.reconnectAttempt,
      RECONNECT_DELAYS.length - 1,
    );
    const delay = RECONNECT_DELAYS[delayIndex]!;
    this.reconnectAttempt++;

    setTimeout(() => {
      if (!this.intentionallyClosed) {
        this.connect();
      }
    }, delay);
  }
}
