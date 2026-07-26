// WebSocket client with auto-reconnect. Emits envelopes {topic, ts, data} from
// the backend hub (docs/04-api-contract.md#websocket-ws).
import { useEffect, useRef, useState } from "react";
import { getToken } from "./auth";

export interface Envelope<T = unknown> {
  topic: string;
  ts: number;
  data: T;
}

function wsUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const token = getToken();
  return `${proto}://${location.host}/ws${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}

/** Subscribe to a single topic; returns the latest payload for that topic. */
export function useTopic<T>(topic: string): T | null {
  const [value, setValue] = useState<T | null>(null);
  const ref = useRef<WebSocket | null>(null);

  useEffect(() => {
    let closed = false;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      const ws = new WebSocket(wsUrl());
      ref.current = ws;
      ws.onmessage = (e) => {
        const env = JSON.parse(e.data) as Envelope<T>;
        if (env.topic === topic) setValue(env.data);
      };
      ws.onclose = () => {
        if (!closed) retry = setTimeout(connect, 1500);
      };
      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      closed = true;
      clearTimeout(retry);
      ref.current?.close();
    };
  }, [topic]);

  return value;
}
