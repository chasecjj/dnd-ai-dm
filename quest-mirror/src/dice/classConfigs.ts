import type { DiceClassConfig } from "./types"

/**
 * Rogue — Obsidian and bone.
 * Matte black die with off-white bone number inlays.
 * Nearly silent landing — soft tap, like a coin on felt.
 * Scars: nat 20 = silver hairline, nat 1 = dark scoring.
 */
const ROGUE: DiceClassConfig = {
  className: "rogue",
  material: {
    baseColor: "#1a1a1a",
    roughness: 0.95,
    metalness: 0.1,
    emissive: "#000000",
    emissiveIntensity: 0,
    clearcoat: 0.05,
  },
  numberColor: "#d4c9a8",
  sound: {
    roll: "rogue_roll",
    land: "rogue_land",
  },
  scarStyle: {
    nat20Color: "#c0c0c0",
    nat1Color: "#2a2020",
  },
}

/** All registered class configs. */
export const CLASS_CONFIGS: Record<string, DiceClassConfig> = {
  rogue: ROGUE,
}

/** Get config for a class, falling back to rogue. */
export function getClassConfig(className?: string): DiceClassConfig {
  return CLASS_CONFIGS[className?.toLowerCase() ?? "rogue"] ?? ROGUE
}
