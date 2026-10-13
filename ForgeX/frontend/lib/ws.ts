
"use client";

// Live case channel: JOB_STATUS / JOB_COMPLETE / JOB_FAILED / SCRIPT_COMPLETE.
// REST polling should remain the source of truth if the socket is disconnected.

import { useEffect, useRef, useState } from "react";
import { getToken } from "@/lib/api";

export interface WsMessage {
  type: "JOB_STATUS" | "JOB_COMPLETE" | "JOB_FAILED" | "SCRIPT_COMPLETE" | string;
  [key: string]: unknown;
}

const RECONNECT_DELAY_MS = 4000;
const MAX_RECONNECT_DELAY_MS = 30000;

function buildWebSocketUrl(
  token: string,
  investigationId: string
): string {
  const configuredUrl = process.env.NEXT_PUBLIC_WS_URL;

  // Configure this to point directly to your deployed backend.
  // Example: wss://your-backend.onrender.com/ws
  const url = configuredUrl
    ? new URL(configuredUrl)
    : new URL("/ws", window.location.origin);

  // Convert HTTP(S) URLs to WebSocket protocols when necessary.
  if (url.protocol === "https:") {
    url.protocol = "wss:";
  } else if (url.protocol === "http:") {
    url.protocol = "ws:";
  }

  if (url.protocol !== "ws:" && url.protocol !== "wss:") {
    throw new Error("NEXT_PUBLIC_WS_URL must use ws:// or wss://.");
  }

  url.searchParams.set("token", token);
  url.searchParams.set("investigation_id", investigationId);

  return url.toString();
}

export function useCaseSocket(
  investigationId: string | null | undefined,
  onMessage: (message: WsMessage) => void
) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const handlerRef = useRef(onMessage);

  // Keep the latest callback without reconnecting the socket.
  handlerRef.current = onMessage;

  useEffect(() => {
    if (!investigationId) {
      setConnected(false);
      return;
    }

    let disposed = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let socket: WebSocket | null = null;
    let reconnectAttempts = 0;

    const connect = () => {
      if (disposed) return;

      const token = getToken();

      // Wait for authentication to become available.
      if (!token) {
        retryTimer = setTimeout(connect, RECONNECT_DELAY_MS);
        return;
      }

      let url: string;

      try {
        url = buildWebSocketUrl(token, investigationId);
      } catch (error) {
        console.error("WebSocket configuration error:", error);
        setConnected(false);
        return;
      }

      try {
        socket = new WebSocket(url);
        wsRef.current = socket;
      } catch (error) {
        console.error("Unable to create WebSocket:", error);
        scheduleReconnect();
        return;
      }

      socket.onopen = () => {
        if (disposed || socket !== wsRef.current) {
          socket?.close();
          return;
        }

        reconnectAttempts = 0;
        setConnected(true);
      };

      socket.onmessage = (event: MessageEvent<string>) => {
        if (disposed || socket !== wsRef.current) return;

        try {
          const message = JSON.parse(event.data) as WsMessage;

          if (
            message !== null &&
            typeof message === "object" &&
            typeof message.type === "string"
          ) {
            handlerRef.current(message);
          }
        } catch {
          console.warn("Ignoring malformed WebSocket message.");
        }
      };

      socket.onerror = () => {
        // onclose handles reconnection.
        socket?.close();
      };

      socket.onclose = () => {
        if (socket === wsRef.current) {
          wsRef.current = null;
          setConnected(false);
        }

        if (!disposed) {
          scheduleReconnect();
        }
      };
    };

    const scheduleReconnect = () => {
      if (disposed || retryTimer) return;

      const delay = Math.min(
        RECONNECT_DELAY_MS * 2 ** reconnectAttempts,
        MAX_RECONNECT_DELAY_MS
      );

      reconnectAttempts += 1;

      retryTimer = setTimeout(() => {
        retryTimer = undefined;
        connect();
      }, delay);
    };

    connect();

    return () => {
      disposed = true;

      if (retryTimer) {
        clearTimeout(retryTimer);
      }

      const currentSocket = socket;
      socket = null;

      if (wsRef.current === currentSocket) {
        wsRef.current = null;
      }

      if (currentSocket) {
        currentSocket.onopen = null;
        currentSocket.onmessage = null;
        currentSocket.onerror = null;
        currentSocket.onclose = null;
        currentSocket.close();
      }

      setConnected(false);
    };
  }, [investigationId]);

  return { connected };
}
