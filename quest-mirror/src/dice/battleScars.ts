// quest-mirror/src/dice/battleScars.ts
import type { BattleScar } from "./types"

const STORAGE_KEY = "qm_battle_scars"

/** Load all scars for a character from localStorage. */
export function loadScars(characterName: string): BattleScar[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const all: BattleScar[] = JSON.parse(raw)
    return all.filter(s => s.characterName === characterName)
  } catch {
    return []
  }
}

/** Add a new scar and persist to localStorage. */
export function addScar(scar: BattleScar): void {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const all: BattleScar[] = raw ? JSON.parse(raw) : []
    all.push(scar)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all))
  } catch {
    console.warn("[BattleScars] Failed to persist scar to localStorage")
  }
}

/** Get scars for a specific die face. */
export function getScarsForFace(characterName: string, face: number): BattleScar[] {
  return loadScars(characterName).filter(s => s.face === face)
}

/** Count total scars by type for a character. */
export function scarSummary(characterName: string): { nat20: number; nat1: number; critKill: number } {
  const scars = loadScars(characterName)
  return {
    nat20: scars.filter(s => s.scarType === "nat20").length,
    nat1: scars.filter(s => s.scarType === "nat1").length,
    critKill: scars.filter(s => s.scarType === "crit_kill").length,
  }
}

/**
 * Record a battle scar from a critical roll.
 * Call this when a nat 20 or nat 1 occurs.
 */
export function recordBattleScar(
  characterName: string,
  natural: number,
  topFace: number,
  sessionId?: number,
  turnNumber?: number,
): void {
  let scarType: BattleScar["scarType"]
  if (natural === 20) scarType = "nat20"
  else if (natural === 1) scarType = "nat1"
  else return

  addScar({
    face: topFace,
    scarType,
    characterName,
    sessionId,
    turnNumber,
    createdAt: new Date().toISOString(),
  })
}
