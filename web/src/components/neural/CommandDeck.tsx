"use client";

import React, { useRef, useEffect } from "react";
import { ArrowUp, Square } from "lucide-react";

interface CommandDeckProps {
  input: string;
  setInput: (value: string) => void;
  onSend: (message: string) => void;
  onStop: () => void;
  isStreaming: boolean;
  activeTools?: string[];
}

export function CommandDeck({
  input,
  setInput,
  onSend,
  onStop,
  isStreaming,
  activeTools = [],
}: CommandDeckProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea to fit its content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const newHeight = Math.min(textareaRef.current.scrollHeight, 180);
      textareaRef.current.style.height = `${newHeight}px`;
    }
  }, [input]);

  const canSend = Boolean(input.trim()) && !isStreaming;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend) onSend(input);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-4 pt-2">
      <div className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-white py-2 pl-4 pr-2 shadow-sm transition focus-within:border-indigo-400 focus-within:ring-4 focus-within:ring-indigo-100">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message Lamit…"
          aria-label="Message"
          rows={1}
          disabled={isStreaming}
          className="flex-1 resize-none bg-transparent py-2 text-base text-slate-900 placeholder:text-slate-400 outline-none leading-relaxed max-h-44 disabled:opacity-60"
        />

        {isStreaming ? (
          <button
            type="button"
            onClick={onStop}
            className="shrink-0 flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-white hover:bg-slate-700 transition-colors"
            title="Stop generating"
            aria-label="Stop generating"
          >
            <Square className="w-3.5 h-3.5 fill-current" />
          </button>
        ) : (
          <button
            type="button"
            onClick={() => {
              if (canSend) onSend(input);
            }}
            disabled={!canSend}
            className="shrink-0 flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white transition-colors hover:bg-indigo-500 disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed"
            title="Send (Enter)"
            aria-label="Send message"
          >
            <ArrowUp className="w-4 h-4 stroke-[2.5]" />
          </button>
        )}
      </div>

      <p className="mt-2 text-center text-xs text-slate-400">
        {isStreaming && activeTools.length > 0
          ? `Using ${activeTools.join(", ")}…`
          : "Enter to send · Shift + Enter for a new line"}
      </p>
    </div>
  );
}
