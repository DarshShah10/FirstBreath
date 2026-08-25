import { fmtClock } from "@/lib/format";
import { cn } from "@/lib/cn";

/** The Golden Hour clock — the design's protagonist. */
export function GoldenClock({
  minutes,
  size = "md",
  tone,
  label = "golden hour",
}: {
  minutes: number;
  size?: "md" | "xl";
  tone?: string;
  label?: string;
}) {
  return (
    <div className="flex flex-col">
      <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-faint">{label}</span>
      <span
        className={cn(
          "font-display font-bold tnum leading-[0.95] tracking-tight",
          size === "xl"
            ? "text-[clamp(3rem,8vw,7.5rem)]"
            : "text-4xl md:text-5xl",
          tone ?? (minutes <= 5 ? "text-red" : minutes <= 10 ? "text-amber" : "text-bone")
        )}
      >
        {fmtClock(minutes)}
      </span>
    </div>
  );
}

const EVENT_TONE: Record<string, { color: string; label: string }> = {
  radio: { color: "text-teal-300", label: "RADIO" },
  agent_decision: { color: "text-blue", label: "BRAIN" },
  dispatch: { color: "text-amber", label: "DISPATCH" },
  pre_alert: { color: "text-blue", label: "PRE-ALERT" },
  ot_reserved: { color: "text-blue", label: "OT" },
  ot_ready: { color: "text-green", label: "OT READY" },
  staff_paged: { color: "text-blue", label: "PAGE" },
  staff_arrived: { color: "text-green", label: "STAFF IN" },
  blood_requested: { color: "text-amber", label: "BLOOD" },
  blood_ready: { color: "text-green", label: "BLOOD OK" },
  reroute: { color: "text-red", label: "REROUTE" },
  traffic_changed: { color: "text-amber", label: "TRAFFIC" },
  amb_departed: { color: "text-mute", label: "ROLLING" },
  arrived_patient: { color: "text-blue", label: "ON SCENE" },
  transport_started: { color: "text-blue", label: "TRANSPORT" },
  arrived_hospital: { color: "text-green", label: "ARRIVED" },
  case_completed: { color: "text-green", label: "OUTCOME" },
  case_failed: { color: "text-red", label: "FAILED" },
  action_rejected: { color: "text-red", label: "REJECT" },
  case_queued: { color: "text-red", label: "CALL" },
  escalated: { color: "text-red", label: "ESCALATE" },
  run_started: { color: "text-mute", label: "START" },
  run_completed: { color: "text-green", label: "COMPLETE" },
};

export function eventTone(t: string) {
  return EVENT_TONE[t] ?? { color: "text-faint", label: t.replace(/_/g, " ").toUpperCase() };
}

/**
 * EventFeed — the transcript as an editorial chronology.
 * One row per event: timestamp · stamp · description.
 */
export function EventFeed({
  events,
  className,
  maxHeight,
}: {
  events: Array<{ id?: number; event_type: string; sim_time: number; agent_id?: string | null; payload: Record<string, any> }>;
  className?: string;
  maxHeight?: string;
}) {
  const visible = events.filter((e) => e.event_type !== "tick");
  return (
    <div
      className={cn("flow-root", className)}
      style={maxHeight ? { maxHeight, overflowY: "auto" } : undefined}
    >
      {visible.map((e, i) => {
        const tone = eventTone(e.event_type);
        const desc: string = e.payload?.description || "";
        return (
          <div key={e.id ?? i} className="group grid grid-cols-[64px_92px_1fr] items-baseline gap-3 border-t border-line/60 py-2.5 first:border-t-0">
            <span className="font-mono text-[11px] tnum text-faint transition-colors group-hover:text-mute">
              {fmtClock(e.sim_time)}
            </span>
            <span className={`font-mono text-[9px] uppercase tracking-[0.18em] ${tone.color}`}>
              {tone.label}
            </span>
            <span className="text-[13px] leading-snug text-bone/85">
              {desc}
              {e.agent_id && (
                <span className="ml-2 font-mono text-[10px] text-faint">— {e.agent_id}</span>
              )}
            </span>
          </div>
        );
      })}
      {!visible.length && (
        <div className="py-10 text-center font-mono text-xs text-faint">
          channel open — awaiting first transmission
        </div>
      )}
    </div>
  );
}

/** Vertical progress rail used by pinned scroll sections. */
export function ProgressRail({ progress }: { progress: number }) {
  return (
    <div className="pointer-events-none absolute left-6 top-1/2 hidden h-[46vh] -translate-y-1/2 flex-col items-center gap-3 md:flex">
      <span className="font-mono text-[9px] tracking-[0.25em] text-faint">T+00</span>
      <div className="relative w-px flex-1 bg-line">
        <div
          className="absolute left-0 top-0 w-px bg-red"
          style={{ height: `${Math.round(progress * 100)}%` }}
        />
        <div
          className="absolute left-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-red shadow-[0_0_12px_rgba(229,72,77,0.9)]"
          style={{ top: `${Math.round(progress * 100)}%` }}
        />
      </div>
      <span className="font-mono text-[9px] tracking-[0.25em] text-faint">T+30</span>
    </div>
  );
}
