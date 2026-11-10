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
  const bottomRef = useRef<HTMLDivElement>(null);

  // Keep the latest turn in view as tokens stream in
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
    <div className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="max-w-3xl mx-auto px-4 py-6 flex flex-col gap-6">
        {messages.map((msg, idx) => (
          <ThoughtEpoch
            key={msg.id || idx}
            message={msg}
            onSendToCanvas={onSendToCanvas}
          />
        ))}

        {/* Turn currently being generated */}
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
          />
        )}

        {/* Approval request waiting after the stream paused */}
        {!isStreaming && interrupt && (
          <ThoughtEpoch
            message={{ thread_id: "", role: "assistant", content: "" }}
            interrupt={interrupt}
            onResumeInterrupt={onResumeInterrupt}
          />
        )}

        <div ref={bottomRef} className="h-1 shrink-0" />
      </div>
    </div>
  );
}
