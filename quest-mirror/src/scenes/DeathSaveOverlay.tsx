// quest-mirror/src/scenes/DeathSaveOverlay.tsx
import { useState, useEffect } from "react"

interface DeathSaveOverlayProps {
  active: boolean
  onRoll: () => void
  result: number | null
  onComplete: (outcome: "stabilized" | "dead") => void
}

interface DeathSaveState {
  successes: number
  failures: number
  outcome: "stabilized" | "dead" | null
}

export function DeathSaveOverlay({ active, onRoll, result, onComplete }: DeathSaveOverlayProps) {
  const [state, setState] = useState<DeathSaveState>({
    successes: 0, failures: 0, outcome: null,
  })
  const [showRollPrompt, setShowRollPrompt] = useState(true)
  const [heartbeatBpm, setHeartbeatBpm] = useState(40)

  useEffect(() => {
    if (active) {
      setState({ successes: 0, failures: 0, outcome: null })
      setShowRollPrompt(true)
      setHeartbeatBpm(40)
    }
  }, [active])

  // Process roll result
  useEffect(() => {
    if (result === null || !active) return

    setState(prev => {
      let { successes, failures } = prev
      if (result === 20) {
        return { successes: 3, failures, outcome: "stabilized" }
      } else if (result === 1) {
        failures = Math.min(3, failures + 2)
      } else if (result >= 10) {
        successes = Math.min(3, successes + 1)
      } else {
        failures = Math.min(3, failures + 1)
      }
      const outcome = successes >= 3 ? "stabilized" : failures >= 3 ? "dead" : null
      return { successes, failures, outcome }
    })

    setShowRollPrompt(false)
    setTimeout(() => setShowRollPrompt(true), 1500)
  }, [result, active])

  // Update heartbeat
  useEffect(() => {
    const { successes, failures, outcome } = state
    if (outcome === "stabilized") setHeartbeatBpm(72)
    else if (outcome === "dead") setHeartbeatBpm(0)
    else if (failures >= 2) setHeartbeatBpm(25)
    else if (successes >= 2) setHeartbeatBpm(55)
    else setHeartbeatBpm(40)
  }, [state])

  // Report outcome after delay
  useEffect(() => {
    if (state.outcome) {
      const delay = state.outcome === "dead" ? 4000 : 2000
      const timer = setTimeout(() => onComplete(state.outcome!), delay)
      return () => clearTimeout(timer)
    }
  }, [state.outcome, onComplete])

  if (!active) return null

  const { successes, failures, outcome } = state

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 200,
      background: "rgba(10, 8, 6, 0.92)",
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: "2rem",
      animation: "qm-death-enter 1.5s ease-out",
    }}>
      {/* Breathe prompt */}
      {outcome === null && (
        <div style={{
          fontFamily: "var(--qm-font-heading, 'Cormorant Garamond')",
          fontSize: "1.5rem", fontStyle: "italic",
          color: "#6a5a4a", letterSpacing: "0.1em",
          animation: "qm-breathe 4s ease-in-out infinite",
        }}>Breathe.</div>
      )}

      {outcome === "stabilized" && (
        <div style={{
          fontFamily: "var(--qm-font-heading)", fontSize: "2rem",
          color: "#daa520", textShadow: "0 0 30px rgba(218,165,32,0.5)",
          animation: "qm-gold-reveal 1s ease-out",
        }}>Not today.</div>
      )}
      {outcome === "dead" && (
        <div style={{
          fontFamily: "var(--qm-font-heading)", fontSize: "1.5rem",
          color: "#4a3a2a", fontStyle: "italic",
        }}>The light fades...</div>
      )}

      {/* Candles */}
      <div style={{ display: "flex", gap: "2rem" }}>
        {/* Success candles */}
        {[0, 1, 2].map(i => {
          const isLit = i < successes
          return (
            <div key={`s${i}`} style={{ textAlign: "center" }}>
              <div style={{
                width: "24px", height: "60px",
                background: isLit
                  ? "linear-gradient(to top, #daa520, #fff8dc)"
                  : "linear-gradient(to top, #3a3020, #2a2018)",
                borderRadius: "2px 2px 0 0", margin: "0 auto 0.5rem",
                boxShadow: isLit ? "0 0 20px rgba(218,165,32,0.5)" : "none",
                transition: "all 0.5s ease",
              }}>
                {isLit && (
                  <div style={{
                    width: "8px", height: "16px",
                    background: "radial-gradient(ellipse, #fff 0%, #ffa500 50%, transparent 100%)",
                    borderRadius: "50% 50% 20% 20%", margin: "-12px auto 0",
                    animation: "qm-flame-flicker 0.8s ease-in-out infinite alternate",
                  }} />
                )}
              </div>
              <div style={{ fontSize: "0.625rem", color: "#4a3a2a", letterSpacing: "0.05em" }}>
                {isLit ? "SAVED" : ""}
              </div>
            </div>
          )
        })}

        <div style={{ width: "2rem" }} />

        {/* Failure markers */}
        {[0, 1, 2].map(i => {
          const isLost = i < failures
          return (
            <div key={`f${i}`} style={{ textAlign: "center" }}>
              <div style={{
                width: "24px", height: "60px",
                background: isLost
                  ? "linear-gradient(to top, #4a1a1a, #2a0a0a)"
                  : "linear-gradient(to top, #3a3020, #2a2018)",
                borderRadius: "2px 2px 0 0", margin: "0 auto 0.5rem",
                boxShadow: isLost ? "0 0 20px rgba(80,20,20,0.5)" : "none",
                transition: "all 0.5s ease",
              }}>
                {isLost && (
                  <div style={{
                    width: "8px", height: "12px",
                    background: "linear-gradient(to top, #333, transparent)",
                    margin: "-8px auto 0",
                    animation: "qm-smoke-rise 1.5s ease-out infinite",
                  }} />
                )}
              </div>
              <div style={{ fontSize: "0.625rem", color: "#4a1a1a", letterSpacing: "0.05em" }}>
                {isLost ? "LOST" : ""}
              </div>
            </div>
          )
        })}
      </div>

      {/* Heartbeat */}
      {heartbeatBpm > 0 && (
        <div style={{
          width: "6px", height: "6px", borderRadius: "50%",
          background: heartbeatBpm > 50 ? "#daa520" : "#6a3a2a",
          animation: `qm-heartbeat ${60 / heartbeatBpm}s ease-in-out infinite`,
        }} />
      )}

      {/* Roll prompt */}
      {outcome === null && showRollPrompt && (
        <button onClick={onRoll} style={{
          padding: "0.75rem 2rem", background: "transparent",
          border: "1px solid #4a3a2a", borderRadius: "0.375rem",
          color: "#6a5a4a", fontFamily: "var(--qm-font-narrative)",
          fontStyle: "italic", fontSize: "1rem", cursor: "pointer",
          transition: "border-color 300ms, color 300ms",
        }}
        onMouseEnter={e => { e.currentTarget.style.borderColor = "#8a7a6a"; e.currentTarget.style.color = "#8a7a6a" }}
        onMouseLeave={e => { e.currentTarget.style.borderColor = "#4a3a2a"; e.currentTarget.style.color = "#6a5a4a" }}
        >Roll the bones...</button>
      )}

      <style>{`
        @keyframes qm-death-enter { 0% { opacity: 0; } 100% { opacity: 1; } }
        @keyframes qm-breathe { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.8; } }
        @keyframes qm-flame-flicker { 0% { transform: scaleY(1) scaleX(1); opacity: 0.9; } 100% { transform: scaleY(1.2) scaleX(0.85); opacity: 1; } }
        @keyframes qm-smoke-rise { 0% { opacity: 0.6; transform: translateY(0); } 100% { opacity: 0; transform: translateY(-20px); } }
        @keyframes qm-heartbeat { 0%, 100% { transform: scale(1); opacity: 0.5; } 15% { transform: scale(1.8); opacity: 1; } 30% { transform: scale(1); opacity: 0.5; } 45% { transform: scale(1.4); opacity: 0.8; } }
        @keyframes qm-gold-reveal { 0% { opacity: 0; transform: scale(0.8); } 100% { opacity: 1; transform: scale(1); } }
      `}</style>
    </div>
  )
}
