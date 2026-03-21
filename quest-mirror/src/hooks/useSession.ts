import { useState, useCallback } from "react";
import { api } from "../api/client.ts";
import type { SessionInfo, CharacterData } from "../api/types.ts";

export type AppPhase = "auth" | "lobby" | "playing";

export function useSession() {
  const [phase, setPhase] = useState<AppPhase>("auth");
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("qm_token"),
  );
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [characters, setCharacters] = useState<CharacterData[]>([]);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(async (passphrase: string) => {
    try {
      const { token: newToken } = await api.auth.login(passphrase);
      localStorage.setItem("qm_token", newToken);
      setToken(newToken);
      setPhase("lobby");
      setError(null);
      const [chars, sess] = await Promise.all([
        api.characters.list(),
        api.sessions.list(),
      ]);
      setCharacters(chars);
      setSessions(sess);
    } catch (e: unknown) {
      const message =
        e instanceof Error ? e.message : "Login failed";
      setError(message);
    }
  }, []);

  const createSession = useCallback(async (characterName: string) => {
    try {
      const newSession = await api.sessions.create(characterName);
      setSession(newSession);
      setPhase("playing");
      setError(null);
    } catch (e: unknown) {
      const message =
        e instanceof Error ? e.message : "Failed to create session";
      setError(message);
    }
  }, []);

  const resumeSession = useCallback((sessionInfo: SessionInfo) => {
    setSession(sessionInfo);
    setPhase("playing");
  }, []);

  const endSession = useCallback(() => {
    setSession(null);
    setPhase("lobby");
  }, []);

  return {
    phase,
    token,
    session,
    characters,
    sessions,
    error,
    login,
    createSession,
    resumeSession,
    endSession,
  };
}
