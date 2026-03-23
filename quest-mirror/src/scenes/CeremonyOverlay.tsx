import { useEffect, useState } from "react"
import type { CeremonyType } from "../dice/types.ts"

interface CeremonyOverlayProps {
  type: CeremonyType
  visual: string | undefined
}

export function CeremonyOverlay({ type, visual }: CeremonyOverlayProps) {
  const [opacity, setOpacity] = useState(0)

  useEffect(() => {
    requestAnimationFrame(() => setOpacity(1))
  }, [])

  if (type === "none" || type === "death_save") return null

  const isNat20 = type === "nat20"

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        zIndex: 100,
        transition: "opacity 300ms ease",
        opacity,
      }}
    >
      {/* Nat 20: Golden cracks */}
      {isNat20 && visual === "golden_cracks" && (
        <div style={{
          position: "absolute",
          inset: 0,
          background: "radial-gradient(circle at center, rgba(218,165,32,0.3) 0%, transparent 60%)",
          animation: "qm-crack-expand 0.8s ease-out forwards",
        }} />
      )}

      {/* Nat 20: Die radiance */}
      {isNat20 && (visual === "die_radiance" || visual === "golden_embers") && (
        <div style={{
          position: "absolute",
          inset: 0,
          background: "radial-gradient(circle at center, rgba(255,215,0,0.4) 0%, transparent 50%)",
          animation: "qm-radiance-pulse 1.5s ease-in-out",
        }} />
      )}

      {/* Nat 20: Fade to warmth */}
      {isNat20 && visual === "fade_to_warmth" && (
        <div style={{
          position: "absolute",
          inset: 0,
          boxShadow: "inset 0 0 80px rgba(218,165,32,0.15)",
        }} />
      )}

      {/* Nat 1: Screen drop */}
      {!isNat20 && visual === "screen_drop" && (
        <div style={{
          position: "absolute",
          inset: 0,
          background: "rgba(0,0,0,0.1)",
          animation: "qm-screen-drop 200ms cubic-bezier(0.55, 0, 1, 0.45) forwards",
        }} />
      )}

      {/* Nat 1: Crimson glow */}
      {!isNat20 && (visual === "die_crimson" || visual === "failure_flash") && (
        <div style={{
          position: "absolute",
          inset: 0,
          background: "radial-gradient(circle at center, rgba(139,26,26,0.35) 0%, transparent 60%)",
          animation: "qm-crimson-pulse 1s ease-in-out",
        }} />
      )}

      {/* Nat 1: Warmth returns */}
      {!isNat20 && visual === "warmth_returns" && (
        <div style={{
          position: "absolute",
          inset: 0,
          opacity: 0,
          transition: "opacity 500ms ease",
        }} />
      )}

      <style>{`
        @keyframes qm-crack-expand {
          0% { transform: scale(0.3); opacity: 0; }
          50% { opacity: 1; }
          100% { transform: scale(2); opacity: 0.8; }
        }
        @keyframes qm-radiance-pulse {
          0% { opacity: 0.5; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1.2); }
          100% { opacity: 0; transform: scale(1.5); }
        }
        @keyframes qm-crimson-pulse {
          0% { opacity: 0; }
          30% { opacity: 1; }
          100% { opacity: 0.3; }
        }
        @keyframes qm-screen-drop {
          0% { transform: translateY(0); }
          100% { transform: translateY(20px); }
        }
      `}</style>
    </div>
  )
}
