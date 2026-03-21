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
    <div className="flex h-screen w-screen overflow-hidden bg-[var(--qm-bg)]">
      <main
        className="flex-1 overflow-y-auto transition-all duration-500"
        style={{
          maxWidth: isRailOpen ? "var(--qm-spine-width)" : "100%",
          margin: "0 auto",
        }}
      >
        {narrative}
      </main>
      {isRailOpen && contextRail && (
        <aside
          className="h-screen overflow-y-auto border-l border-[var(--qm-border)]"
          style={{
            width: "var(--qm-rail-width)",
            background: "var(--qm-surface-glass)",
            backdropFilter: `blur(var(--qm-blur))`,
          }}
        >
          {contextRail}
        </aside>
      )}
    </div>
  );
}
