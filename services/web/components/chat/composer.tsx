"use client";

import { Send } from "lucide-react";
import { useRef, useState, useEffect } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function Composer({ onSend, disabled, placeholder }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement | null>(null);

  // Auto-grow textarea
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = Math.min(el.scrollHeight, 240) + "px";
  }, [value]);

  function submit() {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="border-t border-border bg-surface">
      <div className="max-w-3xl mx-auto p-4">
        <div className="flex items-end gap-2 rounded-xl border border-border bg-bg p-2 focus-within:border-primary">
          <textarea
            ref={ref}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder={placeholder || "Ask about customer reviews… (Enter to send, Shift+Enter for newline)"}
            className="flex-1 resize-none bg-transparent outline-none px-2 py-2 text-sm placeholder:text-muted"
            disabled={disabled}
          />
          <button
            onClick={submit}
            disabled={disabled || !value.trim()}
            className="rounded-lg bg-primary text-primary-fg p-2 disabled:opacity-50"
            title="Send"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-muted text-center mt-2">
          Answers are grounded in your review corpus and always cite review IDs.
        </p>
      </div>
    </div>
  );
}
