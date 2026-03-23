import type { CeremonyType, CeremonyStep } from "./types.ts"

const CEREMONY_TIMELINES: Record<Exclude<CeremonyType, "none" | "death_save">, CeremonyStep[]> = {
  nat20: [
    { timeMs: 0,    action: "hold",       visual: "die_glow_gold" },
    { timeMs: 500,  action: "crack",      visual: "golden_cracks",    audio: "nat20_boom" },
    { timeMs: 800,  action: "ignite",     visual: "die_radiance",     audio: "nat20_ring" },
    { timeMs: 1200, action: "particles",  visual: "golden_embers" },
    { timeMs: 2000, action: "restore",    visual: "fade_to_warmth" },
    { timeMs: 2500, action: "complete" },
  ],
  nat1: [
    { timeMs: 0,    action: "hold" },
    { timeMs: 300,  action: "drop",       visual: "screen_drop" },
    { timeMs: 500,  action: "glow",       visual: "die_crimson",      audio: "nat1_cello" },
    { timeMs: 800,  action: "flash",      visual: "failure_flash",    audio: "nat1_clatter" },
    { timeMs: 1500, action: "recover",    visual: "warmth_returns" },
    { timeMs: 2000, action: "complete" },
  ],
}

export interface CeremonyState {
  type: CeremonyType
  currentStepIdx: number
  startedAt: number
  steps: CeremonyStep[]
  isComplete: boolean
}

export function createCeremony(type: Exclude<CeremonyType, "none" | "death_save">): CeremonyState {
  return {
    type,
    currentStepIdx: 0,
    startedAt: performance.now(),
    steps: CEREMONY_TIMELINES[type],
    isComplete: false,
  }
}

/** Advance ceremony based on elapsed time. Returns NEW state + current visual/audio cues. */
export function tickCeremony(
  state: CeremonyState,
  now: number,
): { state: CeremonyState; visual: string | undefined; audio: string | undefined } {
  const elapsed = now - state.startedAt
  let visual: string | undefined
  let audio: string | undefined
  let newStepIdx = state.currentStepIdx
  let isComplete = state.isComplete

  for (let i = state.steps.length - 1; i >= 0; i--) {
    if (elapsed >= state.steps[i].timeMs) {
      if (i > state.currentStepIdx) {
        audio = state.steps[i].audio
        newStepIdx = i
      }
      visual = state.steps[i].visual
      if (state.steps[i].action === "complete") {
        isComplete = true
      }
      break
    }
  }

  return {
    state: { ...state, currentStepIdx: newStepIdx, isComplete },
    visual,
    audio,
  }
}

/** Determine ceremony type from a d20 roll result. */
export function getCeremonyType(natural: number, dieSize: number): CeremonyType {
  if (dieSize !== 20) return "none"
  if (natural === 20) return "nat20"
  if (natural === 1) return "nat1"
  return "none"
}
