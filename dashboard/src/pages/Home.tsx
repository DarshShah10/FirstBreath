import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { gsap, ScrollTrigger, useGSAP, onSystemReady } from "@/lib/gsap";
import CityMap from "@/components/map/CityMap";
import Ticker from "@/components/system/Ticker";
import { Button, Kicker } from "@/components/ui/kit";
import { GoldenClock, ProgressRail } from "@/components/timeline/TimelineKit";
import Footer from "@/components/system/Footer";
import { replaySnapshot, replayEventsUpTo, REPLAY_DURATION_MIN } from "@/lib/mock";
import type { WorldSnapshot } from "@/lib/api";

/* â”€â”€ chapters of the archived festival run â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
const CHAPTERS = [
  {
    t0: 0, t1: 2,
    n: "01", title: "THE CALL",
    body: "T+00:00. A CTG monitor flags late decelerations â€” fetal distress, severity 9, twenty-minute window. Two minutes later a second call: hemorrhage on FC Road. Two patients. One network.",
  },
  {
    t0: 2, t1: 8,
    n: "02", title: "THE DECISION",
    body: "The dispatcher agent reads both scenes and commits inside half a minute: Unit 001 to Ward 3, Mobile ICU to FC Road, Central Maternity pre-alerted. Its reasoning lands on the record, verbatim.",
  },
  {
    t0: 8, t1: 14,
    n: "03", title: "THE CITY FIGHTS BACK",
    body: "A Ganesh procession pins the main arterial to heavy traffic. The world model doesn't negotiate â€” every minute on that road costs exactly what physics says it costs.",
  },
  {
    t0: 14, t1: 20,
    n: "04", title: "THE RACE",
    body: "Hospital agents page surgeons, reserve an operating theater, cross-match blood â€” all before the ambulances arrive. Preparation is the cheapest intervention in the chain.",
  },
  {
    t0: 20, t1: 26,
    n: "05", title: "TRANSPORT",
    body: "Both patients aboard. ETAs tick against windows. The procession eases to moderate â€” four minutes too late for one of them.",
  },
  {
    t0: 26, t1: 31,
    n: "06", title: "THE VERDICT",
    body: "One delivered inside the window. One eight minutes late â€” the OT was ready, the road was not. FirstBreath does not narrate success stories. It reports what happened.",
  },
];

export default function Home() {
  return (
    <div className="bg-void">
      <Hero />
      <GoldenHourScroll />
      <Manifesto />
      <Footer />
    </div>
  );
}

/* â”€â”€ HERO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

function Hero() {
  const rootRef = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      onSystemReady(() => {
        const tl = gsap.timeline({ delay: 0.15 });
        tl.from("[data-hero-line] span", {
          yPercent: 110,
          duration: 1.1,
          stagger: 0.09,
          ease: "power4.out",
        })
          .from("[data-hero-kicker]", { opacity: 0, y: 12, duration: 0.7 }, "-=0.7")
          .from("[data-hero-sub]", { opacity: 0, y: 16, duration: 0.7 }, "-=0.5")
          .from("[data-hero-cta]", { opacity: 0, y: 16, duration: 0.7 }, "-=0.45")
          .from("[data-hero-meta]", { opacity: 0, duration: 0.9 }, "-=0.4");

        gsap.to("[data-hero-map]", {
          yPercent: 18,
          ease: "none",
          scrollTrigger: {
            trigger: rootRef.current,
            start: "top top",
            end: "bottom top",
            scrub: true,
          },
        });
        gsap.to("[data-hero-copy]", {
          yPercent: -30,
          opacity: 0.25,
          ease: "none",
          scrollTrigger: {
            trigger: rootRef.current,
            start: "top top",
            end: "bottom top",
            scrub: true,
          },
        });
      });
    },
    { scope: rootRef }
  );

  return (
    <section ref={rootRef} className="relative flex h-[100svh] flex-col overflow-hidden">
      {/* district underlay */}
      <div data-hero-map className="absolute inset-0 opacity-[0.55]">
        <CityMap snapshot={null} />
        <div className="absolute inset-0 bg-gradient-to-b from-void/70 via-void/30 to-void" />
      </div>

      <div
        data-hero-copy
        className="relative z-10 mx-auto flex w-full max-w-[1600px] flex-1 flex-col justify-end px-6 pb-24 md:px-12"
      >
        <div data-hero-kicker className="mb-8 flex items-center gap-4">
          <span className="h-2 w-2 rounded-full bg-red shadow-[0_0_14px_rgba(229,72,77,0.9)]" />
          <span className="font-mono text-[10px] uppercase tracking-[0.32em] text-mute">
            FirstBreath Response System â€” Sector 12 Â· Noida
          </span>
        </div>

        <h1 className="font-display font-bold leading-[0.88] tracking-[-0.03em]">
          <span data-hero-line className="block overflow-hidden">
            <span className="block text-[clamp(3.4rem,11vw,10rem)]">EVERY SECOND</span>
          </span>
          <span data-hero-line className="block overflow-hidden">
            <span className="text-stroke block text-[clamp(3.4rem,11vw,10rem)]">IS SOMEONE'S</span>
          </span>
          <span data-hero-line className="block overflow-hidden">
            <span className="block text-[clamp(3.4rem,11vw,10rem)] text-red">
              GOLDEN HOUR.
            </span>
          </span>
        </h1>

        <div className="mt-10 flex flex-col gap-8 md:flex-row md:items-end md:justify-between">
          <p data-hero-sub className="max-w-md text-[15px] leading-relaxed text-mute">
            A dispatcher AI, ambulance crews and hospital coordinators reason their way
            through a simulated emergency â€” over honest physics, where every minute,
            bed and unit of blood is accounted for.
          </p>
          <div data-hero-cta className="flex items-center gap-5">
            <Link to="/new">
              <Button>Run simulation</Button>
            </Link>
            <a href="#golden-hour" className="font-mono text-[10px] uppercase tracking-[0.25em] text-faint underline-offset-4 hover:text-bone hover:underline">
              watch one unfold â†“
            </a>
          </div>
        </div>

        <div data-hero-meta className="mt-14 border-t border-line pt-5">
          <Ticker
            items={[
              "dispatcher â€” ai",
              "ambulance units â€” ai",
              "hospital coordinators â€” ai",
              "world model â€” deterministic",
              "transcript â€” verbatim",
              "sector 12 grid â€” live",
            ]}
          />
        </div>
      </div>
    </section>
  );
}

