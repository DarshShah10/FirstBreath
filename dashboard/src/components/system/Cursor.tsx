import { useEffect, useRef } from "react";
import { gsap } from "@/lib/gsap";

/**
 * Custom cursor: precise dot + lagging ring. Desktop only.
 * Elements tagged [data-cursor="view"|"link"|"stop"] change ring behavior.
 */
export default function Cursor() {
  const dotRef = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!window.matchMedia("(pointer: fine)").matches) return;

    const dot = dotRef.current!;
    const ring = ringRef.current!;
    gsap.set([dot, ring], { xPercent: -50, yPercent: -50, opacity: 0 });

    const dotX = gsap.quickTo(dot, "x", { duration: 0.08, ease: "power2.out" });
    const dotY = gsap.quickTo(dot, "y", { duration: 0.08, ease: "power2.out" });
    const ringX = gsap.quickTo(ring, "x", { duration: 0.42, ease: "power3.out" });
    const ringY = gsap.quickTo(ring, "y", { duration: 0.42, ease: "power3.out" });

    let shown = false;
    const move = (e: MouseEvent) => {
      if (!shown) {
        shown = true;
        gsap.to([dot, ring], { opacity: 1, duration: 0.3 });
      }
      dotX(e.clientX);
      dotY(e.clientY);
      ringX(e.clientX);
      ringY(e.clientY);

      const target = (e.target as HTMLElement)?.closest?.(
        "a, button, input, select, [data-cursor]"
      ) as HTMLElement | null;
      const mode = target?.dataset?.cursor || (target ? "link" : null);

      if (mode === "stop") {
        gsap.to(ring, { scale: 2.4, borderColor: "rgba(229,72,77,0.9)", duration: 0.3 });
        gsap.to(dot, { scale: 0, duration: 0.25 });
      } else if (mode) {
        gsap.to(ring, { scale: 1.7, borderColor: "rgba(242,243,245,0.7)", duration: 0.3 });
        gsap.to(dot, { scale: 1.6, backgroundColor: "#E5484D", duration: 0.25 });
      } else {
        gsap.to(ring, { scale: 1, borderColor: "rgba(242,243,245,0.35)", duration: 0.35 });
        gsap.to(dot, { scale: 1, backgroundColor: "#F2F3F5", duration: 0.25 });
      }
    };

    const down = () => gsap.to(ring, { scale: 0.85, duration: 0.15 });
    const up = () => gsap.to(ring, { scale: 1, duration: 0.25 });

    window.addEventListener("mousemove", move, { passive: true });
    window.addEventListener("mousedown", down);
    window.addEventListener("mouseup", up);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mousedown", down);
      window.removeEventListener("mouseup", up);
    };
  }, []);

  return (
    <div className="pointer-events-none fixed inset-0 z-[200] hidden [@media(pointer:fine)]:block" aria-hidden>
      <div
        ref={ringRef}
        className="fixed left-0 top-0 h-9 w-9 rounded-full border"
        style={{ borderColor: "rgba(242,243,245,0.35)" }}
      />
      <div ref={dotRef} className="fixed left-0 top-0 h-1.5 w-1.5 rounded-full bg-bone" />
    </div>
  );
}
