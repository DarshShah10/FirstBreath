import { useEffect, useRef, useCallback, useState } from 'react';
import { getSimulation, getSimulationResults } from '../api';
import type { SimulationState, SimulationResults } from '../types';

export interface UseSimulationPollingOptions {
  simulationId?: string;
  enabled?: boolean;
  interval?: number;
  onStateUpdate?: (state: SimulationState) => void;
  onResultsUpdate?: (results: SimulationResults) => void;
  onStatusChange?: (status: string) => void;
}

export interface UseSimulationPollingReturn {
  isPolling: boolean;
  lastPollTime: Date | null;
  pollNow: () => Promise<void>;
  error: Error | null;
}

export function useSimulationPolling(
  options: UseSimulationPollingOptions = {}
): UseSimulationPollingReturn {
  const {
    simulationId,
    enabled = true,
    interval = 2000,
    onStateUpdate,
    onResultsUpdate,
    onStatusChange,
  } = options;

  const [isPolling, setIsPolling] = useState(false);
  const [lastPollTime, setLastPollTime] = useState<Date | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const previousStatusRef = useRef<string | null>(null);

  const poll = useCallback(async () => {
    if (!simulationId) return;

    try {
      const data = await getSimulation(simulationId);
      const { simulation, simulation_state } = data;

      setLastPollTime(new Date());
      setError(null);

      if (simulation_state) {
        onStateUpdate?.(simulation_state);
      }

      if (simulation?.status !== previousStatusRef.current) {
        previousStatusRef.current = simulation?.status || null;
        onStatusChange?.(simulation?.status || 'unknown');

        if (simulation?.status === 'completed' || simulation?.status === 'stopped') {
          try {
            const results = await getSimulationResults(simulationId);
            onResultsUpdate?.(results);
          } catch (err) {
            console.error('[Polling] Failed to fetch results:', err);
          }
        }
      }
    } catch (err) {
      console.error('[Polling] Error:', err);
      setError(err instanceof Error ? err : new Error('Polling failed'));
    }
  }, [simulationId, onStateUpdate, onResultsUpdate, onStatusChange]);

  const pollNow = useCallback(async () => {
    await poll();
  }, [poll]);

  useEffect(() => {
    if (!enabled || !simulationId) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setIsPolling(false);
      return;
    }

    setIsPolling(true);

    poll();

    intervalRef.current = setInterval(poll, interval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setIsPolling(false);
    };
  }, [enabled, simulationId, interval, poll]);

  return {
    isPolling,
    lastPollTime,
    pollNow,
    error,
  };
}

export default useSimulationPolling;
