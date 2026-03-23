/** Phase of the dice roll lifecycle. */
export type DicePhase =
  | "idle"
  | "ready"
  | "rolling"
  | "settling"
  | "result"
  | "ceremony"
  | "done"

/** Ceremony type triggered by the roll result. */
export type CeremonyType = "none" | "nat20" | "nat1" | "death_save"

/** Material config for a character class's dice. */
export interface DiceClassConfig {
  className: string
  material: {
    baseColor: string
    roughness: number
    metalness: number
    emissive?: string
    emissiveIntensity?: number
    clearcoat?: number
  }
  numberColor: string
  sound: {
    roll: string
    land: string
  }
  scarStyle: {
    nat20Color: string
    nat1Color: string
  }
}

/** A battle scar on a specific die face. */
export interface BattleScar {
  face: number
  scarType: "nat20" | "nat1" | "crit_kill"
  characterName: string
  sessionId?: number
  turnNumber?: number
  createdAt?: string
}

/** Props for the DiceScene component. */
export interface DiceSceneProps {
  formula: string
  rollType: string
  prompt: string
  requestId: string
  autoTimeoutS: number
  onResult: (requestId: string, total: number, natural: number) => void
  characterClass?: string
  characterName?: string
}

/** Ceremony timing step. */
export interface CeremonyStep {
  timeMs: number
  action: string
  visual?: string
  audio?: string
}
