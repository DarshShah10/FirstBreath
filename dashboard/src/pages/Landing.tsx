import React, { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import TopBar from '@/components/TopBar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { StatBlock, LiveDot, Separator } from '@/components/ui/bits';
import { healthCheck, getStatus } from '@/api';

/* â”€â”€ animated aurora backdrop â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
function Aurora() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let raf = 0;
    let t = 0;
    const resize = () => {
      canvas.width = canvas.offsetWidth * (window.devicePixelRatio || 1);
      canvas.height = canvas.offsetHeight * (window.devicePixelRatio || 1);
    };
    resize();
    window.addEventListener('resize', resize);

    const blobs = [
      { x: 0.22, y: 0.3, r: 0.42, c: [255, 61, 81], s: 0.00016 },   // emergency red
      { x: 0.72, y: 0.62, r: 0.5, c: [45, 212, 191], s: 0.00011 },  // teal
      { x: 0.5, y: 0.85, r: 0.38, c: [77, 163, 255], s: 0.00013 },  // blue
      { x: 0.85, y: 0.15, r: 0.3, c: [255, 176, 46], s: 0.00019 },  // amber
    ];

    const draw = () => {
      t += 16;
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = 'lighter';
      for (const b of blobs) {
        const bx = (b.x + Math.sin(t * b.s * 1.3) * 0.08) * w;
        const by = (b.y + Math.cos(t * b.s) * 0.06) * h;
        const rad = b.r * Math.min(w, h) * (1 + Math.sin(t * b.s * 2.7) * 0.12);
        const g = ctx.createRadialGradient(bx, by, 0, bx, by, rad);
        g.addColorStop(0, `rgba(${b.c[0]},${b.c[1]},${b.c[2]},0.075)`);
        g.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);
      }
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      className="pointer-events-none absolute inset-0 h-full w-full opacity-90"
      aria-hidden
    />
  );
}

/* â”€â”€ radar sweep ornament â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
function RadarSweep() {
  return (
    <div className="relative h-44 w-44 select-none" aria-hidden>
      <div className="absolute inset-0 rounded-full border border-line" />
      <div className="absolute inset-6 rounded-full border border-line/70" />
      <div className="absolute inset-12 rounded-full border border-line/50" />
      <div className="absolute inset-[72px] rounded-full border border-line/40" />
      <div className="absolute left-1/2 top-1/2 h-px w-1/2 origin-left animate-[spin_4s_linear_infinite] bg-gradient-to-r from-teal to-transparent" />
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
        <span className="h-1.5 w-1.5 rounded-full bg-emergency block shadow-[0_0_10px_rgba(255,61,81,0.9)]" />
      </div>
    </div>
  );
}

export default function Landing() {
  const [status, setStatus] = useStatus();

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar />

      {/* hero */}
      <section className="bg-grid relative flex flex-1 flex-col items-center justify-center overflow-hidden px-6 py-24 text-center">
        <Aurora />
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-void" />

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 flex max-w-4xl flex-col items-center"
        >
          <Badge tone="emergency" className="mb-6 px-3 py-1">
            <LiveDot tone="bg-emergency" label="" />
            multi-agent response simulation Â· v2
          </Badge>

          <h1 className="font-display text-5xl font-bold leading-[1.02] tracking-tight sm:text-7xl md:text-8xl">
            Simulate the
            <br />
            <span className="bg-gradient-to-r from-emergency via-warn to-teal bg-clip-text text-transparent">
              Golden Hour.
            </span>
          </h1>

          <p className="mt-6 max-w-2xl text-balance text-base leading-relaxed text-muted sm:text-lg">
            A dispatcher AI, ambulance crews and hospital coordinators â€” real agents,
            reasoning under time pressure over honest physics. Every minute, bed and
            blood unit tracked. Every decision on the record.
          </p>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <Link to="/new">
              <Button size="lg" className="px-8">
                Declare an emergency
              </Button>
            </Link>
            <Link to="/history">
              <Button variant="outline" size="lg">
                View run history
              </Button>
            </Link>
          </div>

          <div className="mt-14 flex items-center gap-6 opacity-80">
            <RadarSweep />
          </div>
        </motion.div>
      </section>

      {/* live strip */}
      <section className="border-t border-line bg-abyss/60">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-10 gap-y-4 px-6 py-5">
          <LiveDot />
          <Separator vertical className="hidden h-8 sm:block" />
          <StatBlock
            label="engine"
            value={<span className="text-teal">ONLINE</span>}
            sub={status?.service ? String(status.service).slice(0, 28) : 'connectingâ€¦'}
          />
          <StatBlock label="simulations" value={status?.simulations?.total ?? 'â€”'} sub="total runs" />
          <StatBlock
            label="active now"
            value={
              <span className={(status?.simulations?.running ?? 0) > 0 ? 'text-warn' : ''}>
                {status?.simulations?.running ?? 'â€”'}
              </span>
            }
            sub="in flight"
          />
          <StatBlock label="completed" value={status?.simulations?.completed ?? 'â€”'} sub="archived" />
          <div className="ml-auto hidden font-mono text-[10px] uppercase tracking-[0.2em] text-faint md:block">
            dispatcher Â· ambulance units Â· hospitals â€” all AI
          </div>
        </div>
      </section>

      {/* how it works */}
      <section className="mx-auto grid max-w-[1600px] gap-4 px-6 py-16 md:grid-cols-3">
        {[
          {
            n: '01',
            t: 'Declare the emergency',
            d: 'Structured intake or a scenario document. Severity, vitals, location, golden-hour window.',
            c: 'text-emergency',
          },
          {
            n: '02',
            t: 'Agents take over',
            d: 'The dispatcher triages, ambulances race real traffic physics, hospitals prep OTs and blood â€” negotiating over radio the whole way.',
            c: 'text-warn',
          },
          {
            n: '03',
            t: 'Get the debrief',
            d: 'An honest verdict: where the chain held, where it snapped, and the intervention that would have changed the outcome.',
            c: 'text-teal',
          },
        ].map((s, i) => (
          <motion.div
            key={s.n}
            initial={{ opacity: 0, y: 18 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.12, duration: 0.55 }}
            className="group rounded-lg border border-line bg-panel/50 p-6 transition-colors hover:border-line-bright"
          >
            <span className={`font-mono text-xs ${s.c}`}>{s.n}</span>
            <h3 className="mt-3 font-display text-xl font-semibold">{s.t}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted">{s.d}</p>
          </motion.div>
        ))}
      </section>
    </div>
  );
}

/* tiny hook so Landing stays tidy */
function useStatus() {
  const [status, setStatus] = React.useState<any>(null);
  useEffect(() => {
    let alive = true;
    Promise.all([getStatus().catch(() => null), healthCheck().catch(() => null)]).then(
      ([st, hc]) => {
        if (!alive) return;
        setStatus({ ...(st || {}), service: hc?.service });
      }
    );
    return () => {
      alive = false;
    };
  }, []);
  return [status, setStatus] as const;
}


