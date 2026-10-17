"use client";

import React, { useState } from "react";
import { User } from "@/lib/types";
import {
  Sparkles,
  Command,
  Database,
  Zap,
  Columns,
  Layers,
  Edit2,
  Check,
  X,
  LogOut,
  User as UserIcon,
} from "lucide-react";

interface HeaderCanopyProps {
  threadTitle: string;
  onRenameThread: (newTitle: string) => void;
  onOpenThreadDrawer: () => void;
  onToggleCanvas: () => void;
  isCanvasOpen: boolean;
  currentUser: User | null;
  onOpenAuth: () => void;
  onLogout: () => void;
  backendOnline: boolean;
  turnCount: number;
}

export function HeaderCanopy({
  threadTitle,
  onRenameThread,
  onOpenThreadDrawer,
  onToggleCanvas,
  isCanvasOpen,
  currentUser,
  onOpenAuth,
  onLogout,
  backendOnline,
  turnCount,
}: HeaderCanopyProps) {
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editedTitle, setEditedTitle] = useState(threadTitle);

  const handleSaveTitle = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (editedTitle.trim() && editedTitle !== threadTitle) {
      onRenameThread(editedTitle.trim());
    }
    setIsEditingTitle(false);
  };

  return (
    <header className="h-16 border-b border-white/[0.06] px-4 md:px-6 flex items-center justify-between shrink-0 bg-[#090b10]/85 backdrop-blur-xl z-30 relative select-none">
      {/* Left: Brand Identity & Neural Engine Indicator */}
      <div className="flex items-center gap-4 min-w-0">
        <button
          onClick={onOpenThreadDrawer}
          className="group flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.06] transition-all text-left"
          title="Open Conversation Constellation (⌘K)"
        >
          <div className="relative flex items-center justify-center w-6 h-6 rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-indigo-400 group-hover:scale-105 transition-transform">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-bold tracking-widest uppercase text-white/90 font-mono flex items-center gap-1.5">
              LAMIT
              <span className="text-[10px] text-zinc-500 font-normal">v2.0</span>
            </span>
          </div>
          <kbd className="hidden sm:inline-flex items-center gap-0.5 text-[10px] text-zinc-500 px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.06]">
            <Command className="w-2.5 h-2.5" />K
          </kbd>
        </button>

        {/* Divider */}
        <div className="h-4 w-px bg-white/10 hidden sm:block" />

        {/* Center-Left: Contextual Thread Orbit */}
        <div className="flex items-center gap-2 min-w-0">
          {isEditingTitle ? (
            <form onSubmit={handleSaveTitle} className="flex items-center gap-1.5">
              <input
                type="text"
                value={editedTitle}
                onChange={(e) => setEditedTitle(e.target.value)}
                autoFocus
                className="bg-black/60 border border-indigo-500/50 rounded-lg px-2.5 py-1 text-xs text-white outline-none w-48 sm:w-64"
              />
              <button
                type="submit"
                className="p-1 rounded text-emerald-400 hover:bg-emerald-500/10"
              >
                <Check className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditedTitle(threadTitle);
                  setIsEditingTitle(false);
                }}
                className="p-1 rounded text-zinc-400 hover:bg-white/5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </form>
          ) : (
            <div className="flex items-center gap-1.5 group max-w-[200px] sm:max-w-xs md:max-w-md truncate">
              <span className="text-sm font-medium text-zinc-200 truncate font-sans">
                {threadTitle || "New Thought Horizon"}
              </span>
              <button
                onClick={() => {
                  setEditedTitle(threadTitle);
                  setIsEditingTitle(true);
                }}
                className="opacity-0 group-hover:opacity-100 p-1 text-zinc-500 hover:text-white rounded hover:bg-white/5 transition-opacity"
                title="Rename conversation"
              >
                <Edit2 className="w-3 h-3" />
              </button>
            </div>
          )}

          {turnCount > 0 && (
            <span className="hidden md:inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono text-zinc-400 bg-white/[0.03] border border-white/[0.05]">
              {turnCount} {turnCount === 1 ? "turn" : "turns"}
            </span>
          )}
        </div>
      </div>

      {/* Right: Telemetry & Workspace Stage Switcher */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Backend & Memory Telemetry */}
        <div className="hidden lg:flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono bg-white/[0.02] border border-white/[0.05] text-zinc-400">
            <Database className="w-3 h-3 text-indigo-400" />
            <span>PostgreSQL Memory</span>
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                backendOnline ? "bg-emerald-400 shadow-[0_0_6px_#34d399]" : "bg-amber-400"
              }`}
            />
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono bg-white/[0.02] border border-white/[0.05] text-zinc-400">
            <Zap className="w-3 h-3 text-cyan-400" />
            <span>Semantic Cache</span>
            <span className="text-cyan-400/80">0.88</span>
          </div>
        </div>

        {/* Workspace Canvas / Split Horizon Toggle */}
        <button
          onClick={onToggleCanvas}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-medium transition-all ${
            isCanvasOpen
              ? "bg-indigo-600/20 border-indigo-500/40 text-indigo-300 shadow-[0_0_12px_rgba(99,102,241,0.2)]"
              : "bg-white/[0.03] hover:bg-white/[0.08] border-white/[0.06] text-zinc-400 hover:text-white"
          }`}
          title="Toggle Side-by-Side Artifact & Memory Canvas"
        >
          <Columns className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Canvas</span>
        </button>

        {/* User Account / Session Portal */}
        {currentUser ? (
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 pl-2 pr-1 py-1 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              {currentUser.avatar_url ? (
                <img
                  src={currentUser.avatar_url}
                  alt={currentUser.name || "User"}
                  className="w-5 h-5 rounded-full object-cover"
                />
              ) : (
                <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-indigo-500 to-cyan-500 flex items-center justify-center text-[10px] text-white font-bold">
                  {(currentUser.name || currentUser.email || "U")[0].toUpperCase()}
                </div>
              )}
              <span className="text-xs text-zinc-300 font-medium hidden md:inline max-w-[100px] truncate">
                {currentUser.name || currentUser.email.split("@")[0]}
              </span>
              <button
                onClick={onLogout}
                className="p-1 hover:text-rose-400 text-zinc-500 rounded hover:bg-white/5 transition-colors"
                title="Sign out"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={onOpenAuth}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white text-xs font-semibold shadow-lg shadow-indigo-500/20 transition-all"
          >
            <UserIcon className="w-3.5 h-3.5" />
            <span>Sign In</span>
          </button>
        )}
      </div>
    </header>
  );
}
