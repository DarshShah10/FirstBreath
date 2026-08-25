import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { gsap, ScrollTrigger } from "@/lib/gsap";
import { scrollToTop } from "@/lib/lenis";

/**
 * Route-change shutter: three graphite columns sweep up over the old page,
 * then lift to reveal the new one. Also resets scroll position.
 */
export default function PageTransition({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [displayed, setDisplayed] = useState(location.pathname);
  const rootRef = useRef<HTMLDivElement>(null);
  const first = useRef(true);

  useEffect(() => {
    if (location.pathname === displayed) return;

    const panels = rootRef.current?.querySelectorAll("[data-panel]");
    if (!panels?.length) {
      setDisplayed(location.pathname);
      return;
    }

    const tl = gsap.timeline({
      onComplete: () => {
        setDisplayed(location.pathname);
      },
    });
    tl.set(rootRef.current, { pointerEvents: "auto", visibility: "visible" })
      .fromTo(
        panels,
        { yPercent: 100 },
        { yPercent: 0, duration: 0.45, stagger: 0.06, ease: "power4.inOut" }
      )
      .add(() => {
        scrollToTop(true);
        ScrollTrigger.refresh();
      })
      .to(panels, { yPercent: -100, duration: 0.6, stagger: 0.06, ease: "power4.inOut" }, "+=0.05")
      .set(rootRef.current, { pointerEvents: "none", visibility: "hidden" })
      .add(() => ScrollTrigger.refresh());

    return () => {
      tl.kill();
    };
  }, [location.pathname, displayed]);

  // first paint of the app: keep overlay hidden (preloader handles the intro)
  useEffect(() => {
    if (first.current) {
      first.current = false;
      gsap.set(rootRef.current, { visibility: "hidden" });
    }
  }, []);

  return (
    <>
      <div
        ref={rootRef}
        className="pointer-events-none fixed inset-0 z-[120] flex"
        style={{ visibility: "hidden" }}
        aria-hidden
      >
        {[0, 1, 2, 3].map((i) => (
          <div key={i} data-panel className="h-full flex-1 bg-panel2 translate-y-full" />
        ))}
        <div
          data-panel
          className="absolute inset-x-0 top-1/2 -translate-y-1/2 text-center font-mono text-[10px] uppercase tracking-[0.3em] text-faint"
        >
          {labelFor(location.pathname)}
        </div>
      </div>
      <div key={displayed} className="contents">
        {children}
      </div>
    </>
  );
}

function labelFor(path: string): string {
  if (path.startsWith("/run")) return "opening live feed";
  if (path.startsWith("/debrief")) return "compiling debrief";
  if (path.startsWith("/new")) return "opening intake";
  if (path.startsWith("/history")) return "pulling archive";
  return "firstbreath";
}
