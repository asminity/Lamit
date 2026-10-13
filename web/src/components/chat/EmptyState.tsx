"use client";

import React from "react";
import { Sparkles, CloudSun, TrendingUp, BookOpen, Globe, Search } from "lucide-react";

interface EmptyStateProps {
  onSelectPrompt: (prompt: string) => void;
}

export function EmptyState({ onSelectPrompt }: EmptyStateProps) {
  const suggestions = [
    {
      icon: CloudSun,
      title: "Real-time Weather",
      prompt: "What is the current weather in Tokyo today?",
      tag: "get_weather",
    },
    {
      icon: TrendingUp,
      title: "Market Stock Prices",
      prompt: "What is the latest stock price and performance for Apple (AAPL)?",
      tag: "stock_price",
    },
    {
      icon: BookOpen,
      title: "ArXiv Research",
      prompt: "Search ArXiv for recent papers on LLM multi-agent architectures and summarize.",
      tag: "arxiv_search",
    },
    {
      icon: Globe,
      title: "Wikipedia Knowledge",
      prompt: "Summarize the history and architecture of the James Webb Space Telescope from Wikipedia.",
      tag: "wikipedia",
    },
  ];

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 max-w-2xl mx-auto text-center">
      <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-500 via-violet-600 to-fuchsia-500 flex items-center justify-center shadow-xl shadow-indigo-500/20 mb-4 animate-bounce-subtle">
        <Sparkles className="w-6 h-6 text-white" />
      </div>

      <h2 className="text-xl font-bold text-white tracking-tight">
        How can I help you today?
      </h2>
      <p className="text-xs text-zinc-400 mt-1.5 max-w-md leading-relaxed">
        Equipped with 12 real-time tools, PostgreSQL memory checkpointing, and short-term conversation summarization.
      </p>

      {/* Suggested prompts grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-8 w-full text-left">
        {suggestions.map((item, idx) => {
          const Icon = item.icon;
          return (
            <button
              key={idx}
              onClick={() => onSelectPrompt(item.prompt)}
              className="group p-3.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.06] border border-white/5 hover:border-indigo-500/30 transition-all duration-200 text-left active:scale-[0.98]"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <div className="p-1 rounded-md bg-indigo-500/10 text-indigo-400 group-hover:text-indigo-300">
                  <Icon className="w-3.5 h-3.5" />
                </div>
                <span className="text-xs font-semibold text-zinc-200 group-hover:text-white">
                  {item.title}
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 line-clamp-2 leading-relaxed">
                {item.prompt}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
