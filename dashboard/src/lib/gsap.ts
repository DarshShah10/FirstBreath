import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(ScrollTrigger, useGSAP);

gsap.defaults({ ease: "power3.out", duration: 0.9 });

export { gsap, ScrollTrigger, useGSAP };

/** Resolve once the boot preloader has lifted. */
export function onSystemReady(cb: () => void): void {
  if ((window as any).__fbReady) {
    cb();
    return;
  }
  const handler = () => {
    window.removeEventListener("fb:ready", handler);
    cb();
  };
  window.addEventListener("fb:ready", handler);
}

export function markSystemReady(): void {
  (window as any).__fbReady = true;
  window.dispatchEvent(new Event("fb:ready"));
}
