import { useRef, useEffect } from "react";
import { BreathGroup } from "../components/BreathGroup.tsx";
import { PlayerInput } from "../components/PlayerInput.tsx";
import type { DisplayedGroup } from "../hooks/useBreathGroups.ts";

interface NarrativeSpineProps {
  groups: DisplayedGroup[];
  location: string;
  locationDetail?: string; // e.g. "Evening, 14th of Deepwinter"
  sessionInfo?: string; // e.g. "Solo XLII · Turn VII"
  characterName: string;
  processing: boolean;
  onPlayerInput: (text: string) => void;
  turnCount: number;
}

export function NarrativeSpine({
  groups,
  location,
  locationDetail,
  sessionInfo,
  characterName,
  processing,
  onPlayerInput,
  turnCount: _turnCount,
}: NarrativeSpineProps) {
  // _turnCount available for sessionInfo display — turn grouping derives from groups
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new content
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [groups.length, processing]);

  // Group breath groups into turns for turn markers
  const turnsWithGroups = groupByTurns(groups);

  return (
    <div
      ref={scrollRef}
      className="flex flex-col h-full overflow-y-auto px-12 py-8"
      style={{ background: "var(--qm-bg)" }}
    >
      <div style={{ maxWidth: "700px", margin: "0 auto", width: "100%" }}>
        {/* Location header */}
        <div className="flex items-baseline justify-between mb-8">
          <h1
            className="text-2xl tracking-wide"
            style={{
              fontFamily: "var(--qm-font-heading)",
              color: "var(--qm-text)",
              fontWeight: 400,
            }}
          >
            {location || "Unknown Location"}
          </h1>
          {(locationDetail || sessionInfo) && (
            <div
              className="text-right text-xs"
              style={{
                fontFamily: "var(--qm-font-ui)",
                color: "var(--qm-text-dim)",
                fontStyle: "italic",
              }}
            >
              {locationDetail && <div>{locationDetail}</div>}
              {sessionInfo && <div>{sessionInfo}</div>}
            </div>
          )}
        </div>

        {/* Narrative manuscript with turn markers */}
        <article
          className="flex-1"
          style={{
            fontFamily: "var(--qm-font-narrative)",
            color: "var(--qm-text)",
            fontSize: "17px",
            lineHeight: 1.85,
            textAlign: "justify",
          }}
        >
          {turnsWithGroups.map((turn, turnIdx) => (
            <div key={turn.turnNumber} className="mb-6">
              {/* Turn marker */}
              {turn.turnNumber > 0 && (
                <div
                  className="mb-4 mt-8 text-xs tracking-[0.2em] uppercase"
                  style={{
                    fontFamily: "var(--qm-font-ui)",
                    color: "var(--qm-text-dim)",
                    opacity: 0.6,
                  }}
                >
                  Turn {toRoman(turn.turnNumber)}
                </div>
              )}

              {turn.groups.map((group, groupIdx) => (
                <BreathGroup
                  key={group.id}
                  group={group}
                  isFirstInTurn={groupIdx === 0 && !group.isPlayer && turnIdx > 0}
                />
              ))}
            </div>
          ))}

          {/* Pulsing quill cursor when processing */}
          {processing && (
            <span
              className="inline-block w-0.5 h-5 ml-1 align-middle animate-pulse rounded-sm"
              style={{ backgroundColor: "var(--qm-accent)" }}
            />
          )}
        </article>

        {/* Player input */}
        <PlayerInput
          onSubmit={onPlayerInput}
          disabled={processing}
          characterName={characterName}
        />
      </div>
    </div>
  );
}

// --- Helpers ---

interface TurnGroup {
  turnNumber: number;
  groups: DisplayedGroup[];
}

function groupByTurns(groups: DisplayedGroup[]): TurnGroup[] {
  if (groups.length === 0) return [];

  const turns: TurnGroup[] = [];
  let currentTurn: TurnGroup = { turnNumber: 0, groups: [] };
  let turnCounter = 0;

  for (const group of groups) {
    if (group.isPlayer && currentTurn.groups.length > 0) {
      // Player input starts a new turn
      turns.push(currentTurn);
      turnCounter++;
      currentTurn = { turnNumber: turnCounter, groups: [group] };
    } else {
      currentTurn.groups.push(group);
    }
  }

  if (currentTurn.groups.length > 0) {
    turns.push(currentTurn);
  }

  return turns;
}

function toRoman(num: number): string {
  const values = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1];
  const numerals = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"];
  let result = "";
  for (let i = 0; i < values.length; i++) {
    while (num >= values[i]) {
      result += numerals[i];
      num -= values[i];
    }
  }
  return result;
}
