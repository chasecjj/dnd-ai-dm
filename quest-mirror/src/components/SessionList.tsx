import type { SessionInfo, CharacterData } from "../api/types.ts";

interface SessionListProps {
  sessions: SessionInfo[];
  characters: CharacterData[];
  onResume: (session: SessionInfo) => void;
  onCreate: (characterName: string) => void;
  error: string | null;
}

/** Lobby screen — active sessions to resume and characters to start new ones. */
export function SessionList({
  sessions,
  characters,
  onResume,
  onCreate,
  error,
}: SessionListProps) {
  const activeSessions = sessions.filter((s) => s.status === "active");
  const activeCharNames = new Set(activeSessions.map((s) => s.character_name));

  return (
    <div
      className="flex min-h-screen items-center justify-center p-8"
      style={{ background: "var(--qm-bg)" }}
    >
      <div className="w-full max-w-lg space-y-8">
        {/* Heading */}
        <h1
          className="text-center text-3xl tracking-wide"
          style={{
            fontFamily: "var(--qm-font-heading)",
            color: "var(--qm-accent)",
          }}
        >
          Quest Mirror
        </h1>
        <p
          className="text-center text-sm"
          style={{
            fontFamily: "var(--qm-font-ui)",
            color: "var(--qm-text-dim)",
          }}
        >
          Choose a character or resume an adventure.
        </p>

        {/* Error banner */}
        {error && (
          <div
            className="rounded border px-4 py-2 text-sm"
            style={{
              borderColor: "#c44",
              color: "#f88",
              background: "rgba(200, 50, 50, 0.12)",
              fontFamily: "var(--qm-font-ui)",
            }}
          >
            {error}
          </div>
        )}

        {/* Active Sessions */}
        {activeSessions.length > 0 && (
          <section className="space-y-3">
            <h2
              className="text-xs font-semibold uppercase tracking-widest"
              style={{
                fontFamily: "var(--qm-font-ui)",
                color: "var(--qm-text-dim)",
              }}
            >
              Resume Adventure
            </h2>
            {activeSessions.map((s) => (
              <button
                key={s.id}
                onClick={() => onResume(s)}
                className="flex w-full items-center justify-between rounded-lg border px-5 py-3 text-left transition-colors duration-200 hover:brightness-125"
                style={{
                  background: "var(--qm-surface)",
                  borderColor: "var(--qm-border-bright)",
                  fontFamily: "var(--qm-font-ui)",
                  color: "var(--qm-text)",
                }}
              >
                <div>
                  <span
                    className="block font-medium"
                    style={{ color: "var(--qm-accent)" }}
                  >
                    {s.character_name}
                  </span>
                  <span
                    className="text-xs"
                    style={{ color: "var(--qm-text-dim)" }}
                  >
                    {s.current_location} &middot; Turn {s.turn_count}
                  </span>
                </div>
                <span
                  className="text-xs"
                  style={{ color: "var(--qm-text-dim)" }}
                >
                  &rarr;
                </span>
              </button>
            ))}
          </section>
        )}

        {/* Characters */}
        <section className="space-y-3">
          <h2
            className="text-xs font-semibold uppercase tracking-widest"
            style={{
              fontFamily: "var(--qm-font-ui)",
              color: "var(--qm-text-dim)",
            }}
          >
            New Adventure
          </h2>
          {characters.length === 0 && (
            <p
              className="text-sm italic"
              style={{
                fontFamily: "var(--qm-font-ui)",
                color: "var(--qm-text-dim)",
              }}
            >
              No characters found.
            </p>
          )}
          {characters.map((c) => {
            const hasActive = activeCharNames.has(c.name);
            return (
              <button
                key={c.name}
                onClick={() => onCreate(c.name)}
                disabled={hasActive}
                className="flex w-full items-center justify-between rounded-lg border px-5 py-3 text-left transition-colors duration-200 hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
                style={{
                  background: "var(--qm-surface-glass)",
                  borderColor: "var(--qm-border)",
                  fontFamily: "var(--qm-font-ui)",
                  color: "var(--qm-text)",
                }}
              >
                <div>
                  <span className="block font-medium">{c.name}</span>
                  {(c.race || c.class) && (
                    <span
                      className="text-xs"
                      style={{ color: "var(--qm-text-dim)" }}
                    >
                      {[c.race, c.class, c.level ? `Lv ${c.level}` : null]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  )}
                </div>
                {hasActive ? (
                  <span
                    className="text-xs"
                    style={{ color: "var(--qm-text-dim)" }}
                  >
                    in session
                  </span>
                ) : (
                  <span
                    className="text-xs"
                    style={{ color: "var(--qm-accent)" }}
                  >
                    +
                  </span>
                )}
              </button>
            );
          })}
        </section>
      </div>
    </div>
  );
}
