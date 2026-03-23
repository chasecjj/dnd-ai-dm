import { useState, useCallback, useEffect, Suspense, lazy } from "react";
import { useSession } from "./hooks/useSession";
import { useWebSocket } from "./hooks/useWebSocket";
import { useBreathGroups } from "./hooks/useBreathGroups";
import { AdaptiveSpine } from "./layouts/AdaptiveSpine";
import { NarrativeSpine } from "./panels/NarrativeSpine";
import CharacterPanel from "./panels/CharacterPanel";
import { SessionList } from "./components/SessionList";
import { SessionControls } from "./components/SessionControls";

const DiceScene = lazy(() => import("./scenes/DiceScene"));
import { applyPreset, PRESETS } from "./theme/environments";
import type {
  ServerMsg,
  CharacterData,
  SceneData,
  RollRequestMsg,
} from "./api/types";
import "./theme/tokens.css";

export default function App() {
  // ── Session lifecycle ───────────────────────────────────────────
  const {
    phase,
    token,
    session,
    characters,
    sessions,
    error,
    login,
    createSession,
    resumeSession,
    endSession,
  } = useSession();

  // ── Breath-group rendering ──────────────────────────────────────
  const { groups, addNarrative, addPlayerInput, clearGroups } =
    useBreathGroups();

  // ── Local state ─────────────────────────────────────────────────
  const [character, setCharacter] = useState<CharacterData | null>(null);
  const [scene, setScene] = useState<SceneData | null>(null);
  const [chaos, setChaos] = useState(5);
  const [location, setLocation] = useState("Unknown");
  const [isProcessing, setIsProcessing] = useState(false);
  const [rollRequest, setRollRequest] = useState<RollRequestMsg | null>(null);
  const [turnCount, setTurnCount] = useState(0);
  const [passphrase, setPassphrase] = useState("");

  // ── Theme initialization (H5 fix: useEffect, not useState) ─────
  useEffect(() => {
    document.documentElement.setAttribute("data-brand", "quest-mirror");
    applyPreset(PRESETS.tavern);
  }, []);

  // ── WebSocket message handler ──────────────────────────────────
  const handleServerMessage = useCallback(
    (msg: ServerMsg) => {
      switch (msg.type) {
        case "narrative_stream":
          addNarrative(msg);
          if (msg.is_final) {
            setIsProcessing(false);
            setTurnCount((prev) => prev + 1);
          }
          break;

        case "state_update":
          if (msg.character != null) setCharacter(msg.character);
          if (msg.scene != null) setScene(msg.scene);
          break;

        case "environment_change":
          setLocation(msg.location);
          setChaos(msg.chaos);
          break;

        case "chaos_update":
          setChaos(msg.chaos_factor);
          break;

        case "state_sync":
          if (msg.character != null) setCharacter(msg.character);
          if (msg.scene != null) setScene(msg.scene);
          if (msg.chaos != null) setChaos(msg.chaos.chaos_factor);
          if (msg.environment != null) setLocation(msg.environment.location);
          // Replay recent turns
          clearGroups();
          for (const turn of msg.recent_turns) {
            addPlayerInput(turn.player_input);
            addNarrative({
              type: "narrative_stream",
              text: turn.narrative,
              mood: "neutral",
              breath_group: 0,
              is_final: true,
            });
          }
          if (msg.recent_turns.length > 0) {
            setTurnCount(
              msg.recent_turns[msg.recent_turns.length - 1].turn,
            );
          }
          break;

        case "roll_request":
          setRollRequest(msg);
          break;

        case "session_event":
          if (msg.event_type === "start") {
            if (msg.opening_narrative) {
              addNarrative({
                type: "narrative_stream",
                text: msg.opening_narrative,
                mood: "neutral",
                breath_group: 0,
                is_final: true,
              });
            }
            if (msg.character != null) setCharacter(msg.character);
          } else if (msg.event_type === "undo_complete") {
            setIsProcessing(false);
          } else if (msg.event_type === "end") {
            endSession();
          }
          break;

        case "error":
          setIsProcessing(false);
          addNarrative({
            type: "narrative_stream",
            text: `_${msg.message}_`,
            mood: "neutral",
            breath_group: 0,
            is_final: true,
          });
          break;

        case "heartbeat_ack":
          // no-op
          break;
      }
    },
    [addNarrative, addPlayerInput, clearGroups, endSession],
  );

  // ── WebSocket connection ────────────────────────────────────────
  const { status, send } = useWebSocket(
    session?.id ?? null,
    token,
    handleServerMessage,
  );

  // ── Action handlers ─────────────────────────────────────────────
  const handlePlayerInput = useCallback(
    (text: string) => {
      if (text.trim().toLowerCase() === "undo") {
        send({ type: "undo" });
        return;
      }
      addPlayerInput(text);
      setIsProcessing(true);
      send({ type: "player_input", text });
    },
    [addPlayerInput, send],
  );

  const handleUndo = useCallback(() => {
    send({ type: "undo" });
  }, [send]);

  const handleEndSession = useCallback(() => {
    send({ type: "session_end" });
  }, [send]);

  const handleRollResult = useCallback(
    (requestId: string, result: number, natural: number) => {
      send({
        type: "dice_result",
        request_id: requestId,
        result,
        natural,
      });
      setRollRequest(null);
    },
    [send],
  );

  // ── Auth screen ─────────────────────────────────────────────────
  if (phase === "auth") {
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        style={{ background: "var(--qm-bg)" }}
      >
        <div className="w-full max-w-sm space-y-6 p-8">
          <h1
            className="text-center text-3xl tracking-wide"
            style={{
              fontFamily: "var(--qm-font-heading)",
              color: "var(--qm-accent)",
            }}
          >
            Quest Mirror
          </h1>
          <p
            className="text-center text-sm"
            style={{
              fontFamily: "var(--qm-font-ui)",
              color: "var(--qm-text-dim)",
            }}
          >
            Enter the passphrase to begin.
          </p>

          <div className="space-y-3">
            <input
              type="password"
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && passphrase.trim()) {
                  void login(passphrase.trim());
                }
              }}
              placeholder="Passphrase"
              className="w-full rounded-lg border px-4 py-2.5 text-sm outline-none transition-colors duration-150 focus:brightness-125"
              style={{
                background: "var(--qm-surface)",
                borderColor: "var(--qm-border)",
                color: "var(--qm-text)",
                fontFamily: "var(--qm-font-ui)",
              }}
            />
            <button
              onClick={() => void login(passphrase.trim())}
              disabled={!passphrase.trim()}
              className="w-full rounded-lg px-4 py-2.5 text-sm font-medium transition-colors duration-150 hover:brightness-125 disabled:cursor-not-allowed disabled:opacity-40"
              style={{
                background: "var(--qm-accent)",
                color: "var(--qm-bg)",
                fontFamily: "var(--qm-font-ui)",
              }}
            >
              Enter
            </button>
          </div>

          {error && (
            <div
              className="rounded border px-4 py-2 text-center text-sm"
              style={{
                borderColor: "#c44",
                color: "#f88",
                background: "rgba(200, 50, 50, 0.12)",
                fontFamily: "var(--qm-font-ui)",
              }}
            >
              {error}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Lobby screen ────────────────────────────────────────────────
  if (phase === "lobby") {
    return (
      <SessionList
        sessions={sessions}
        characters={characters}
        onResume={resumeSession}
        onCreate={(name) => void createSession(name)}
        error={error}
      />
    );
  }

  // ── Playing screen ──────────────────────────────────────────────
  const characterName = session?.character_name ?? "Adventurer";

  return (
    <div className="flex h-screen flex-col">
      {/* Connection status bar */}
      {status !== "connected" && (
        <div
          className="flex items-center justify-center px-4 py-1.5 text-xs"
          style={{
            background:
              status === "connecting"
                ? "rgba(200, 150, 50, 0.15)"
                : "rgba(200, 50, 50, 0.15)",
            color:
              status === "connecting" ? "#f0c040" : "#f88",
            fontFamily: "var(--qm-font-ui)",
            borderBottom: "1px solid var(--qm-border)",
          }}
        >
          {status === "connecting" && "Connecting..."}
          {status === "disconnected" && "Disconnected. Attempting to reconnect..."}
          {status === "connection_lost" && "Connection lost. Attempting to reconnect..."}
          {status === "session_expired" && "Session expired. Please refresh."}
          {status === "idle" && "Initializing..."}
        </div>
      )}

      {/* Main content area */}
      <div className="flex-1 overflow-hidden">
        <AdaptiveSpine
          narrative={
            <div className="relative h-full">
              <NarrativeSpine
                groups={groups}
                location={location}
                characterName={characterName}
                processing={isProcessing}
                onPlayerInput={handlePlayerInput}
                turnCount={turnCount}
              />
              {/* 3D Dice scene (lazy-loaded) */}
              {rollRequest && (
                <div className="absolute inset-x-0 bottom-4 flex justify-center px-4" style={{ zIndex: 50 }}>
                  <div className="w-full max-w-lg">
                    <Suspense fallback={
                      <div style={{
                        height: "280px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        background: "var(--qm-surface)",
                        borderRadius: "0.5rem",
                        fontFamily: "var(--qm-font-narrative)",
                        fontStyle: "italic",
                        color: "var(--qm-text-dim)",
                      }}>
                        Summoning the bones...
                      </div>
                    }>
                      <DiceScene
                        formula={rollRequest.formula}
                        rollType={rollRequest.roll_type}
                        prompt={rollRequest.prompt}
                        requestId={rollRequest.request_id}
                        autoTimeoutS={rollRequest.auto_timeout_s}
                        onResult={handleRollResult}
                      />
                    </Suspense>
                  </div>
                </div>
              )}
            </div>
          }
          contextRail={
            <CharacterPanel
              character={character}
              scene={scene}
              chaosLevel={chaos}
            />
          }
        />
      </div>

      {/* Session controls footer */}
      <SessionControls
        turnCount={turnCount}
        onUndo={handleUndo}
        onEndSession={handleEndSession}
      />
    </div>
  );
}
