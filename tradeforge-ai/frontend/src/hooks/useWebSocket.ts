/**
 * TradeForge AI — React hook for Socket.IO real-time streams.
 *
 * Wraps the socket.io-client API with connection state tracking,
 * automatic reconnect (via Socket.IO built-ins), JSON message parsing,
 * room subscription, and a typed sender.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { io, type Socket } from 'socket.io-client';

export type WebSocketReadyState = 'connecting' | 'open' | 'closing' | 'closed' | 'error';

export interface UseWebSocketOptions {
  url: string | null;
  room?: string;
  onMessage?: (data: unknown) => void;
  onError?: (error: Error) => void;
  onOpen?: () => void;
  onClose?: (reason: string) => void;
}

export interface UseWebSocketReturn {
  readyState: WebSocketReadyState;
  lastMessage: unknown | null;
  sendMessage: (message: unknown) => void;
  error: Error | null;
  connect: () => void;
  disconnect: () => void;
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const { url, room, onMessage, onError, onOpen, onClose } = options;

  const [readyState, setReadyState] = useState<WebSocketReadyState>('closed');
  const [lastMessage, setLastMessage] = useState<unknown | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const socketRef = useRef<Socket | null>(null);
  const intentionalCloseRef = useRef(false);

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
    setReadyState('closed');
  }, []);

  const connect = useCallback(() => {
    if (!url) return;

    disconnect();
    intentionalCloseRef.current = false;

    try {
      const socket = io(url, {
        transports: ['websocket'],
        autoConnect: true,
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
      });
      socketRef.current = socket;
      setReadyState('connecting');

      socket.on('connect', () => {
        setReadyState('open');
        setError(null);
        onOpen?.();
        if (room) {
          socket.emit('subscribe', { room });
        }
      });

      socket.on('disconnect', (reason) => {
        setReadyState('closed');
        onClose?.(reason);
      });

      socket.on('connect_error', (err) => {
        setReadyState('error');
        setError(err);
        onError?.(err);
      });

      socket.on('trade', (data: unknown) => {
        setLastMessage(data);
        onMessage?.(data);
      });

      socket.on('portfolio_update', (data: unknown) => {
        setLastMessage(data);
        onMessage?.(data);
      });
    } catch (err) {
      setReadyState('error');
      const wrapped = err instanceof Error ? err : new Error(String(err));
      setError(wrapped);
      onError?.(wrapped);
      // eslint-disable-next-line no-console
      console.error('Socket.IO connection error:', err);
    }
  }, [url, room, onMessage, onError, onOpen, onClose, disconnect]);

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
      const socket = socketRef.current;
      if (!socket || !socket.connected) {
        // eslint-disable-next-line no-console
        console.warn('Cannot send Socket.IO message: connection is not open');
        return;
      }
      socket.emit('message', message);
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
