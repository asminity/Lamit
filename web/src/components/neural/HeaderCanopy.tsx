"use client";

import React, { useState } from "react";
import { User } from "@/lib/types";
import { Menu, Columns, Edit2, Check, X, LogOut } from "lucide-react";

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
}

const iconButton =
  "p-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors";

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
    <header className="h-14 shrink-0 border-b border-slate-200 bg-white px-3 sm:px-5 flex items-center justify-between gap-3">
      {/* Left: menu, brand, conversation title */}
      <div className="flex items-center gap-2 min-w-0">
        <button
          onClick={onOpenThreadDrawer}
          className={iconButton}
          title="Conversations (Ctrl/⌘ + K)"
          aria-label="Open conversations"
        >
          <Menu className="w-5 h-5" />
        </button>

        <span className="text-base font-semibold tracking-tight text-indigo-600">
          Lamit
        </span>

        <span className="hidden sm:block h-4 w-px bg-slate-200 mx-1" />

        {isEditingTitle ? (
          <form onSubmit={handleSaveTitle} className="flex items-center gap-1 min-w-0">
            <input
              type="text"
              value={editedTitle}
              onChange={(e) => setEditedTitle(e.target.value)}
              autoFocus
              aria-label="Conversation title"
              className="w-40 sm:w-64 rounded-lg border border-indigo-300 bg-white px-2.5 py-1 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-indigo-100"
            />
            <button type="submit" className={iconButton} aria-label="Save title">
              <Check className="w-4 h-4 text-emerald-600" />
            </button>
            <button
              type="button"
              onClick={() => {
                setEditedTitle(threadTitle);
                setIsEditingTitle(false);
              }}
              className={iconButton}
              aria-label="Cancel rename"
            >
              <X className="w-4 h-4" />
            </button>
          </form>
        ) : (
          <div className="hidden sm:flex items-center gap-1 group min-w-0">
            <span className="text-sm text-slate-600 truncate max-w-xs md:max-w-md">
              {threadTitle}
            </span>
            <button
              onClick={() => {
                setEditedTitle(threadTitle);
                setIsEditingTitle(true);
              }}
              className="opacity-0 group-hover:opacity-100 focus:opacity-100 p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-opacity"
              title="Rename conversation"
              aria-label="Rename conversation"
            >
              <Edit2 className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Right: status, canvas, account */}
      <div className="flex items-center gap-2 shrink-0">
        {!backendOnline && (
          <span className="flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            Offline
          </span>
        )}

        <button
          onClick={onToggleCanvas}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
            isCanvasOpen
              ? "bg-indigo-50 text-indigo-700"
              : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          }`}
          title="Toggle side panel"
          aria-pressed={isCanvasOpen}
        >
          <Columns className="w-4 h-4" />
          <span className="hidden sm:inline">Canvas</span>
        </button>

        {currentUser ? (
          <div className="flex items-center gap-1">
            {currentUser.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={currentUser.avatar_url}
                alt={currentUser.name || "User"}
                className="w-8 h-8 rounded-full object-cover"
              />
            ) : (
              <div
                className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-sm font-semibold text-white"
                title={currentUser.name || currentUser.email}
              >
                {(currentUser.name || currentUser.email || "U")[0].toUpperCase()}
              </div>
            )}
            <button
              onClick={onLogout}
              className={iconButton}
              title="Sign out"
              aria-label="Sign out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenAuth}
            className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
          >
            Sign in
          </button>
        )}
      </div>
    </header>
  );
}
