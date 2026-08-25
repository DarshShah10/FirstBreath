import { useEffect, useRef, useState } from "react";
import { gsap, markSystemReady } from "@/lib/gsap";

const BOOT_LINES = [
  "FIRSTBREATH RESPONSE SYSTEM v2.0",
  "CALIBRATING DISTRICT GRID …… SECTOR 12 · NOIDA",
  "UNITS ONLINE … AMB-001 AMB-002 AMB-003 MOBILE-ICU",
  "HOSPITALS LINKED …… CENTRAL / DISTRICT / EMC",
  "AGENT SOCIETY …… DISPATCHER · UNITS · COORDINATORS",
  "GOLDEN HOUR CLOCK —— ARMED",
];

/**
 * Boot sequence preloader. Plays once per browser session,
 * then lifts like a shutter and marks the system ready.
 */
export default function Preloader() {
  const [gone, setGone] = useState(
    () => typeof sessionStorage !== "undefined" && sessionStorage.getItem("fb-booted") === "1"
  );

  if (gone) return null;
  return <Boot onDone={() => { sessionStorage.setItem("fb-booted", "1"); markSystemReady(); setGone(true); }} />;
}

function Boot({ onDone }: { onDone: () => void }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const doneRef = useRef(false);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const lines = root.querySelectorAll("[data-line]");
    const bar = root.querySelector("[data-bar]") as HTMLElement | null;

    const tl = gsap.timeline({
      onComplete: () => {
        if (!doneRef.current) {
          doneRef.current = true;
          onDone();
        }
      },
    });

    tl.set(lines, { opacity: 0 })
      .set(bar, { scaleX: 0 })
      .to(lines, { opacity: 1, duration: 0.01, stagger: 0.26, ease: "none" });
    if (bar) tl.to(bar, { scaleX: 1, duration: BOOT_LINES.length * 0.26 + 0.3, ease: "power1.inOut" }, 0);
    tl.to(root, { yPercent: -100, duration: 0.9, ease: "power4.inOut", delay: 0.4 });

    return () => {
      tl.kill();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      ref={rootRef}
      className="fixed inset-0 z-[150] flex flex-col justify-between bg-panel px-6 py-8 md:px-12"
    >
      <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.25em] text-faint">
        <span>firstbreath</span>
        <span>response system</span>
      </div>

      <div className="space-y-1.5">
        {BOOT_LINES.map((l, i) => (
          <div key={i} data-line
            className={`font-mono text-xs tracking-wide md:text-sm ${i === 0 ? "text-bone" : "text-mute"}`}>
            <span className="mr-3 text-red">›</span>
            {l}
          </div>
        ))}
      </div>

      <div>
        <div className="mb-3 flex items-end justify-between">
          <span className="font-display text-4xl font-bold tracking-tight text-bone md:text-6xl">
            GOLDEN HOUR
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-faint">arming</span>
        </div>
        <div className="h-px w-full bg-line">
          <div data-bar className="h-px w-full origin-left bg-red" />
        </div>
      </div>
    </div>
  );
}
