/**
 * Anatomical Digital Twin — holographic MRI scanner.
 *
 * A glowing translucent brain (hemisphere shells + gyri fold lines) floats in a
 * scanner rig with three dotted-frame orthographic projection planes
 * (Side / Top / Coronal) and a reflective floor. Region "hotspots" glow by
 * clinical status (green / amber / red) and are hoverable for details.
 */
import { useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Line, Html } from '@react-three/drei'
import * as THREE from 'three'
import { HX, AX, AY, AZ, buildGyriSegments, REGION_ANCHORS, STATUS_RGB } from './brainGeometry'

const STAGE_HEX = { Normal: '#22c55e', MCI: '#f59e0b', AD: '#ef4444' }
const CYAN = '#22d3ee'
const CYAN_BRIGHT = '#67e8f9'

// ── ellipse / rectangle point helpers ───────────────────────────────────────────
function ellipse(cx, cy, cz, rx, ry, plane, n = 64) {
  const pts = []
  for (let i = 0; i <= n; i++) {
    const t = (i / n) * Math.PI * 2
    const a = Math.cos(t) * rx, b = Math.sin(t) * ry
    if (plane === 'xy') pts.push([cx + a, cy + b, cz])
    else if (plane === 'xz') pts.push([cx + a, cy, cz + b])
    else pts.push([cx, cy + b, cz + a]) // zy
  }
  return pts
}
function rect(cx, cy, cz, w, h, plane) {
  const hw = w / 2, hh = h / 2
  if (plane === 'xy') return [[cx - hw, cy - hh, cz], [cx + hw, cy - hh, cz], [cx + hw, cy + hh, cz], [cx - hw, cy + hh, cz], [cx - hw, cy - hh, cz]]
  if (plane === 'xz') return [[cx - hw, cy, cz - hh], [cx + hw, cy, cz - hh], [cx + hw, cy, cz + hh], [cx - hw, cy, cz + hh], [cx - hw, cy, cz - hh]]
  return [[cx, cy - hh, cz - hw], [cx, cy - hh, cz + hw], [cx, cy + hh, cz + hw], [cx, cy + hh, cz - hw], [cx, cy - hh, cz - hw]] // zy
}

// ── central hologram brain ──────────────────────────────────────────────────────
function HologramBrain({ regions }) {
  const groupRef = useRef()
  const gyriGeo = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(buildGyriSegments(), 3))
    return g
  }, [])
  const [hover, setHover] = useState(null)
  const rmap = useMemo(() => Object.fromEntries(regions.map((r) => [r.name, r])), [regions])
  useFrame((_, d) => { if (groupRef.current) groupRef.current.rotation.y += d * 0.12 })

  return (
    <group ref={groupRef}>
      {/* translucent hemispheres */}
      {[-1, 1].map((s) => (
        <mesh key={s} position={[s * HX, 0, 0]} scale={[AX, AY, AZ]}>
          <sphereGeometry args={[1, 24, 18]} />
          <meshBasicMaterial color={CYAN} transparent opacity={0.06} side={THREE.DoubleSide} depthWrite={false} />
        </mesh>
      ))}
      {/* gyri fold lines */}
      <lineSegments geometry={gyriGeo}>
        <lineBasicMaterial color={CYAN_BRIGHT} transparent opacity={0.5} />
      </lineSegments>

      {/* region hotspots */}
      {REGION_ANCHORS.map((a, i) => {
        const r = rmap[a.name]
        const status = r?.status || 'Normal'
        const sev = r?.severity ?? 0
        const rgb = STATUS_RGB[status]
        const col = new THREE.Color(rgb[0], rgb[1], rgb[2])
        const size = 0.05 + sev * 0.13
        const isHover = hover === i
        return (
          <mesh key={i} position={a.pos}
            onPointerOver={(e) => { e.stopPropagation(); setHover(i) }}
            onPointerOut={() => setHover(null)}>
            <sphereGeometry args={[isHover ? size * 1.4 : size, 16, 16]} />
            <meshBasicMaterial color={col} transparent opacity={0.9} />
            {isHover && r && (
              <Html center distanceFactor={8}>
                <div className="px-2 py-1 rounded-md text-[11px] whitespace-nowrap"
                  style={{ background: 'rgba(6,11,23,0.92)', border: `1px solid ${STAGE_HEX[status]}66`, color: '#fff' }}>
                  <span className="font-medium">{a.name}</span>{' '}
                  <span style={{ color: STAGE_HEX[status] }}>{status} · {(sev * 100).toFixed(0)}%</span>
                </div>
              </Html>
            )}
          </mesh>
        )
      })}
    </group>
  )
}

