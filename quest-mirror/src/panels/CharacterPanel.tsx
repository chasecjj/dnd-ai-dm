import type { CharacterData, SceneData } from "../api/types";

interface Props {
  character: CharacterData | null;
  scene: SceneData | null;
  chaosLevel: number;
}

/* ── Helpers ───────────────────────────────────────────────────── */

const NEGATIVE_CONDITIONS = new Set([
  "blinded",
  "charmed",
  "deafened",
  "exhaustion",
  "frightened",
  "grappled",
  "incapacitated",
  "invisible",
  "paralyzed",
  "petrified",
  "poisoned",
  "prone",
  "restrained",
  "stunned",
  "unconscious",
  "cursed",
  "diseased",
  "bleeding",
  "confused",
  "dominated",
  "entangled",
  "silenced",
  "slowed",
  "weakened",
]);

function isNegativeCondition(condition: string): boolean {
  return NEGATIVE_CONDITIONS.has(condition.toLowerCase().replace(/\s*\(.*\)/, ""));
}

/** Parse a condition string like "Poisoned (2 rounds)" into name + optional duration. */
function parseCondition(raw: string): { name: string; duration?: string } {
  const match = raw.match(/^(.+?)\s*\(([^)]+)\)\s*$/);
  if (match) return { name: match[1].trim(), duration: match[2].trim() };
  return { name: raw.trim() };
}

/** HP bar gradient: healthy = warm gold, wounded = orange, critical = crimson. */
function hpBarColor(ratio: number): string {
  if (ratio > 0.5) return "var(--qm-accent-soft, #c4a87a)";
  if (ratio > 0.25) return "#c77c32";
  return "var(--qm-accent, #8b1a1a)";
}

/**
 * Parse inventory_notes into structured items.
 * Each line or comma-separated entry becomes an item.
 * Supports formats like:
 *   "Dagger of Whispers — +1, finesse"
 *   "Thieves' Tools: proficient"
 *   "Gold: 127 gp"
 */
function parseInventory(notes: string): Array<{ name: string; property?: string }> {
  // Split on newlines first, then commas if no newlines
  let entries = notes.split(/\n/).map((s) => s.trim()).filter(Boolean);
  if (entries.length === 1 && entries[0].includes(",")) {
    entries = entries[0].split(",").map((s) => s.trim()).filter(Boolean);
  }

  return entries.map((entry) => {
    // Try splitting on common separators: " — ", " - ", ": "
    for (const sep of [" — ", " – ", " - ", ": "]) {
      const idx = entry.indexOf(sep);
      if (idx > 0) {
        return {
          name: entry.slice(0, idx).trim(),
          property: entry.slice(idx + sep.length).trim() || undefined,
        };
      }
    }
    return { name: entry };
  });
}

/** Map demeanor keywords to NPC disposition for coloring. */
function npcDisposition(
  demeanor?: string,
): "hostile" | "friendly" | "background" | "neutral" {
  if (!demeanor) return "neutral";
  const d = demeanor.toLowerCase();
  if (
    d.includes("hostile") ||
    d.includes("aggressive") ||
    d.includes("threatening") ||
    d.includes("angry") ||
    d.includes("menacing") ||
    d.includes("enemy") ||
    d.includes("suspicious")
  )
    return "hostile";
  if (
    d.includes("friendly") ||
    d.includes("warm") ||
    d.includes("helpful") ||
    d.includes("kind") ||
    d.includes("ally") ||
    d.includes("welcoming")
  )
    return "friendly";
  if (
    d.includes("background") ||
    d.includes("indifferent") ||
    d.includes("busy") ||
    d.includes("distracted") ||
    d.includes("distant")
  )
    return "background";
  return "neutral";
}

function npcColor(
  disposition: "hostile" | "friendly" | "background" | "neutral",
): string {
  switch (disposition) {
    case "hostile":
      return "var(--qm-npc-hostile)";
    case "friendly":
      return "var(--qm-npc-friendly)";
    case "background":
      return "var(--qm-npc-background)";
    case "neutral":
    default:
      return "var(--qm-text)";
  }
}

/* ── Sub-components ────────────────────────────────────────────── */

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: "0.65rem",
        fontVariant: "all-small-caps",
        letterSpacing: "0.12em",
        color: "var(--qm-text-dim)",
        marginBottom: "0.5rem",
        fontFamily: "var(--qm-font-ui)",
      }}
    >
      {children}
    </div>
  );
}

function Separator() {
  return (
    <hr
      style={{
        border: "none",
        borderTop: "1px solid var(--qm-border-subtle)",
        margin: "0.75rem 0",
      }}
    />
  );
}

