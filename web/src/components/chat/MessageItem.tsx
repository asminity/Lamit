"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatMessageItem, InterruptData } from "@/lib/types";
import {
  User,
  Sparkles,
  Copy,
  Check,
  Wrench,
  AlertCircle,
  ShieldCheck,
  CheckCircle2,
  XCircle,
} from "lucide-react";

interface MessageItemProps {
  message: ChatMessageItem;
  isStreaming?: boolean;
  activeTools?: string[];
  interrupt?: InterruptData | null;
  onResumeInterrupt?: (decision: unknown) => void;
}

export function MessageItem({
  message,
  isStreaming = false,
  activeTools = [],
  interrupt = null,
  onResumeInterrupt,
}: MessageItemProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`group flex gap-3.5 py-4 px-4 md:px-6 transition-colors ${
        isUser ? "bg-transparent justify-end" : "bg-white/[0.02]"
      }`}
    >
      <div
        className={`flex gap-3 max-w-3xl w-full ${
          isUser ? "flex-row-reverse" : "flex-row"
        }`}
      >
        {/* Avatar */}
        <div
          className={`w-7 h-7 rounded-lg shrink-0 flex items-center justify-center shadow-md ${
            isUser
              ? "bg-gradient-to-tr from-indigo-500 to-indigo-600 text-white"
              : "bg-gradient-to-tr from-violet-600 to-fuchsia-600 text-white"
          }`}
        >
          {isUser ? <User className="w-4 h-4" /> : <Sparkles className="w-3.5 h-3.5" />}
        </div>

        {/* Content Bubble */}
        <div className={`flex flex-col min-w-0 flex-1 ${isUser ? "items-end" : "items-start"}`}>
          <div className="flex items-center gap-2 mb-1.5 text-[11px] text-zinc-400 font-medium">
            <span>{isUser ? "You" : "Assistant"}</span>
            {!isUser && (
              <button
                onClick={handleCopy}
                className="opacity-0 group-hover:opacity-100 p-1 hover:text-white rounded hover:bg-white/5 transition-all text-zinc-500"
                title="Copy message"
              >
                {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              </button>
            )}
          </div>

          {/* Active Tool Calling Pills */}
          {!isUser && activeTools.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {activeTools.map((tool, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-mono animate-tool-pulse"
                >
                  <Wrench className="w-3 h-3 text-indigo-400 animate-spin" />
                  <span>Executing {tool}...</span>
                </div>
              ))}
            </div>
          )}

          {/* Message Text / Markdown */}
          <div
            className={`text-sm rounded-2xl px-4 py-3 shadow-sm ${
              isUser
                ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-tr-sm"
                : "bg-white/[0.04] border border-white/5 text-zinc-100 rounded-tl-sm w-full"
            }`}
          >
            {isUser ? (
              <p className="whitespace-pre-wrap break-words">{message.content}</p>
            ) : (
              <div className="markdown-body text-zinc-200">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>

                {isStreaming && (
                  <span className="inline-block w-1.5 h-4 ml-1 bg-indigo-400 animate-pulse align-middle" />
                )}
              </div>
            )}
          </div>

          {/* Human-in-the-Loop Interruption Card */}
          {interrupt && onResumeInterrupt && (
            <div className="mt-3 w-full max-w-md p-4 rounded-xl bg-amber-950/30 border border-amber-500/30 backdrop-blur-md">
              <div className="flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h4 className="text-xs font-semibold text-amber-200 uppercase tracking-wider">
                    Approval Required
                  </h4>
                  <p className="text-xs text-amber-100/90 mt-1">
                    {interrupt.question || "The assistant requested approval to execute this action:"}
                  </p>
                  {interrupt.action && (
                    <div className="mt-2 p-2 rounded bg-black/40 border border-amber-500/20 text-[11px] font-mono text-amber-300">
                      Action: {interrupt.action}
                    </div>
                  )}

                  <div className="flex items-center gap-2 mt-3">
                    <button
                      onClick={() => onResumeInterrupt(true)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition-colors shadow-sm"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Approve</span>
                    </button>
                    <button
                      onClick={() => onResumeInterrupt(false)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600/80 hover:bg-rose-600 text-white text-xs font-medium transition-colors shadow-sm"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Reject</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