/* â”€â”€ GOLDEN HOUR SCROLL NARRATIVE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

function GoldenHourScroll() {
  const pinRef = useRef<HTMLDivElement>(null);
  const [mockTime, setMockTime] = useState(0);
  const [snap, setSnap] = useState<WorldSnapshot | null>(() => replaySnapshot(0));
  const clockRef = useRef<HTMLSpanElement>(null);
  const eventRef = useRef<HTMLDivElement>(null);
  const chapterRefs = useRef<Array<HTMLDivElement | null>>([]);

  useGSAP(
    () => {
      const el = pinRef.current!;
      const total = REPLAY_DURATION_MIN;

      // chapter visibility tweens
      const tl = gsap.timeline();
      CHAPTERS.forEach((ch, i) => {
        const startP = ch.t0 / total;
        const endP = ch.t1 / total;
        const elRef = () => chapterRefs.current[i];
        tl.fromTo(
          elRef(),
          { opacity: 0, y: 40 },
          {
            opacity: 1,
            y: 0,
            duration: 0.06,
            scrollTrigger: {
              trigger: el,
              start: `top top-=${startP * (el.offsetHeight - window.innerHeight)}`,
              end: `top top-=${endP * (el.offsetHeight - window.innerHeight)}`,
              toggleActions: "play reverse play reverse",
            },
          }
        );
      });

      // master clock + live map scrub
      ScrollTrigger.create({
        trigger: el,
        start: "top top",
        end: "bottom bottom",
        scrub: true,
        onUpdate(self) {
          const p = self.progress;
          const t = p * total;
          if (clockRef.current) {
            const mm = Math.floor(t);
            const ss = Math.floor((t - mm) * 60);
            clockRef.current.textContent = `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
          }
          setMockTime((prev) => (Math.abs(prev - t) > 0.4 ? t : prev));
        },
      });
    },
    { scope: pinRef }
  );

  // keep snapshot + headline event in step with scrub time
  useEffect(() => {
    setSnap(replaySnapshot(mockTime));
    const evts = replayEventsUpTo(mockTime);
    const last = [...evts].reverse().find((e) => e.event_type !== "tick");
    if (eventRef.current && last) {
      eventRef.current.textContent = last.payload?.description ?? "";
    }
  }, [mockTime]);

  const chapterIdx = CHAPTERS.findIndex((c) => mockTime >= c.t0 && mockTime < c.t1);

  return (
    <section id="golden-hour" ref={pinRef} className="relative" style={{ height: "720vh" }}>
      <div className="sticky top-0 flex h-screen flex-col overflow-hidden">
        <ProgressRail progress={Math.min(1, mockTime / REPLAY_DURATION_MIN)} />

        {/* section head */}
        <div className="flex items-center justify-between px-6 pt-24 md:px-14">
          <Kicker index="01â€“06" label="the golden hour â€” archived run, festival conflict" />
          <span className="hidden font-mono text-[10px] uppercase tracking-[0.25em] text-faint md:block">
            scroll = time
          </span>
        </div>

        {/* stage */}
        <div className="relative mx-auto grid w-full max-w-[1600px] flex-1 grid-cols-1 items-center gap-8 px-6 md:grid-cols-2 md:px-14">
          {/* chapter copy */}
          <div className="relative z-10 order-2 grid md:order-1">
            {CHAPTERS.map((ch, i) => (
              <div
                key={ch.n}
                ref={(el) => { chapterRefs.current[i] = el; }}
                className="max-w-lg [grid-area:1/1]"
              >
                <span className="font-mono text-xs tracking-[0.3em] text-red">{ch.n}</span>
                <h3 className="mt-3 font-display text-5xl font-bold tracking-tight md:text-7xl">
                  {ch.title}
                </h3>
                <p className="mt-5 max-w-md text-[15px] leading-relaxed text-mute">{ch.body}</p>
              </div>
            ))}
          </div>

          {/* live map */}
          <div className="relative order-1 h-[46vh] border border-line md:order-2 md:h-[62vh]">
            <CityMap snapshot={snap} />
            <div className="absolute left-4 top-4">
              <GoldenClock minutes={mockTime} size="md" tone={chapterIdx === 5 ? "text-green" : undefined} />
            </div>
            <div className="absolute bottom-4 right-4 font-mono text-[9px] uppercase tracking-[0.25em] text-faint">
              archive Â· seed festival-42
            </div>
          </div>
        </div>

        {/* running transcript line */}
        <div className="border-t border-line bg-panel/60 px-6 py-4 md:px-14">
          <div className="flex items-center gap-4">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-red" />
            <div ref={eventRef} className="truncate font-mono text-xs text-mute">
              system armed
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* â”€â”€ MANIFESTO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

