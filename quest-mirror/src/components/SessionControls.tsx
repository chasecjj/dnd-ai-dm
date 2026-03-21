interface SessionControlsProps {
  turnCount: number;
  onUndo: () => void;
  onEndSession: () => void;
}

/** Footer bar with turn counter, undo, and end-session controls. */
export function SessionControls({
  turnCount,
  onUndo,
  onEndSession,
}: SessionControlsProps) {
  return (
    <footer
      className="flex items-center justify-between border-t px-5 py-2"
      style={{
        background: "var(--qm-surface)",
        borderColor: "var(--qm-border)",
        fontFamily: "var(--qm-font-ui)",
      }}
    >
      {/* Turn counter */}
      <span className="text-xs" style={{ color: "var(--qm-text-dim)" }}>
        Turn {turnCount}
      </span>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={onUndo}
          className="rounded border px-3 py-1 text-xs transition-colors duration-150 hover:brightness-125"
          style={{
            borderColor: "var(--qm-border)",
            color: "var(--qm-text-dim)",
            background: "transparent",
          }}
        >
          Undo
        </button>
        <button
          onClick={onEndSession}
          className="rounded border px-3 py-1 text-xs transition-colors duration-150 hover:brightness-125"
          style={{
            borderColor: "rgba(200, 60, 60, 0.4)",
            color: "#e87070",
            background: "rgba(200, 50, 50, 0.1)",
          }}
        >
          End Session
        </button>
      </div>
    </footer>
  );
}
