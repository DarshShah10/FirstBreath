import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Loader2 } from "lucide-react";
import { Button, Kicker, Readout } from "@/components/ui/kit";
import Footer from "@/components/system/Footer";
import { createSimulation, addCase, runSimulation } from "@/lib/api";
import { fmtClock } from "@/lib/format";
import { cn } from "@/lib/cn";

const TYPES = [
  { id: "fetal_distress", label: "Fetal Distress", desc: "CTG alarm · delivery likely", window: 20 },
  { id: "maternal_hemorrhage", label: "Hemorrhage", desc: "Major blood loss · bank critical", window: 30 },
  { id: "eclampsia", label: "Eclampsia", desc: "Seizure activity · ALS required", window: 25 },
  { id: "cord_prolapse", label: "Cord Prolapse", desc: "Cord before presenting part", window: 15 },
];

const SEVERITIES = ["critical", "severe", "moderate"] as const;

export default function Declare() {
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const [type, setType] = useState(TYPES[0]);
  const [severity, setSeverity] = useState<(typeof SEVERITIES)[number]>("critical");
  const [window_, setWindow_] = useState(20);
  const [address, setAddress] = useState("Ward 3 Bed 4, Sector 12, Noida");
  const [lat, setLat] = useState("28.6100");
  const [lng, setLng] = useState("77.2000");
  const [gestation, setGestation] = useState("36");
  const [blood, setBlood] = useState("O_negative");
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const steps = ["emergency", "severity", "window", "scene", "launch"];
  const progress = ((step + 1) / steps.length) * 100;

  const next = () => setStep((s) => Math.min(s + 1, steps.length - 1));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  const launch = async () => {
    setLaunching(true);
    setError(null);
    try {
      const sim = await createSimulation({ simulation_speed: 1.0 });
      await addCase(sim.simulation_id, {
        severity,
        emergency_type: type.id,
        location: { lat: Number(lat) || 28.61, lng: Number(lng) || 77.2, address },
        patient: {
          gestational_age_weeks: Number(gestation) || 36,
          blood_type: blood.replace("-", "_negative").replace("+", "_positive"),
          complications: type.id === "fetal_distress" ? ["late_decelerations"] : [],
        },
        time_window_minutes: window_,
      });
      await runSimulation(sim.simulation_id, {
        duration_minutes: Math.max(60, window_ + 40),
        engine: "agentic",
        seed: `ui-${Date.now()}`,
      });
      nav(`/run/${sim.simulation_id}`);
    } catch (e: any) {
      setError(e?.message || "Launch failed — backend may be cold-starting. Retry in 60s.");
      setLaunching(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col">
      <div className="bg-grid relative flex flex-1 flex-col">
        <div className="mx-auto w-full max-w-[1200px] flex-1 px-6 pt-28 md:px-12">
          {/* head + progress */}
          <Kicker index="00" label="declare emergency — sequential intake" />
          <div className="mt-6 flex items-baseline justify-between">
            <h1 className="font-display text-5xl font-bold tracking-tight md:text-7xl">
              {steps[step].toUpperCase()}
            </h1>
            <span className="font-mono text-sm tnum text-faint">
              {String(step + 1).padStart(2, "0")}<span className="text-line2">/05</span>
            </span>
          </div>
          <div className="mt-8 h-px w-full bg-line">
            <div
              className="h-px bg-red transition-[width] duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* steps */}
          <div className="relative mt-14 min-h-[380px] flex-1 pb-16">
            {step === 0 && (
              <StepShell hint="what is the clinical emergency?">
                <div className="grid gap-px border border-line md:grid-cols-2">
                  {TYPES.map((t) => (
                    <button
                      key={t.id}
                      data-cursor="link"
                      onClick={() => { setType(t); setWindow_(t.window); }}
                      className={cn(
                        "group flex items-center justify-between p-7 text-left transition-colors",
                        type.id === t.id ? "bg-red/10" : "bg-panel hover:bg-panel2"
                      )}
                    >
                      <span>
                        <span className={cn(
                          "block font-display text-2xl font-semibold",
                          type.id === t.id ? "text-red" : ""
                        )}>
                          {t.label}
                        </span>
                        <span className="mt-1 block font-mono text-[11px] text-faint">{t.desc}</span>
                      </span>
                      <ArrowRight size={18} className={type.id === t.id ? "text-red" : "text-line2"} />
                    </button>
                  ))}
                </div>
              </StepShell>
            )}

            {step === 1 && (
              <StepShell hint="how bad is it, clinically?">
                <div className="space-y-px border border-line">
                  {SEVERITIES.map((s) => (
                    <button
                      key={s}
                      data-cursor="link"
                      onClick={() => setSeverity(s)}
                      className={cn(
                        "flex w-full items-center justify-between px-7 py-6 text-left transition-colors",
                        severity === s ? "bg-red/10" : "bg-panel hover:bg-panel2"
                      )}
                    >
                      <span className={cn("font-display text-3xl font-bold uppercase tracking-tight",
                        severity === s && s === "critical" ? "text-red" : severity === s ? "text-amber" : "")}>
                        {s}
                      </span>
                      <span className="font-mono text-[11px] text-faint">
                        {s === "critical" ? "immediate life threat" : s === "severe" ? "high urgency" : "standard"}
                      </span>
                    </button>
                  ))}
                </div>
              </StepShell>
            )}

            {step === 2 && (
              <StepShell hint="the golden hour window — how long do we have?">
                <div className="py-6">
                  <div className="font-display text-[clamp(4rem,14vw,11rem)] font-bold leading-none tracking-tight text-red tnum">
                    {fmtClock(window_)}
                  </div>
                  <input
                    type="range" min={10} max={60} value={window_}
                    onChange={(e) => setWindow_(Number(e.target.value))}
                    className="mt-8 w-full appearance-none bg-transparent
                      [&::-webkit-slider-runnable-track]:h-px [&::-webkit-slider-runnable-track]:bg-line
                      [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:w-5
                      [&::-webkit-slider-thumb]:-translate-y-2.5 [&::-webkit-slider-thumb]:rounded-full
                      [&::-webkit-slider-thumb]:bg-red [&::-webkit-slider-thumb]:shadow-[0_0_16px_rgba(229,72,77,0.8)]"
                  />
                  <div className="mt-3 flex justify-between font-mono text-[9px] uppercase tracking-[0.2em] text-faint">
                    <span>10 min — dire</span><span>30</span><span>60 min — stable</span>
                  </div>
                </div>
              </StepShell>
            )}

            {step === 3 && (
              <StepShell hint="where is the patient?">
                <div className="grid max-w-2xl gap-px border border-line md:grid-cols-2">
                  <Field label="address / landmark">
                    <input value={address} onChange={(e) => setAddress(e.target.value)}
                      className="w-full bg-panel p-5 font-mono text-sm outline-none focus:bg-panel2" />
                  </Field>
                  <Field label="coordinates (lat, lng)">
                    <div className="flex">
                      <input value={lat} onChange={(e) => setLat(e.target.value)} className="w-full bg-panel p-5 font-mono text-sm outline-none focus:bg-panel2" />
                      <input value={lng} onChange={(e) => setLng(e.target.value)} className="w-full border-l border-line bg-panel p-5 font-mono text-sm outline-none focus:bg-panel2" />
                    </div>
                  </Field>
                  <Field label="gestational age (weeks)">
                    <input value={gestation} onChange={(e) => setGestation(e.target.value)} className="w-full bg-panel p-5 font-mono text-sm outline-none focus:bg-panel2" />
                  </Field>
                  <Field label="blood type">
                    <select value={blood} onChange={(e) => setBlood(e.target.value)}
                      className="w-full bg-panel p-5 font-mono text-sm outline-none focus:bg-panel2">
                      {["O_negative","O_positive","A_negative","A_positive","B_negative","B_positive"].map((b) => <option key={b}>{b}</option>)}
                    </select>
                  </Field>
                </div>
              </StepShell>
            )}

            {step === 4 && (
              <StepShell hint="final check — commit to the record?">
                <div className="grid max-w-3xl gap-px border border-line md:grid-cols-3">
                  <Review label="case"><span className="capitalize">{type.label}</span></Review>
                  <Review label="severity / window">
                    <span className="uppercase">{severity}</span>
                    <span className="block font-mono text-xs text-red">{fmtClock(window_)}</span>
                  </Review>
                  <Review label="scene">{address || `${lat}, ${lng}`}</Review>
                </div>

                {error && (
                  <div className="mt-6 max-w-3xl border border-red/40 bg-red/5 p-4 font-mono text-xs text-red">
                    {error}
                  </div>
                )}
              </StepShell>
            )}
          </div>

          {/* controls */}
          <div className="sticky bottom-0 flex items-center justify-between border-t border-line bg-void/90 py-5 backdrop-blur">
            <button onClick={back} disabled={step === 0}
              className="font-mono text-[10px] uppercase tracking-[0.25em] text-faint transition-colors hover:text-bone disabled:opacity-20">
              ← back
            </button>
            {step < steps.length - 1 ? (
              <Button onClick={next}>Continue <ArrowRight size={14} /></Button>
            ) : (
              <Button onClick={launch} disabled={launching}>
                {launching ? (<><Loader2 size={14} className="animate-spin" /> committing…</>) : ("Launch response chain")}
              </Button>
            )}
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}

/* ── step scaffolding ───────────────────────────────────────────────── */

function StepShell({ hint, children }: { hint: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-8 font-mono text-[11px] uppercase tracking-[0.22em] text-mute">{hint}</p>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block border-b border-line bg-void px-5 py-2 font-mono text-[9px] uppercase tracking-[0.22em] text-faint">
        {label}
      </span>
      {children}
    </label>
  );
}

function Review({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-panel p-6">
      <Readout label={label} value={<span className="text-base leading-snug">{children}</span>} />
    </div>
  );
}
