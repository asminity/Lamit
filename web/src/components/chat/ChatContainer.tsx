"use client";

import React, { useRef, useEffect } from "react";
import { ChatMessageItem, InterruptData } from "@/lib/types";
import { MessageItem } from "./MessageItem";
import { MessageInput } from "./MessageInput";
import { EmptyState } from "./EmptyState";
import { Menu, Sparkles, AlertTriangle, RefreshCw } from "lucide-react";

interface ChatContainerProps {
  threadTitle: string;
  messages: ChatMessageItem[];
  isStreaming: boolean;
  streamingText: string;
  activeTools: string[];
  interrupt: InterruptData | null;
  error: string | null;
  input: string;
  setInput: (value: string) => void;
  onSend: (message: string) => void;
  onStop: () => void;
  onResumeInterrupt: (decision: unknown) => void;
  onToggleSidebar: () => void;
  onSelectPrompt: (prompt: string) => void;
}

export function ChatContainer({
  threadTitle,
  messages,
  isStreaming,
  streamingText,
  activeTools,
  interrupt,
  error,
  input,
  setInput,
  onSend,
  onStop,
  onResumeInterrupt,
  onToggleSidebar,
  onSelectPrompt,
}: ChatContainerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on message or stream updates
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingText, activeTools, isStreaming]);

  const hasMessages = messages.length > 0 || isStreaming;

  return (
    <div className="flex-1 flex flex-col h-screen bg-[#090a0f] overflow-hidden">
      {/* Top Navbar */}
      <header className="h-14 border-b border-white/10 px-4 flex items-center justify-between shrink-0 bg-[#0d0f18]/80 backdrop-blur-md z-10">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={onToggleSidebar}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors"
            title="Toggle sidebar"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2 min-w-0">
            <h2 className="text-sm font-semibold text-white truncate max-w-sm sm:max-w-md">
              {threadTitle || "New Conversation"}
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            PostgreSQL Memory Active
          </span>
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div className="bg-rose-950/70 border-b border-rose-500/30 px-4 py-2 flex items-center justify-between text-xs text-rose-200">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Main Message Scroll Area */}
      <div
        ref={scrollRef}
        id="chat-messages-container"
        className="flex-1 overflow-y-auto overflow-x-hidden flex flex-col"
      >
        {!hasMessages ? (
          <EmptyState onSelectPrompt={onSelectPrompt} />
        ) : (
          <div className="flex-1 py-4 divide-y divide-white/[0.04]">
            {messages.map((msg, index) => (
              <MessageItem key={msg.id || index} message={msg} />
            ))}

            {/* Currently streaming bubble */}
            {isStreaming && (
              <MessageItem
                message={{
                  thread_id: "",
                  role: "assistant",
                  content: streamingText,
                }}
                isStreaming={true}
                activeTools={activeTools}
                interrupt={interrupt}
                onResumeInterrupt={onResumeInterrupt}
              />
            )}

            {/* Interrupted state waiting for resume when not actively streaming text */}
            {!isStreaming && interrupt && (
              <MessageItem
                message={{
                  thread_id: "",
                  role: "assistant",
                  content: "Awaiting your confirmation to proceed:",
                }}
                interrupt={interrupt}
                onResumeInterrupt={onResumeInterrupt}
              />
            )}
          </div>
        )}
      </div>

      {/* Sticky Bottom Input */}
      <div className="shrink-0 pt-2">
        <MessageInput
          input={input}
          setInput={setInput}
          onSend={onSend}
          onStop={onStop}
          isStreaming={isStreaming}
        />
      </div>
    </div>
  );
}
