import { Link, useParams } from "react-router-dom";
import { useEffect, useRef } from "react";
import CityMap from "@/components/map/CityMap";
import Footer from "@/components/system/Footer";
import Ticker from "@/components/system/Ticker";
import { Button, Readout, Stamp } from "@/components/ui/kit";
import { EventFeed, GoldenClock } from "@/components/timeline/TimelineKit";
import { useRunTelemetry } from "@/hooks/useRunTelemetry";
import { fmtClock, titleCase } from "@/lib/format";

export default function Run() {
  const { simId = "" } = useParams();
  const { snap, events, status, source, error, controls } = useRunTelemetry(simId);
  const feedRef = useRef<HTMLDivElement>(null);
  const done = ["completed", "stopped", "failed"].includes(status);

  // keep the transcript pinned to the newest transmission
  useEffect(() => {
    const el = feedRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events.length]);

  const openCases = snap?.cases.filter((c) => !["completed", "failed"].includes(c.status)) ?? [];
  const radioLines = events
    .filter((e) => e.event_type === "radio" || e.event_type === "agent_decision")
    .slice(-6)
    .map((e) => e.payload?.description || "")
    .filter(Boolean);

  return (
    <div className="flex min-h-screen flex-col">
      {/* command strip */}
      <div className="sticky top-0 z-40 border-b border-line bg-void/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1700px] flex-wrap items-center gap-x-10 gap-y-3 px-5 py-4 md:px-10">
          <Link to="/" className="font-mono text-[10px] uppercase tracking-[0.25em] text-faint hover:text-bone">
            ← firstbreath
          </Link>

          <GoldenClock minutes={snap?.sim_time ?? 0} size="md"
            tone={openCases.length && !done ? (openCases.some((c) => c.minutes_left < 6) ? "text-red" : "text-amber") : "text-green"} />

          <div className="hidden h-9 w-px bg-line md:block" />

          <Readout label="active cases" value={
            <span className={openCases.length ? "text-red" : "text-green"}>{String(openCases.length).padStart(2, "0")}</span>
          } />
          <Readout label="units committed" value={snap?.ambulances.filter((a) => a.case_id).length ?? "—"} />
          <Readout label="transmissions" value={events.length} />

          <div className="ml-auto flex items-center gap-3">
            {source === "replay" && (
              <Stamp tone="amber">offline replay</Stamp>
            )}
            <Stamp tone={status === "running" ? "green" : status === "paused" ? "amber" : done ? "neutral" : "red"}>
              {status}
            </Stamp>
            {!done && source === "live" && (
              <>
                {status === "paused" ? (
                  <Button variant="outline" className="!px-4 !py-2" onClick={controls.resume}>resume</Button>
                ) : (
                  <Button variant="outline" className="!px-4 !py-2" onClick={controls.pause}>pause</Button>
                )}
                <Button variant="ghost" className="!px-4 !py-2" onClick={controls.stop}>abort</Button>
              </>
            )}
            {done && simId && (
              <Link to={`/debrief/${simId}`}>
                <Button className="!px-4 !py-2">mission debrief</Button>
              </Link>
            )}
          </div>
        </div>
        {error && (
          <div className="border-t border-amber/30 bg-amber/5 px-5 py-1.5 text-center font-mono text-[10px] uppercase tracking-[0.2em] text-amber">
            {error}
          </div>
        )}
      </div>

      {/* main stage */}
      <div className="grid flex-1 grid-cols-1 lg:grid-cols-[1fr_400px]">
        {/* map */}
        <div className="relative min-h-[52vh] border-b border-line lg:border-b-0 lg:border-r">
          <CityMap snapshot={snap} />
          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between p-4">
            <div className="font-mono text-[9px] uppercase tracking-[0.25em] text-faint">
              live district feed · 1.6s poll
            </div>
          </div>
        </div>

        {/* right rail */}
        <aside className="flex flex-col">
          {/* case vitals */}
          <div className="space-y-px border-b border-line">
            {snap?.cases.map((c) => {
              const closed = ["completed", "failed"].includes(c.status);
              const urgent = !closed && c.minutes_left < 6;
              return (
                <div key={c.id} className={cn(
                  "px-6 py-4",
                  closed ? "bg-panel/40 opacity-60" : urgent ? "bg-red/[0.06]" : "bg-panel"
                )}>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold">{c.id.replace("case_", "CASE ").toUpperCase()}</span>
                    <Stamp tone={c.outcome?.includes("success") ? (c.outcome === "late_success" ? "amber" : "green") : closed ? "red" : urgent ? "red" : "amber"}>
                      {titleCase(c.outcome || c.status)}
                    </Stamp>
                  </div>
                  <div className="mt-1.5 font-display text-lg font-semibold">
                    {titleCase(c.emergency_type)}
                  </div>
                  <div className="mt-0.5 font-mono text-[10px] text-faint">{c.location?.address}</div>
                  {!closed && (
                    <div className="mt-3">
                      <div className="flex justify-between font-mono text-[10px] text-faint">
                        <span>window</span>
                        <span className={urgent ? "font-bold text-red" : "text-amber"}>
                          T−{fmtClock(c.minutes_left)}
                        </span>
                      </div>
                      <div className="mt-1 h-[3px] w-full bg-line">
                        <div
                          className={cn("h-full transition-all duration-700", urgent ? "bg-red" : "bg-amber")}
                          style={{ width: `${Math.max(2, Math.min(100, (c.minutes_left / Math.max(c.deadline, 1)) * 100))}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
            {!snap?.cases.length && (
              <div className="px-6 py-8 text-center font-mono text-xs text-faint">awaiting telemetry…</div>
            )}
          </div>

          {/* transcript */}
          <div ref={feedRef} className="flex-1 overflow-y-auto px-6 py-4" style={{ maxHeight: "48vh" }}>
            <EventFeed events={[...events].reverse()} />
          </div>
        </aside>
      </div>

      {/* radio ticker */}
      <div className="border-t border-line bg-panel">
        <Ticker items={radioLines.length ? radioLines : ["channel open — agents standing by"]} />
      </div>

      <Footer />
    </div>
  );
}

function cn(...args: Array<string | false | null | undefined>): string {
  return args.filter(Boolean).join(" ");
}
