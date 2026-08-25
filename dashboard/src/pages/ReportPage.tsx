import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  CheckCircle2, XCircle, Clock, ArrowLeft, Siren,
  Truck, Building2, Droplets, ListChecks,
} from 'lucide-react';
import TopBar from '@/components/TopBar';
import { Panel, PanelHeader, PanelTitle, PanelContent } from '@/components/ui/panel';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { getWorldSnapshot, type WorldSnapshot } from '@/api';
import { fmtClock } from '@/lib/utils';

export default function ReportPage() {
  const { simId } = useParams<{ simId: string }>();
  const [snap, setSnap] = useState<WorldSnapshot | null>(null);

  useEffect(() => {
    if (!simId) return;
    getWorldSnapshot(simId).then(setSnap).catch(() => {});
  }, [simId]);

  const cases = snap?.cases ?? [];
  const wins = cases.filter((c) => c.outcome?.includes('success')).length;
  const allDone = cases.length > 0 && cases.every((c) => ['completed', 'failed'].includes(c.status));

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar />
      <div className="bg-grid mx-auto w-full max-w-[1200px] flex-1 px-6 py-10">
        <Link to="/new" className="mb-6 inline-flex items-center gap-1.5 font-mono text-xs text-muted hover:text-ink">
          <ArrowLeft size={13} /> new emergency
        </Link>

        {/* verdict banner */}
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className={`relative overflow-hidden rounded-xl border p-8 ${
            !allDone ? 'border-warn/40 bg-warn/5'
            : wins === cases.length ? 'border-go/50 bg-go/8'
            : wins > 0 ? 'border-warn/40 bg-warn/5'
            : 'border-emergency/50 bg-emergency/8'
          }`}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-faint">mission debrief Â· {simId?.slice(0, 14)}</div>
              <h1 className="mt-2 font-display text-4xl font-bold tracking-tight sm:text-5xl">
                {!allDone ? 'Response in progress' :
                 wins === cases.length ? 'All patients delivered' :
                 wins > 0 ? 'Partial success' : 'Windows missed'}
              </h1>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">
                {allDone
                  ? `${wins} of ${cases.length} case(s) reached definitive care inside the golden-hour window. Every decision below is reconstructed from the live transcript.`
                  : 'The simulation is still running â€” this debrief will finalize when the run completes.'}
              </p>
            </div>
            {!allDone && (
              <Link to={`/run/${simId}`}>
                <Button variant="outline" size="sm">Back to console</Button>
              </Link>
            )}
          </div>
        </motion.div>

        {/* case cards */}
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          {cases.map((c, i) => {
            const ok = c.outcome?.includes('success');
            const late = c.outcome === 'late_success';
            return (
              <motion.div
                key={c.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08, duration: 0.45 }}
              >
                <Panel className="h-full">
                  <PanelHeader className="justify-between">
                    <PanelTitle className="flex items-center gap-2">
                      {ok ? <CheckCircle2 size={15} className="text-go" /> : <XCircle size={15} className="text-emergency" />}
                      {c.id.replace('case_', 'CASE ')}
                    </PanelTitle>
                    <Badge tone={ok ? (late ? 'warn' : 'go') : 'emergency'}>
                      {(c.outcome || c.status || '').replace('_', ' ')}
                    </Badge>
                  </PanelHeader>
                  <PanelContent className="space-y-4">
                    <div className="grid grid-cols-3 gap-3 font-mono text-[11px]">
                      <div>
                        <div className="text-[9px] uppercase tracking-widest text-faint">emergency</div>
                        <div className="mt-0.5 capitalize">{(c.emergency_type || '').replace('_', ' ')}</div>
                      </div>
                      <div>
                        <div className="text-[9px] uppercase tracking-widest text-faint">severity</div>
                        <div className="mt-0.5 uppercase">{c.severity}</div>
                      </div>
                      <div>
                        <div className="text-[9px] uppercase tracking-widest text-faint">window</div>
                        <div className="mt-0.5 text-warn tabular-nums">{fmtClock(c.deadline)}</div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div className="flex items-center gap-2 rounded-md border border-line bg-abyss px-3 py-2 text-xs">
                        <Truck size={14} className="text-teal" />
                        {c.ambulance_id || 'â€”'}
                      </div>
                      <div className="flex items-center gap-2 rounded-md border border-line bg-abyss px-3 py-2 text-xs capitalize">
                        <Building2 size={14} className="text-info" />
                        {c.hospital_id?.replace('hospital_', '') || 'â€”'}
                      </div>
                    </div>

                    {/* timeline */}
                    <div>
                      <div className="mb-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-faint">
                        <ListChecks size={11} /> decision timeline
                      </div>
                      <div className="space-y-0">
                        {(c.timeline || []).map((t, j) => (
                          <div key={j} className="flex items-baseline gap-3 border-l border-line py-1 pl-3 text-[12px]">
                            <span className="font-mono text-[10px] tabular-nums text-teal">T+{fmtClock(t.sim_time)}</span>
                            <span className="text-muted">{t.note}</span>
                          </div>
                        ))}
                        {!c.timeline?.length && <div className="text-xs text-faint">no timeline recorded</div>}
                      </div>
                    </div>
                  </PanelContent>
                </Panel>
              </motion.div>
            );
          })}
        </div>

        {!cases.length && (
          <Panel className="mt-6">
            <PanelContent className="flex flex-col items-center gap-3 py-16 text-muted">
              <Siren size={28} />
              <div className="font-mono text-sm">no telemetry found for this run</div>
              <Link to="/new"><Button size="sm" className="mt-2">Declare an emergency</Button></Link>
            </PanelContent>
          </Panel>
        )}
      </div>
    </div>
  );
}

