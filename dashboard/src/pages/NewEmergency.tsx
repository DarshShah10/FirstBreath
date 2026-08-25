import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Activity, HeartPulse, Droplets, Baby, Zap, Clock3,
  MapPin, ArrowRight, Loader2,
} from 'lucide-react';
import TopBar from '@/components/TopBar';
import { Panel, PanelHeader, PanelTitle, PanelContent } from '@/components/ui/panel';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input, Label } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import { StatBlock } from '@/components/ui/bits';
import { createSimulation, addCase, runSimulation } from '@/api';
import { fmtClock } from '@/lib/utils';

const EMERGENCY_TYPES = [
  { id: 'fetal_distress', label: 'Fetal Distress', icon: Activity, desc: 'CTG alarm — immediate delivery likely', defaultWindow: 20 },
  { id: 'maternal_hemorrhage', label: 'Hemorrhage', icon: Droplets, desc: 'Major blood loss — blood bank critical', defaultWindow: 30 },
  { id: 'eclampsia', label: 'Eclampsia', icon: Zap, desc: 'Seizure activity — ALS required', defaultWindow: 25 },
  { id: 'cord_prolapse', label: 'Cord Prolapse', icon: Baby, desc: 'Cord before presenting part', defaultWindow: 15 },
] as const;

const SEVERITIES = [
  { id: 'critical', label: 'CRITICAL', tone: 'emergency' as const },
  { id: 'severe', label: 'SEVERE', tone: 'warn' as const },
  { id: 'moderate', label: 'MODERATE', tone: 'info' as const },
];

