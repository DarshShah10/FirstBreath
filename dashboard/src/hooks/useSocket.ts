import { useEffect, useRef, useCallback, useState } from 'react';
import { io, Socket } from 'socket.io-client';

export interface SimulationEvent {
  type: 'step' | 'case_update' | 'agent_state' | 'alert';
  simulation_id: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface UseSocketOptions {
  simulationId?: string;
  autoConnect?: boolean;
  reconnect?: boolean;
  onStep?: (data: Record<string, unknown>) => void;
  onCaseUpdate?: (data: Record<string, unknown>) => void;
  onAgentState?: (data: Record<string, unknown>) => void;
  onAlert?: (data: Record<string, unknown>) => void;
}

export interface UseSocketReturn {
  isConnected: boolean;
  lastEvent: SimulationEvent | null;
  connect: () => void;
  disconnect: () => void;
  subscribe: (simulationId: string) => void;
  unsubscribe: (simulationId: string) => void;
  emitPing: () => void;
}

const SOCKET_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001';

export function useSocket(options: UseSocketOptions = {}): UseSocketReturn {
  const {
    simulationId,
    autoConnect = true,
    reconnect = true,
    onStep,
    onCaseUpdate,
    onAgentState,
    onAlert,
  } = options;

  const socketRef = useRef<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<SimulationEvent | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;

  const handleEvent = useCallback((event: SimulationEvent) => {
    setLastEvent(event);

    switch (event.type) {
      case 'step':
        onStep?.(event.data);
        break;
      case 'case_update':
        onCaseUpdate?.(event.data);
        break;
      case 'agent_state':
        onAgentState?.(event.data);
        break;
      case 'alert':
        onAlert?.(event.data);
        break;
    }
  }, [onStep, onCaseUpdate, onAgentState, onAlert]);

  const connect = useCallback(() => {
    if (socketRef.current?.connected) return;

    socketRef.current = io(SOCKET_URL, {
      transports: ['websocket', 'polling'],
      reconnection: reconnect,
      reconnectionAttempts: maxReconnectAttempts,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      timeout: 10000,
    });

    const socket = socketRef.current;

    socket.on('connect', () => {
      console.log('[Socket] Connected:', socket.id);
      setIsConnected(true);
      reconnectAttemptsRef.current = 0;

      if (simulationId) {
        socket.emit('subscribe', { simulation_id: simulationId });
      }
    });

    socket.on('disconnect', (reason) => {
      console.log('[Socket] Disconnected:', reason);
      setIsConnected(false);
    });

    socket.on('connect_error', (error) => {
      console.error('[Socket] Connection error:', error.message);
      reconnectAttemptsRef.current += 1;
    });

    socket.on('connected', (data) => {
      console.log('[Socket] Server acknowledged:', data);
    });

    socket.on('subscribed', (data) => {
      console.log('[Socket] Subscribed to:', data.room);
    });

    socket.on('step', (data) => {
      handleEvent({
        type: 'step',
        simulation_id: simulationId || '',
        data,
        timestamp: new Date().toISOString(),
      });
    });

    socket.on('case_update', (data) => {
      handleEvent({
        type: 'case_update',
        simulation_id: simulationId || '',
        data,
        timestamp: new Date().toISOString(),
      });
    });

    socket.on('agent_state', (data) => {
      handleEvent({
        type: 'agent_state',
        simulation_id: simulationId || '',
        data,
        timestamp: new Date().toISOString(),
      });
    });

    socket.on('alert', (data) => {
      handleEvent({
        type: 'alert',
        simulation_id: simulationId || '',
        data,
        timestamp: new Date().toISOString(),
      });
    });

    socket.on('pong', (data) => {
      console.log('[Socket] Ping response:', data);
    });
  }, [simulationId, reconnect, handleEvent]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      if (simulationId) {
        socketRef.current.emit('unsubscribe', { simulation_id: simulationId });
      }
      socketRef.current.disconnect();
      socketRef.current = null;
      setIsConnected(false);
    }
  }, [simulationId]);

  const subscribe = useCallback((simId: string) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('subscribe', { simulation_id: simId });
    }
  }, []);

  const unsubscribe = useCallback((simId: string) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('unsubscribe', { simulation_id: simId });
    }
  }, []);

  const emitPing = useCallback(() => {
    socketRef.current?.emit('ping');
  }, []);

  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  return {
    isConnected,
    lastEvent,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    emitPing,
  };
}

export default useSocket;