// ── one orthographic projection plane (frame + silhouette + label) ──────────────
function ProjectionPlane({ frame, silhouette, extra, label, labelPos, plane }) {
  return (
    <group>
      <Line points={frame} color={CYAN} lineWidth={1} dashed dashSize={0.12} gapSize={0.09} transparent opacity={0.5} />
      <Line points={silhouette} color={CYAN_BRIGHT} lineWidth={1.2} transparent opacity={0.55} />
      {extra && <Line points={extra} color={CYAN_BRIGHT} lineWidth={1} transparent opacity={0.4} />}
      <Html position={labelPos} center>
        <div className="text-[10px] tracking-widest uppercase text-cyan-300/70 select-none whitespace-nowrap">{label}</div>
      </Html>
    </group>
  )
}

function Scene({ regions }) {
  return (
    <>
      <HologramBrain regions={regions} />

      {/* Back wall — Coronal view */}
      <ProjectionPlane
        plane="xy"
        frame={rect(0, 0, -2.4, 5.2, 4.0, 'xy')}
        silhouette={ellipse(0, 0.1, -2.39, 1.35, 1.15, 'xy')}
        extra={[[0, 1.25, -2.39], [0, -1.05, -2.39]]}
        label="Coronal View"
        labelPos={[-1.9, 1.7, -2.4]}
      />
      {/* Floor — Top view */}
      <ProjectionPlane
        plane="xz"
        frame={rect(0, -1.95, 0, 5.2, 4.0, 'xz')}
        silhouette={ellipse(0, -1.94, 0, 1.35, 1.05, 'xz')}
        extra={[[0, -1.94, -1.05], [0, -1.94, 1.05]]}
        label="Top View"
        labelPos={[-1.9, -1.94, -1.7]}
      />
      {/* Left wall — Side view */}
      <ProjectionPlane
        plane="zy"
        frame={rect(-3.0, 0, 0, 4.0, 4.0, 'zy')}
        silhouette={ellipse(-2.99, 0.1, 0, 1.15, 1.2, 'zy')}
        extra={[[-2.99, -0.8, -0.9], [-2.99, -1.05, -1.3]]}
        label="Side View"
        labelPos={[-3.0, 1.7, -1.7]}
      />

      {/* reflective-ish floor glow */}
      <mesh position={[0, -1.96, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[3.2, 48]} />
        <meshBasicMaterial color="#0a2530" transparent opacity={0.35} side={THREE.DoubleSide} />
      </mesh>

      <ambientLight intensity={0.5} />
      <OrbitControls enableZoom enablePan={false} minDistance={3} maxDistance={12} zoomSpeed={0.7} target={[0, -0.2, 0]} />
    </>
  )
}

export default function AnatomicalBrainViz({ regions = [] }) {
  return (
    <div>
      <div className="w-full h-80 rounded-card overflow-hidden relative"
        style={{ background: 'radial-gradient(ellipse at center, #061420 0%, #02060d 70%, #000308 100%)', border: '1px solid rgba(34,211,238,0.2)' }}>
        <div className="absolute inset-0 pointer-events-none z-10"
          style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,120,200,0.025) 3px, rgba(0,120,200,0.025) 4px)' }} />
        <div className="absolute top-2 left-3 text-[10px] tracking-widest uppercase text-cyan-300/50 z-20 select-none pointer-events-none">
          Magnetic Resonance Imaging · Digital Twin
        </div>
        <Canvas camera={{ position: [3.5, 1.8, 6.2], fov: 42 }} dpr={[1, 2]}>
          <Scene regions={regions} />
        </Canvas>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1.5 justify-center mt-2 text-xs text-slate-400 select-none">
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: '#22c55e', boxShadow: '0 0 6px #22c55e' }} /> Normal</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: '#f59e0b', boxShadow: '0 0 6px #f59e0b' }} /> MCI</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: '#ef4444', boxShadow: '0 0 6px #ef4444' }} /> Atrophied</span>
        <span className="text-white/50">· hover a hotspot for region detail</span>
      </div>
    </div>
  )
}
