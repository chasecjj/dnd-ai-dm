export interface EnvironmentPreset {
  name: string;
  bg: string;
  surface: string;
  text: string;
  textDim: string;
  accent: string;
}

export const PRESETS: Record<string, EnvironmentPreset> = {
  tavern: {
    name: "Tavern",
    bg: "#f5f0e8",
    surface: "#ede5d8",
    text: "#2a2018",
    textDim: "#8a7e6e",
    accent: "#8b1a1a",
  },
};

export function applyPreset(preset: EnvironmentPreset, timeOfDay?: string) {
  const root = document.documentElement;
  root.style.setProperty("--qm-bg", preset.bg);
  root.style.setProperty("--qm-surface", preset.surface);
  root.style.setProperty("--qm-text", preset.text);
  root.style.setProperty("--qm-text-dim", preset.textDim);
  root.style.setProperty("--qm-accent", preset.accent);
  if (timeOfDay) {
    root.setAttribute("data-time", timeOfDay);
  }
}
