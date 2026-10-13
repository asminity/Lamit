"use client";

import { useState, useRef, useCallback } from "react";
import { StreamEvent, InterruptData } from "@/lib/types";
import { getStreamUrl, resumeInterruptedRun } from "@/lib/api";

interface UseChatStreamOptions {
  onDone?: (threadId: string, titleUpdated: boolean) => void;
  onError?: (errorMsg: string) => void;
}

export function useChatStream({ onDone, onError }: UseChatStreamOptions = {}) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [activeTools, setActiveTools] = useState<string[]>([]);
  const [interrupt, setInterrupt] = useState<InterruptData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  const stopStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const processSSE = async (response: Response, threadId: string) => {
    if (!response.ok) {
      const errText = await response.text();
      let errorMsg = `Server error (${response.status})`;
      try {
        const parsed = JSON.parse(errText);
        if (parsed.detail) errorMsg = parsed.detail;
      } catch {
        if (errText) errorMsg = errText;
      }
      throw new Error(errorMsg);
    }

    if (!response.body) {
      throw new Error("ReadableStream not supported by browser");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          const trimmed = block.trim();
          if (!trimmed.startsWith("data: ")) continue;
          const jsonStr = trimmed.slice(6);
          try {
            const event: StreamEvent = JSON.parse(jsonStr);

            if (event.type === "text" && event.content) {
              setStreamingText((prev) => prev + event.content);
            } else if (event.type === "tool_start" && event.name) {
              setActiveTools((prev) => Array.from(new Set([...prev, event.name!])));
            } else if (event.type === "tool_end" && event.name) {
              setActiveTools((prev) => prev.filter((t) => t !== event.name));
            } else if (event.type === "interrupt" && event.interrupt) {
              setInterrupt(event.interrupt);
            } else if (event.type === "done") {
              onDone?.(threadId, !!event.title_updated);
            } else if (event.type === "error" && event.message) {
              setError(event.message);
              onError?.(event.message);
            }
          } catch {
            // Ignore partial/malformed chunk
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  };

  const startStream = useCallback(
    async (threadId: string, message: string) => {
      stopStream();
      setIsStreaming(true);
      setStreamingText("");
      setActiveTools([]);
      setInterrupt(null);
      setError(null);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const response = await fetch(getStreamUrl(), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ thread_id: threadId, message }),
          signal: controller.signal,
        });

        await processSSE(response, threadId);
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") {
          // Expected cancellation by user
          return;
        }
        const msg = err instanceof Error ? err.message : "Streaming failed";
        setError(msg);
        onError?.(msg);
      } finally {
        setIsStreaming(false);
      }
    },
    [stopStream, onDone, onError]
  );

  const resumeStream = useCallback(
    async (threadId: string, decision: unknown) => {
      stopStream();
      setIsStreaming(true);
      setError(null);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const response = await resumeInterruptedRun(threadId, decision);
        setInterrupt(null);
        await processSSE(response, threadId);
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") return;
        const msg = err instanceof Error ? err.message : "Failed to resume run";
        setError(msg);
        onError?.(msg);
      } finally {
        setIsStreaming(false);
      }
    },
    [stopStream, onDone, onError]
  );

  return {
    isStreaming,
    streamingText,
    activeTools,
    interrupt,
    error,
    startStream,
    resumeStream,
    stopStream,
  };
}
