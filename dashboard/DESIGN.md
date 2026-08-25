# FirstBreath — Design System

> Dark-graphite emergency control room wearing an editorial magazine's
> typography. Color is rationed like morphine; motion never decorates —
> it reports.

---

## 1. Visual identity

**One sentence:** a near-black command room where medical-white grotesk
headlines carry the drama and monospace system data carries the truth.

**The living Golden Hour.** Every screen renders the same underlying object —
*the run's timeline* — at different zoom levels. The landing page replays an
archived run as scroll-driven cinema (scroll position = simulation time).
Live Simulation runs the identical timeline against real telemetry, binding
map, clock, radio and vitals to one clock tick. When an event fires, five
things move in one coordinated beat. That synchrony is the design.

**Banned vocabulary:** purple gradients, neon/cyberpunk glow, glassmorphism,
card grids, default shadcn look, decorative animation, spinner loaders.

---

## 2. Palette

| Token | Value | Role |
|---|---|---|
| `void` | `#0A0C0E` | page canvas |
| `panel` | `#101317` | raised surface |
| `panel2` | `#161A1F` | highest surface / overlays |
| `line` | `#22272E` | hairlines, rules |
| `line2` | `#2E3540` | emphasized rules, outlines |
| `bone` | `#F2F3F5` | medical white — headlines, primary text |
| `mute` | `#9AA1AB` | secondary text |
| `faint` | `#5C646E` | meta, labels |
| `red` | `#E5484D` | **emergency only**: the call, countdowns, failure |
| `amber` | `#F5A623` | caution: traffic, tight windows, paused |
| `green` | `#3DD68C` | success states, readiness |
| `blue` | `#6C9EF8` | hospital/informational, used sparingly |

Rules:
- Red appears only when clinically justified. If everything is red,
  nothing is.
- Surfaces layer `void → panel → panel2`. Never pure black, never pure white.
- A film-grain overlay sits at 5% over every screen.

## 3. Typography

| Face | Use |
|---|---|
| **Space Grotesk** (`font-display`) | headlines, verdict words, wordmark. Tight tracking (-0.03em), weights 600–700, sizes up to 10rem+ |
| **Archivo** (`font-sans`) | body copy 13–15px / relaxed leading |
| **JetBrains Mono** (`font-mono`) | ALL system data: clocks, ETAs, coordinates, labels, stamps. Always `tabular-nums`, uppercase + letterspaced for labels |

Scale anchors: hero display `clamp(3.4rem, 11vw, 10rem)` · section titles
`text-5xl–7xl` · kicker/labels `10px mono, tracking 0.25em`.

Editorial device: **outlined text** (`.text-stroke`) for the middle line of
the hero triple-statement — fill, stroke, red.

## 4. Motion rulebook

Single motion system: **GSAP + ScrollTrigger** (via `@gsap/react`'s
`useGSAP`). Lenis drives smooth scroll on GSAP's ticker.

| Pattern | Spec |
|---|---|
| Headline reveal | lines masked, `yPercent 110 → 0`, `power4.out`, stagger 0.09 |
| Boot preloader | mono lines typed in, progress rule, shutter lift `power4.inOut` |
| Route transition | 4 graphite columns sweep up, hold 50ms, sweep away; scroll resets mid-cover |
| Scroll narrative | pinned section, scrub = sim time; chapters crossfade ±40px |
| Map pursuit | ambulance markers lerp toward polled positions at 5.5%/frame, heading rotates shortest-path |
| Hover | color/border transitions 300ms; solid buttons slide a bone wipe under label |
| Reduced motion | grain static, no smooth-scroll assumptions |

Motion must always answer *"what caused this?"* — if it can't, cut it.

## 5. Layout & components

- 12-col editorial grid, max width 1600, gutters 24/48px.
- Information lives on **ruled baselines** (`border-line`), not card boxes.
- Bespoke primitives only: `Button`, `Stamp`, `Readout`, `Kicker`,
  `GoldenClock`, `EventFeed`, `ProgressRail`, `CityMap`.
- The **SVG city** is drawn from real registry coordinates
  (lat 28.598–28.634, lng 77.196–77.234) projected into a 1000×1000 viewBox.
- Custom cursor: 6px dot (instant) + 36px ring (lagging). Desktop
  `(pointer:fine)` only; native cursor hidden there.

## 6. Data honesty

All telemetry flows through the typed client (`lib/api.ts`). When the
backend is unreachable, Live Simulation degrades to a recorded replay of
the canonical archived run and stamps itself `OFFLINE REPLAY` — the site
must never show a dead screen or a spinner.
