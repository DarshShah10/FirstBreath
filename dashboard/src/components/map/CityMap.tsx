import { useEffect, useMemo, useRef } from "react";
import type { WorldSnapshot } from "@/lib/api";
import { cn } from "@/lib/cn";

/**
 * CityMap — hand-authored SVG district of Sector 12, Noida.
 * Real lat/lng bounds projected into a fixed viewBox. No tiles, no libs:
 * roads, hospitals (capacity arcs), ambulances (pursuit-interpolated
 * heading vectors), patient sites (pulsing), traffic conditions.
 */

// district bounds — matches backend registry coordinates
const LAT0 = 28.598, LAT1 = 28.634;
const LNG0 = 77.196, LNG1 = 77.234;
export const VW = 1000;
export const VH = 1000;

export function project(lat: number, lng: number): { x: number; y: number } {
  const x = ((lng - LNG0) / (LNG1 - LNG0)) * VW;
  const y = (1 - (lat - LAT0) / (LAT1 - LAT0)) * VH;
  return { x, y };
}

const GRID_LINES: Array<[[number, number], [number, number]]> = [
  [[28.634, 77.196], [28.634, 77.234]],
  [[28.62, 77.198], [28.62, 77.234]],
  [[28.608, 77.196], [28.608, 77.234]],
  [[28.598, 77.21], [28.634, 77.21]],
  [[28.602, 77.222], [28.63, 77.222]],
  [[28.626, 77.198], [28.626, 77.216]],
];

const ROUTES: Array<{ id: string; from: [number, number]; to: [number, number] }> = [
  { id: "route_patient_central_main", from: [28.61, 77.2], to: [28.6139, 77.209] },
  { id: "route_patient_central_alt", from: [28.61, 77.2], to: [28.6139, 77.209] },
  { id: "route_patient_district", from: [28.61, 77.2], to: [28.6239, 77.219] },
];

const HOSPITAL_PINS = [
  { id: "hospital_central", label: "CENTRAL", at: [28.6139, 77.209] as const },
  { id: "hospital_district", label: "DISTRICT", at: [28.6239, 77.219] as const },
  { id: "hospital_emergency", label: "EMC", at: [28.6039, 77.229] as const },
];

function routePath(a: [number, number], b: [number, number]): string {
  const p1 = project(a[0], a[1]);
  const p2 = project(b[0], b[1]);
  const mx = (p1.x + p2.x) / 2;
  const my = (p1.y + p2.y) / 2;
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const len = Math.hypot(dx, dy) || 1;
  const bow = 20;
  return `M ${p1.x} ${p1.y} Q ${mx + (-dy / len) * bow} ${my + (dx / len) * bow} ${p2.x} ${p2.y}`;
}

const CONDITION_COLOR: Record<string, string> = {
  clear: "#232A33",
  light: "#39424F",
  moderate: "#F5A62399",
  heavy: "#F5A623",
  blocked: "#E5484D",
};

interface AmbMarkerState {
  x: number; y: number; tx: number; ty: number;
  rot: number; trot: number;
}

