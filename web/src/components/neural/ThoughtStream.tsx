"use client";

import React, { useRef, useEffect } from "react";
import { ChatMessageItem, InterruptData } from "@/lib/types";
import { ThoughtEpoch } from "./ThoughtEpoch";
import { EmptyHorizon } from "./EmptyHorizon";

interface ThoughtStreamProps {
  messages: ChatMessageItem[];
  isStreaming: boolean;
  streamingText: string;
  activeTools: string[];
  interrupt: InterruptData | null;
  onResumeInterrupt: (decision: unknown) => void;
  onSelectPrompt: (prompt: string) => void;
  onSendToCanvas?: (content: string, title?: string) => void;
}

export function ThoughtStream({
  messages,
  isStreaming,
  streamingText,
  activeTools,
  interrupt,
  onResumeInterrupt,
  onSelectPrompt,
  onSendToCanvas,
}: ThoughtStreamProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest turn as tokens stream in
  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, streamingText, activeTools, isStreaming]);

  const hasMessages = messages.length > 0 || isStreaming;

  if (!hasMessages) {
    return <EmptyHorizon onSelectPrompt={onSelectPrompt} />;
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto overflow-x-hidden flex flex-col divide-y divide-white/[0.02]"
    >
      {/* Historical Turns */}
      {messages.map((msg, idx) => (
        <ThoughtEpoch
          key={msg.id || idx}
          message={msg}
          onSendToCanvas={onSendToCanvas}
        />
      ))}

      {/* Active Streaming Turn */}
      {isStreaming && (
        <ThoughtEpoch
          message={{
            thread_id: "",
            role: "assistant",
            content: streamingText,
          }}
          isStreaming={true}
          activeTools={activeTools}
          interrupt={interrupt}
          onResumeInterrupt={onResumeInterrupt}
          onSendToCanvas={onSendToCanvas}
        />
      )}

      {/* Waiting Interrupt Approval (when not streaming new tokens) */}
      {!isStreaming && interrupt && (
        <ThoughtEpoch
          message={{
            thread_id: "",
            role: "assistant",
            content: "Action halted pending security clearance confirmation:",
          }}
          interrupt={interrupt}
          onResumeInterrupt={onResumeInterrupt}
        />
      )}

      <div ref={bottomRef} className="h-4 shrink-0" />
    </div>
  );
}
