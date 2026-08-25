import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import * as d3 from 'd3';
import {
  Pause, Play, Square, Radio, Network, Gauge, FileText,
} from 'lucide-react';
import TopBar from '@/components/TopBar';
import { Panel, PanelHeader, PanelContent } from '@/components/ui/panel';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { StatBlock, LiveDot } from '@/components/ui/bits';
import {
  getWorldSnapshot, getEvents, getSimulation,
  pauseSimulation, resumeSimulation, stopSimulation,
  type WorldSnapshot, type TranscriptEvent,
} from '@/api';
import { fmtClock } from '@/lib/utils';

/* ── event → feed item styling ────────────────────────────────────── */
const EVENT_STYLE: Record<string, { tone: any; label: string }> = {
  radio:            { tone: 'teal',      label: 'RADIO' },
  agent_decision:   { tone: 'violet',    label: 'BRAIN' },
  dispatch:         { tone: 'warn',      label: 'DISPATCH' },
  pre_alert:        { tone: 'info',      label: 'PRE-ALERT' },
  ot_reserved:      { tone: 'info',      label: 'OT RESERVE' },
  ot_ready:         { tone: 'go',        label: 'OT READY' },
  staff_paged:      { tone: 'info',      label: 'PAGE' },
  staff_arrived:    { tone: 'go',        label: 'STAFF IN' },
  blood_requested:  { tone: 'warn',      label: 'BLOOD REQ' },
  blood_ready:      { tone: 'go',        label: 'BLOOD OK' },
  reroute:          { tone: 'critical',  label: 'REROUTE' },
  traffic_changed:  { tone: 'warn',      label: 'TRAFFIC' },
  amb_departed:     { tone: 'neutral',   label: 'ROLLING' },
  arrived_patient:  { tone: 'info',      label: 'ON SCENE' },
  transport_started:{ tone: 'info',      label: 'TRANSPORT' },
  arrived_hospital: { tone: 'go',        label: 'ARRIVED' },
  case_completed:   { tone: 'go',        label: 'OUTCOME' },
  case_failed:      { tone: 'emergency', label: 'FAILED' },
  action_rejected:  { tone: 'emergency', label: 'REJECTED' },
  case_queued:      { tone: 'emergency', label: '911 CALL' },
  run_started:      { tone: 'teal',      label: 'START' },
  run_finished:     { tone: 'go',        label: 'COMPLETE' },
  escalated:        { tone: 'emergency', label: 'ESCALATE' },
};

function evStyle(t: string) {
  return EVENT_STYLE[t] || { tone: 'neutral' as const, label: t.replace(/_/g, ' ').toUpperCase() };
}

const AGENT_COLOR: Record<string, string> = {
  dispatcher: 'text-warn',
  hospital: 'text-info',
  ambulance: 'text-teal',
  system: 'text-faint',
  world: 'text-muted',
  scenario: 'text-violet',
};

/* ── D3 response graph ────────────────────────────────────────────── */
const GROUP_COLORS: Record<string, string> = {
  patient: '#ff3d51',
  ambulance: '#2dd4bf',
  hospital: '#4da3ff',
  staff: '#a78bfa',
  dispatch: '#ffb02e',
  traffic: '#ff5c39',
  system: '#566073',
};

