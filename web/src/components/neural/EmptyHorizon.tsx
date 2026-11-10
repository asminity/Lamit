"use client";

import React from "react";
import { BookOpen, TrendingUp, Database, Mail } from "lucide-react";

interface EmptyHorizonProps {
  onSelectPrompt: (prompt: string) => void;
}

const suggestions = [
  {
    label: "Find recent research",
    prompt:
      "Search Arxiv and Google Scholar for the most recent breakthroughs in state space models and LLM reasoning architectures.",
    icon: BookOpen,
    tint: "bg-sky-50 text-sky-600",
  },
  {
    label: "Check the markets",
    prompt:
      "Look up the current stock price and key technical trends for NVDA and AAPL, and summarize market sentiment.",
    icon: TrendingUp,
    tint: "bg-emerald-50 text-emerald-600",
  },
  {
    label: "Explain an architecture",
    prompt:
      "How does Lamit's PostgreSQL semantic caching layer compare to Redis or vector databases in latency and consistency?",
    icon: Database,
    tint: "bg-violet-50 text-violet-600",
  },
  {
    label: "Draft an email",
    prompt:
      "Draft a concise project status report email to engineering-team@company.com with human-in-the-loop verification.",
    icon: Mail,
    tint: "bg-amber-50 text-amber-600",
  },
];

export function EmptyHorizon({ onSelectPrompt }: EmptyHorizonProps) {
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="min-h-full max-w-2xl mx-auto px-4 py-10 flex flex-col items-center justify-center">
        <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight text-slate-900 text-center">
          How can I help today?
        </h1>
        <p className="mt-3 text-base text-slate-500 text-center">
          Ask a question, or start with one of these.
        </p>

        <div className="mt-8 w-full grid grid-cols-1 sm:grid-cols-2 gap-3">
          {suggestions.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                onClick={() => onSelectPrompt(item.prompt)}
                className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-left transition hover:border-indigo-300 hover:shadow-md hover:shadow-indigo-100"
              >
                <span className={`shrink-0 rounded-xl p-2 ${item.tint}`}>
                  <Icon className="w-4 h-4" />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-slate-900">
                    {item.label}
                  </span>
                  <span className="mt-0.5 block text-sm text-slate-500 line-clamp-2">
                    {item.prompt}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
