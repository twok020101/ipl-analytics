"use client";

/**
 * WebSocket hook for real-time live score updates.
 *
 * Connects to ws://<api>/ws/live and receives JSON payloads every ~30s.
 * Falls back to HTTP polling if WebSocket connection fails.
 *
 * Features:
 *  - Auto-reconnect with exponential backoff (1s → 2s → 4s → ... → 30s)
 *  - Heartbeat ping every 15s to keep connection alive
 *  - Seamless fallback to REST polling on WS failure
 *  - Connection status exposed for UI indicators
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { BASE_URL, fetchLiveScores as fetchLiveScoresHttp } from "@/lib/api";
import type {
  LiveMatch,
  LiveUpcomingMatch,
  LiveRecentResult,
} from "@/lib/types";

export type ConnectionStatus = "connecting" | "connected" | "disconnected" | "fallback";

interface LiveScoresState {
  live: LiveMatch[];
  upcoming: LiveUpcomingMatch[];
  recent_results: LiveRecentResult[];
  fetched_at: string | null;
}

interface UseLiveScoresReturn {
  data: LiveScoresState;
  status: ConnectionStatus;
  clientCount: number;
}

// Derive WebSocket URL from the REST API URL
function getWsUrl(): string {
  const base = BASE_URL.replace(/\/api\/v1$/, "");
  const wsProtocol = base.startsWith("https") ? "wss" : "ws";
  const host = base.replace(/^https?:\/\//, "");
  return `${wsProtocol}://${host}/ws/live`;
}

const HEARTBEAT_INTERVAL = 15_000;   // 15s ping to keep alive
const MAX_RECONNECT_DELAY = 30_000;  // Cap backoff at 30s
const FALLBACK_POLL_INTERVAL = 30_000; // HTTP poll every 30s as fallback

export function useLiveScores(): UseLiveScoresReturn {
  const [data, setData] = useState<LiveScoresState>({
    live: [],
    upcoming: [],
    recent_results: [],
    fetched_at: null,
  });
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [clientCount, setClientCount] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
  const heartbeatTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fallbackTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  // HTTP fallback polling — reuses the typed fetchAPI wrapper
  const pollHttp = useCallback(async () => {
    try {
      const json = await fetchLiveScoresHttp() as Record<string, unknown>;
      if (mountedRef.current) {
        setData({
          live: (json.live || []) as LiveMatch[],
          upcoming: (json.upcoming || []) as LiveUpcomingMatch[],
          recent_results: (json.recent_results || []) as LiveRecentResult[],
          fetched_at: (json.fetched_at as string) || new Date().toISOString(),
        });
      }
    } catch {
      // Silently fail — next poll will retry
    }
  }, []);

  // Start HTTP fallback
  const startFallback = useCallback(() => {
    if (fallbackTimer.current) return;
    setStatus("fallback");
    pollHttp(); // Immediate first fetch
    fallbackTimer.current = setInterval(pollHttp, FALLBACK_POLL_INTERVAL);
  }, [pollHttp]);

  // Stop HTTP fallback
  const stopFallback = useCallback(() => {
    if (fallbackTimer.current) {
      clearInterval(fallbackTimer.current);
      fallbackTimer.current = null;
    }
  }, []);

  // WebSocket connection
  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const wsUrl = getWsUrl();
    setStatus("connecting");

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setStatus("connected");
        reconnectAttempt.current = 0;
        stopFallback();

        // Start heartbeat
        heartbeatTimer.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, HEARTBEAT_INTERVAL);
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "heartbeat") return; // Server keepalive — ignore
          if (payload.type === "live_update") {
            setData({
              live: payload.live || [],
              upcoming: payload.upcoming || [],
              recent_results: payload.recent_results || [],
              fetched_at: payload.fetched_at || new Date().toISOString(),
            });
            setClientCount(payload.clients || 0);
          }
        } catch {
          // Ignore non-JSON messages (e.g., "pong")
        }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        cleanup();
        scheduleReconnect();
      };

      ws.onerror = () => {
        // onclose will fire after this — reconnect handled there
      };
    } catch {
      // WebSocket constructor failed — fall back to HTTP
      startFallback();
    }
  }, [stopFallback, startFallback]);

  // Cleanup WebSocket resources
  const cleanup = useCallback(() => {
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current);
      heartbeatTimer.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current = null;
    }
  }, []);

  // Reconnect with exponential backoff
  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;

    const attempt = reconnectAttempt.current++;
    const delay = Math.min(1000 * Math.pow(2, attempt), MAX_RECONNECT_DELAY);

    setStatus("disconnected");

    // After 3 failed attempts, switch to HTTP fallback while still trying WS
    if (attempt >= 3) {
      startFallback();
    }

    reconnectTimer.current = setTimeout(() => {
      if (mountedRef.current) connect();
    }, delay);
  }, [connect, startFallback]);

  // Mount / unmount
  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      // Capture ws ref before cleanup nulls it, so we can close the connection
      const ws = wsRef.current;
      cleanup();
      stopFallback();
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      if (ws && ws.readyState !== WebSocket.CLOSED) {
        ws.close();
      }
    };
  }, [connect, cleanup, stopFallback]);

  return { data, status, clientCount };
}