export default function NewEmergency() {
  const nav = useNavigate();
  const [type, setType] = useState<string>('fetal_distress');
  const [severity, setSeverity] = useState('critical');
  const [window_, setWindow_] = useState(20);
  const [address, setAddress] = useState('Sector 12, Noida, UP');
  const [lat, setLat] = useState('28.6100');
  const [lng, setLng] = useState('77.2000');
  const [gestation, setGestation] = useState('36');
  const [bloodType, setBloodType] = useState('O_negative');
  const [complications, setComplications] = useState('late_decelerations');
  const [engine, setEngine] = useState<'agentic' | 'deterministic'>('agentic');
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = useMemo(() => EMERGENCY_TYPES.find((t) => t.id === type)!, [type]);

  const pickType = (t: (typeof EMERGENCY_TYPES)[number]) => {
    setType(t.id);
    setWindow_(t.defaultWindow);
  };

  const launch = async () => {
    setLaunching(true);
    setError(null);
    try {
      const sim = await createSimulation({ simulation_speed: 1.0 });
      await addCase(sim.simulation_id, {
        severity,
        emergency_type: type,
        location: { lat: Number(lat), lng: Number(lng), address },
        patient: {
          gestational_age_weeks: Number(gestation) || 36,
          blood_type: bloodType.replace('-', '_negative').replace('+', '_positive'),
          complications: complications.split(',').map((c) => c.trim()).filter(Boolean),
        },
        time_window_minutes: window_,
      } as any);
      await runSimulation(sim.simulation_id, {
        duration_minutes: Math.max(60, window_ + 40),
        engine,
        seed: `ui-${Date.now()}`,
      });
      nav(`/run/${sim.simulation_id}`);
    } catch (e: any) {
      setError(e?.response?.data?.error || e?.message || 'Launch failed');
      setLaunching(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar />
      <div className="bg-grid relative flex-1">
        <div className="mx-auto max-w-[1400px] px-6 py-10">
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <div className="flex items-end justify-between gap-4 pb-8">
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-faint">intake · step 1 of 1</div>
                <h1 className="mt-1 font-display text-4xl font-bold tracking-tight">
                  Declare emergency
                </h1>
              </div>
              <Badge tone="warn" className="hidden sm:flex">
                <Clock3 size={11} /> every second counts
              </Badge>
            </div>
          </motion.div>

          <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
            {/* left: form */}
            <motion.div
              initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.08 }}
              className="space-y-5"
            >
              {/* emergency type */}
              <Panel>
                <PanelHeader><PanelTitle>Emergency type</PanelTitle></PanelHeader>
                <PanelContent className="grid gap-3 sm:grid-cols-2">
                  {EMERGENCY_TYPES.map((t) => {
                    const Icon = t.icon;
                    const active = type === t.id;
                    return (
                      <button
                        key={t.id}
                        onClick={() => pickType(t)}
                        className={`group flex items-start gap-3 rounded-lg border p-4 text-left transition-all cursor-pointer ${
                          active
                            ? 'border-emergency/60 bg-emergency/8 shadow-[0_0_24px_-10px_rgba(255,61,81,0.55)]'
                            : 'border-line bg-abyss hover:border-line-bright'
                        }`}
                      >
                        <span className={`mt-0.5 rounded-md border p-2 ${
                          active ? 'border-emergency/50 bg-emergency/15 text-emergency'
                                 : 'border-line bg-panel-2 text-muted group-hover:text-ink'}`}>
                          <Icon size={18} />
                        </span>
                        <span>
                          <span className="block font-display font-semibold">{t.label}</span>
                          <span className="mt-0.5 block text-xs text-muted">{t.desc}</span>
                        </span>
                      </button>
                    );
                  })}
                </PanelContent>
              </Panel>

              {/* severity + window */}
              <Panel>
                <PanelHeader><PanelTitle>Severity & golden-hour window</PanelTitle></PanelHeader>
                <PanelContent className="space-y-6">
                  <div className="flex flex-wrap gap-2">
                    {SEVERITIES.map((s) => (
                      <button
                        key={s.id}
                        onClick={() => setSeverity(s.id)}
                        className="cursor-pointer"
                      >
                        <Badge tone={severity === s.id ? s.tone : 'neutral'}
                               className={`px-3 py-1 ${severity === s.id ? '' : 'opacity-60 hover:opacity-100'}`}>
                          {s.label}
                        </Badge>
                      </button>
                    ))}
                  </div>
                  <div>
                    <div className="mb-3 flex items-center justify-between">
                      <Label>time window</Label>
                      <span className="font-mono text-2xl font-bold tabular-nums text-warn">
                        {fmtClock(window_)}
                      </span>
                    </div>
                    <Slider value={window_} min={10} max={60} onValueChange={setWindow_} />
                    <div className="mt-1.5 flex justify-between font-mono text-[9px] uppercase tracking-widest text-faint">
                      <span>10 min · dire</span><span>60 min · stable</span>
                    </div>
                  </div>
                </PanelContent>
              </Panel>

              {/* location + patient */}
              <div className="grid gap-5 md:grid-cols-2">
                <Panel>
                  <PanelHeader><MapPin size={12} /> incident location</PanelHeader>
                  <PanelContent className="space-y-3">
                    <div className="space-y-1.5">
                      <Label>address</Label>
                      <Input value={address} onChange={(e) => setAddress(e.target.value)} />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1.5">
                        <Label>latitude</Label>
                        <Input value={lat} onChange={(e) => setLat(e.target.value)} className="font-mono" />
                      </div>
                      <div className="space-y-1.5">
                        <Label>longitude</Label>
                        <Input value={lng} onChange={(e) => setLng(e.target.value)} className="font-mono" />
                      </div>
                    </div>
                  </PanelContent>
                </Panel>

                <Panel>
                  <PanelHeader><HeartPulse size={12} /> patient</PanelHeader>
                  <PanelContent className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1.5">
                        <Label>gestation (wks)</Label>
                        <Input value={gestation} onChange={(e) => setGestation(e.target.value)} className="font-mono" />
                      </div>
                      <div className="space-y-1.5">
                        <Label>blood type</Label>
                        <select
                          value={bloodType}
                          onChange={(e) => setBloodType(e.target.value)}
                          className="h-9 w-full rounded-md border border-line bg-abyss px-3 text-sm text-ink focus-visible:outline-none focus-visible:border-info/60"
                        >
                          {['O_negative','O_positive','A_negative','A_positive','B_negative','B_positive','AB_negative','AB_positive'].map((b) => (
                            <option key={b}>{b}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <Label>complications (comma-sep)</Label>
                      <Input value={complications} onChange={(e) => setComplications(e.target.value)} />
                    </div>
                  </PanelContent>
                </Panel>
              </div>
            </motion.div>

            {/* right: launch console */}
            <motion.div
              initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.16 }}
            >
              <Panel glow className="sticky top-[72px] scanline">
                <PanelHeader className="justify-between">
                  launch console
                  <span className="h-2 w-2 rounded-full bg-go shadow-[0_0_8px_rgba(52,211,153,0.9)]" />
                </PanelHeader>
                <PanelContent className="space-y-5">
                  <div className="rounded-lg border border-line bg-abyss p-4">
                    <div className="font-mono text-[10px] uppercase tracking-widest text-faint">scenario summary</div>
                    <div className="mt-2 space-y-1.5 font-mono text-sm">
                      <div className="flex justify-between"><span className="text-muted">type</span><span>{selected.label}</span></div>
                      <div className="flex justify-between"><span className="text-muted">severity</span><span className="uppercase">{severity}</span></div>
                      <div className="flex justify-between"><span className="text-muted">window</span><span className="text-warn tabular-nums">{fmtClock(window_)}</span></div>
                      <div className="flex justify-between"><span className="text-muted">blood</span><span>{bloodType}</span></div>
                    </div>
                  </div>

                  <div>
                    <Label className="mb-2 block">simulation engine</Label>
                    <div className="grid grid-cols-2 gap-2">
                      {(['agentic', 'deterministic'] as const).map((m) => (
                        <button
                          key={m}
                          onClick={() => setEngine(m)}
                          className={`cursor-pointer rounded-md border px-3 py-2.5 text-left transition-all ${
                            engine === m
                              ? 'border-teal/60 bg-teal/10 shadow-[0_0_20px_-8px_rgba(45,212,191,0.6)]'
                              : 'border-line bg-abyss opacity-70 hover:opacity-100'
                          }`}
                        >
                          <div className={`font-display text-sm font-semibold capitalize ${engine === m ? 'text-teal' : ''}`}>
                            {m}
                          </div>
                          <div className="mt-0.5 text-[10px] leading-tight text-muted">
                            {m === 'agentic' ? 'AI agents decide & talk' : 'pure physics, no LLM'}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {error && (
                    <div className="rounded-md border border-emergency/40 bg-emergency/10 p-3 text-xs text-emergency">
                      {error}
                    </div>
                  )}

                  <Button
                    className="w-full"
                    size="lg"
                    disabled={launching}
                    onClick={launch}
                  >
                    {launching ? (
                      <><Loader2 className="animate-spin" size={16} /> launching…</>
                    ) : (
                      <>Run simulation <ArrowRight size={16} /></>
                    )}
                  </Button>

                  <div className="flex justify-between font-mono text-[9px] uppercase tracking-widest text-faint">
                    <StatBlock label="units on standby" value="4 ambulances" tone="text-sm" />
                    <StatBlock label="hospitals" value="3 receiving" tone="text-sm" />
                  </div>
                </PanelContent>
              </Panel>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  );
}
