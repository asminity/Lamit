"use client";

import React, { useRef, useEffect } from "react";
import { Send, Square, Sparkles, Compass } from "lucide-react";

interface MessageInputProps {
  input: string;
  setInput: (value: string) => void;
  onSend: (message: string) => void;
  onStop?: () => void;
  isStreaming: boolean;
  disabled?: boolean;
}

export function MessageInput({
  input,
  setInput,
  onSend,
  onStop,
  isStreaming,
  disabled = false,
}: MessageInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        180
      )}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming && input.trim()) {
        onSend(input);
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isStreaming && input.trim()) {
      onSend(input);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-4">
      <form
        onSubmit={handleSubmit}
        className="relative flex flex-col bg-[#121420]/90 backdrop-blur-xl border border-white/10 rounded-2xl shadow-xl shadow-black/40 focus-within:border-indigo-500/50 transition-all duration-200"
      >
        <div className="flex items-end px-3 py-2.5 gap-2">
          <textarea
            ref={textareaRef}
            id="chat-input-textarea"
            rows={1}
            value={input}
            disabled={disabled}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              disabled
                ? "Select or create a conversation to start chatting..."
                : isStreaming
                ? "Assistant is generating response..."
                : "Ask anything, search the web, check stocks, or find research papers..."
            }
            className="flex-1 bg-transparent text-sm text-zinc-100 placeholder-zinc-500 resize-none focus:outline-none max-h-44 py-1 leading-relaxed"
          />

          {isStreaming ? (
            <button
              id="stop-generating-button"
              type="button"
              onClick={onStop}
              className="p-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition-all active:scale-95 flex items-center justify-center shrink-0"
              title="Stop generating"
            >
              <Square className="w-4 h-4 fill-current" />
            </button>
          ) : (
            <button
              id="send-message-button"
              type="submit"
              disabled={disabled || !input.trim()}
              className={`p-2 rounded-xl transition-all duration-200 flex items-center justify-center shrink-0 ${
                input.trim() && !disabled
                  ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-500/20 hover:from-indigo-500 hover:to-violet-500 active:scale-95"
                  : "bg-white/[0.04] text-zinc-600 cursor-not-allowed"
              }`}
              title="Send message (Enter)"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Footer info pills */}
        <div className="flex items-center justify-between px-3.5 py-1.5 border-t border-white/5 text-[11px] text-zinc-500">
          <div className="flex items-center gap-1.5">
            <Compass className="w-3 h-3 text-indigo-400/80" />
            <span>Tools: DuckDuckGo • Wikipedia • ArXiv • Weather • Stocks • YouTube</span>
          </div>
          <span className="hidden sm:inline">Enter to send • Shift+Enter for newline</span>
        </div>
      </form>
    </div>
  );
}
