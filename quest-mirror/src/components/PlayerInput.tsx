import { useState, useRef, useEffect, type KeyboardEvent } from "react";

interface Props {
  onSubmit: (text: string) => void;
  disabled?: boolean;
  characterName?: string;
}

const HINT_CHIPS = [
  { label: "\u23EA Undo last", value: "Undo last" },
  { label: "\uD83D\uDD0D Survey the room", value: "Survey the room" },
  { label: "\uD83C\uDFB2 Cast the bones", value: "Cast the bones" },
];

export function PlayerInput({
  onSubmit,
  disabled = false,
  characterName = "your character",
}: Props) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!disabled && inputRef.current) {
      inputRef.current.focus();
    }
  }, [disabled]);

  function submit() {
    const trimmed = value.trim();
    if (trimmed.length > 0 && !disabled) {
      onSubmit(trimmed);
      setValue("");
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function handleChip(chipValue: string) {
    if (!disabled) {
      onSubmit(chipValue);
    }
  }

  return (
    <div style={{ padding: "0.75rem 0 0.5rem" }}>
      {/* Input row: textarea + send button */}
      <div style={{ display: "flex", alignItems: "flex-end", gap: "0.75rem" }}>
        <textarea
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          maxLength={2000}
          rows={2}
          placeholder={
            disabled
              ? "Awaiting the DM\u2019s narration\u2026"
              : `What does ${characterName} do next?`
          }
          style={{
            flex: 1,
            resize: "none",
            background: "transparent",
            border: "none",
            borderBottom: "1px solid var(--qm-border-subtle, rgba(139,26,26,0.2))",
            outline: "none",
            fontFamily: "var(--qm-font-narrative)",
            fontStyle: "italic",
            fontSize: "1.1rem",
            lineHeight: 1.6,
            color: "var(--qm-text)",
            caretColor: "var(--qm-accent, #8b1a1a)",
            padding: "0.5rem 0.25rem",
          }}
        />

        {/* Circular send button */}
        <button
          type="button"
          onClick={submit}
          disabled={disabled || value.trim().length === 0}
          aria-label="Send"
          style={{
            width: "2.5rem",
            height: "2.5rem",
            minWidth: "2.5rem",
            borderRadius: "50%",
            border: "none",
            background: "var(--qm-accent, #8b1a1a)",
            color: "var(--qm-bg, #f5f0e8)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: disabled || value.trim().length === 0 ? "default" : "pointer",
            opacity: disabled || value.trim().length === 0 ? 0.35 : 1,
            transition: "opacity 200ms ease, transform 150ms ease",
            fontSize: "1.1rem",
            flexShrink: 0,
            marginBottom: "0.35rem",
          }}
          onMouseEnter={(e) => {
            if (!disabled && value.trim().length > 0) {
              (e.currentTarget as HTMLButtonElement).style.transform = "scale(1.08)";
            }
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.transform = "scale(1)";
          }}
        >
          <span style={{ lineHeight: 1 }}>{"\u25B6"}</span>
        </button>
      </div>

      {/* Hint chips */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.25rem",
          marginTop: "0.5rem",
          fontFamily: "var(--qm-font-ui)",
          fontSize: "0.75rem",
          color: "var(--qm-text-dim, rgba(80,60,40,0.5))",
          userSelect: "none",
        }}
      >
        {HINT_CHIPS.map((chip, idx) => (
          <span key={chip.value} style={{ display: "inline-flex", alignItems: "center" }}>
            {idx > 0 && (
              <span
                style={{
                  margin: "0 0.35rem",
                  opacity: 0.4,
                }}
              >
                {"\u00B7"}
              </span>
            )}
            <button
              type="button"
              onClick={() => handleChip(chip.value)}
              disabled={disabled}
              style={{
                background: "none",
                border: "none",
                padding: "0.15rem 0.2rem",
                fontFamily: "inherit",
                fontSize: "inherit",
                color: "inherit",
                cursor: disabled ? "default" : "pointer",
                opacity: disabled ? 0.35 : 1,
                transition: "color 150ms ease",
                borderRadius: "0.25rem",
              }}
              onMouseEnter={(e) => {
                if (!disabled) {
                  (e.currentTarget as HTMLButtonElement).style.color =
                    "var(--qm-accent, #8b1a1a)";
                }
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.color = "inherit";
              }}
            >
              {chip.label}
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}
