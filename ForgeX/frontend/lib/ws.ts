"use client";

// Live case channel: WebSocket fan-out from the backend (JOB_STATUS / JOB_COMPLETE /
// JOB_FAILED / SCRIPT_COMPLETE). Falls back to polling-friendly usage: consumers
// treat `connected` as advisory and keep REST polling as the source of truth.
import { useEffect, useRef, useState } from "react";
import { getToken } from "@/lib/api";

export interface WsMessage {
  type: "JOB_STATUS" | "JOB_COMPLETE" | "JOB_FAILED" | "SCRIPT_COMPLETE" | string;
  [k: string]: unknown;
}

export function useCaseSocket(investigationId: string | null | undefined, onMessage: (m: WsMessage) => void) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const handler = useRef(onMessage);
  handler.current = onMessage;

  useEffect(() => {
    if (!investigationId) return;
    let closed = false;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let ws: WebSocket | null = null;

    const connect = () => {
      if (closed) return;
      const token = getToken();
      if (!token) return;
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${proto}//${window.location.host}/ws?token=${encodeURIComponent(token)}&investigation_id=${encodeURIComponent(investigationId)}`;
      try {
        ws = new WebSocket(url);
      } catch {
        return;
      }
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onmessage = (ev) => {
        try {
          handler.current(JSON.parse(ev.data) as WsMessage);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) retry = setTimeout(connect, 4000);
      };
      ws.onerror = () => ws?.close();
    };

    connect();
    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      wsRef.current?.close();
      wsRef.current = null;
      setConnected(false);
    };
  }, [investigationId]);

  return { connected };
}
