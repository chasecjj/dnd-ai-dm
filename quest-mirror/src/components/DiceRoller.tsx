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

/** Format a formula string with spaces around the operator for display. */
function formatFormula(formula: string): string {
  return formula.replace(/([+-])/, " $1 ");
}

/**
 * Parchment-manuscript dice roller bar.
 *
 * Appears as a horizontal strip above the input area when a RollRequestMsg
 * is active; hidden otherwise. Thematic language: "The fates demand a roll",
 * "Cast the Bones".
 *
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

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.75rem",
        padding: "0.625rem 1rem",
        background: "var(--qm-surface)",
        border: "1px solid var(--qm-border-subtle)",
        borderRadius: "0.5rem",
        fontFamily: "var(--qm-font-ui)",
      }}
    >
      {/* Left: narrative prompt */}
      <span
        style={{
          fontFamily: "var(--qm-font-narrative)",
          fontStyle: "italic",
          fontSize: "0.875rem",
          color: "var(--qm-text-warm)",
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}
      >
        The fates demand a roll:
      </span>

      {/* Center: formula pill */}
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          padding: "0.2rem 0.75rem",
          background: "var(--qm-dice-bg)",
          color: "var(--qm-dice-text)",
          borderRadius: "9999px",
          fontSize: "0.8125rem",
          fontWeight: 600,
          letterSpacing: "0.03em",
          flexShrink: 0,
        }}
      >
        {formatFormula(rollRequest.formula)}
      </span>

      {/* Spacer */}
      <span style={{ flex: 1 }} />

      {/* Result display or action button */}
      {result !== null ? (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
            fontFamily: "var(--qm-font-heading, var(--qm-font-ui))",
            fontSize: "1.25rem",
            fontWeight: 700,
            color: isNat20
              ? "#b8860b"
              : isNat1
                ? "#8b1a1a"
                : "var(--qm-text-warm)",
            textShadow: isNat20
              ? "0 0 8px rgba(218,165,32,0.4)"
              : isNat1
                ? "0 0 8px rgba(139,26,26,0.3)"
                : "none",
          }}
        >
          {result.total}
          {/* Natural roll breakdown when modifier is present */}
          {result.total !== result.natural && (
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 400,
                color: "var(--qm-text-dim)",
                textShadow: "none",
              }}
            >
              (nat {result.natural})
            </span>
          )}
        </span>
      ) : (
        <>
          {/* Cast the Bones button */}
          <button
            onClick={performRoll}
            disabled={rolling}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.375rem",
              padding: "0.375rem 1rem",
              background: "var(--qm-accent)",
              color: "#f5f0e8",
              border: "none",
              borderRadius: "0.375rem",
              fontSize: "0.8125rem",
              fontWeight: 600,
              fontFamily: "var(--qm-font-ui)",
              cursor: rolling ? "not-allowed" : "pointer",
              opacity: rolling ? 0.7 : 1,
              transition: "opacity 150ms, background 150ms",
              flexShrink: 0,
            }}
            onMouseEnter={(e) => {
              if (!rolling) {
                (e.currentTarget as HTMLButtonElement).style.background =
                  "var(--qm-accent-hover)";
              }
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background =
                "var(--qm-accent)";
            }}
          >
            {rolling ? (
              <>
                <span
                  style={{
                    display: "inline-block",
                    width: "0.875rem",
                    height: "0.875rem",
                    border: "2px solid rgba(245,240,232,0.3)",
                    borderTopColor: "#f5f0e8",
                    borderRadius: "50%",
                    animation: "qm-bones-spin 0.6s linear infinite",
                  }}
                />
                Casting...
              </>
            ) : (
              "Cast the Bones"
            )}
          </button>

          {/* Far right: auto countdown */}
          {countdown !== null && countdown > 0 && !rolling && (
            <span
              style={{
                fontSize: "0.75rem",
                color: "var(--qm-text-dim)",
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
            >
              auto in {countdown}s
            </span>
          )}
        </>
      )}

      {/* CSS keyframes injected once */}
      <style>{`
        @keyframes qm-bones-spin {
          0%   { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
