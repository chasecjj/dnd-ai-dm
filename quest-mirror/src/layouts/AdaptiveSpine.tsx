import type { ReactNode } from "react";

interface AdaptiveSpineProps {
  narrative: ReactNode;
  contextRail?: ReactNode;
  isRailOpen?: boolean;
}

export function AdaptiveSpine({
  narrative,
  contextRail,
  isRailOpen = true,
}: AdaptiveSpineProps) {
  return (
    <div
      className="flex h-screen w-screen overflow-hidden"
      style={{ background: "var(--qm-bg)" }}
    >
      {/* Left sidebar — icon buttons */}
      <nav
        className="flex flex-col items-center gap-4 py-6 px-3"
        style={{
          background: "var(--qm-surface)",
          borderRight: "1px solid var(--qm-border-subtle)",
        }}
      >
        <SidebarIcon label="Close" symbol="✕" />
        <SidebarIcon label="Bookmarks" symbol="★" />
        <SidebarIcon label="Character" symbol="☻" />
        <SidebarIcon label="Quests" symbol="🔥" />
        <div className="flex-1" />
        <SidebarIcon label="Settings" symbol="⚙" />
      </nav>

      {/* Narrative spine — center */}
      <main
        className="flex-1 overflow-hidden transition-all duration-500"
        style={{
          maxWidth: isRailOpen ? "var(--qm-spine-width)" : "100%",
        }}
      >
        {narrative}
      </main>

      {/* Context rail — right side */}
      {isRailOpen && contextRail && (
        <aside
          className="h-screen overflow-y-auto"
          style={{
            width: "var(--qm-rail-width)",
            background: "var(--qm-surface)",
            borderLeft: "1px solid var(--qm-border-subtle)",
          }}
        >
          {contextRail}
        </aside>
      )}
    </div>
  );
}

function SidebarIcon({ label, symbol }: { label: string; symbol: string }) {
  return (
    <button
      title={label}
      className="w-8 h-8 flex items-center justify-center rounded text-sm transition-colors hover:opacity-70"
      style={{ color: "var(--qm-text-dim)" }}
    >
      {symbol}
    </button>
  );
}
