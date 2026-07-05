/**
 * TradeForge AI — React hook for WebSocket streams.
 *
 * Wraps the native `WebSocket` API with connection state tracking,
 * automatic reconnect, JSON message parsing, and a typed sender.
 *
 * Note: The backend Socket.IO server is not yet mounted; until then
 * this hook gracefully degrades to a "closed" state and can be pointed
 * at any plain WebSocket endpoint once available.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

export type WebSocketReadyState = 'connecting' | 'open' | 'closing' | 'closed' | 'error';

export interface UseWebSocketOptions {
  url: string | null;
  reconnect?: boolean;
  reconnectIntervalMs?: number;
  maxReconnects?: number;
  onMessage?: (data: unknown) => void;
  onError?: (event: Event) => void;
  onOpen?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
}

export interface UseWebSocketReturn {
  readyState: WebSocketReadyState;
  lastMessage: unknown | null;
  sendMessage: (message: unknown) => void;
  error: Event | null;
  connect: () => void;
  disconnect: () => void;
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    url,
    reconnect = true,
    reconnectIntervalMs = 3000,
    maxReconnects = 5,
    onMessage,
    onError,
    onOpen,
    onClose,
  } = options;

  const [readyState, setReadyState] = useState<WebSocketReadyState>('closed');
  const [lastMessage, setLastMessage] = useState<unknown | null>(null);
  const [error, setError] = useState<Event | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalCloseRef = useRef(false);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    clearReconnectTimer();
    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
    setReadyState('closed');
    reconnectCountRef.current = 0;
  }, [clearReconnectTimer]);

  const connect = useCallback(() => {
    if (!url) return;

    disconnect();
    intentionalCloseRef.current = false;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;
      setReadyState('connecting');

      ws.onopen = (event) => {
        setReadyState('open');
        setError(null);
        reconnectCountRef.current = 0;
        onOpen?.(event);
      };

      ws.onmessage = (event) => {
        let parsed: unknown;
        try {
          parsed = JSON.parse(event.data);
        } catch {
          parsed = event.data;
        }
        setLastMessage(parsed);
        onMessage?.(parsed);
      };

      ws.onerror = (event) => {
        setReadyState('error');
        setError(event);
        onError?.(event);
      };

      ws.onclose = (event) => {
        setReadyState('closed');
        onClose?.(event);

        if (!intentionalCloseRef.current && reconnect && reconnectCountRef.current < maxReconnects) {
          reconnectCountRef.current += 1;
          reconnectTimerRef.current = setTimeout(() => {
            connect();
          }, reconnectIntervalMs);
        }
      };
    } catch (err) {
      setReadyState('error');
      // eslint-disable-next-line no-console
      console.error('WebSocket connection error:', err);
    }
  }, [url, reconnect, reconnectIntervalMs, maxReconnects, onMessage, onError, onOpen, onClose, disconnect]);

  useEffect(() => {
    if (url) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [url, connect, disconnect]);

  const sendMessage = useCallback(
    (message: unknown) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        // eslint-disable-next-line no-console
        console.warn('Cannot send WebSocket message: connection is not open');
        return;
      }
      const payload = typeof message === 'string' ? message : JSON.stringify(message);
      ws.send(payload);
    },
    [],
  );

  return {
    readyState,
    lastMessage,
    sendMessage,
    error,
    connect,
    disconnect,
  };
}