function ResponseGraph({ simId }: { simId: string }) {
  const ref = useRef<SVGSVGElement>(null);
  const dataRef = useRef<any>({ nodes: [], links: [] });

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const apiBase = (import.meta as any).env?.VITE_API_URL || '/api/v1';
        const r = await fetch(`${apiBase}/simulations/${simId}/d3`);
        if (!r.ok) return;
        const j = await r.json();
        if (!alive) return;
        dataRef.current = { nodes: j.nodes || [], links: j.links || [] };
      } catch { /* keep last */ }
    };
    tick();
    const iv = setInterval(tick, 2000);
    return () => { alive = false; clearInterval(iv); };
  }, [simId]);

  useEffect(() => {
    if (!ref.current) return;
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();
    const width = ref.current.clientWidth || 600;
    const height = ref.current.clientHeight || 420;

    const g = svg.append('g');
    const zoom = d3.zoom().scaleExtent([0.4, 2.5]).on('zoom', (e) => g.attr('transform', e.transform));
    svg.call(zoom as any);

    const simulation = d3
      .forceSimulation()
      .force('link', d3.forceLink().id((d: any) => d.id).distance(90).strength(0.4))
      .force('charge', d3.forceManyBody().strength(-260))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide(34));

    let nodeSel: any = null;
    let linkSel: any = null;

    const update = () => {
      const { nodes, links } = dataRef.current;
      if (!nodes.length) return;

      // join
      linkSel = g.selectAll('line.link').data(links, (d: any) => `${d.source?.id || d.source}-${d.target?.id || d.target}`);
      linkSel.exit().remove();
      linkSel = linkSel.enter()
        .append('line')
        .attr('class', 'link')
        .attr('stroke', (d: any) =>
          d.type === 'blocks' ? '#ff3d5166' :
          d.status === 'en_route_patient' || d.status === 'transporting' ? '#2dd4bf88' : '#1b2436')
        .attr('stroke-width', (d: any) => (d.type === 'blocks' ? 1.6 : 1.1))
        .attr('stroke-dasharray', (d: any) => (d.type === 'blocks' ? '4 3' : d.status ? 'none' : '2 3'))
        .merge(linkSel);

      nodeSel = g.selectAll('g.node').data(nodes, (d: any) => d.id);
      nodeSel.exit().remove();
      const entered = nodeSel.enter().append('g').attr('class', 'node').call(drag(simulation) as any);
      entered.append('circle')
        .attr('r', (d: any) => (d.group === 'patient' ? 13 : d.group === 'hospital' ? 11 : 8));
      entered.append('text')
        .attr('dx', (d: any) => (d.group === 'patient' ? 17 : 12))
        .attr('dy', 4)
        .text((d: any) => d.name);
      nodeSel = entered.merge(nodeSel);

      nodeSel.selectAll('circle')
        .attr('fill', (d: any) => {
          const base = GROUP_COLORS[d.group] || '#566073';
          return d.status === 'completed' ? '#34d399' : base;
        })
        .attr('opacity', 0.92)
        .attr('stroke', (d: any) =>
          ['dispatched', 'en_route_patient', 'stabilizing', 'transporting', 'preparing'].includes(d.status)
            ? '#ffffffaa' : '#04060a')
        .attr('stroke-width', (d: any) => (
          ['dispatched', 'en_route_patient', 'stabilizing', 'transporting', 'preparing'].includes(d.status) ? 2 : 1));

      nodeSel.selectAll('text')
        .attr('fill', '#8a94a7')
        .attr('font-size', 9)
        .attr('font-family', 'JetBrains Mono, monospace');

      simulation.nodes(nodes as any);
      (simulation.force('link') as any).links(links);
      simulation.alpha(0.6).restart();

      simulation.on('tick', () => {
        linkSel
          .attr('x1', (d: any) => d.source.x).attr('y1', (d: any) => d.source.y)
          .attr('x2', (d: any) => d.target.x).attr('y2', (d: any) => d.target.y);
        nodeSel.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
      });
    };

    update();
    const iv = setInterval(update, 2100);
    function drag(sim: any) {
      return d3.drag()
        .on('start', (event: any, d: any) => { if (!event.active) sim.alphaTarget(0.4).restart(); d.fx = d.x; d.fy = d.y; })
        .on('drag', (event: any, d: any) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event: any, d: any) => { if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; });
    }
    return () => { clearInterval(iv); simulation.stop(); };
  }, []);

  return <svg ref={ref} className="h-full w-full" />;
}

