import { useState, useEffect, useRef, useCallback } from "react";
import type { RollRequestMsg } from "../api/types.ts";

interface Props {
  rollRequest: RollRequestMsg | null;
  onRollResult: (requestId: string, result: number, natural: number) => void;
}

/** Parse a dice formula like "1d20+5" into { count, dieSize, modifier }. */
function parseFormula(formula: string) {
  const dieMatch = formula.match(/(\d*)d(\d+)/);
  const modMatch = formula.match(/[+-]\d+/);
  return {
    count: dieMatch ? parseInt(dieMatch[1] || "1", 10) : 1,
    dieSize: dieMatch ? parseInt(dieMatch[2], 10) : 20,
    modifier: modMatch ? parseInt(modMatch[0], 10) : 0,
  };
}

/**
 * Click-to-roll dice component with auto-timeout and nat 20/1 color treatment.
 *
 * Appears as a glass panel when a RollRequestMsg is active; hidden otherwise.
 * Uses a ref-based stale-closure fix (H9) so the auto-roll timeout always
 * reads the latest rollRequest.
 */
export function DiceRoller({ rollRequest, onRollResult }: Props) {
  const [rolling, setRolling] = useState(false);
  const [result, setResult] = useState<{
    total: number;
    natural: number;
  } | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);

  // ── H9 stale-closure fix ──────────────────────────────────────
  const rollRequestRef = useRef(rollRequest);
  rollRequestRef.current = rollRequest;

  const rollingRef = useRef(rolling);
  rollingRef.current = rolling;

  const onRollResultRef = useRef(onRollResult);
  onRollResultRef.current = onRollResult;

  // ── Roll logic ────────────────────────────────────────────────
  const performRoll = useCallback(() => {
    const req = rollRequestRef.current;
    if (!req || rollingRef.current) return;

    setRolling(true);
    const { count, dieSize, modifier } = parseFormula(req.formula);

    // Simulate roll after 800ms spin animation
    setTimeout(() => {
      let natural = 0;
      for (let i = 0; i < count; i++) {
        natural += Math.floor(Math.random() * dieSize) + 1;
      }
      const total = natural + modifier;

      setResult({ total, natural });
      setRolling(false);
      onRollResultRef.current(req.request_id, total, natural);
    }, 800);
  }, []);

  // ── Reset state when rollRequest changes ──────────────────────
  useEffect(() => {
    setResult(null);
    setRolling(false);

    if (rollRequest) {
      setCountdown(rollRequest.auto_timeout_s);
    } else {
      setCountdown(null);
    }
  }, [rollRequest]);

  // ── Auto-roll countdown timer ─────────────────────────────────
  useEffect(() => {
    if (countdown === null || countdown <= 0) return;

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev === null) return null;
        const next = prev - 1;
        if (next <= 0) {
          performRoll();
          return 0;
        }
        return next;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [countdown, performRoll]);

  // ── Render ────────────────────────────────────────────────────
  if (!rollRequest) return null;

  const { dieSize } = parseFormula(rollRequest.formula);
  const isNat20 = result !== null && dieSize === 20 && result.natural === 20;
  const isNat1 = result !== null && dieSize === 20 && result.natural === 1;

  const resultBorder = isNat20
    ? "2px solid rgba(255, 200, 50, 0.8)"
    : isNat1
      ? "2px solid rgba(220, 50, 50, 0.8)"
      : "2px solid var(--qm-border)";

  const resultBg = isNat20
    ? "rgba(255, 200, 50, 0.15)"
    : isNat1
      ? "rgba(220, 50, 50, 0.15)"
      : "transparent";

  return (
    <div
      className="flex flex-col items-center gap-3 rounded-lg border p-5"
      style={{
        background: "var(--qm-surface-glass)",
        backdropFilter: "blur(var(--qm-blur))",
        WebkitBackdropFilter: "blur(var(--qm-blur))",
        borderColor: "var(--qm-border)",
        fontFamily: "var(--qm-font-ui)",
      }}
    >
      {/* DM prompt */}
      <p
        className="text-center text-sm leading-relaxed italic"
        style={{
          fontFamily: "var(--qm-font-narrative)",
          color: "var(--qm-text-warm)",
        }}
      >
        {rollRequest.prompt}
      </p>

      {/* Roll info: type + formula */}
      <span
        className="text-xs font-semibold tracking-widest uppercase"
        style={{ color: "var(--qm-text-dim)" }}
      >
        {rollRequest.roll_type.toUpperCase()} &mdash; {rollRequest.formula}
      </span>

      {/* Die button or result display */}
      {result === null ? (
        <button
          onClick={performRoll}
          disabled={rolling}
          className="flex items-center justify-center transition-transform duration-150 hover:scale-110 disabled:cursor-not-allowed"
          style={{
            width: 72,
            height: 72,
            border: "2px solid var(--qm-accent)",
            borderRadius: 8,
            background: "var(--qm-surface)",
            color: "var(--qm-accent)",
            fontFamily: "var(--qm-font-heading)",
            fontSize: "1.5rem",
            fontWeight: 700,
            animation: rolling ? "qm-dice-spin 0.4s linear infinite" : "none",
          }}
        >
          d{dieSize}
        </button>
      ) : (
        <div
          className="flex items-center justify-center rounded-lg"
          style={{
            width: 80,
            height: 80,
            border: resultBorder,
            background: resultBg,
            fontFamily: "var(--qm-font-heading)",
            fontSize: "2.25rem",
            fontWeight: 700,
            color: isNat20
              ? "#ffd666"
              : isNat1
                ? "#ff6b6b"
                : "var(--qm-text)",
          }}
        >
          {result.total}
        </div>
      )}

      {/* Auto-roll countdown */}
      {result === null && countdown !== null && countdown > 0 && !rolling && (
        <span className="text-xs" style={{ color: "var(--qm-text-dim)" }}>
          Auto-roll in {countdown}s
        </span>
      )}

      {/* Natural roll breakdown when modifier is present */}
      {result !== null && result.total !== result.natural && (
        <span className="text-xs" style={{ color: "var(--qm-text-dim)" }}>
          Natural {result.natural}
        </span>
      )}

      {/* CSS keyframes injected once */}
      <style>{`
        @keyframes qm-dice-spin {
          0%   { transform: rotate(0deg) scale(1); }
          25%  { transform: rotate(90deg) scale(1.05); }
          50%  { transform: rotate(180deg) scale(1); }
          75%  { transform: rotate(270deg) scale(1.05); }
          100% { transform: rotate(360deg) scale(1); }
        }
      `}</style>
    </div>
  );
}
