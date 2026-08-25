import { useCallback, useEffect, useRef, useState } from "react";
import {
  getEvents, getSnapshot, pauseSimulation, resumeSimulation, stopSimulation,
  type TranscriptEvent, type WorldSnapshot,
} from "@/lib/api";
import { replaySnapshot, replayEventsUpTo } from "@/lib/mock";

export interface Telemetry {
  snap: WorldSnapshot | null;
  events: TranscriptEvent[];
  status: string;                 // running | paused | completed | failed | connecting | offline-replay
  source: "live" | "replay" | "connecting";
  error: string | null;
  controls: {
    pause: () => void;
    resume: () => void;
    stop: () => void;
  };
}

/**
 * Unified run telemetry. Live-polls snapshot + incremental transcript.
 * If the API is unreachable (Render cold-start / network), degrades to a
 * local replay of the canonical archived run so the console is never dead.
 */
export function useRunTelemetry(simId: string | undefined): Telemetry {
  const [snap, setSnap] = useState<WorldSnapshot | null>(null);
  const [events, setEvents] = useState<TranscriptEvent[]>([]);
  const [status, setStatus] = useState("connecting");
  const [source, setSource] = useState<"live" | "replay" | "connecting">("connecting");
  const [error, setError] = useState<string | null>(null);

  const cursor = useRef(0);
  const replayT = useRef(0);
  const liveRef = useRef(false);

  useEffect(() => {
    if (!simId) return;
    let alive = true;

    const pollLive = async () => {
      try {
        const s = await getSnapshot(simId);
        if (!alive) return;
        liveRef.current = true;
        setSource("live");
        setSnap(s);
        setStatus(s.runtime_status || "running");
        setError(null);

        const evts = await getEvents(simId, cursor.current);
        if (!alive || !evts.length) return;
        cursor.current = Math.max(...evts.map((e) => e.id ?? 0), cursor.current);
        setEvents((prev) => {
          const seen = new Set(prev.map((p) => p.id));
          return [...prev, ...evts.filter((e) => !seen.has(e.id))].slice(-500);
        });
      } catch {
        // degrade to replay only after first failure
        if (alive && !liveRef.current && source !== "live") {
          setSource("replay");
          setError("backend unreachable â€” replaying archived run");
        }
      }
    };

    pollLive();
    const iv = setInterval(() => {
      if (liveRef.current) pollLive();
    }, 1600);

    return () => {
      alive = false;
      clearInterval(iv);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simId]);

  // replay clock when degraded
  useEffect(() => {
    if (source !== "replay") return;
    let alive = true;
    const iv = setInterval(() => {
      if (!alive) return;
      replayT.current += 0.5;
      setSnap(replaySnapshot(replayT.current));
      setEvents(replayEventsUpTo(replayT.current));
      setStatus(replayT.current >= 30 ? 'completed' : 'running');
    }, 400);
    return () => {
      alive = false;
      clearInterval(iv);
    };
  }, [source]);

  const controls = {
    pause: () => simId && pauseSimulation(simId).catch(() => {}),
    resume: () => simId && resumeSimulation(simId).catch(() => {}),
    stop: () => simId && stopSimulation(simId).catch(() => {}),
  };

  return { snap, events, status, source, error, controls };
}

