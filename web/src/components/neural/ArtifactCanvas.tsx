"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  X,
  Code2,
  Database,
  Layers,
  Copy,
  Check,
  Maximize2,
  Cpu,
  Zap,
  Sparkles,
  Activity,
} from "lucide-react";
import { ChatMessageItem } from "@/lib/types";

interface ArtifactCanvasProps {
  isOpen: boolean;
  onClose: () => void;
  activeArtifactText?: string;
  activeArtifactTitle?: string;
  messages: ChatMessageItem[];
  threadId: string;
}

export function ArtifactCanvas({
  isOpen,
  onClose,
  activeArtifactText = "",
  activeArtifactTitle = "Workspace Canvas",
  messages,
  threadId,
}: ArtifactCanvasProps) {
  const [tab, setTab] = useState<"artifact" | "memory" | "tools">("artifact");
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(activeArtifactText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Extract tools used across messages
  const usedTools = Array.from(
    new Set(
      messages
        .map((m) => m.tool_name)
        .filter((t): t is string => Boolean(t && t !== "semantic_cache"))
    )
  );

  const cacheHitCount = messages.filter(
    (m) => m.tool_name === "semantic_cache" || m.cached
  ).length;

  return (
    <aside className="w-full lg:w-[420px] xl:w-[480px] h-full border-l border-white/[0.08] bg-[#0a0d14]/95 backdrop-blur-2xl flex flex-col z-20 shrink-0 transition-all select-none">
      {/* Top Navigation & Tabs */}
      <div className="h-16 px-4 border-b border-white/[0.06] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-white/[0.03] border border-white/[0.05]">
          <button
            onClick={() => setTab("artifact")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              tab === "artifact"
                ? "bg-indigo-600/25 text-indigo-200 border border-indigo-500/30 shadow-sm"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Code2 className="w-3.5 h-3.5 text-cyan-400" />
            <span>Artifact</span>
          </button>
          <button
            onClick={() => setTab("memory")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              tab === "memory"
                ? "bg-indigo-600/25 text-indigo-200 border border-indigo-500/30 shadow-sm"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Database className="w-3.5 h-3.5 text-emerald-400" />
            <span>Memory</span>
          </button>
          <button
            onClick={() => setTab("tools")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              tab === "tools"
                ? "bg-indigo-600/25 text-indigo-200 border border-indigo-500/30 shadow-sm"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Activity className="w-3.5 h-3.5 text-violet-400" />
            <span>Telemetry</span>
          </button>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 text-zinc-400 hover:text-white rounded-lg hover:bg-white/[0.05] transition-colors"
          title="Close Canvas"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Main Tab Content */}
      <div className="flex-1 overflow-y-auto p-5 no-scrollbar text-zinc-100">
        {tab === "artifact" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
              <div>
                <h3 className="text-sm font-semibold text-white font-sans">
                  {activeArtifactTitle}
                </h3>
                <span className="text-[11px] font-mono text-zinc-400">
                  {activeArtifactText ? `${activeArtifactText.length} characters` : "Empty canvas"}
                </span>
              </div>
              {activeArtifactText && (
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-zinc-300 border border-white/[0.06] transition-colors"
                >
                  {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copied ? "Copied" : "Copy"}</span>
                </button>
              )}
            </div>

            {activeArtifactText ? (
              <div className="markdown-body text-xs leading-relaxed select-text font-sans">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {activeArtifactText}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="py-12 flex flex-col items-center justify-center text-center text-zinc-500">
                <Layers className="w-10 h-10 mb-3 text-zinc-600 stroke-[1.5]" />
                <p className="text-xs font-sans max-w-xs text-zinc-400">
                  No active artifact selected. Click the expand icon on any response in the dialogue stream to inspect it here.
                </p>
              </div>
            )}
          </div>
        )}

        {tab === "memory" && (
          <div className="space-y-4 font-mono text-xs">
            <div className="p-4 rounded-xl bg-black/40 border border-white/[0.06] space-y-3">
              <div className="flex items-center justify-between text-zinc-300">
                <span className="text-zinc-400">PostgreSQL Thread:</span>
                <span className="text-cyan-400 truncate max-w-[200px]">{threadId || "Unset"}</span>
              </div>
              <div className="flex items-center justify-between text-zinc-300">
                <span className="text-zinc-400">Total Turn Epochs:</span>
                <span className="text-white font-bold">{messages.length}</span>
              </div>
              <div className="flex items-center justify-between text-zinc-300">
                <span className="text-zinc-400">Semantic Cache Hits:</span>
                <span className="text-emerald-400 font-bold">{cacheHitCount}</span>
              </div>
              <div className="flex items-center justify-between text-zinc-300">
                <span className="text-zinc-400">Memory Compactor:</span>
                <span className="text-indigo-400">12 Turns Trigger</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-indigo-950/20 border border-indigo-500/20 space-y-2">
              <div className="flex items-center gap-2 text-indigo-300 text-xs font-semibold">
                <Database className="w-3.5 h-3.5" />
                <span>LangGraph StateCheckpointer</span>
              </div>
              <p className="text-[11px] text-zinc-400 font-sans leading-relaxed">
                Conversation turns and memory compression summaries are continuously committed to PostgreSQL tables: <code className="text-indigo-300">checkpoints</code>, <code className="text-indigo-300">checkpoint_blobs</code>, and <code className="text-indigo-300">chat_messages</code>.
              </p>
            </div>
          </div>
        )}

        {tab === "tools" && (
          <div className="space-y-4 font-mono text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
              <span className="text-xs text-zinc-400 uppercase tracking-wider">Tool Registry</span>
              <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                All Systems Operational
              </span>
            </div>

            <div className="space-y-2">
              {[
                { name: "Google & DuckDuckGo Search", desc: "Live web indexing & facts", tag: "Web" },
                { name: "Arxiv & Google Scholar", desc: "Academic literature synthesis", tag: "Research" },
                { name: "Yahoo Finance", desc: "Real-time ticker metrics & history", tag: "Market" },
                { name: "Open-Meteo Meteorology", desc: "Lat/long & global forecast", tag: "Weather" },
                { name: "Gmail Action Bridge", desc: "Human-in-the-loop email gate", tag: "HITL Action" },
              ].map((tool, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] flex items-center justify-between gap-3"
                >
                  <div>
                    <h4 className="text-xs font-semibold text-zinc-200">{tool.name}</h4>
                    <p className="text-[10px] text-zinc-400 font-sans">{tool.desc}</p>
                  </div>
                  <span className="text-[10px] text-zinc-400 bg-white/[0.04] px-2 py-0.5 rounded border border-white/[0.06] shrink-0">
                    {tool.tag}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
