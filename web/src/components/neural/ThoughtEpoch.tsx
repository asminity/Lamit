"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatMessageItem, InterruptData } from "@/lib/types";
import {
  Sparkles,
  User,
  Copy,
  Check,
  Zap,
  Wrench,
  ShieldAlert,
  ArrowRight,
  Maximize2,
  Terminal,
  Clock,
  Send,
  XCircle,
  CheckCircle2,
} from "lucide-react";

interface ThoughtEpochProps {
  message: ChatMessageItem;
  isStreaming?: boolean;
  activeTools?: string[];
  interrupt?: InterruptData | null;
  onResumeInterrupt?: (decision: unknown) => void;
  onSendToCanvas?: (content: string, title?: string) => void;
}

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

  const isCacheHit =
    message.tool_name === "semantic_cache" || message.cached === true;

  return (
    <article
      className={`group relative py-7 px-4 sm:px-8 md:px-12 transition-all ${
        isUser
          ? "bg-transparent"
          : "bg-[#090b12]/50 border-y border-white/[0.03] backdrop-blur-sm"
      }`}
    >
      <div className="max-w-4xl mx-auto flex gap-4 md:gap-6">
        {/* Entity Indicator Icon */}
        <div className="shrink-0 pt-0.5">
          {isUser ? (
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-500/20 to-indigo-600/20 border border-indigo-500/30 text-indigo-300 flex items-center justify-center shadow-inner">
              <User className="w-4 h-4" />
            </div>
          ) : (
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-500/20 via-indigo-500/20 to-violet-500/20 border border-cyan-500/30 text-cyan-300 flex items-center justify-center shadow-[0_0_15px_rgba(6,182,212,0.15)]">
              <Sparkles className="w-4 h-4 text-cyan-400" />
            </div>
          )}
        </div>

        {/* Content Body */}
        <div className="flex-1 min-w-0">
          {/* Epoch Header Meta */}
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2.5">
              <span className="text-xs font-semibold tracking-wide uppercase font-mono text-zinc-300">
                {isUser ? "You" : "Lamit Neural"}
              </span>

              {/* Cache Hit Badge */}
              {!isUser && isCacheHit && (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-cyan-500/10 text-cyan-300 border border-cyan-500/25 shadow-[0_0_8px_rgba(6,182,212,0.15)]">
                  <Zap className="w-2.5 h-2.5 fill-cyan-400 text-cyan-400" />
                  Semantic Cache Hit
                  {message.similarity ? ` (${(message.similarity * 100).toFixed(1)}% match)` : ""}
                </span>
              )}

              {/* Tool Execution Badge (Stored) */}
              {!isUser && message.tool_name && message.tool_name !== "semantic_cache" && (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono text-indigo-300 bg-indigo-500/10 border border-indigo-500/20">
                  <Wrench className="w-2.5 h-2.5 text-indigo-400" />
                  Executed {message.tool_name}
                </span>
              )}
            </div>

            {/* Quick Actions */}
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              {onSendToCanvas && !isUser && message.content && (
                <button
                  onClick={() => onSendToCanvas(message.content, "Synthesized Knowledge")}
                  className="p-1.5 text-zinc-400 hover:text-white rounded-lg hover:bg-white/[0.05] transition-colors"
                  title="Open in Workspace Canvas"
                >
                  <Maximize2 className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                onClick={handleCopy}
                className="p-1.5 text-zinc-400 hover:text-white rounded-lg hover:bg-white/[0.05] transition-colors"
                title="Copy contents"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          {/* Active Tool Calling Matrix (Live Stream) */}
          {!isUser && activeTools.length > 0 && (
            <div className="flex flex-wrap gap-2 my-3 p-3 rounded-xl bg-indigo-950/30 border border-indigo-500/20">
              <span className="text-[11px] font-mono text-indigo-300 flex items-center gap-2 w-full mb-1">
                <Terminal className="w-3.5 h-3.5 text-indigo-400 animate-pulse" />
                Orchestrating multi-step tools:
              </span>
              {activeTools.map((tool, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 px-3 py-1 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-200 text-xs font-mono animate-pulse"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                  <span>Invoking {tool}...</span>
                </div>
              ))}
            </div>
          )}

          {/* Human-In-The-Loop Interrupt Approval Gate */}
          {interrupt && (
            <div className="my-4 rounded-2xl bg-amber-950/20 border border-amber-500/30 p-5 shadow-2xl relative overflow-hidden backdrop-blur-md">
              <div className="absolute top-0 right-0 p-3 opacity-15">
                <ShieldAlert className="w-20 h-20 text-amber-400" />
              </div>
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 shrink-0">
                  <ShieldAlert className="w-5 h-5" />
                </div>
                <div className="flex-1">
                  <h4 className="text-sm font-semibold text-amber-200 uppercase tracking-wider font-mono">
                    Security Clearance Required
                  </h4>
                  <p className="text-xs text-zinc-300 mt-1">
                    {interrupt.question || "Lamit is requesting authorization before executing a sensitive outbound action:"}
                  </p>

                  {/* Interrupt Manifest Preview */}
                  <div className="mt-3 p-3 rounded-xl bg-black/50 border border-white/10 font-mono text-xs space-y-1.5 text-zinc-300">
                    {interrupt.recipient && (
                      <div>
                        <span className="text-zinc-500">Recipient: </span>
                        <span className="text-white">{String(interrupt.recipient)}</span>
                      </div>
                    )}
                    {interrupt.subject && (
                      <div>
                        <span className="text-zinc-500">Subject: </span>
                        <span className="text-white">{String(interrupt.subject)}</span>
                      </div>
                    )}
                    {interrupt.body && (
                      <div className="pt-1 text-zinc-400 whitespace-pre-wrap max-h-36 overflow-y-auto border-t border-white/5 mt-1">
                        {String(interrupt.body)}
                      </div>
                    )}
                  </div>

                  {/* Dual Tactical Decision Buttons */}
                  <div className="mt-4 flex items-center gap-3">
                    <button
                      onClick={() => onResumeInterrupt?.(true)}
                      className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-500/20 transition-all hover:scale-105 active:scale-95"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Authorize & Execute</span>
                    </button>
                    <button
                      onClick={() => onResumeInterrupt?.(false)}
                      className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.05] hover:bg-rose-500/20 border border-white/10 hover:border-rose-500/40 text-zinc-300 hover:text-rose-300 text-xs font-medium transition-all"
                    >
                      <XCircle className="w-4 h-4" />
                      <span>Reject & Cancel</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Main Message Content */}
          <div className="markdown-body text-zinc-100 text-sm leading-relaxed font-sans">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
            {isStreaming && <span className="streaming-cursor" />}
          </div>
        </div>
      </div>
    </article>
  );
}
