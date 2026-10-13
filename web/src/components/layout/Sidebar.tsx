"use client";

import React, { useState } from "react";
import { ThreadItem, User } from "@/lib/types";
import {
  MessageSquare,
  Plus,
  Trash2,
  Edit2,
  Check,
  X,
  Search,
  Sparkles,
  Layers,
  ChevronLeft,
  ChevronRight,
  LogOut,
  User as UserIcon,
} from "lucide-react";

interface SidebarProps {
  threads: ThreadItem[];
  activeThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  onNewThread: () => void;
  onDeleteThread: (threadId: string) => void;
  onUpdateTitle: (threadId: string, newTitle: string) => void;
  backendOnline: boolean;
  isOpen: boolean;
  onToggleOpen: () => void;
  currentUser?: User | null;
  onOpenAuth?: () => void;
  onLogout?: () => void;
}

export function Sidebar({
  threads,
  activeThreadId,
  onSelectThread,
  onNewThread,
  onDeleteThread,
  onUpdateTitle,
  backendOnline,
  isOpen,
  onToggleOpen,
  currentUser,
  onOpenAuth,
  onLogout,
}: SidebarProps) {
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const filteredThreads = threads.filter((t) =>
    (t.title || "New Conversation").toLowerCase().includes(search.toLowerCase())
  );

  const startEditing = (t: ThreadItem, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(t.thread_id);
    setEditTitle(t.title);
  };

  const handleSaveTitle = (threadId: string, e: React.MouseEvent | React.FormEvent) => {
    e.stopPropagation();
    if (editTitle.trim()) {
      onUpdateTitle(threadId, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleCancelTitle = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
  };

  const confirmDelete = (threadId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onDeleteThread(threadId);
    setDeletingId(null);
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-30 md:hidden backdrop-blur-sm"
          onClick={onToggleOpen}
        />
      )}

      <aside
        id="app-sidebar"
        className={`fixed md:static inset-y-0 left-0 z-40 flex flex-col w-72 bg-[#0d0f18] border-r border-white/10 transition-all duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0 md:w-0 md:opacity-0 md:pointer-events-none"
        }`}
      >
        {/* Header */}
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-white tracking-tight flex items-center gap-1.5">
                LangGraph AI
                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  v2.0
                </span>
              </h1>
              <p className="text-[11px] text-zinc-400">PostgreSQL Memory</p>
            </div>
          </div>
          <button
            onClick={onToggleOpen}
            className="md:hidden text-zinc-400 hover:text-white p-1 rounded-md hover:bg-white/5"
            title="Close sidebar"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
        </div>

        {/* New Chat Button */}
        <div className="p-3">
          <button
            id="new-chat-button"
            onClick={onNewThread}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white text-sm font-medium shadow-md shadow-indigo-500/15 hover:shadow-indigo-500/25 transition-all duration-200 active:scale-[0.98]"
          >
            <Plus className="w-4 h-4" />
            <span>New Conversation</span>
          </button>
        </div>

        {/* Search */}
        <div className="px-3 pb-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-zinc-500" />
            <input
              id="search-threads-input"
              type="text"
              placeholder="Search conversations..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-white/[0.04] border border-white/5 rounded-lg pl-8 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-indigo-500/50 transition-colors"
            />
          </div>
        </div>

        {/* Thread List */}
        <div className="flex-1 overflow-y-auto px-2 space-y-1 py-1">
          {filteredThreads.length === 0 ? (
            <div className="text-center py-8 text-xs text-zinc-500">
              {search ? "No conversations found" : "No saved conversations"}
            </div>
          ) : (
            filteredThreads.map((thread) => {
              const isActive = thread.thread_id === activeThreadId;
              const isEditing = thread.thread_id === editingId;
              const isDeleting = thread.thread_id === deletingId;

              return (
                <div
                  key={thread.thread_id}
                  id={`thread-item-${thread.thread_id}`}
                  onClick={() => onSelectThread(thread.thread_id)}
                  className={`group relative flex items-center justify-between p-2.5 rounded-xl text-xs cursor-pointer transition-all duration-150 ${
                    isActive
                      ? "bg-white/[0.08] text-white border border-white/10 font-medium shadow-sm"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0 flex-1">
                    <MessageSquare
                      className={`w-4 h-4 shrink-0 ${
                        isActive ? "text-indigo-400" : "text-zinc-500 group-hover:text-zinc-400"
                      }`}
                    />

                    {isEditing ? (
                      <form
                        onSubmit={(e) => handleSaveTitle(thread.thread_id, e)}
                        className="flex items-center gap-1 flex-1 mr-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="text"
                          autoFocus
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          className="w-full bg-black/40 border border-indigo-500 rounded px-1.5 py-0.5 text-xs text-white focus:outline-none"
                        />
                        <button
                          type="submit"
                          className="p-1 hover:text-emerald-400"
                          title="Save title"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={handleCancelTitle}
                          className="p-1 hover:text-rose-400"
                          title="Cancel"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </form>
                    ) : (
                      <span className="truncate flex-1">
                        {thread.title || "New Conversation"}
                      </span>
                    )}
                  </div>

                  {/* Action icons */}
                  {!isEditing && (
                    <div
                      className={`items-center gap-1 shrink-0 ${
                        isActive ? "flex" : "hidden group-hover:flex"
                      }`}
                    >
                      {isDeleting ? (
                        <div
                          className="flex items-center gap-1 bg-rose-950/80 border border-rose-500/30 rounded px-1.5 py-0.5"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            onClick={(e) => confirmDelete(thread.thread_id, e)}
                            className="text-rose-400 hover:text-rose-300 text-[10px] font-semibold"
                          >
                            Delete
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setDeletingId(null);
                            }}
                            className="text-zinc-400 hover:text-white"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ) : (
                        <>
                          <button
                            onClick={(e) => startEditing(thread, e)}
                            className="p-1 text-zinc-500 hover:text-zinc-200 rounded hover:bg-white/5 transition-colors"
                            title="Rename"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setDeletingId(thread.thread_id);
                            }}
                            className="p-1 text-zinc-500 hover:text-rose-400 rounded hover:bg-white/5 transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* User Profile & Account Footer */}
        <div className="p-3 border-t border-white/10 bg-black/40">
          {currentUser ? (
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5 min-w-0">
                {currentUser.avatar_url ? (
                  <img
                    src={currentUser.avatar_url}
                    alt={currentUser.name || currentUser.email}
                    className="w-8 h-8 rounded-full border border-white/10 shrink-0"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center text-xs font-bold text-white shrink-0 shadow-sm">
                    {(currentUser.name || currentUser.email).charAt(0).toUpperCase()}
                  </div>
                )}
                <div className="min-w-0">
                  <div className="text-xs font-medium text-zinc-200 truncate">
                    {currentUser.name || currentUser.email.split("@")[0]}
                  </div>
                  <div className="text-[10px] text-zinc-500 truncate">
                    {currentUser.email}
                  </div>
                </div>
              </div>
              {onLogout && (
                <button
                  onClick={onLogout}
                  className="p-1.5 text-zinc-400 hover:text-rose-400 rounded-lg hover:bg-white/5 transition"
                  title="Sign Out"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              )}
            </div>
          ) : (
            <button
              onClick={onOpenAuth}
              className="w-full py-2 px-3 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-300 hover:text-indigo-200 text-xs font-semibold flex items-center justify-center gap-2 transition"
            >
              <UserIcon className="w-3.5 h-3.5" />
              <span>Sign In / Register</span>
            </button>
          )}
        </div>

        {/* Status */}
        <div className="px-3 py-2 border-t border-white/5 bg-black/20 flex items-center justify-between text-[11px] text-zinc-400">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                backendOnline ? "bg-emerald-400 shadow-sm shadow-emerald-400/50" : "bg-rose-500"
              }`}
            />
            <span>{backendOnline ? "Backend Connected" : "Connecting..."}</span>
          </div>
          <div className="flex items-center gap-1 text-zinc-500">
            <Layers className="w-3 h-3" />
            <span>{threads.length} threads</span>
          </div>
        </div>
      </aside>
    </>
  );
}