export default function CityMap({
  snapshot,
  className,
}: {
  snapshot: WorldSnapshot | null;
  className?: string;
}) {
  const markerEls = useRef<Record<string, SVGGElement | null>>({});
  const markerState = useRef<Record<string, AmbMarkerState>>({});
  const rafRef = useRef(0);

  // ingest latest polled positions as pursuit targets
  useEffect(() => {
    if (!snapshot) return;
    for (const amb of snapshot.ambulances) {
      const p = project(amb.location.lat, amb.location.lng);
      const st =
        markerState.current[amb.id] ??
        (markerState.current[amb.id] = { x: p.x, y: p.y, tx: p.x, ty: p.y, rot: 0, trot: 0 });
      st.tx = p.x;
      st.ty = p.y;
      st.trot = headingFor(amb.status);
    }
  }, [snapshot]);

  // single rAF loop: chase targets, write transforms directly
  useEffect(() => {
    const loop = () => {
      for (const [id, st] of Object.entries(markerState.current)) {
        st.x += (st.tx - st.x) * 0.055;
        st.y += (st.ty - st.y) * 0.055;
        let dr = ((st.trot - st.rot + 540) % 360) - 180;
        st.rot += dr * 0.08;
        const el = markerEls.current[id];
        if (el) el.setAttribute("transform", `translate(${st.x.toFixed(1)},${st.y.toFixed(1)}) rotate(${st.rot.toFixed(1)})`);
      }
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  const routeTone = useMemo(() => {
    const map: Record<string, string> = {};
    snapshot?.routes.forEach((r) => {
      map[r.id] = CONDITION_COLOR[r.worst_condition] ?? CONDITION_COLOR.clear;
    });
    return map;
  }, [snapshot]);

  return (
    <div className={cn("relative h-full w-full overflow-hidden bg-void", className)}>
      <svg
        viewBox={`0 0 ${VW} ${VH}`}
        className="h-full w-full"
        preserveAspectRatio="xMidYMid slice"
        role="img"
        aria-label="District response map"
      >
        {/* sector blocks */}
        <g opacity={0.4}>
          {[
            [80, 90, 300, 220], [430, 60, 260, 180], [740, 120, 190, 260],
            [110, 380, 240, 200], [420, 330, 300, 240], [770, 440, 160, 210],
            [90, 650, 280, 230], [450, 640, 250, 250], [750, 700, 200, 190],
          ].map(([x, y, w, h], i) => (
            <rect key={i} x={x} y={y} width={w} height={h} fill="#0D1013" stroke="#151A21" strokeWidth={1} />
          ))}
        </g>

        {/* street grid */}
        {GRID_LINES.map(([[a1, a2], [b1, b2]], i) => {
          const p1 = project(a1, a2);
          const p2 = project(b1, b2);
          return (
            <line key={i} x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
              stroke="#12161C" strokeWidth={16} strokeLinecap="square" />
          );
        })}

        {/* response routes */}
        {ROUTES.map((r) => {
          const tone = routeTone[r.id] ?? CONDITION_COLOR.clear;
          const hot = tone !== CONDITION_COLOR.clear && tone !== CONDITION_COLOR.light;
          return (
            <path key={r.id} d={routePath(r.from, r.to)} fill="none"
              stroke={hot ? tone : "#1B212A"}
              strokeWidth={hot ? 7 : 5}
              strokeLinecap="round"
              opacity={hot ? 0.85 : 1}
            />
          );
        })}

        {/* hospitals */}
        {HOSPITAL_PINS.map((h) => {
          const p = project(h.at[0], h.at[1]);
          const state = snapshot?.hospitals.find((x) => x.id === h.id);
          const otRatio = state ? state.ot_available / Math.max(1, state.ot_total) : 1;
          const ready = !!state?.ot_ready || state?.ot_reserved === 0 && false;
          const arcColor = state?.ot_ready ? "#3DD68C" : otRatio > 0.3 ? "#6c9ef8" : "#F5A623";
          return (
            <g key={h.id} transform={`translate(${p.x},${p.y})`}>
              <circle r={30} fill="#0D1013" stroke="#1B212A" strokeWidth={3} />
              <circle
                r={30} fill="none" strokeWidth={3}
                stroke={state ? arcColor : "#1B212A"}
                strokeDasharray={`${otRatio * 188} 188`}
                transform="rotate(-90)"
                strokeLinecap="round"
              />
              <rect x={-8} y={-8} width={16} height={16} fill="#0D1013" stroke="#39424F" strokeWidth={1.5} />
              <rect x={-3} y={-3} width={6} height={6}
                fill={ready ? "#3DD68C" : state ? "#6c9ef8" : "#39424F"} />
              <text y={54} textAnchor="middle" fill="#5C646E" fontSize={17}
                fontFamily="JetBrains Mono, monospace">{h.label}</text>
            </g>
          );
        })}

        {/* patient sites */}
        {snapshot?.cases.map((c) => {
          if (["completed", "failed"].includes(c.status)) return null;
          const p = project(c.location.lat, c.location.lng);
          return (
            <g key={c.id} transform={`translate(${p.x},${p.y})`}>
              <circle r={10} fill="none" stroke="#E5484D" strokeWidth={2}>
                <animate attributeName="r" values="8;26" dur="1.8s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.9;0" dur="1.8s" repeatCount="indefinite" />
              </circle>
              <rect x={-7} y={-2.4} width={14} height={4.8} fill="#E5484D" />
              <rect x={-2.4} y={-7} width={4.8} height={14} fill="#E5484D" />
            </g>
          );
        })}

        {/* ambulances */}
        {snapshot?.ambulances.map((amb) => (
          <g key={amb.id}
             ref={(el) => {
               markerEls.current[amb.id] = el;
               if (el && !markerState.current[amb.id]) {
                 const p = project(amb.location.lat, amb.location.lng);
                 markerState.current[amb.id] = { x: p.x, y: p.y, tx: p.x, ty: p.y, rot: 0, trot: 0 };
                 el.setAttribute("transform", `translate(${p.x},${p.y})`);
               }
             }}
             data-amb={amb.id}>
            {amb.case_id && (
              <line x1={0} y1={-14} x2={0} y2={-44} stroke="#E5484D" strokeWidth={1.5} opacity={0.55} />
            )}
            <polygon points="0,-13 9,11 -9,11"
              fill={amb.case_id ? "#F2F3F5" : "#39424F"}
              stroke="#0A0C0E" strokeWidth={2} />
            {amb.eta_min != null && (
              <text y={-54} textAnchor="middle" fill="#E5484D" fontSize={19}
                fontFamily="JetBrains Mono, monospace" fontWeight={700}>
                {Math.ceil(amb.eta_min)}′
              </text>
            )}
          </g>
        ))}

        {/* frame meta */}
        <g fill="#39424F" fontFamily="JetBrains Mono, monospace" fontSize={16}>
          <text x={24} y={42}>28.634°N</text>
          <text x={VW - 160} y={VH - 24}>77.234°E</text>
          <text x={24} y={VH - 24}>SECTOR GRID · NOIDA · UP</text>
        </g>
      </svg>
    </div>
  );
}

function headingFor(status: string): number {
  switch (status) {
    case "en_route_patient": return -45;
    case "en_route_hospital": return 135;
    case "returning": return 45;
    default: return 0;
  }
}
