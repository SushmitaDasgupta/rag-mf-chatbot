import { useCallback, useEffect, useRef, useState } from "react";
import { postChat, stripStructuredFooter } from "../api/client";
import type { ChatApiResponse, ChatMessage } from "../types";

const MIN_SUBMIT_GAP_SECONDS = 2;

function newId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function sessionTitle(messages: ChatMessage[]): string {
  const first = messages.find((m) => m.role === "user");
  if (!first) return "New chat";
  const t = first.content.trim();
  return t.length > 36 ? `${t.slice(0, 33)}…` : t;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [inputShake, setInputShake] = useState(false);
  const [, setTick] = useState(0);
  const lastSubmitRef = useRef(0);

  useEffect(() => {
    if (cooldownUntil <= Date.now()) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, [cooldownUntil]);

  const cooldownRemaining = Math.max(0, Math.ceil((cooldownUntil - Date.now()) / 1000));
  const canSend = !loading && cooldownRemaining === 0;

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return false;

      const now = Date.now();
      if (now - lastSubmitRef.current < MIN_SUBMIT_GAP_SECONDS * 1000) {
        setInputShake(true);
        window.setTimeout(() => setInputShake(false), 200);
        return false;
      }
      if (cooldownUntil > now) {
        setInputShake(true);
        window.setTimeout(() => setInputShake(false), 200);
        return false;
      }

      lastSubmitRef.current = now;
      const userMsg: ChatMessage = { id: newId(), role: "user", content: trimmed };
      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);

      try {
        const { status, data } = await postChat(trimmed);

        if ("detail" in data && !("type" in data)) {
          setMessages((prev) => [
            ...prev,
            {
              id: newId(),
              role: "assistant",
              content: "Something went wrong. Please try again in a moment.",
              isError: true,
            },
          ]);
          return false;
        }

        const response = data as ChatApiResponse;
        if (status === 429 && response.retry_after_seconds) {
          setCooldownUntil(Date.now() + response.retry_after_seconds * 1000);
          setInputShake(true);
          window.setTimeout(() => setInputShake(false), 200);
        }

        const body = stripStructuredFooter(response.text);
        const isRefusal =
          response.type === "refusal" ||
          response.type === "performance_refusal" ||
          response.type === "unsupported" ||
          response.type === "rate_limited";
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: "assistant",
            content: body,
            responseType: response.type,
            citationUrl: isRefusal ? null : response.citation_url,
            lastUpdated: isRefusal ? null : response.last_updated_from_sources,
            isError: status >= 500,
          },
        ]);
        return true;
      } catch (err) {
        const detail = err instanceof Error ? err.message : "";
        const hint = import.meta.env.PROD
          ? `Could not reach the API. ${detail || "Set RAILWAY_API_URL on Vercel and redeploy."}`
          : "Could not reach the API. Start the backend with: uvicorn src.api.main:app --reload";
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: "assistant",
            content: hint,
            isError: true,
          },
        ]);
        return false;
      } finally {
        setLoading(false);
      }
    },
    [cooldownUntil, loading],
  );

  const newChat = useCallback(() => {
    setMessages((current) => {
      if (current.length > 0) {
        const id = activeSessionId ?? newId();
        const title = sessionTitle(current);
        setSessions((prev) => {
          const without = prev.filter((s) => s.id !== id);
          return [{ id, title, messages: current }, ...without].slice(0, 8);
        });
        setActiveSessionId(null);
      }
      return [];
    });
  }, [activeSessionId]);

  const selectSession = useCallback(
    (id: string) => {
      const found = sessions.find((s) => s.id === id);
      if (!found) return;
      setMessages((current) => {
        if (current.length > 0 && activeSessionId) {
          setSessions((prev) =>
            prev.map((s) => (s.id === activeSessionId ? { ...s, messages: current } : s)),
          );
        } else if (current.length > 0) {
          const sid = activeSessionId ?? newId();
          setSessions((prev) => [
            { id: sid, title: sessionTitle(current), messages: current },
            ...prev.filter((s) => s.id !== sid),
          ]);
        }
        return found.messages;
      });
      setActiveSessionId(id);
    },
    [activeSessionId, sessions],
  );

  const sidebarSessions = sessions.map((s) => ({ id: s.id, title: s.title }));

  return {
    messages,
    loading,
    canSend,
    cooldownRemaining,
    inputShake,
    sendMessage,
    newChat,
    selectSession,
    sidebarSessions,
    activeSessionId,
  };
}
