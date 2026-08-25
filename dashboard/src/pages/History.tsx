import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Footer from "@/components/system/Footer";
import { Kicker, Stamp } from "@/components/ui/kit";
import { getHistory } from "@/lib/api";

export default function History() {
  const nav = useNavigate();
  const [runs, setRuns] = useState<Array<Record<string, any>>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getHistory().then(setRuns).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      <div className="mx-auto w-full max-w-[1200px] flex-1 px-6 pt-28 md:px-12">
        <Kicker index="§" label="the archive" />
        <h1 className="mt-6 font-display text-5xl font-bold tracking-tight md:text-7xl">HISTORY</h1>
        <p className="mt-4 max-w-md text-sm text-mute">
          Every simulation is persisted with its full transcript. Open one to
          revisit the console — or read its debrief.
        </p>

        <div className="mt-14 border-t border-line pb-24">
          {/* header row */}
          <div className="hidden grid-cols-[1fr_140px_140px_90px] gap-4 border-b border-line py-3 font-mono text-[9px] uppercase tracking-[0.25em] text-faint md:grid">
            <span>simulation id</span>
            <span>created</span>
            <span>status</span>
            <span className="text-right">open</span>
          </div>

          {loading && (
            <div className="py-20 text-center font-mono text-xs text-faint">pulling archive…</div>
          )}

          {!loading && !runs.length && (
            <div className="py-20 text-center font-mono text-xs text-faint">
              archive empty — declare an emergency to begin
            </div>
          )}

          {runs.map((r) => (
            <button
              key={r.id}
              onClick={() => nav(`/run/${r.id}`)}
              data-cursor="link"
              className="group grid w-full grid-cols-2 items-baseline gap-4 border-b border-line py-4 text-left transition-colors hover:bg-panel md:grid-cols-[1fr_140px_140px_90px]"
            >
              <span className="truncate font-mono text-sm group-hover:text-red">{String(r.id)}</span>
              <span className="font-mono text-[11px] tnum text-faint">
                {String(r.created_at || "").slice(0, 16).replace("T", " ")}
              </span>
              <span>
                <Stamp tone={r.status === "completed" ? "green" : r.status === "failed" ? "red" : "amber"}>
                  {String(r.status)}
                </Stamp>
              </span>
              <span className="text-right font-mono text-[10px] uppercase tracking-[0.2em] text-faint transition-colors group-hover:text-bone">
                open →
              </span>
            </button>
          ))}
        </div>
      </div>
      <Footer />
    </div>
  );
}
