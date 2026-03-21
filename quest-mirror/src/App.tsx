import { useEffect } from "react";
import { AdaptiveSpine } from "./layouts/AdaptiveSpine";
import { applyPreset, PRESETS } from "./theme/environments";
import "./theme/tokens.css";

export default function App() {
  useEffect(() => {
    document.documentElement.setAttribute("data-brand", "quest-mirror");
    applyPreset(PRESETS.tavern);
  }, []);

  return (
    <AdaptiveSpine
      narrative={
        <div className="p-8" style={{ fontFamily: "var(--qm-font-narrative)", color: "var(--qm-text)" }}>
          <h1 style={{ fontFamily: "var(--qm-font-heading)", color: "var(--qm-accent)", fontSize: "1.5rem", marginBottom: "1.5rem" }}>
            Quest Mirror
          </h1>
          <p className="text-lg leading-relaxed" style={{ maxWidth: "680px" }}>
            The portal awaits. Select a character to begin your journey.
          </p>
        </div>
      }
      contextRail={
        <div className="p-6 text-sm" style={{ fontFamily: "var(--qm-font-ui)", color: "var(--qm-text-dim)" }}>
          <h2 style={{ color: "var(--qm-accent)", fontWeight: 600, marginBottom: "1rem" }}>
            Character
          </h2>
          <p>No active session.</p>
        </div>
      }
    />
  );
}
