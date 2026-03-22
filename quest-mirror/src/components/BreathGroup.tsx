import type { DisplayedGroup } from "../hooks/useBreathGroups.ts";
import type { ReactNode } from "react";

interface Props {
  group: DisplayedGroup;
  isFirstInTurn?: boolean;
}

export function BreathGroup({ group, isFirstInTurn = false }: Props) {
  // Player input — blockquote style with left border
  if (group.isPlayer) {
    return (
      <blockquote
        className="my-5 py-3 px-5 rounded-sm"
        style={{
          fontFamily: "var(--qm-font-narrative)",
          color: "var(--qm-text)",
          fontSize: "15px",
          lineHeight: 1.7,
          background: "var(--qm-player-bg)",
          borderLeft: "3px solid var(--qm-player-border)",
        }}
      >
        {group.text}
      </blockquote>
    );
  }

  // DM narrative — with optional drop cap
  const rendered = renderWithDiceBadges(group.text);

  // Drop cap on first narrative paragraph of a new turn
  if (isFirstInTurn && group.text.length > 50) {
    const firstChar = group.text[0];
    const restRendered = renderWithDiceBadges(group.text.slice(1));

    return (
      <span
        className={`inline transition-opacity duration-500 ${group.visible ? "opacity-100" : "opacity-0"}`}
      >
        <span
          className="float-left mr-2 mt-1"
          style={{
            fontFamily: "var(--qm-font-dropcap)",
            fontSize: "3.2em",
            lineHeight: 0.8,
            color: "var(--qm-accent)",
            fontWeight: 600,
          }}
        >
          {firstChar}
        </span>
        {restRendered}
      </span>
    );
  }

  return (
    <span
      className={`inline transition-opacity duration-500 ${group.visible ? "opacity-100" : "opacity-0"}`}
    >
      {rendered}
    </span>
  );
}

/**
 * Render text with inline dice badges.
 * Detects [roll:17] or [dice:1d20+5=17] patterns and renders as
 * small crimson pill badges inline with the narrative.
 */
function renderWithDiceBadges(text: string): ReactNode {
  const dicePattern = /\[(?:roll|dice)[:\s]*([^\]]*?=?\s*(\d+))\]/gi;

  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  dicePattern.lastIndex = 0;
  while ((match = dicePattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const rollValue = match[2] || match[1];
    parts.push(
      <span
        key={match.index}
        className="inline-flex items-center mx-1 px-2 py-0.5 rounded-sm text-xs font-semibold"
        style={{
          background: "var(--qm-dice-badge)",
          color: "var(--qm-dice-badge-text)",
          fontFamily: "var(--qm-font-ui)",
          fontSize: "11px",
          verticalAlign: "middle",
        }}
      >
        &#x1f3b2; {rollValue}
      </span>
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? <>{parts}</> : text;
}