/* ── page ─────────────────────────────────────────────────────────── */
export default function MissionControl() {
  const { simId } = useParams<{ simId: string }>();
  const [snap, setSnap] = useState<WorldSnapshot | null>(null);
  const [feed, setFeed] = useState<TranscriptEvent[]>([]);
  const [runtimeStatus, setRuntimeStatus] = useState<string>('connecting');
  const [paused, setPaused] = useState(false);
  const cursorRef = useRef(0);
  const feedEndRef = useRef<HTMLDivElement>(null);

  const pollOnce = useCallback(async () => {
    if (!simId) return;
    try {
      const s = await getWorldSnapshot(simId);
      setSnap(s);
      setRuntimeStatus(s.runtime_status || 'running');
      setPaused(s.runtime_status === 'paused');

      const { events } = await getEvents(simId, cursorRef.current);
      if (events.length) {
        cursorRef.current = Math.max(...events.map((e) => e.id || 0), cursorRef.current);
        setFeed((f) => [...f, ...events].slice(-400));
      }
    } catch {
      /* transient */
    }
  }, [simId]);

  useEffect(() => {
    pollOnce();
    const iv = setInterval(pollOnce, 1600);
    return () => clearInterval(iv);
  }, [pollOnce]);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [feed.length]);

  const done = runtimeStatus === 'completed' || runtimeStatus === 'stopped' || runtimeStatus === 'failed';

  const onTogglePause = async () => {
    if (!simId) return;
    try {
      if (paused) await resumeSimulation(simId);
      else await pauseSimulation(simId);
    } catch {}
  };
  const onStop = async () => {
    if (!simId) return;
    try { await stopSimulation(simId); } catch {}
  };

  const openCases = snap?.cases.filter((c) => !['completed', 'failed'].includes(c.status)) ?? [];
  const finishedCases = snap?.cases.filter((c) => ['completed', 'failed'].includes(c.status)) ?? [];

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopBar />

      {/* command strip */}
      <div className="flex flex-wrap items-center gap-x-8 gap-y-2 border-b border-line bg-abyss/70 px-6 py-3">
        <StatBlock
          label="T-plus"
          value={<span className={openCases.length && !done ? 'text-warn' : 'text-ink'}>{fmtClock(snap?.sim_time ?? 0)}</span>}
          sub="mission clock"
        />
        <SeparatorV />
        <StatBlock
          label="active cases"
          value={<span className={openCases.length ? 'text-emergency' : 'text-go'}>{openCases.length}</span>}
          sub={`${finishedCases.length} resolved`}
        />
        <SeparatorV />
        <StatBlock label="units deployed" value={snap?.ambulances.filter((a) => a.case_id).length ?? '—'} sub={`of ${snap?.ambulances.length ?? '—'} available`} />
        <SeparatorV />
        <StatBlock
          label="status"
          value={
            <span className={
              runtimeStatus === 'completed' ? 'text-go' :
              runtimeStatus === 'paused' ? 'text-warn' :
              runtimeStatus === 'failed' ? 'text-emergency' : 'text-teal'
            }>
              {(runtimeStatus || '—').toUpperCase()}
            </span>
          }
          sub={done ? 'final' : 'streaming'}
        />

        <div className="ml-auto flex items-center gap-2">
          {done ? (
            <Link to={`/report/${simId}`}>
              <Button size="sm" variant="go">
                <FileText size={14} /> Mission debrief
              </Button>
            </Link>
          ) : (
            <>
              <Button size="sm" variant={paused ? 'go' : 'secondary'} onClick={onTogglePause}>
                {paused ? <><Play size={13} /> Resume</> : <><Pause size={13} /> Pause</>}
              </Button>
              <Button size="sm" variant="ghost" onClick={onStop}>
                <Square size={13} /> Abort
              </Button>
            </>
          )}
        </div>
      </div>

      {/* three panes */}
      <div className="grid flex-1 grid-cols-1 gap-px overflow-hidden bg-line lg:grid-cols-[380px_1fr_320px]">
        {/* RADIO FEED */}
        <Panel className="flex flex-col rounded-none border-0 !bg-void">
          <PanelHeader className="justify-between border-b border-line">
            <span className="flex items-center gap-2"><Radio size={12} /> net traffic</span>
            {!done && <LiveDot tone={paused ? 'bg-warn' : 'bg-go'} label={paused ? 'held' : 'live'} />}
          </PanelHeader>
          <PanelContent className="flex-1 space-y-2 overflow-y-auto p-3">
            <AnimatePresence initial={false}>
              {feed.map((e, i) => {
                const st = evStyle(e.event_type);
                const desc = e.payload?.description || JSON.stringify(e.payload).slice(0, 120);
                return (
                  <motion.div
                    key={e.id ?? i}
                    initial={{ opacity: 0, x: -14 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.25 }}
                    className="rounded-md border border-line/70 bg-panel/60 p-2.5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <Badge tone={st.tone}>{st.label}</Badge>
                      <span className="font-mono text-[10px] tabular-nums text-faint">
                        T+{fmtClock(e.sim_time || 0)}
                      </span>
                    </div>
                    <div className="mt-1.5 text-[13px] leading-snug">
                      <span className={`font-mono text-[11px] ${AGENT_COLOR[e.agent_type || ''] || 'text-muted'}`}>
                        {e.agent_id || e.agent_type}:{' '}
                      </span>
                      {desc}
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
            <div ref={feedEndRef} />
          </PanelContent>
        </Panel>

        {/* GRAPH */}
        <Panel className="relative flex flex-col rounded-none border-0 !bg-void scanline">
          <PanelHeader className="justify-between border-b border-line">
            <span className="flex items-center gap-2"><Network size={12} /> response chain</span>
            <div className="flex gap-3 font-mono text-[9px] uppercase tracking-wider text-faint">
              <span className="flex items-center gap-1"><i className="h-1.5 w-1.5 rounded-full inline-block" style={{ background: GROUP_COLORS.patient }} /> patient</span>
              <span className="flex items-center gap-1"><i className="h-1.5 w-1.5 rounded-full inline-block" style={{ background: GROUP_COLORS.ambulance }} /> unit</span>
              <span className="flex items-center gap-1"><i className="h-1.5 w-1.5 rounded-full inline-block" style={{ background: GROUP_COLORS.hospital }} /> hospital</span>
              <span className="flex items-center gap-1"><i className="h-1.5 w-1.5 rounded-full inline-block" style={{ background: GROUP_COLORS.staff }} /> staff</span>
            </div>
          </PanelHeader>
          <div className="flex-1">
            <ResponseGraph simId={simId!} />
          </div>
        </Panel>

        {/* CASE VITALS */}
        <Panel className="flex flex-col rounded-none border-0 !bg-void">
          <PanelHeader className="border-b border-line">
            <span className="flex items-center gap-2"><Gauge size={12} /> case vitals</span>
          </PanelHeader>
          <PanelContent className="flex-1 space-y-3 overflow-y-auto p-3">
            {snap?.cases.map((c) => {
              const closed = ['completed', 'failed'].includes(c.status);
              const urgent = !closed && c.minutes_left < 8;
              return (
                <div key={c.id} className={`rounded-lg border p-3 ${
                  closed ? 'border-line/60 bg-panel/40 opacity-75'
                         : urgent ? 'border-emergency/50 bg-emergency/8'
                         : 'border-warn/30 bg-warn/5'}`}>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold">{c.id.replace('case_', 'CASE ')}</span>
                    <Badge tone={c.outcome?.includes('success') ? 'go' : closed ? 'emergency' : urgent ? 'emergency' : 'warn'}>
                      {c.outcome || c.status}
                    </Badge>
                  </div>
                  <div className="mt-2 font-display text-lg font-semibold capitalize">
                    {(c.emergency_type || '').replace('_', ' ')}
                  </div>
                  <div className="mt-0.5 text-[11px] text-muted">{c.location?.address}</div>
                  {!closed && (
                    <div className="mt-2.5">
                      <div className="flex justify-between font-mono text-[10px] text-faint">
                        <span>window remaining</span>
                        <span className={`tabular-nums ${urgent ? 'text-emergency font-bold' : 'text-warn'}`}>
                          T-{fmtClock(c.minutes_left)}
                        </span>
                      </div>
                      <div className="mt-1 h-1 rounded-full bg-line overflow-hidden">
                        <div
                          className={`h-full rounded-full ${urgent ? 'bg-emergency' : 'bg-warn'} transition-all duration-500`}
                          style={{ width: `${Math.max(2, Math.min(100, (c.minutes_left / (c.deadline || 20)) * 100))}%` }}
                        />
                      </div>
                    </div>
                  )}
                  <div className="mt-2 flex gap-2 font-mono text-[10px] text-muted">
                    {c.ambulance_id && <Badge tone="teal">{c.ambulance_id}</Badge>}
                    {c.hospital_id && <Badge tone="info" className="capitalize">{c.hospital_id.replace('hospital_', '')}</Badge>}
                  </div>
                </div>
              );
            })}
            {!snap?.cases.length && (
              <div className="flex h-full items-center justify-center font-mono text-xs text-faint">
                awaiting telemetry…
              </div>
            )}
          </PanelContent>
        </Panel>
      </div>
    </div>
  );
}

function SeparatorV() {
  return <div className="hidden h-8 w-px bg-line sm:block" />;
}
