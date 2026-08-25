import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import Footer from "@/components/system/Footer";
import { Button, Kicker, Readout, Stamp } from "@/components/ui/kit";
import { EventFeed, GoldenClock } from "@/components/timeline/TimelineKit";
import { getEvents, getResults, getSnapshot, type TranscriptEvent, type WorldSnapshot } from "@/lib/api";
import { fmtClock, titleCase } from "@/lib/format";

export default function Debrief() {
  const { simId = "" } = useParams();
  const [snap, setSnap] = useState<WorldSnapshot | null>(null);
  const [events, setEvents] = useState<TranscriptEvent[]>([]);
  const [results, setResults] = useState<Record<string, any> | null>(null);

  useEffect(() => {
    if (!simId) return;
    getSnapshot(simId).then(setSnap).catch(() => {});
    getEvents(simId).then(setEvents).catch(() => {});
    getResults(simId).then(setResults).catch(() => {});
  }, [simId]);

  const cases = snap?.cases ?? [];
  const wins = cases.filter((c) => c.outcome === "success").length;
  const lates = cases.filter((c) => c.outcome === "late_success").length;
  const fails = cases.filter((c) => c.outcome === "failed" || c.outcome === "failed_unassigned").length;
  const allDone = cases.length > 0 && cases.every((c) => ["completed", "failed"].includes(c.status));

  const decisions = useMemo(() => events.filter((e) => e.event_type === "agent_decision").length, [events]);
  const radios = useMemo(() => events.filter((e) => e.event_type === "radio").length, [events]);
  const simTime = snap?.sim_time ?? 0;

  const verdict =
    !allDone ? { word: "IN PROGRESS", tone: "text-amber", note: "The run is still live — this debrief finalizes when the chain resolves." }
      : fails > 0 ? { word: "WINDOWS MISSED", tone: "text-red", note: `${fails} case(s) never reached definitive care inside the window.` }
      : lates > 0 ? { word: "DELIVERED — LATE", tone: "text-amber", note: `${wins} inside the window, ${lates} late. The record shows exactly where the minutes went.` }
      : { word: "ALL DELIVERED", tone: "text-green", note: `Every case reached care inside its window. ${decisions} agent decisions on the record.` };

  // bottleneck read-out derived honestly from outcomes + transcript
  const bottlenecks = useMemo(() => {
    const out: Array<{ title: string; detail: string }> = [];
    const traffic = events.filter((e) => e.event_type === "traffic_changed");
    if (traffic.length && lates > 0) {
      out.push({
        title: "Road conditions ate the margin",
        detail: `${traffic.length} traffic event(s) recorded. The world model priced every one of them into the ETAs you see here.`,
      });
    }
    const lateCase = cases.find((c) => c.outcome === "late_success" || c.outcome?.startsWith("failed"));
    if (lateCase) {
      out.push({
        title: `${titleCase(lateCase.id)} crossed its line at T+${fmtClock(lateCase.deadline)}`,
        detail: `Dispatch happened at the times shown in the chronology; transport physics did the rest.`,
      });
    }
    if (!bottlenecks.length && allDone) {
      out.push({ title: "No single point of failure", detail: "Coordination held across dispatch, units and hospitals." });
    }
    return out;
  }, [events, cases, lates, allDone]);

  return (
    <div className="flex min-h-screen flex-col">
      <div className="mx-auto w-full max-w-[1400px] flex-1 px-6 pt-24 md:px-12">
        <Link to={`/run/${simId}`} className="mb-10 inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.25em] text-faint hover:text-bone">
          <ArrowLeft size={13} /> back to console
        </Link>

        {/* verdict */}
        <Kicker index="§" label={`mission debrief · ${simId.slice(0, 16)}`} />
        <h1 className={`mt-6 font-display font-bold leading-[0.9] tracking-tight ${verdict.tone} text-[clamp(3rem,9vw,8rem)]`}>
          {verdict.word}
        </h1>
        <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-mute">{verdict.note}</p>

        {/* stat wall */}
        <div className="mt-14 grid grid-cols-2 gap-px border border-line md:grid-cols-4">
          <WallStat label="mission clock" value={<GoldenClock minutes={simTime} />} />
          <WallStat label="inside window" value={`${wins}/${cases.length}`} tone={wins === cases.length ? "text-green" : "text-amber"} />
          <WallStat label="agent decisions" value={decisions} sub={`${radios} radio transmissions`} />
          <WallStat label="late deliveries" value={lates} tone={lates ? "text-red" : undefined} />
        </div>

        {/* two-column: chronology + findings */}
        <div className="mt-16 grid gap-12 pb-24 lg:grid-cols-[1fr_380px]">
          <div>
            <h2 className="font-display text-3xl font-bold tracking-tight">Chronology</h2>
            <p className="mt-2 max-w-lg text-sm text-mute">
              Reconstructed verbatim from the append-only transcript. No paraphrasing.
            </p>
            <div className="mt-8 border-t border-line">
              <EventFeed events={[...events].reverse()} maxHeight="70vh" />
            </div>
          </div>

          <aside className="space-y-10">
            <div>
              <h2 className="font-display text-2xl font-bold tracking-tight">Where it strained</h2>
              <div className="mt-5 space-y-4">
                {bottlenecks.map((b, i) => (
                  <div key={i} className="border-l-2 border-red/50 pl-4">
                    <div className="text-sm font-semibold">{b.title}</div>
                    <p className="mt-1 text-[13px] leading-relaxed text-mute">{b.detail}</p>
                  </div>
                ))}
                {!allDone && (
                  <Stamp tone="amber">debrief finalizes when the run completes</Stamp>
                )}
              </div>
            </div>

            {/* per-case ledger */}
            <div>
              <h2 className="font-display text-2xl font-bold tracking-tight">Case ledger</h2>
              <div className="mt-5 space-y-px border border-line">
                {cases.map((c) => (
                  <div key={c.id} className="bg-panel p-4">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs">{c.id.replace("case_", "").toUpperCase()}</span>
                      <Stamp tone={c.outcome === "success" ? "green" : c.outcome ? "amber" : "neutral"}>
                        {titleCase(c.outcome || c.status)}
                      </Stamp>
                    </div>
                    <div className="mt-1 text-sm capitalize text-mute">{titleCase(c.emergency_type)}</div>
                  </div>
                ))}
                {!cases.length && (
                  <div className="p-6 text-center font-mono text-xs text-faint">no telemetry</div>
                )}
              </div>
            </div>

            {results?.metrics && (
              <div className="border border-line p-5">
                <Readout
                  label="engine metrics"
                  value={<span className="text-sm">{JSON.stringify(results.metrics)}</span>}
                />
              </div>
            )}

            <Link to="/new">
              <Button>Run another emergency</Button>
            </Link>
          </aside>
        </div>
      </div>
      <Footer />
    </div>
  );
}

function WallStat({
  label, value, sub, tone,
}: {
  label: string; value: React.ReactNode; sub?: string; tone?: string;
}) {
  return (
    <div className="bg-panel p-6">
      <Readout label={label} value={value} sub={sub} tone={tone ?? "text-2xl"} />
    </div>
  );
}
