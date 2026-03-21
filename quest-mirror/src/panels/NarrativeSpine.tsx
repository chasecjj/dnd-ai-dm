import { useRef, useEffect } from "react";
import { BreathGroup } from "../components/BreathGroup.tsx";
import { PlayerInput } from "../components/PlayerInput.tsx";
import type { DisplayedGroup } from "../hooks/useBreathGroups.ts";

interface NarrativeSpineProps {
  groups: DisplayedGroup[];
  location: string;
  characterName: string;
  processing: boolean;
  onPlayerInput: (text: string) => void;
}

export function NarrativeSpine({
  groups,
  location,
  characterName,
  processing,
  onPlayerInput,
}: NarrativeSpineProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new content
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [groups.length, processing]);

  return (
    <div
      ref={scrollRef}
      className="flex flex-col h-full overflow-y-auto p-8"
      style={{ maxWidth: "680px", margin: "0 auto" }}
    >
      {/* Location header */}
      <h1
        className="text-2xl mb-1 tracking-wide"
        style={{
          fontFamily: "var(--qm-font-heading)",
          color: "var(--qm-accent)",
        }}
      >
        {location}
      </h1>

      {/* Character name subheading */}
      <p
        className="text-sm mb-6"
        style={{
          fontFamily: "var(--qm-font-ui)",
          color: "var(--qm-text-dim)",
        }}
      >
        {characterName}
      </p>

      {/* Narrative manuscript */}
      <article
        className="text-lg leading-relaxed flex-1"
        style={{
          fontFamily: "var(--qm-font-narrative)",
          color: "var(--qm-text)",
        }}
      >
        {groups.map((group) => (
          <BreathGroup key={group.id} group={group} />
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
      <PlayerInput onSubmit={onPlayerInput} disabled={processing} />
    </div>
  );
}
