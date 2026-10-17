"use client";

import React, { useState, useEffect, useCallback } from "react";
import { ThreadItem, ChatMessageItem, User } from "@/lib/types";
import {
  fetchThreads,
  createThread,
  deleteThread,
  updateThreadTitle,
  fetchThreadMessages,
  fetchHealth,
  fetchCurrentUser,
  logoutUser,
} from "@/lib/api";
import { useChatStream } from "@/hooks/useChatStream";
import {
  HeaderCanopy,
  CommandDeck,
  ThoughtStream,
  ArtifactCanvas,
  ThreadDrawer,
  AuthPortal,
} from "@/components/neural";
import { AlertTriangle } from "lucide-react";

export default function Home() {
  const [threads, setThreads] = useState<ThreadItem[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [input, setInput] = useState("");
  const [threadDrawerOpen, setThreadDrawerOpen] = useState(false);
  const [canvasOpen, setCanvasOpen] = useState(false);
  const [activeArtifact, setActiveArtifact] = useState<{ text: string; title: string }>({
    text: "",
    title: "Workspace Canvas",
  });
  const [backendOnline, setBackendOnline] = useState(false);

  // Authentication State
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [authModalOpen, setAuthModalOpen] = useState(false);

  // Load threads
  const loadThreads = useCallback(async () => {
    try {
      const data = await fetchThreads();
      setThreads(data);
      setBackendOnline(true);
      return data;
    } catch (err: unknown) {
      if (err instanceof Error && err.message === "UNAUTHORIZED") {
        setCurrentUser(null);
        setAuthModalOpen(true);
      }
      setBackendOnline(false);
      return [];
    }
  }, []);

  // System Health & Session Initialization
  useEffect(() => {
    const init = async () => {
      // 1. Health check
      try {
        await fetchHealth();
        setBackendOnline(true);
      } catch {
        setBackendOnline(false);
      }

      // 2. Query params check (Google OAuth callback)
      if (typeof window !== "undefined") {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get("auth") === "success") {
          window.history.replaceState({}, document.title, window.location.pathname);
        } else if (urlParams.get("auth_error")) {
          alert(`Google Authentication error: ${urlParams.get("auth_error")}`);
          window.history.replaceState({}, document.title, window.location.pathname);
        }
      }

      // 3. User session lookup
      try {
        const user = await fetchCurrentUser();
        setCurrentUser(user);
        if (user) {
          const loaded = await loadThreads();
          if (loaded.length > 0 && !activeThreadId) {
            setActiveThreadId(loaded[0].thread_id);
          }
        } else {
          setAuthModalOpen(true);
        }
      } catch {
        setAuthModalOpen(true);
      }
    };

    init();
  }, [loadThreads, activeThreadId]);

  // Global Keyboard Shortcuts (⌘K / Ctrl+K for Thread Constellation)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setThreadDrawerOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Load message history when active thread changes
  useEffect(() => {
    if (!activeThreadId) {
      setMessages([]);
      return;
    }

    let isMounted = true;
    fetchThreadMessages(activeThreadId)
      .then((history) => {
        if (isMounted) setMessages(history);
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.message === "UNAUTHORIZED") {
          setCurrentUser(null);
          setAuthModalOpen(true);
        }
        console.error("Failed to load thread messages:", err);
      });

    return () => {
      isMounted = false;
    };
  }, [activeThreadId]);

  // Stream completion handler
  const handleStreamDone = useCallback(
    async (
      threadId: string,
      titleUpdated: boolean,
      cached?: boolean,
      similarity?: number
    ) => {
      try {
        const updatedMsgs = await fetchThreadMessages(threadId);
        // Tag latest assistant message with cache metadata if hit
        if (cached && updatedMsgs.length > 0) {
          const lastIdx = updatedMsgs.length - 1;
          if (updatedMsgs[lastIdx].role === "assistant") {
            updatedMsgs[lastIdx].cached = true;
            updatedMsgs[lastIdx].similarity = similarity;
          }
        }
        setMessages(updatedMsgs);
      } catch (err) {
        console.error("Failed to rehydrate messages:", err);
      }

      if (titleUpdated) {
        setTimeout(() => {
          loadThreads();
        }, 1200);
      }
    },
    [loadThreads]
  );

  const {
    isStreaming,
    streamingText,
    activeTools,
    interrupt,
    error,
    startStream,
    resumeStream,
    stopStream,
  } = useChatStream({
    onDone: handleStreamDone,
    onError: (err) => {
      if (err.includes("401") || err.toLowerCase().includes("authentication required")) {
        setCurrentUser(null);
        setAuthModalOpen(true);
      }
      console.error("Stream error:", err);
    },
  });

  // Auth Callbacks
  const handleAuthSuccess = async (user: User) => {
    setCurrentUser(user);
    setAuthModalOpen(false);
    const loaded = await loadThreads();
    if (loaded.length > 0) {
      setActiveThreadId(loaded[0].thread_id);
    } else {
      setActiveThreadId(null);
      setMessages([]);
    }
  };

  const handleLogout = async () => {
    await logoutUser();
    setCurrentUser(null);
    setThreads([]);
    setActiveThreadId(null);
    setMessages([]);
    setAuthModalOpen(true);
  };

  // Thread Operations
  const handleNewThread = async () => {
    if (!currentUser) {
      setAuthModalOpen(true);
      return;
    }
    try {
      const newId = await createThread();
      setActiveThreadId(newId);
      setMessages([]);
      await loadThreads();
    } catch (err) {
      console.error("Failed to create thread:", err);
    }
  };

  const handleDeleteThread = async (threadId: string) => {
    try {
      await deleteThread(threadId);
      const remaining = threads.filter((t) => t.thread_id !== threadId);
      setThreads(remaining);

      if (activeThreadId === threadId) {
        if (remaining.length > 0) {
          setActiveThreadId(remaining[0].thread_id);
        } else {
          setActiveThreadId(null);
          setMessages([]);
        }
      }
    } catch (err) {
      console.error("Failed to delete thread:", err);
    }
  };

  const handleUpdateTitle = async (threadId: string, newTitle: string) => {
    try {
      await updateThreadTitle(threadId, newTitle);
      setThreads((prev) =>
        prev.map((t) => (t.thread_id === threadId ? { ...t, title: newTitle } : t))
      );
    } catch (err) {
      console.error("Failed to update title:", err);
    }
  };

  // Transmission flow
  const handleSendMessage = async (text: string) => {
    if (!currentUser) {
      setAuthModalOpen(true);
      return;
    }

    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;

    let targetThreadId = activeThreadId;

    if (!targetThreadId) {
      try {
        targetThreadId = await createThread();
        setActiveThreadId(targetThreadId);
        await loadThreads();
      } catch (err) {
        console.error("Failed to auto-create thread:", err);
        return;
      }
    }

    const optimisticUserMsg: ChatMessageItem = {
      thread_id: targetThreadId,
      role: "user",
      content: trimmed,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUserMsg]);
    setInput("");

    await startStream(targetThreadId, trimmed);
  };

  const handleResumeInterrupt = async (decision: unknown) => {
    if (!activeThreadId) return;
    await resumeStream(activeThreadId, decision);
  };

  const handleSendToCanvas = (content: string, title?: string) => {
    setActiveArtifact({
      text: content,
      title: title || "Extracted Knowledge Artifact",
    });
    setCanvasOpen(true);
  };

  const activeThread = threads.find((t) => t.thread_id === activeThreadId);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#06070a] text-zinc-100 antialiased font-sans ambient-matrix-bg relative">
      {/* Background Dot Matrix Texture */}
      <div className="absolute inset-0 ambient-dot-grid opacity-35 pointer-events-none" />

      {/* Main Dynamic Viewport */}
      <div className="flex-1 flex flex-col h-full min-w-0 relative z-10">
        {/* Top Canopy */}
        <HeaderCanopy
          threadTitle={activeThread?.title || "New Thought Horizon"}
          onRenameThread={(newTitle) => {
            if (activeThreadId) handleUpdateTitle(activeThreadId, newTitle);
          }}
          onOpenThreadDrawer={() => setThreadDrawerOpen(true)}
          onToggleCanvas={() => setCanvasOpen((prev) => !prev)}
          isCanvasOpen={canvasOpen}
          currentUser={currentUser}
          onOpenAuth={() => setAuthModalOpen(true)}
          onLogout={handleLogout}
          backendOnline={backendOnline}
          turnCount={messages.length}
        />

        {/* Global Error Notice */}
        {error && (
          <div className="bg-rose-950/60 border-b border-rose-500/30 px-4 py-2 flex items-center justify-between text-xs text-rose-200 z-20">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          </div>
        )}

        {/* Main Dialogue & Cognitive Viewport */}
        <div className="flex-1 flex min-h-0 overflow-hidden relative">
          {/* Main Thought Stream */}
          <main className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
            <ThoughtStream
              messages={messages}
              isStreaming={isStreaming}
              streamingText={streamingText}
              activeTools={activeTools}
              interrupt={interrupt}
              onResumeInterrupt={handleResumeInterrupt}
              onSelectPrompt={(prompt) => {
                setInput(prompt);
                handleSendMessage(prompt);
              }}
              onSendToCanvas={handleSendToCanvas}
            />

            {/* Tactical Floating Command Deck */}
            <CommandDeck
              input={input}
              setInput={setInput}
              onSend={handleSendMessage}
              onStop={stopStream}
              isStreaming={isStreaming}
              activeTools={activeTools}
            />
          </main>

          {/* Dual-Horizon Workspace Canvas */}
          <ArtifactCanvas
            isOpen={canvasOpen}
            onClose={() => setCanvasOpen(false)}
            activeArtifactText={activeArtifact.text}
            activeArtifactTitle={activeArtifact.title}
            messages={messages}
            threadId={activeThreadId || ""}
          />
        </div>
      </div>

      {/* Thread Constellation Slide-over Drawer */}
      <ThreadDrawer
        isOpen={threadDrawerOpen}
        onClose={() => setThreadDrawerOpen(false)}
        threads={threads}
        activeThreadId={activeThreadId}
        onSelectThread={(id) => setActiveThreadId(id)}
        onNewThread={handleNewThread}
        onDeleteThread={handleDeleteThread}
      />

      {/* Authentication Portal */}
      <AuthPortal
        isOpen={authModalOpen}
        onClose={currentUser ? () => setAuthModalOpen(false) : undefined}
        onSuccess={handleAuthSuccess}
      />
    </div>
  );
}
