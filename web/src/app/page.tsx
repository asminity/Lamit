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
import { Sidebar } from "@/components/layout";
import { ChatContainer } from "@/components/chat";
import { AuthModal } from "@/components/auth";

export default function Home() {
  const [threads, setThreads] = useState<ThreadItem[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [input, setInput] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [backendOnline, setBackendOnline] = useState(false);

  // Authentication State
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);

  // Load threads for the authenticated user
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

  // Check health and authentication on mount
  useEffect(() => {
    const init = async () => {
      // 1. Health check
      try {
        await fetchHealth();
        setBackendOnline(true);
      } catch {
        setBackendOnline(false);
      }

      // 2. Check for redirect query params (e.g. from Google OAuth callback)
      if (typeof window !== "undefined") {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get("auth") === "success") {
          window.history.replaceState({}, document.title, window.location.pathname);
        } else if (urlParams.get("auth_error")) {
          alert(`Google Authentication error: ${urlParams.get("auth_error")}`);
          window.history.replaceState({}, document.title, window.location.pathname);
        }
      }

      // 3. Check current user session
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
      } finally {
        setAuthChecked(true);
      }
    };

    init();
  }, [loadThreads, activeThreadId]);

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

  // Stream completion callback
  const handleStreamDone = useCallback(
    async (threadId: string, titleUpdated: boolean) => {
      try {
        const updatedMsgs = await fetchThreadMessages(threadId);
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

  // Authentication callbacks
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

  // New Thread
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

  // Delete Thread
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

  // Update Title
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

  // Send message flow
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

  // Resume interrupted flow (HITL)
  const handleResumeInterrupt = async (decision: unknown) => {
    if (!activeThreadId) return;
    await resumeStream(activeThreadId, decision);
  };

  const activeThread = threads.find((t) => t.thread_id === activeThreadId);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#090a0f] text-zinc-100 antialiased font-sans">
      <Sidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onSelectThread={(id) => setActiveThreadId(id)}
        onNewThread={handleNewThread}
        onDeleteThread={handleDeleteThread}
        onUpdateTitle={handleUpdateTitle}
        backendOnline={backendOnline}
        isOpen={sidebarOpen}
        onToggleOpen={() => setSidebarOpen((prev) => !prev)}
        currentUser={currentUser}
        onOpenAuth={() => setAuthModalOpen(true)}
        onLogout={handleLogout}
      />

      <ChatContainer
        threadTitle={activeThread?.title || "New Conversation"}
        messages={messages}
        isStreaming={isStreaming}
        streamingText={streamingText}
        activeTools={activeTools}
        interrupt={interrupt}
        error={error}
        input={input}
        setInput={setInput}
        onSend={handleSendMessage}
        onStop={stopStream}
        onResumeInterrupt={handleResumeInterrupt}
        onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
        onSelectPrompt={(prompt) => {
          setInput(prompt);
          handleSendMessage(prompt);
        }}
      />

      {/* Authentication Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={currentUser ? () => setAuthModalOpen(false) : undefined}
        onSuccess={handleAuthSuccess}
      />
    </div>
  );
}
