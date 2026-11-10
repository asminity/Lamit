"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatMessageItem, InterruptData } from "@/lib/types";
import { Copy, Check, Zap, Wrench, ShieldAlert, Maximize2 } from "lucide-react";

interface ThoughtEpochProps {
  message: ChatMessageItem;
  isStreaming?: boolean;
  activeTools?: string[];
  interrupt?: InterruptData | null;
  onResumeInterrupt?: (decision: unknown) => void;
  onSendToCanvas?: (content: string, title?: string) => void;
}

const actionButton =
  "p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors";

export function ThoughtEpoch({
  message,
  isStreaming = false,
  activeTools = [],
  interrupt = null,
  onResumeInterrupt,
  onSendToCanvas,
}: ThoughtEpochProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-[15px] leading-relaxed text-white">
          {message.content}
        </div>
      </div>
    );
  }

  const isCacheHit =
    message.tool_name === "semantic_cache" || message.cached === true;
  const storedTool =
    message.tool_name && message.tool_name !== "semantic_cache"
      ? message.tool_name
      : null;
  const isThinking =
    isStreaming && !message.content && activeTools.length === 0 && !interrupt;

  return (
    <article className="group">
      {/* Tools currently running */}
      {activeTools.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {activeTools.map((tool) => (
            <span
              key={tool}
              className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
              Using {tool}
            </span>
          ))}
        </div>
      )}

      {isThinking && (
        <div className="flex items-center gap-1.5 py-2" aria-label="Thinking">
          <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.3s]" />
          <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.15s]" />
          <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce" />
        </div>
      )}

      {/* Message content */}
      {(message.content || (isStreaming && !isThinking)) && (
        <div className="markdown-body text-[15px]">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
          {isStreaming && <span className="streaming-cursor" />}
        </div>
      )}

      {/* Approval request for a sensitive action */}
      {interrupt && (
        <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-amber-900">
            <ShieldAlert className="w-4 h-4 text-amber-600" />
            Approval needed
          </div>
          <p className="mt-1 text-sm text-amber-900/80">
            {interrupt.question ||
              "Lamit wants to perform this action. Review it before it runs."}
          </p>

          {(interrupt.recipient || interrupt.subject || interrupt.body) && (
            <div className="mt-3 space-y-1.5 rounded-xl border border-amber-200 bg-white p-3 text-sm text-slate-700">
              {interrupt.recipient && (
                <div>
                  <span className="text-slate-500">To: </span>
                  {String(interrupt.recipient)}
                </div>
              )}
              {interrupt.subject && (
                <div>
                  <span className="text-slate-500">Subject: </span>
                  {String(interrupt.subject)}
                </div>
              )}
              {interrupt.body && (
                <div className="mt-1 max-h-40 overflow-y-auto whitespace-pre-wrap border-t border-slate-100 pt-2 text-slate-600">
                  {String(interrupt.body)}
                </div>
              )}
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              onClick={() => onResumeInterrupt?.(true)}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
            >
              Approve
            </button>
            <button
              onClick={() => onResumeInterrupt?.(false)}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
            >
              Reject
            </button>
          </div>
        </div>
      )}

      {/* Footer: badges and actions */}
      {!isStreaming && message.content && (
        <div className="mt-2 flex items-center gap-2">
          {isCacheHit && (
            <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-700">
              <Zap className="w-3 h-3" />
              Cached
              {message.similarity
                ? ` · ${(message.similarity * 100).toFixed(0)}% match`
                : ""}
            </span>
          )}
          {storedTool && (
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
              <Wrench className="w-3 h-3" />
              {storedTool}
            </span>
          )}

          <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
            <button
              onClick={handleCopy}
              className={actionButton}
              title="Copy"
              aria-label="Copy message"
            >
              {copied ? (
                <Check className="w-4 h-4 text-emerald-600" />
              ) : (
                <Copy className="w-4 h-4" />
              )}
            </button>
            {onSendToCanvas && (
              <button
                onClick={() => onSendToCanvas(message.content, "Response")}
                className={actionButton}
                title="Open in canvas"
                aria-label="Open in canvas"
              >
                <Maximize2 className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      )}
    </article>
  );
}
