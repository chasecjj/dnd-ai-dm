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
      className="h-screen w-screen overflow-hidden"
      style={{
        display: "grid",
        gridTemplateColumns: isRailOpen
          ? "48px 1fr 320px"
          : "48px 1fr",
        gridTemplateRows: "1fr",
        background: "var(--qm-bg)",
      }}
    >
      {/* Nav rail — dark sidebar */}
      <nav
        className="flex flex-col items-center gap-4 py-5 px-2"
        style={{
          background: "var(--qm-sidebar-bg)",
          borderRight: "1px solid var(--qm-sidebar-border)",
        }}
      >
        <SidebarIcon label="Close" symbol="✕" />
        <SidebarIcon label="Bookmarks" symbol="★" active />
        <SidebarIcon label="Character" symbol="☻" />
        <SidebarIcon label="Quests" symbol="🔥" />
        <div className="flex-1" />
        <SidebarIcon label="Settings" symbol="⚙" />
      </nav>

      {/* Narrative spine — center, takes remaining space */}
      <main
        className="overflow-hidden"
        style={{
          background: "var(--qm-bg-light)",
          borderRight: isRailOpen ? "1px solid var(--qm-bg-shadow)" : undefined,
        }}
      >
        {narrative}
      </main>

      {/* Character panel — right side, fixed width */}
      {isRailOpen && contextRail && (
        <aside
          className="h-screen overflow-y-auto"
          style={{
            background: "var(--qm-bg)",
            borderLeft: "1px solid var(--qm-bg-shadow)",
          }}
        >
          {contextRail}
        </aside>
      )}
    </div>
  );
}

function SidebarIcon({ label, symbol, active }: { label: string; symbol: string; active?: boolean }) {
  return (
    <button
      title={label}
      className="w-8 h-8 flex items-center justify-center rounded text-sm transition-colors"
      style={{
        color: active ? "var(--qm-sidebar-active)" : "var(--qm-sidebar-text)",
      }}
    >
      {symbol}
    </button>
  );
}
