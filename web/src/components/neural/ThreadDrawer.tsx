"use client";

import React, { useState, useMemo, useEffect } from "react";
import { ThreadItem } from "@/lib/types";
import { X, Search, Plus, Trash2 } from "lucide-react";

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

  // Escape closes the drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const filteredThreads = useMemo(() => {
    if (!search.trim()) return threads;
    const q = search.toLowerCase();
    return threads.filter((t) => t.title.toLowerCase().includes(q));
  }, [threads, search]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div onClick={onClose} className="fixed inset-0 bg-slate-900/30" />

      <div className="relative z-10 flex h-full w-full max-w-sm flex-col bg-white shadow-xl">
        <div className="h-14 shrink-0 px-4 flex items-center justify-between border-b border-slate-200">
          <h2 className="text-base font-semibold text-slate-900">Conversations</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors"
            aria-label="Close conversations"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-3">
          <button
            onClick={() => {
              onNewThread();
              onClose();
            }}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New chat
          </button>

          <div className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 focus-within:border-indigo-400 focus-within:ring-4 focus-within:ring-indigo-100 transition">
            <Search className="w-4 h-4 text-slate-400 shrink-0" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search"
              aria-label="Search conversations"
              className="w-full bg-transparent text-sm text-slate-900 placeholder:text-slate-400 outline-none"
              autoFocus
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-4">
          {filteredThreads.length === 0 ? (
            <p className="px-4 py-12 text-center text-sm text-slate-500">
              {search.trim()
                ? `No conversations match “${search}”.`
                : "No conversations yet."}
            </p>
          ) : (
            filteredThreads.map((thread) => {
              const isActive = thread.thread_id === activeThreadId;
              const isDeleting = threadToDelete === thread.thread_id;

              return (
                <div
                  key={thread.thread_id}
                  className={`group flex items-center gap-2 rounded-xl px-3 py-2.5 transition-colors ${
                    isActive ? "bg-indigo-50" : "hover:bg-slate-50"
                  }`}
                >
                  <button
                    onClick={() => {
                      onSelectThread(thread.thread_id);
                      onClose();
                    }}
                    className="flex-1 min-w-0 text-left"
                  >
                    <span
                      className={`block truncate text-sm font-medium ${
                        isActive ? "text-indigo-700" : "text-slate-800"
                      }`}
                    >
                      {thread.title || "Untitled conversation"}
                    </span>
                    {thread.updated_at && (
                      <span className="block text-xs text-slate-500">
                        {new Date(thread.updated_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    )}
                  </button>

                  {isDeleting ? (
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => {
                          onDeleteThread(thread.thread_id);
                          setThreadToDelete(null);
                        }}
                        className="rounded-lg bg-rose-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-rose-500"
                      >
                        Delete
                      </button>
                      <button
                        onClick={() => setThreadToDelete(null)}
                        className="rounded-lg px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setThreadToDelete(thread.thread_id)}
                      className="shrink-0 p-1.5 rounded-lg text-slate-400 opacity-0 transition-opacity hover:bg-white hover:text-rose-600 group-hover:opacity-100 focus:opacity-100"
                      title="Delete conversation"
                      aria-label="Delete conversation"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
