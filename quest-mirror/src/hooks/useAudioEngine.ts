import { useRef, useCallback, useEffect, useState } from "react"
import { Howl } from "howler"

interface AudioEngine {
  play: (key: string, volume?: number) => number | undefined
  unlock: () => void
  preloadCeremonySounds: () => void
  getContext: () => AudioContext | null
  isReady: boolean
}

const DICE_SPRITES: Record<string, [number, number]> = {
  rogue_roll: [0, 800],
  rogue_land: [800, 400],
}

const CEREMONY_SPRITES: Record<string, [number, number]> = {
  nat20_boom: [0, 1200],
  nat20_ring: [1200, 2000],
  nat1_cello: [0, 1500],
  nat1_clatter: [1500, 800],
  heartbeat: [0, 1000],
  candle_ignite: [1000, 500],
  candle_extinguish: [1500, 500],
  gold_crack: [2000, 1000],
  die_shatter: [3000, 1500],
}

export function useAudioEngine(): AudioEngine {
  const contextRef = useRef<AudioContext | null>(null)
  const diceHowlRef = useRef<Howl | null>(null)
  const ceremonyHowlRef = useRef<Howl | null>(null)
  const [isReady, setIsReady] = useState(false)

  useEffect(() => {
    try {
      diceHowlRef.current = new Howl({
        src: ["/sounds/dice-sprites.webm", "/sounds/dice-sprites.mp3"],
        sprite: DICE_SPRITES,
        volume: 0.6,
        preload: true,
        onloaderror: () => {
          console.warn("[Audio] Dice sound sprites not found — running silent")
          diceHowlRef.current = null
        },
      })
    } catch {
      console.warn("[Audio] Howler initialization failed — running silent")
    }

    return () => {
      diceHowlRef.current?.unload()
      ceremonyHowlRef.current?.unload()
      contextRef.current?.close()
    }
  }, [])

  const unlock = useCallback(() => {
    if (contextRef.current) return
    try {
      const ctx = new AudioContext()
      if (ctx.state === "suspended") ctx.resume()
      contextRef.current = ctx
      setIsReady(true)
    } catch {
      console.warn("[Audio] AudioContext creation failed")
    }
  }, [])

  const preloadCeremonySounds = useCallback(() => {
    if (ceremonyHowlRef.current) return
    try {
      ceremonyHowlRef.current = new Howl({
        src: ["/sounds/ceremony-sprites.webm", "/sounds/ceremony-sprites.mp3"],
        sprite: CEREMONY_SPRITES,
        volume: 0.8,
        preload: true,
        onloaderror: () => {
          console.warn("[Audio] Ceremony sound sprites not found — ceremonies will be silent")
          ceremonyHowlRef.current = null
        },
      })
    } catch {
      // Silent fallback
    }
  }, [])

  const play = useCallback((key: string, volume?: number): number | undefined => {
    if (DICE_SPRITES[key] && diceHowlRef.current) {
      const id = diceHowlRef.current.play(key)
      if (volume !== undefined) diceHowlRef.current.volume(volume, id)
      return id
    }
    if (CEREMONY_SPRITES[key] && ceremonyHowlRef.current) {
      const id = ceremonyHowlRef.current.play(key)
      if (volume !== undefined) ceremonyHowlRef.current.volume(volume, id)
      return id
    }
    return undefined
  }, [])

  const getContext = useCallback(() => contextRef.current, [])

  return { play, unlock, preloadCeremonySounds, getContext, isReady }
}
