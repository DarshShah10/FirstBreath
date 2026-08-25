import { useEffect } from "react";
import Lenis from "lenis";
import { gsap, ScrollTrigger } from "./gsap";

/**
 * Mounts the global smooth-scroll loop and hands control of `scrollTo`
 * to GSAP's ticker so ScrollTrigger stays perfectly in sync.
 */
export function SmoothScroll({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.15,
      easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
    });

    lenis.on("scroll", ScrollTrigger.update);

    const raf = (time: number) => lenis.raf(time * 1000);
    gsap.ticker.add(raf);
    gsap.ticker.lagSmoothing(0);

    (window as any).__lenis = lenis;

    return () => {
      gsap.ticker.remove(raf);
      lenis.destroy();
      (window as any).__lenis = undefined;
    };
  }, []);

  return <>{children}</>;
}

export function scrollToTop(immediate = true) {
  const lenis = (window as any).__lenis as Lenis | undefined;
  if (lenis) lenis.scrollTo(0, { immediate });
  else window.scrollTo(0, 0);
}
