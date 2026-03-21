/**
 * REST API fetch wrapper for Quest Mirror.
 *
 * Provides typed methods for authentication, character listing,
 * and solo session management. WebSocket connections are handled
 * separately — this module covers only HTTP endpoints.
 */

import type { CharacterData, SessionInfo, TurnData } from "./types";

const BASE_URL = "/api";

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  auth: {
    login(passphrase: string) {
      return fetchJSON<{ token: string }>("/auth", {
        method: "POST",
        body: JSON.stringify({ passphrase }),
      });
    },
  },
  characters: {
    list() {
      return fetchJSON<CharacterData[]>("/characters");
    },
    get(name: string) {
      return fetchJSON<CharacterData>(
        `/characters/${encodeURIComponent(name)}`,
      );
    },
  },
  sessions: {
    list() {
      return fetchJSON<SessionInfo[]>("/solo/sessions");
    },
    create(characterName: string) {
      return fetchJSON<SessionInfo>("/solo/sessions", {
        method: "POST",
        body: JSON.stringify({ character_name: characterName }),
      });
    },
    history(sessionId: string, page = 1) {
      return fetchJSON<{ turns: TurnData[]; turn_count: number }>(
        `/solo/sessions/${sessionId}/history?page=${page}`,
      );
    },
  },
};
