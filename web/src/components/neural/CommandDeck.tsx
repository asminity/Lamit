"use client";

import React, { useRef, useEffect, useState } from "react";
import {
  ArrowUp,
  Square,
  Globe,
  BookOpen,
  Mail,
  TrendingUp,
  CloudSun,
  Sparkles,
  Cpu,
  Layers,
} from "lucide-react";
import { CognitiveMode } from "@/lib/types";

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
  const [mode, setMode] = useState<CognitiveMode>("inference");

  // Auto-resize textarea smoothly
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const newHeight = Math.min(textareaRef.current.scrollHeight, 180);
      textareaRef.current.style.height = `${newHeight}px`;
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

  const handleApplyPreset = (prefix: string) => {
    setInput(prefix);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto px-4 pb-5 pt-2 relative z-20">
      {/* Floating Tactical Console Body */}
      <div className="relative rounded-2xl bg-[#0e111a]/90 backdrop-blur-2xl border border-white/[0.08] shadow-[0_12px_40px_rgba(0,0,0,0.6)] transition-all focus-within:border-indigo-500/40 focus-within:shadow-[0_12px_50px_rgba(99,102,241,0.15)] overflow-hidden">
        {/* Subtle Ambient Top Accent Glow */}
        <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-indigo-500/50 to-transparent" />

        {/* Tactical Header Ribbon: Cognitive Modes & Tool Sensors */}
        <div className="flex items-center justify-between px-3.5 pt-2.5 pb-1 border-b border-white/[0.04]">
          {/* Cognitive Mode Switches */}
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setMode("inference")}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all ${
                mode === "inference"
                  ? "bg-white/[0.08] text-white shadow-sm"
                  : "text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.03]"
              }`}
            >
              <Cpu className="w-3 h-3 text-cyan-400" />
              <span>Inference</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setMode("research");
                if (!input.trim()) handleApplyPreset("Search scholar and arxiv for ");
              }}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all ${
                mode === "research"
                  ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                  : "text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.03]"
              }`}
            >
              <Globe className="w-3 h-3 text-indigo-400" />
              <span>Deep Research</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setMode("actions");
                if (!input.trim()) handleApplyPreset("Draft an email to ");
              }}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all ${
                mode === "actions"
                  ? "bg-violet-600/20 text-violet-300 border border-violet-500/30"
                  : "text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.03]"
              }`}
            >
              <Mail className="w-3 h-3 text-violet-400" />
              <span>Action Agent</span>
            </button>
          </div>

          {/* Active Tools Signal */}
          <div className="hidden sm:flex items-center gap-2 text-[10px] font-mono text-zinc-500">
            {isStreaming && activeTools.length > 0 ? (
              <span className="flex items-center gap-1.5 text-cyan-400">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
                Active: {activeTools.join(", ")}
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <span>12 Tools Ready</span>
                <span className="text-zinc-600">•</span>
                <span>Semantic Cache</span>
              </span>
            )}
          </div>
        </div>

        {/* Input Area */}
        <div className="p-3.5 flex items-end gap-3">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              mode === "research"
                ? "Inquire deep research (Arxiv, Google Scholar, DuckDuckGo, Financial markets)..."
                : mode === "actions"
                ? "Command action agent (e.g., Draft email with human-in-the-loop verification)..."
                : "Ask Lamit anything, explore a hypothesis, or orchestrate complex tasks..."
            }
            rows={1}
            disabled={isStreaming}
            className="flex-1 bg-transparent border-0 outline-none resize-none text-sm text-zinc-100 placeholder:text-zinc-600 focus:ring-0 leading-relaxed max-h-44 disabled:opacity-50"
          />

          {/* Action Trigger / Waveform */}
          <div className="flex items-center gap-1.5 shrink-0">
            {isStreaming ? (
              <button
                type="button"
                onClick={onStop}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 text-rose-300 text-xs font-medium transition-all group"
                title="Halt current generation"
              >
                <Square className="w-3.5 h-3.5 fill-rose-400 text-rose-400 group-hover:scale-110 transition-transform" />
                <span className="hidden sm:inline">Halt</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={() => {
                  if (input.trim()) onSend(input);
                }}
                disabled={!input.trim()}
                className={`p-2.5 rounded-xl transition-all flex items-center justify-center ${
                  input.trim()
                    ? "bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-500 text-white shadow-lg shadow-indigo-500/25 hover:scale-105 active:scale-95"
                    : "bg-white/[0.04] text-zinc-600 cursor-not-allowed"
                }`}
                title="Transmit prompt (Enter)"
              >
                <ArrowUp className="w-4 h-4 stroke-[2.5]" />
              </button>
            )}
          </div>
        </div>

        {/* Bottom Contextual Catalyst Badges */}
        {!input.trim() && !isStreaming && (
          <div className="px-3.5 pb-2.5 pt-0.5 flex items-center gap-1.5 overflow-x-auto text-[11px] text-zinc-500 no-scrollbar">
            <span className="text-zinc-600 font-mono text-[10px] shrink-0 uppercase tracking-wider">Quick:</span>
            <button
              type="button"
              onClick={() => handleApplyPreset("What is the latest stock price and performance of AAPL?")}
              className="px-2 py-0.5 rounded-md bg-white/[0.03] hover:bg-white/[0.06] text-zinc-400 hover:text-zinc-200 border border-white/[0.04] transition-colors shrink-0 flex items-center gap-1"
            >
              <TrendingUp className="w-3 h-3 text-emerald-400" />
              AAPL Price
            </button>
            <button
              type="button"
              onClick={() => handleApplyPreset("Search arxiv for quantum computing breakthroughs in 2025")}
              className="px-2 py-0.5 rounded-md bg-white/[0.03] hover:bg-white/[0.06] text-zinc-400 hover:text-zinc-200 border border-white/[0.04] transition-colors shrink-0 flex items-center gap-1"
            >
              <BookOpen className="w-3 h-3 text-cyan-400" />
              Quantum Arxiv
            </button>
            <button
              type="button"
              onClick={() => handleApplyPreset("Check the current weather in Tokyo and forecast")}
              className="px-2 py-0.5 rounded-md bg-white/[0.03] hover:bg-white/[0.06] text-zinc-400 hover:text-zinc-200 border border-white/[0.04] transition-colors shrink-0 flex items-center gap-1"
            >
              <CloudSun className="w-3 h-3 text-amber-400" />
              Tokyo Weather
            </button>
            <button
              type="button"
              onClick={() => handleApplyPreset("Explain how semantic caching with vector similarity works in LangGraph")}
              className="px-2 py-0.5 rounded-md bg-white/[0.03] hover:bg-white/[0.06] text-zinc-400 hover:text-zinc-200 border border-white/[0.04] transition-colors shrink-0 flex items-center gap-1"
            >
              <Sparkles className="w-3 h-3 text-violet-400" />
              Semantic Cache
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
