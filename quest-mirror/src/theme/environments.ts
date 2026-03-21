export interface EnvironmentPreset {
  name: string;
  bg: string;
  surface: string;
  text: string;
  textDim: string;
  accent: string;
  glowColor: string;
  ambientOrigin: string;
}

export const PRESETS: Record<string, EnvironmentPreset> = {
  tavern: {
    name: "Tavern",
    bg: "#0a0908",
    surface: "rgba(20, 18, 15, 0.85)",
    text: "#e8e0d4",
    textDim: "#9a9080",
    accent: "#d4a855",
    glowColor: "rgba(212, 168, 85, 0.08)",
    ambientOrigin: "center bottom",
  },
};

export function applyPreset(preset: EnvironmentPreset, timeOfDay?: string) {
  const root = document.documentElement;
  root.style.setProperty("--qm-bg", preset.bg);
  root.style.setProperty("--qm-surface", preset.surface);
  root.style.setProperty("--qm-text", preset.text);
  root.style.setProperty("--qm-text-dim", preset.textDim);
  root.style.setProperty("--qm-accent", preset.accent);
  root.style.setProperty("--qm-glow-color", preset.glowColor);
  root.style.setProperty("--qm-ambient-origin", preset.ambientOrigin);
  if (timeOfDay) {
    root.setAttribute("data-time", timeOfDay);
  }
}