function StatBox({ label, value }: { label: string; value: string | number }) {
  return (
    <div
      style={{
        border: "1px solid var(--qm-border-subtle)",
        padding: "0.5rem 0.75rem",
        textAlign: "center",
        flex: 1,
        minWidth: 0,
      }}
    >
      <div
        style={{
          fontSize: "1.35rem",
          fontWeight: 600,
          color: "var(--qm-text)",
          fontFamily: "var(--qm-font-heading)",
          lineHeight: 1.1,
        }}
      >
        {value}
      </div>
      <div
        style={{
          fontSize: "0.6rem",
          fontVariant: "all-small-caps",
          letterSpacing: "0.1em",
          color: "var(--qm-text-dim)",
          marginTop: "0.2rem",
          fontFamily: "var(--qm-font-ui)",
        }}
      >
        {label}
      </div>
    </div>
  );
}

/* ── Main Component ────────────────────────────────────────────── */

export default function CharacterPanel({
  character,
  scene,
  chaosLevel: _chaosLevel,
}: Props) {
  if (!character) {
    return (
      <div
        style={{
          padding: "2rem 1.5rem",
          textAlign: "center",
          color: "var(--qm-text-dim)",
          fontFamily: "var(--qm-font-ui)",
          fontStyle: "italic",
          fontSize: "0.85rem",
        }}
      >
        Awaiting character data...
      </div>
    );
  }

  const hpCurrent = character.hp_current ?? 0;
  const hpMax = character.hp_max ?? 1;
  const hpRatio = hpMax > 0 ? hpCurrent / hpMax : 0;
  const hpPercent = Math.max(0, Math.min(100, hpRatio * 100));

  const hasSpellSlots =
    character.spell_slots_max != null && character.spell_slots_max > 0;
  const spellSlotsRemaining = hasSpellSlots
    ? (character.spell_slots_max ?? 0) - (character.spell_slots_used ?? 0)
    : 0;

  const conditions = (character.conditions ?? []).map(parseCondition);
  const inventoryItems = character.inventory_notes
    ? parseInventory(character.inventory_notes)
    : [];
  const entities = scene?.entities_present ?? [];

  // Build subtitle from class info
  const subtitle = [character.race, character.class]
    .filter(Boolean)
    .join(" ")
    || undefined;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 0,
        padding: "1.25rem 1rem",
        fontFamily: "var(--qm-font-ui)",
        backgroundColor: "var(--qm-bg-deep)",
        borderRight: "1px solid var(--qm-border-subtle)",
        height: "100%",
        overflowY: "auto",
        boxSizing: "border-box",
      }}
    >
      {/* ── Panel Header ─────────────────────────────────────── */}
      <div style={{ textAlign: "center", marginBottom: "0.25rem" }}>
        <div
          style={{
            fontSize: "0.6rem",
            fontVariant: "all-small-caps",
            letterSpacing: "0.2em",
            color: "var(--qm-text-dim)",
            fontFamily: "var(--qm-font-ui)",
          }}
        >
          CHARACTER
        </div>
        <div
          style={{
            fontSize: "0.5rem",
            color: "var(--qm-text-dim)",
            opacity: 0.6,
            marginTop: "0.1rem",
          }}
        >
          auto-updated
        </div>
      </div>

      <Separator />

      {/* ── Character Identity ───────────────────────────────── */}
      <div style={{ textAlign: "center", marginBottom: "0.75rem" }}>
        <h2
          style={{
            fontFamily: "var(--qm-font-heading)",
            fontSize: "1.5rem",
            fontWeight: 600,
            color: "var(--qm-text)",
            margin: 0,
            lineHeight: 1.2,
          }}
        >
          {character.name}
        </h2>
        {subtitle && (
          <div
            style={{
              fontSize: "0.8rem",
              fontStyle: "italic",
              color: "var(--qm-text-dim)",
              marginTop: "0.2rem",
            }}
          >
            {subtitle}
            {character.level != null && ` \u00B7 Level ${character.level}`}
          </div>
        )}
      </div>

      {/* ── Stats Row ────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          gap: "0.35rem",
          marginBottom: "0.75rem",
        }}
      >
        <StatBox label="ARMOUR" value={character.ac ?? "\u2014"} />
        <StatBox label="VITALITY" value={hpCurrent} />
        <StatBox label="INITIATIVE" value="\u2014" />
      </div>

      {/* ── HP Bar ───────────────────────────────────────────── */}
      <div style={{ marginBottom: "1rem" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            marginBottom: "0.3rem",
          }}
        >
          <span
            style={{
              fontSize: "0.65rem",
              fontVariant: "all-small-caps",
              letterSpacing: "0.08em",
              color: "var(--qm-text-dim)",
              fontFamily: "var(--qm-font-ui)",
            }}
          >
            Hit Points
          </span>
          <span
            style={{
              fontSize: "0.7rem",
              fontWeight: 600,
              color: "var(--qm-text)",
              fontFamily: "var(--qm-font-ui)",
            }}
          >
            {hpCurrent} OF {hpMax}
          </span>
        </div>
        <div
          style={{
            height: "0.4rem",
            borderRadius: "0.2rem",
            overflow: "hidden",
            backgroundColor: "var(--qm-border-subtle)",
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${hpPercent}%`,
              borderRadius: "0.2rem",
              backgroundColor: hpBarColor(hpRatio),
              transition: "width 0.4s ease, background-color 0.4s ease",
            }}
          />
        </div>
      </div>

      {/* ── Conditions ───────────────────────────────────────── */}
      {conditions.length > 0 && (
        <div style={{ marginBottom: "1rem" }}>
          <SectionHeader>CONDITIONS</SectionHeader>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "0.3rem",
            }}
          >
            {conditions.map((cond) => {
              const negative = isNegativeCondition(cond.name);
              return (
                <span
                  key={cond.name}
                  style={{
                    display: "inline-flex",
                    alignItems: "baseline",
                    gap: "0.25rem",
                    padding: "0.2rem 0.5rem",
                    fontSize: "0.65rem",
                    fontWeight: 500,
                    borderRadius: "0.2rem",
                    border: `1px solid ${
                      negative
                        ? "var(--qm-condition-negative-border)"
                        : "var(--qm-condition-neutral-border)"
                    }`,
                    backgroundColor: negative
                      ? "var(--qm-condition-negative-bg)"
                      : "var(--qm-condition-neutral-bg)",
                    color: negative
                      ? "var(--qm-condition-negative-text)"
                      : "var(--qm-condition-neutral-text)",
                    fontFamily: "var(--qm-font-ui)",
                  }}
                >
                  {cond.name}
                  {cond.duration && (
                    <span style={{ fontSize: "0.55rem", opacity: 0.7 }}>
                      {cond.duration}
                    </span>
                  )}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Arcane Reserves (Spell Slots) ────────────────────── */}
      {hasSpellSlots && (
        <div style={{ marginBottom: "1rem" }}>
          <SectionHeader>ARCANE RESERVES</SectionHeader>
          <div style={{ display: "flex", gap: "0.25rem", flexWrap: "wrap" }}>
            {Array.from({ length: character.spell_slots_max! }).map((_, i) => {
              const filled = i < spellSlotsRemaining;
              return (
                <div
                  key={i}
                  style={{
                    width: "0.7rem",
                    height: "0.7rem",
                    border: `1px solid ${
                      filled
                        ? "var(--qm-accent)"
                        : "var(--qm-border-subtle)"
                    }`,
                    backgroundColor: filled
                      ? "var(--qm-accent)"
                      : "transparent",
                    borderRadius: "0.1rem",
                    transition: "background-color 0.3s ease",
                  }}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* ── Possessions ──────────────────────────────────────── */}
      {inventoryItems.length > 0 && (
        <div style={{ marginBottom: "1rem" }}>
          <SectionHeader>POSSESSIONS</SectionHeader>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "0.3rem",
            }}
          >
            {inventoryItems.map((item, i) => (
              <div
                key={`${item.name}-${i}`}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  gap: "0.5rem",
                  fontSize: "0.75rem",
                }}
              >
                <span
                  style={{
                    color: "var(--qm-text)",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {item.name}
                </span>
                {item.property && (
                  <span
                    style={{
                      color: "var(--qm-text-dim)",
                      fontStyle: "italic",
                      fontSize: "0.65rem",
                      whiteSpace: "nowrap",
                      flexShrink: 0,
                    }}
                  >
                    {item.property}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Present in Scene ─────────────────────────────────── */}
      {entities.length > 0 && (
        <div style={{ marginBottom: "0.5rem" }}>
          <SectionHeader>PRESENT IN SCENE</SectionHeader>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "0.4rem",
            }}
          >
            {entities.map((entity) => {
              const disposition = npcDisposition(entity.current_demeanor);
              const nameColor = npcColor(disposition);
              const isBackground = disposition === "background";
              return (
                <div
                  key={entity.name}
                  style={{
                    fontSize: "0.75rem",
                    lineHeight: 1.35,
                  }}
                >
                  <span
                    style={{
                      fontWeight: isBackground ? 400 : 600,
                      fontStyle: isBackground ? "italic" : "normal",
                      color: nameColor,
                    }}
                  >
                    {entity.name}
                  </span>
                  {(entity.role_or_relationship || entity.current_demeanor) && (
                    <span
                      style={{
                        color: "var(--qm-text-dim)",
                        fontSize: "0.65rem",
                        marginLeft: "0.35rem",
                      }}
                    >
                      {entity.role_or_relationship || entity.current_demeanor}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
