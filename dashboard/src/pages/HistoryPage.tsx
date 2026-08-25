import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Radio, ArrowRight } from 'lucide-react';
import TopBar from '@/components/TopBar';
import { Badge } from '@/components/ui/badge';
import { getHistory } from '@/api';

export default function HistoryPage() {
  const nav = useNavigate();
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getHistory().then(setRuns).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar />
      <div className="bg-grid mx-auto w-full max-w-[1100px] flex-1 px-6 py-10">
        <div className="pb-8">
          <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-faint">archive</div>
          <h1 className="mt-1 font-display text-4xl font-bold tracking-tight">Run history</h1>
        </div>

        {loading && <div className="py-20 text-center font-mono text-sm text-faint">loading archive…</div>}

        {!loading && runs.length === 0 && (
          <div className="rounded-lg border border-dashed border-line p-16 text-center">
            <Radio className="mx-auto mb-3 text-faint" size={26} />
            <div className="font-display text-lg font-semibold">No simulations yet</div>
            <p className="mx-auto mt-1 max-w-sm text-sm text-muted">
              Declare your first emergency and it will land here with its full transcript.
            </p>
            <Link to="/new" className="mt-4 inline-block">
              <Badge tone="emergency" className="cursor-pointer px-4 py-1.5 text-xs">declare emergency</Badge>
            </Link>
          </div>
        )}

        <div className="space-y-2">
          {runs.map((r, i) => (
            <motion.button
              key={r.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.04, 0.4) }}
              onClick={() => nav(`/run/${r.id}`)}
              className="group flex w-full cursor-pointer items-center gap-4 rounded-lg border border-line bg-panel/60 px-5 py-4 text-left transition-all hover:border-line-bright hover:bg-panel"
            >
              <span className={`h-2 w-2 rounded-full ${
                r.status === 'completed' ? 'bg-go' : r.status === 'failed' ? 'bg-emergency' : 'bg-warn'
              } shadow-current`} />
              <div className="min-w-0 flex-1">
                <div className="truncate font-mono text-sm">{r.id}</div>
                <div className="text-[11px] text-faint">
                  created {String(r.created_at).slice(0, 19).replace('T', ' ')} UTC
                </div>
              </div>
              <Badge tone={r.status === 'created' ? 'neutral' : r.status === 'completed' ? 'go' : 'warn'}>
                {r.status}
              </Badge>
              <ArrowRight size={15} className="text-faint transition-transform group-hover:translate-x-1 group-hover:text-ink" />
            </motion.button>
          ))}
        </div>
      </div>
    </div>
  );
}
