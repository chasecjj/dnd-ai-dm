import type { CharacterData, SceneData } from "../api/types";

interface Props {
  character: CharacterData | null;
  scene: SceneData | null;
  chaosLevel: number;
}

function StatBox({ label, value }: { label: string; value: unknown }) {
  return (
    <div
      className="p-2 rounded text-center"
      style={{ border: "1px solid var(--qm-border)" }}
    >
      <div className="text-xs" style={{ color: "var(--qm-text-dim)" }}>
        {label}
      </div>
      <div
        className="text-lg font-semibold"
        style={{ color: "var(--qm-text)" }}
      >
        {String(value ?? "—")}
      </div>
    </div>
  );
}

function hpBarColor(ratio: number): string {
  if (ratio > 0.5) return "var(--qm-hp-green, #22c55e)";
  if (ratio > 0.25) return "var(--qm-hp-amber, #f59e0b)";
  return "var(--qm-hp-red, #ef4444)";
}

export default function CharacterPanel({
  character,
  scene,
  chaosLevel,
}: Props) {
  if (!character) {
    return (
      <div
        className="p-4 text-center"
        style={{ color: "var(--qm-text-dim)", fontFamily: "var(--qm-font-ui)" }}
      >
        No character data.
      </div>
    );
  }

  const hpCurrent = character.hp_current ?? 0;
  const hpMax = character.hp_max ?? 1;
  const hpRatio = hpMax > 0 ? hpCurrent / hpMax : 0;

  const hasSpellSlots =
    character.spell_slots_max != null && character.spell_slots_max > 0;

  return (
    <div
      className="flex flex-col gap-4 p-4"
      style={{ fontFamily: "var(--qm-font-ui)" }}
    >
      {/* 1. Character Identity */}
      <div>
        <h2
          className="text-xl font-bold leading-tight"
          style={{
            fontFamily: "var(--qm-font-heading)",
            color: "var(--qm-accent)",
          }}
        >
          {character.name}
        </h2>
        {(character.race || character.class || character.level != null) && (
          <div className="text-sm" style={{ color: "var(--qm-text-dim)" }}>
            {[
              character.race,
              character.class,
              character.level != null ? `Lvl ${character.level}` : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </div>
        )}
      </div>

      {/* 2. HP Gauge */}
      <div>
        <div className="flex justify-between text-xs mb-1">
          <span style={{ color: "var(--qm-text-dim)" }}>HP</span>
          <span style={{ color: "var(--qm-text)" }}>
            {hpCurrent}/{hpMax}
          </span>
        </div>
        <div
          className="h-3 rounded-full overflow-hidden"
          style={{ backgroundColor: "var(--qm-surface, #1e1e1e)" }}
        >
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{
              width: `${Math.max(0, Math.min(100, hpRatio * 100))}%`,
              backgroundColor: hpBarColor(hpRatio),
            }}
          />
        </div>
      </div>

      {/* 3. Stats Grid */}
      <div className={`grid gap-2 ${hasSpellSlots ? "grid-cols-2" : "grid-cols-1"}`}>
        <StatBox label="AC" value={character.ac} />
        {hasSpellSlots && (
          <StatBox
            label="Spell Slots"
            value={`${(character.spell_slots_max ?? 0) - (character.spell_slots_used ?? 0)}/${character.spell_slots_max}`}
          />
        )}
      </div>

      {/* 4. Conditions */}
      {character.conditions && character.conditions.length > 0 && (
        <div>
          <div
            className="text-xs mb-1 uppercase tracking-wide"
            style={{ color: "var(--qm-text-dim)" }}
          >
            Conditions
          </div>
          <div className="flex flex-wrap gap-1">
            {character.conditions.map((condition) => (
              <span
                key={condition}
                className="px-2 py-0.5 rounded text-xs font-medium"
                style={{
                  backgroundColor: "var(--qm-condition-bg, rgba(239, 68, 68, 0.15))",
                  color: "var(--qm-condition-text, #fca5a5)",
                  border: "1px solid var(--qm-condition-border, rgba(239, 68, 68, 0.3))",
                }}
              >
                {condition}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 5. Scene Presence */}
      {scene?.entities_present && scene.entities_present.length > 0 && (
        <div>
          <div
            className="text-xs mb-1 uppercase tracking-wide"
            style={{ color: "var(--qm-text-dim)" }}
          >
            Scene Presence
          </div>
          <ul className="space-y-1">
            {scene.entities_present.map((entity) => (
              <li
                key={entity.name}
                className="text-sm flex items-baseline gap-1"
              >
                <span style={{ color: "var(--qm-text)" }}>{entity.name}</span>
                {entity.current_demeanor && (
                  <span
                    className="text-xs italic"
                    style={{ color: "var(--qm-text-dim)" }}
                  >
                    — {entity.current_demeanor}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 6. Inventory */}
      {character.inventory_notes && (
        <div>
          <div
            className="text-xs mb-1 uppercase tracking-wide"
            style={{ color: "var(--qm-text-dim)" }}
          >
            Inventory
          </div>
          <pre
            className="text-xs whitespace-pre-wrap p-2 rounded"
            style={{
              color: "var(--qm-text)",
              backgroundColor: "var(--qm-surface, #1e1e1e)",
              fontFamily: "var(--qm-font-ui)",
            }}
          >
            {character.inventory_notes}
          </pre>
        </div>
      )}

      {/* 7. Chaos Level */}
      <div
        className="flex items-center justify-between pt-2 text-xs"
        style={{
          borderTop: "1px solid var(--qm-border)",
          color: "var(--qm-text-dim)",
        }}
      >
        <span>Chaos</span>
        <div className="flex items-center gap-1">
          <div
            className="h-1.5 rounded-full overflow-hidden"
            style={{
              width: "4rem",
              backgroundColor: "var(--qm-surface, #1e1e1e)",
            }}
          >
            <div
              className="h-full rounded-full transition-all duration-300"
              style={{
                width: `${(chaosLevel / 9) * 100}%`,
                backgroundColor: "var(--qm-accent, #8b5cf6)",
              }}
            />
          </div>
          <span>{chaosLevel}/9</span>
        </div>
      </div>
    </div>
  );
}
