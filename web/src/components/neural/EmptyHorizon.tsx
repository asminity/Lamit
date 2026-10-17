"use client";

import React from "react";
import {
  Sparkles,
  BookOpen,
  TrendingUp,
  Mail,
  Zap,
  Cpu,
  Layers,
  ArrowRight,
  Database,
  Search,
} from "lucide-react";

interface EmptyHorizonProps {
  onSelectPrompt: (prompt: string) => void;
}

export function EmptyHorizon({ onSelectPrompt }: EmptyHorizonProps) {
  const capabilities = [
    {
      title: "Real-time Multi-Tool Orchestration",
      desc: "Live search via DuckDuckGo & Google, stock telemetry, and real-time meteorology.",
      icon: Search,
      tag: "12 Tools Active",
      accent: "text-cyan-400",
      border: "border-cyan-500/20",
    },
    {
      title: "Scientific Synthesis (Arxiv & Scholar)",
      desc: "Semantic parsing of academic pre-prints, computer science, and physics literature.",
      icon: BookOpen,
      tag: "Arxiv & Scholar",
      accent: "text-indigo-400",
      border: "border-indigo-500/20",
    },
    {
      title: "PostgreSQL Memory & LangGraph Checkpointer",
      desc: "Full conversational state checkpointer with adaptive short-term memory compaction.",
      icon: Database,
      tag: "Async Postgres",
      accent: "text-emerald-400",
      border: "border-emerald-500/20",
    },
    {
      title: "Zero-Latency Semantic Caching",
      desc: "Instant cosine similarity vector cache serving matching queries in under 5ms.",
      icon: Zap,
      tag: "0.88 Cosine Sim",
      accent: "text-violet-400",
      border: "border-violet-500/20",
    },
  ];

  const suggestedInquiries = [
    {
      label: "Research Breakthroughs",
      prompt: "Search Arxiv and Google Scholar for the most recent breakthroughs in state space models and LLM reasoning architectures.",
      category: "Academic",
    },
    {
      label: "Financial Market Analysis",
      prompt: "Look up the current stock price and key technical trends for NVDA and AAPL, and summarize market sentiment.",
      category: "Markets",
    },
    {
      label: "System Architecture",
      prompt: "How does Lamit's PostgreSQL semantic caching layer compare to Redis or vector databases in latency and consistency?",
      category: "Engineering",
    },
    {
      label: "Action Agent Workflow",
      prompt: "Draft a concise project status report email to engineering-team@company.com with human-in-the-loop verification.",
      category: "Action Agent",
    },
  ];

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 md:p-12 max-w-5xl mx-auto overflow-y-auto no-scrollbar relative select-none">
      {/* Background Radial Glow */}
      <div className="absolute top-1/4 w-96 h-96 rounded-full bg-indigo-600/10 blur-[120px] pointer-events-none -z-10 animate-breathing-glow" />
      <div className="absolute bottom-1/4 w-96 h-96 rounded-full bg-cyan-600/10 blur-[120px] pointer-events-none -z-10 animate-breathing-glow" />

      {/* Atmospheric Brand Monolith */}
      <div className="flex flex-col items-center text-center mb-8 sm:mb-12">
        <div className="relative mb-5">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-600/30 via-cyan-500/20 to-violet-600/30 border border-white/10 flex items-center justify-center shadow-[0_0_30px_rgba(99,102,241,0.25)] backdrop-blur-xl">
            <Sparkles className="w-8 h-8 text-cyan-300" />
          </div>
          <span className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full bg-emerald-400 border-2 border-[#06070a] shadow-[0_0_8px_#34d399]" />
        </div>

        <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-white mb-2 font-sans">
          Lamit Neural Workspace
        </h1>
        <p className="text-sm sm:text-base text-zinc-400 max-w-xl leading-relaxed">
          An autonomous cognitive environment powered by LangGraph, PostgreSQL vector persistence, and multi-step reasoning tools.
        </p>
      </div>

      {/* Cognitive Capabilities Matrix */}
      <div className="w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 mb-8">
        {capabilities.map((cap, idx) => {
          const Icon = cap.icon;
          return (
            <div
              key={idx}
              className={`p-4 rounded-2xl bg-[#0d1017]/70 border ${cap.border} backdrop-blur-md flex flex-col justify-between transition-all hover:bg-[#121622]/80 hover:scale-[1.02] shadow-sm`}
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="p-2 rounded-xl bg-white/[0.03] border border-white/[0.05]">
                    <Icon className={`w-4 h-4 ${cap.accent}`} />
                  </div>
                  <span className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider bg-white/[0.03] px-2 py-0.5 rounded-full border border-white/[0.04]">
                    {cap.tag}
                  </span>
                </div>
                <h3 className="text-xs font-semibold text-zinc-200 mb-1.5 font-sans">
                  {cap.title}
                </h3>
                <p className="text-[11px] text-zinc-400 leading-relaxed font-sans">
                  {cap.desc}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Suggested Inquiries */}
      <div className="w-full">
        <div className="flex items-center gap-2 mb-3 px-1 text-xs font-mono uppercase tracking-widest text-zinc-400">
          <Layers className="w-3.5 h-3.5 text-indigo-400" />
          <span>Explore Cognitive Horizons</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {suggestedInquiries.map((item, idx) => (
            <button
              key={idx}
              onClick={() => onSelectPrompt(item.prompt)}
              className="group p-3.5 rounded-xl bg-[#0b0e15]/60 hover:bg-white/[0.04] border border-white/[0.05] hover:border-indigo-500/30 text-left transition-all flex items-center justify-between gap-3 shadow-sm hover:shadow-indigo-500/10"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-mono font-medium text-cyan-400 uppercase tracking-wider">
                    {item.category}
                  </span>
                  <span className="text-xs font-semibold text-zinc-200 group-hover:text-white transition-colors truncate">
                    {item.label}
                  </span>
                </div>
                <p className="text-xs text-zinc-400 truncate font-sans">
                  {item.prompt}
                </p>
              </div>
              <ArrowRight className="w-4 h-4 text-zinc-600 group-hover:text-cyan-400 group-hover:translate-x-1 transition-all shrink-0" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
