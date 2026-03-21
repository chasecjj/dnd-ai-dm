import type { DisplayedGroup } from "../hooks/useBreathGroups.ts";

interface Props {
  group: DisplayedGroup;
}

export function BreathGroup({ group }: Props) {
  if (group.isPlayer) {
    return (
      <p
        className="my-4 pl-4 italic opacity-80 text-base leading-relaxed"
        style={{
          fontFamily: "var(--qm-font-narrative)",
          color: "var(--qm-accent)",
          borderLeft: "2px solid var(--qm-accent-dim)",
        }}
      >
        {group.text}
      </p>
    );
  }
  return (
    <span
      className={`inline transition-opacity duration-500 ${group.visible ? "opacity-100" : "opacity-0"}`}
    >
      {group.text}
    </span>
  );
}
