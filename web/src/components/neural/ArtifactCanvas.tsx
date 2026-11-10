"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { X, Copy, Check } from "lucide-react";
import { ChatMessageItem } from "@/lib/types";

interface ArtifactCanvasProps {
  isOpen: boolean;
  onClose: () => void;
  activeArtifactText?: string;
  activeArtifactTitle?: string;
  messages: ChatMessageItem[];
  threadId: string;
}

type Tab = "content" | "session";

export function ArtifactCanvas({
  isOpen,
  onClose,
  activeArtifactText = "",
  activeArtifactTitle = "Canvas",
  messages,
  threadId,
}: ArtifactCanvasProps) {
  const [tab, setTab] = useState<Tab>("content");
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(activeArtifactText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

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

  const tabClass = (value: Tab) =>
    `rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
      tab === value
        ? "bg-white text-slate-900 shadow-sm"
        : "text-slate-500 hover:text-slate-900"
    }`;

  return (
    <aside className="w-full lg:w-[420px] xl:w-[480px] h-full shrink-0 border-l border-slate-200 bg-white flex flex-col">
      <div className="h-14 shrink-0 border-b border-slate-200 px-4 flex items-center justify-between">
        <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1">
          <button onClick={() => setTab("content")} className={tabClass("content")}>
            Content
          </button>
          <button onClick={() => setTab("session")} className={tabClass("session")}>
            Session
          </button>
        </div>

        <button
          onClick={onClose}
          className="p-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors"
          title="Close canvas"
          aria-label="Close canvas"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        {tab === "content" &&
          (activeArtifactText ? (
            <>
              <div className="mb-4 flex items-center justify-between gap-3">
                <h3 className="text-base font-semibold text-slate-900 truncate">
                  {activeArtifactTitle}
                </h3>
                <button
                  onClick={handleCopy}
                  className="shrink-0 flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  {copied ? (
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
              <div className="markdown-body text-sm">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {activeArtifactText}
                </ReactMarkdown>
              </div>
            </>
          ) : (
            <p className="py-16 text-center text-sm text-slate-500">
              Nothing here yet. Hover a response and choose “Open in canvas” to
              read it side by side.
            </p>
          ))}

        {tab === "session" && (
          <dl className="divide-y divide-slate-100 text-sm">
            <div className="flex items-center justify-between gap-4 py-3">
              <dt className="text-slate-500">Messages</dt>
              <dd className="font-medium text-slate-900">{messages.length}</dd>
            </div>
            <div className="flex items-center justify-between gap-4 py-3">
              <dt className="text-slate-500">Cached answers</dt>
              <dd className="font-medium text-slate-900">{cacheHitCount}</dd>
            </div>
            <div className="flex items-start justify-between gap-4 py-3">
              <dt className="text-slate-500 shrink-0">Tools used</dt>
              <dd className="font-medium text-slate-900 text-right">
                {usedTools.length > 0 ? usedTools.join(", ") : "None yet"}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4 py-3">
              <dt className="text-slate-500 shrink-0">Thread ID</dt>
              <dd className="font-mono text-xs text-slate-600 truncate">
                {threadId || "Not started"}
              </dd>
            </div>
          </dl>
        )}
      </div>
    </aside>
  );
}
