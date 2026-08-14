import { useEffect, useRef, useState, useCallback } from 'react';

interface WebSocketOptions {
  onMessage?: (data: any) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

export const useWebSocket = (
  url: string,
  options: WebSocketOptions = {}
) => {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const closedByUsRef = useRef(false);

  // Callers pass inline arrow functions, so these change identity on every
  // render. Keep them in a ref so the socket lifecycle depends only on `url`.
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const clearReconnect = useCallback(() => {
    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    closedByUsRef.current = false;
    clearReconnect();

    try {
      // If there's an existing socket, close it first
      if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
        try {
          wsRef.current.onclose = null;
          wsRef.current.close(1000, 'reconnecting');
        } catch {}
      }

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected', url);
        reconnectAttemptsRef.current = 0;
        clearReconnect();
        setConnected(true);
        optionsRef.current.onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
          optionsRef.current.onMessage?.(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error, 'raw:', event.data);
        }
      };

      ws.onclose = (event: CloseEvent) => {
        console.warn('WebSocket closed', { code: event.code, reason: event.reason, wasClean: event.wasClean });
        setConnected(false);
        optionsRef.current.onDisconnect?.();

        // Don't reconnect when we closed the socket ourselves (unmount, url
        // change, explicit disconnect). A client-initiated close() with no
        // status code reports as 1005, so we can't rely on the code alone.
        if (closedByUsRef.current) {
          return;
        }

        const attempts = ++reconnectAttemptsRef.current;
        const delay = Math.min(3000 * attempts, 30000); // backoff up to 30s
        console.log(`Reconnecting in ${delay}ms (attempt ${attempts})`);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, delay);
      };

      ws.onerror = (event) => {
        console.error('WebSocket error event:', event);
        optionsRef.current.onError?.(event);
        // The socket will usually be closed after an error; the onclose handler will decide reconnects
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
    }
  }, [url, clearReconnect]);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected');
    }
  }, []);

  const disconnect = useCallback(() => {
    closedByUsRef.current = true;
    reconnectAttemptsRef.current = 0;
    clearReconnect();
    try {
      wsRef.current?.close(1000, 'client disconnect');
    } catch {}
    wsRef.current = null;
  }, [clearReconnect]);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connected,
    lastMessage,
    sendMessage,
    disconnect,
  };
};
