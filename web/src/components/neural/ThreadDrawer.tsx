"use client";

import React, { useState, useMemo, useEffect } from "react";
import { ThreadItem } from "@/lib/types";
import {
  X,
  Search,
  Plus,
  Trash2,
  Clock,
  Sparkles,
  Database,
  ArrowRight,
  MessageSquare,
  Compass,
} from "lucide-react";

interface ThreadDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  threads: ThreadItem[];
  activeThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  onNewThread: () => void;
  onDeleteThread: (threadId: string) => void;
}

export function ThreadDrawer({
  isOpen,
  onClose,
  threads,
  activeThreadId,
  onSelectThread,
  onNewThread,
  onDeleteThread,
}: ThreadDrawerProps) {
  const [search, setSearch] = useState("");
  const [threadToDelete, setThreadToDelete] = useState<string | null>(null);

  // Keyboard shortcut: Escape to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Filter threads by search term
  const filteredThreads = useMemo(() => {
    if (!search.trim()) return threads;
    const q = search.toLowerCase();
    return threads.filter((t) => t.title.toLowerCase().includes(q));
  }, [threads, search]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex select-none">
      {/* Backdrop */}
      <div
        onClick={onClose}
        className="fixed inset-0 bg-black/75 backdrop-blur-md transition-opacity animate-fade-in"
      />

      {/* Slide-over Drawer Panel */}
      <div className="relative w-full max-w-md sm:max-w-lg h-full bg-[#0a0d14] border-r border-white/[0.08] shadow-2xl flex flex-col z-10 overflow-hidden">
        {/* Drawer Header */}
        <div className="h-16 px-5 border-b border-white/[0.06] flex items-center justify-between shrink-0 bg-[#0d1018]/80">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Compass className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white tracking-wide uppercase font-mono">
                Thread Constellation
              </h2>
              <span className="text-[10px] text-zinc-500 font-mono">
                {threads.length} {threads.length === 1 ? "Conversation" : "Conversations"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                onNewThread();
                onClose();
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white text-xs font-semibold shadow-lg shadow-indigo-500/20 transition-all hover:scale-105 active:scale-95"
            >
              <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
              <span>New Horizon</span>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-zinc-400 hover:text-white rounded-lg hover:bg-white/[0.05] transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="p-4 border-b border-white/[0.04]">
          <div className="flex items-center gap-2.5 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.06] focus-within:border-indigo-500/40 transition-colors">
            <Search className="w-4 h-4 text-zinc-500 shrink-0" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search conversations by title or topic..."
              className="bg-transparent text-xs text-zinc-100 placeholder:text-zinc-600 outline-none w-full font-sans"
              autoFocus
            />
            {search && (
              <button
                onClick={() => setSearch("")}
                className="text-zinc-500 hover:text-zinc-300 text-xs"
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {/* Thread List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2 no-scrollbar">
          {filteredThreads.length === 0 ? (
            <div className="py-16 text-center text-zinc-500 text-xs">
              <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-30 text-zinc-400" />
              <p>No conversations found matching &quot;{search}&quot;</p>
            </div>
          ) : (
            filteredThreads.map((thread) => {
              const isActive = thread.thread_id === activeThreadId;
              const isDeleting = threadToDelete === thread.thread_id;

              return (
                <div
                  key={thread.thread_id}
                  className={`group relative p-3 rounded-xl border transition-all flex items-center justify-between gap-3 ${
                    isActive
                      ? "bg-indigo-600/15 border-indigo-500/40 text-white shadow-sm"
                      : "bg-white/[0.02] hover:bg-white/[0.05] border-white/[0.04] text-zinc-300"
                  }`}
                >
                  <button
                    onClick={() => {
                      onSelectThread(thread.thread_id);
                      onClose();
                    }}
                    className="flex-1 text-left min-w-0"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          isActive ? "bg-cyan-400 animate-pulse" : "bg-zinc-600"
                        }`}
                      />
                      <h3 className="text-xs font-semibold truncate font-sans">
                        {thread.title || "Untitled Conversation"}
                      </h3>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-zinc-500 font-mono">
                      <Clock className="w-2.5 h-2.5" />
                      <span>
                        {thread.updated_at
                          ? new Date(thread.updated_at).toLocaleDateString(undefined, {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : "Active"}
                      </span>
                    </div>
                  </button>

                  {/* Actions */}
                  <div className="flex items-center gap-1 shrink-0">
                    {isDeleting ? (
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => {
                            onDeleteThread(thread.thread_id);
                            setThreadToDelete(null);
                          }}
                          className="px-2 py-0.5 rounded bg-rose-600 text-white text-[10px] font-bold"
                        >
                          Confirm
                        </button>
                        <button
                          onClick={() => setThreadToDelete(null)}
                          className="px-2 py-0.5 rounded bg-white/10 text-zinc-300 text-[10px]"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setThreadToDelete(thread.thread_id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1.5 text-zinc-500 hover:text-rose-400 rounded-lg hover:bg-white/5 transition-opacity"
                        title="Delete thread"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Bottom Drawer Footer */}
        <div className="p-4 border-t border-white/[0.06] bg-[#0c0f16]/90 flex items-center justify-between text-[11px] font-mono text-zinc-500">
          <div className="flex items-center gap-1.5">
            <Database className="w-3 h-3 text-emerald-400" />
            <span>PostgreSQL Synchronized</span>
          </div>
          <span>Press ESC to dismiss</span>
        </div>
      </div>
    </div>
  );
}
