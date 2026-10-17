"use client";

import { useState, useRef, useCallback } from "react";
import { InterruptData } from "@/lib/types";
import { getStreamUrl, resumeInterruptedRun } from "@/lib/api";

interface UseChatStreamOptions {
  onDone?: (
    threadId: string,
    titleUpdated: boolean,
    cached?: boolean,
    similarity?: number
  ) => void;
  onError?: (errorMsg: string) => void;
}

export function useChatStream({ onDone, onError }: UseChatStreamOptions = {}) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [activeTools, setActiveTools] = useState<string[]>([]);
  const [interrupt, setInterrupt] = useState<InterruptData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isCachedHit, setIsCachedHit] = useState<boolean>(false);
  const [cacheSimilarity, setCacheSimilarity] = useState<number | undefined>(undefined);

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
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() || "";

        for (const block of blocks) {
          const trimmed = block.trim();
          if (!trimmed) continue;

          let eventType = "message";
          let dataStr = "";

          const lines = trimmed.split("\n");
          for (const line of lines) {
            const l = line.trim();
            if (l.startsWith("event: ")) {
              eventType = l.slice(7).trim();
            } else if (l.startsWith("data: ")) {
              dataStr = l.slice(6).trim();
            }
          }

          if (!dataStr) continue;

          try {
            const payload = JSON.parse(dataStr);

            if (eventType === "text" && payload.content) {
              setStreamingText((prev) => prev + payload.content);
            } else if (eventType === "tool_start" && payload.name) {
              setActiveTools((prev) => Array.from(new Set([...prev, payload.name])));
            } else if (eventType === "tool_end" && payload.name) {
              setActiveTools((prev) => prev.filter((t) => t !== payload.name));
            } else if (eventType === "interrupt" && payload.interrupt) {
              setInterrupt(payload.interrupt);
            } else if (eventType === "done") {
              if (payload.cached) {
                setIsCachedHit(true);
                setCacheSimilarity(payload.similarity);
              }
              onDone?.(
                threadId,
                !!payload.title_updated,
                payload.cached,
                payload.similarity
              );
            } else if (eventType === "error" && payload.message) {
              setError(payload.message);
              onError?.(payload.message);
            }
          } catch {
            // Ignore incomplete / malformed JSON frame
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
      setIsCachedHit(false);
      setCacheSimilarity(undefined);

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
    isCachedHit,
    cacheSimilarity,
    startStream,
    resumeStream,
    stopStream,
  };
}
