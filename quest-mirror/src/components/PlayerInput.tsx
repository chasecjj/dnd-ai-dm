import { useState, useRef, useEffect, type KeyboardEvent } from "react";

interface PlayerInputProps {
  onSubmit: (text: string) => void;
  disabled?: boolean;
  hints?: string[];
}

const DEFAULT_HINTS = ["Look around", "Undo"];

export function PlayerInput({
  onSubmit,
  disabled = false,
  hints = DEFAULT_HINTS,
}: PlayerInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!disabled && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [disabled]);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const trimmed = value.trim();
      if (trimmed.length > 0 && !disabled) {
        onSubmit(trimmed);
        setValue("");
      }
    }
  }

  function handleHint(hint: string) {
    if (!disabled) {
      onSubmit(hint);
    }
  }

  return (
    <div className="mt-6">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        maxLength={2000}
        rows={2}
        placeholder={disabled ? "Awaiting the DM..." : "What do you do?"}
        className="w-full resize-none bg-transparent border-none outline-none text-lg leading-relaxed placeholder:opacity-40"
        style={{
          fontFamily: "var(--qm-font-narrative)",
          color: "var(--qm-text)",
          caretColor: "var(--qm-accent)",
        }}
      />
      <div className="flex gap-2 mt-2">
        {hints.map((hint) => (
          <button
            key={hint}
            type="button"
            onClick={() => handleHint(hint)}
            disabled={disabled}
            className="px-3 py-1 text-xs rounded-full border transition-colors duration-200 hover:bg-[var(--qm-accent-dim)] disabled:opacity-30"
            style={{
              fontFamily: "var(--qm-font-ui)",
              color: "var(--qm-text-dim)",
              borderColor: "var(--qm-border)",
            }}
          >
            {hint}
          </button>
        ))}
      </div>
    </div>
  );
}
