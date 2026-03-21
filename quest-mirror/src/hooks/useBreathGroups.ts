import { useState, useRef, useCallback } from "react";
import type { NarrativeStreamMsg } from "../api/types.ts";

export interface DisplayedGroup {
  id: string;
  text: string;
  mood: string;
  isPlayer: boolean;
  visible: boolean;
}

const BREATH_GROUP_DELAY_MS = 300; // Phase 1a: uniform timing

export function useBreathGroups() {
  const [groups, setGroups] = useState<DisplayedGroup[]>([]);
  const queueRef = useRef<NarrativeStreamMsg[]>([]);
  const processingRef = useRef(false);
  const idCounter = useRef(0);

  const processQueue = useCallback(async () => {
    if (processingRef.current) return;
    processingRef.current = true;
    while (queueRef.current.length > 0) {
      const msg = queueRef.current.shift()!;
      const id = `bg-${idCounter.current++}`;
      setGroups((prev) => [
        ...prev,
        { id, text: msg.text, mood: msg.mood, isPlayer: false, visible: false },
      ]);
      await new Promise((r) => setTimeout(r, 50)); // brief pause for DOM
      setGroups((prev) =>
        prev.map((g) => (g.id === id ? { ...g, visible: true } : g)),
      );
      if (!msg.is_final) {
        await new Promise((r) => setTimeout(r, BREATH_GROUP_DELAY_MS));
      }
    }
    processingRef.current = false;
  }, []);

  const addNarrative = useCallback(
    (msg: NarrativeStreamMsg) => {
      queueRef.current.push(msg);
      void processQueue();
    },
    [processQueue],
  );

  const addPlayerInput = useCallback((text: string) => {
    const id = `pi-${idCounter.current++}`;
    setGroups((prev) => [
      ...prev,
      { id, text, mood: "neutral", isPlayer: true, visible: true },
    ]);
  }, []);

  const clearGroups = useCallback(() => {
    setGroups([]);
    queueRef.current = [];
  }, []);

  return { groups, addNarrative, addPlayerInput, clearGroups };
}