function Manifesto() {
  const rootRef = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      gsap.utils.toArray<HTMLElement>("[data-principle]").forEach((el, i) => {
        gsap.from(el, {
          opacity: 0,
          y: 40,
          duration: 0.8,
          delay: i * 0.08,
          scrollTrigger: { trigger: el, start: "top 85%" },
        });
      });
    },
    { scope: rootRef }
  );

  return (
    <section ref={rootRef} className="border-t border-line">
      <div className="mx-auto max-w-[1600px] px-6 py-28 md:px-14">
        <Kicker index="Â§" label="operating principles" />
        <div className="mt-14 grid gap-12 md:grid-cols-3">
          {[
            {
              n: "A", t: "Agents propose.\nPhysics disposes.",
              d: "An AI can reroute an ambulance â€” but how long the detour takes is settled by segment-by-segment road math. No hallucinated ETAs survive contact with the transcript.",
            },
            {
              n: "B", t: "Every word\nis on tape.",
              d: "Each decision, radio call and rejection is written to an append-only log. The debrief quotes it. Nothing is paraphrased into convenience.",
            },
            {
              n: "C", t: "Honesty\nover drama.",
              d: "When a window is missed, the report says so â€” and shows which minute, which unit, and what would have changed it.",
            },
          ].map((p) => (
            <div key={p.n} data-principle className="border-t border-line pt-6">
              <span className="font-mono text-xs tracking-[0.3em] text-red">{p.n}</span>
              <h3 className="mt-4 whitespace-pre-line font-display text-2xl font-semibold leading-tight">
                {p.t}
              </h3>
              <p className="mt-4 text-sm leading-relaxed text-mute">{p.d}</p>
            </div>
          ))}
        </div>

        <div className="mt-24 flex flex-col items-start justify-between gap-8 border-t border-line pt-12 md:flex-row md:items-center">
          <p className="max-w-xl font-display text-2xl font-medium leading-snug md:text-3xl">
            Ready to put a response chain under the microscope?
          </p>
          <Link to="/new">
            <Button>Declare an emergency</Button>
          </Link>
        </div>
      </div>
    </section>
  );
}

