/**
 * Brain hologram visualization.
 *
 * Shape: two hemisphere ellipsoids with gyri fold lines (latitude rings +
 *        diagonal sulci curves) = recognisable brain silhouette.
 * Neurons: green (Normal), amber (MCI), red (AD) glowing spheres inside.
 * Connections: white lines between nearby neurons.
 * Signals: gold glowing dots travelling along white lines.
 *          On AD connections the dot fades out halfway (severed synapse).
 */
import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'

// ── Brain volume geometry ─────────────────────────────────────────────────────
const HX = 0.60          // hemisphere centre X offset
const AX = 1.50          // X semi-axis
const AY = 1.20          // Y semi-axis
const AZ = 1.05          // Z semi-axis

function insideBrain(x, y, z) {
  const L = ((x + HX) / AX) ** 2 + (y / AY) ** 2 + (z / AZ) ** 2
  const R = ((x - HX) / AX) ** 2 + (y / AY) ** 2 + (z / AZ) ** 2
  return Math.min(L, R) <= 1.0
}

function sampleBrainPoints(n) {
  const pts = []
  let tries = 0
  while (pts.length < n && tries < n * 120) {
    tries++
    const x = (Math.random() - 0.5) * 4.4
    const y = (Math.random() - 0.58) * 3.0
    const z = (Math.random() - 0.5) * 2.4
    if (insideBrain(x, y, z)) pts.push(new THREE.Vector3(x, y, z))
  }
  return pts
}

function buildEdges(pts, maxDist, maxConn) {
  const edges = []; const seen = new Set()
  for (let i = 0; i < pts.length; i++) {
    const nbrs = []
    for (let j = 0; j < pts.length; j++) {
      if (i === j) continue
      const d = pts[i].distanceTo(pts[j])
      if (d < maxDist) nbrs.push({ j, d })
    }
    nbrs.sort((a, b) => a.d - b.d)
    let added = 0
    for (const { j } of nbrs) {
      if (added >= maxConn) break
      const key = `${Math.min(i, j)}_${Math.max(i, j)}`
      if (!seen.has(key)) { seen.add(key); edges.push([i, j]); added++ }
    }
  }
  return edges
}

// ── Gyri fold line segments ───────────────────────────────────────────────────
// Each hemisphere draws:
//   • 5 latitude rings (gyri parallels)
//   • 4 longitude arcs  (meridians)
//   • 3 diagonal sulcal curves
// All merged into a flat float array for one LineSegments draw call.
function buildGyriSegments() {
  const segs = []

  for (const side of [-1, 1]) {
    const ox = side * HX
    // Outward phi range for this hemisphere:
    //   left (side=-1)  → phi: π/2 → 3π/2  (left-facing arc)
    //   right (side=+1) → phi: -π/2 → π/2  (right-facing arc)
    const phiMid = side < 0 ? Math.PI : 0          // centre of outward arc
    const HALF = Math.PI * 0.98                      // slightly less than π

    // Latitude rings (constant theta)
    for (const f of [0.20, 0.34, 0.50, 0.65, 0.80]) {
      const theta = f * Math.PI
      const N = 28
      for (let i = 0; i < N; i++) {
        const phi0 = phiMid - HALF + (i / N) * HALF * 2
        const phi1 = phiMid - HALF + ((i + 1) / N) * HALF * 2
        segs.push(
          ox + AX * Math.sin(theta) * Math.cos(phi0), AY * Math.cos(theta), AZ * Math.sin(theta) * Math.sin(phi0),
          ox + AX * Math.sin(theta) * Math.cos(phi1), AY * Math.cos(theta), AZ * Math.sin(theta) * Math.sin(phi1),
        )
      }
    }

    // Longitude arcs (constant phi within hemisphere)
    for (const dPhi of [-0.55, -0.18, 0.18, 0.55]) {
      const phi = phiMid + dPhi
      const M = 20
      for (let i = 0; i < M; i++) {
        const t0 = (i / M) * Math.PI
        const t1 = ((i + 1) / M) * Math.PI
        segs.push(
          ox + AX * Math.sin(t0) * Math.cos(phi), AY * Math.cos(t0), AZ * Math.sin(t0) * Math.sin(phi),
          ox + AX * Math.sin(t1) * Math.cos(phi), AY * Math.cos(t1), AZ * Math.sin(t1) * Math.sin(phi),
        )
      }
    }

    // Diagonal sulcal folds
    for (let k = 0; k < 3; k++) {
      const tStart = 0.22 + k * 0.22
      const pOff = (k - 1) * 0.38
      const K = 18
      for (let i = 0; i < K; i++) {
        const t0 = i / K, t1 = (i + 1) / K
        const th0 = (tStart + t0 * 0.34) * Math.PI
        const th1 = (tStart + t1 * 0.34) * Math.PI
        const ph0 = phiMid + pOff + t0 * Math.PI * 0.28
        const ph1 = phiMid + pOff + t1 * Math.PI * 0.28
        segs.push(
          ox + AX * Math.sin(th0) * Math.cos(ph0), AY * Math.cos(th0), AZ * Math.sin(th0) * Math.sin(ph0),
          ox + AX * Math.sin(th1) * Math.cos(ph1), AY * Math.cos(th1), AZ * Math.sin(th1) * Math.sin(ph1),
        )
      }
    }
  }

  // Interhemispheric fissure: ellipse in x=0 plane
  const F = 36
  for (let i = 0; i < F; i++) {
    const a0 = (i / F) * Math.PI * 2, a1 = ((i + 1) / F) * Math.PI * 2
    segs.push(
      0, AY * Math.cos(a0) * 1.06, AZ * Math.sin(a0) * 0.98,
      0, AY * Math.cos(a1) * 1.06, AZ * Math.sin(a1) * 0.98,
    )
  }

  return new Float32Array(segs)
}

// ── Node & edge config ────────────────────────────────────────────────────────
const N_NEURONS = 62
const MAX_DIST = 1.48
const MAX_CONN = 4

const NODE_COLOR = { Normal: '#22ff55', MCI: '#ffbb22', AD: '#ff3333' }
const NODE_EMISSIVE = { Normal: '#00cc33', MCI: '#cc7700', AD: '#bb0000' }
const NODE_EMISSIVE_INT = { Normal: 1.4, MCI: 1.0, AD: 0.35 }

// ── Three.js scene ────────────────────────────────────────────────────────────
function BrainHologram({ regions, connectivity }) {
  const groupRef = useRef()
  const pulseRef = useRef([])    // { t, speed } per edge
  const pulseMeshes = useRef([]) // mesh refs per edge

  // Stable neuron positions (no deps → runs once per mount)
  const neurons = useMemo(() => sampleBrainPoints(N_NEURONS), [])
  const edges   = useMemo(() => buildEdges(neurons, MAX_DIST, MAX_CONN), [neurons])

  // Reactive neuron status (changes when twin data arrives)
  const neuronStatus = useMemo(() => neurons.map((_, i) => {
    if (!regions?.length) return 'Normal'
    return regions[i % regions.length]?.status ?? 'Normal'
  }), [regions, neurons])

  // Which edges carry active pulses
  const activeEdge = useMemo(() => edges.map(([i, j]) => {
    const ad = neuronStatus[i] === 'AD' || neuronStatus[j] === 'AD'
    const threshold = ad ? 0.12 : 0.45 + connectivity * 0.48
    return Math.random() < threshold
  }), [edges, neuronStatus, connectivity])

  // Initialise pulse phases whenever edge list changes
  useMemo(() => {
    pulseRef.current = edges.map(() => ({
      t: Math.random(),
      speed: 0.22 + Math.random() * 0.28,
    }))
  }, [edges])

  // Gyri geometry (one LineSegments for all fold lines)
  const gyriGeo = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(buildGyriSegments(), 3))
    return g
  }, [])

  // White neural connection geometry (one LineSegments)
  const connGeo = useMemo(() => {
    const pos = []
    for (const [i, j] of edges) {
      pos.push(neurons[i].x, neurons[i].y, neurons[i].z,
               neurons[j].x, neurons[j].y, neurons[j].z)
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3))
    return g
  }, [neurons, edges])

  useFrame((_, delta) => {
    // Slow Y rotation
    if (groupRef.current) groupRef.current.rotation.y += delta * 0.09

    // Advance each pulse dot along its edge
    for (let k = 0; k < edges.length; k++) {
      if (!activeEdge[k]) continue
      const p = pulseRef.current[k]
      if (!p) continue
      p.t = (p.t + delta * p.speed) % 1.0

      const [i, j] = edges[k]
      const a = neurons[i], b = neurons[j]
      const mesh = pulseMeshes.current[k]
      if (!mesh) continue

      mesh.position.set(
        a.x + (b.x - a.x) * p.t,
        a.y + (b.y - a.y) * p.t,
        a.z + (b.z - a.z) * p.t,
      )

      // AD synapses: signal fades after the halfway point
      const isAD = neuronStatus[i] === 'AD' || neuronStatus[j] === 'AD'
      if (isAD && mesh.material) {
        mesh.material.opacity = p.t < 0.5 ? 1.0 : Math.max(0, 1.0 - (p.t - 0.5) * 2.4)
      }
    }
  })

  return (
    <group ref={groupRef}>

      {/* ── Hemisphere semi-transparent fills (DoubleSide = visible from inside too) */}
      {[-1, 1].map((s) => (
        <mesh key={s} position={[s * HX, 0, 0]} scale={[AX, AY, AZ]}>
          <sphereGeometry args={[1, 5, 4]} />
          <meshStandardMaterial color="#061828" transparent opacity={0.10} side={THREE.DoubleSide} />
        </mesh>
      ))}

      {/* ── Brain outline: gyri fold lines + interhemispheric fissure ─── */}
      <lineSegments geometry={gyriGeo}>
        <lineBasicMaterial color="#1a7acc" transparent opacity={0.55} />
      </lineSegments>

      {/* ── White neural connection lines ──────────────────────────────── */}
      <lineSegments geometry={connGeo}>
        <lineBasicMaterial color="#ffffff" transparent opacity={0.38} />
      </lineSegments>

      {/* ── Neuron nodes ───────────────────────────────────────────────── */}
      {neurons.map((pos, i) => {
        const st = neuronStatus[i]
        return (
          <mesh key={i} position={pos.toArray()}>
            <sphereGeometry args={[0.068, 9, 9]} />
            <meshStandardMaterial
              color={NODE_COLOR[st] ?? '#22ff55'}
              emissive={NODE_EMISSIVE[st] ?? '#00cc33'}
              emissiveIntensity={NODE_EMISSIVE_INT[st] ?? 1.4}
              roughness={0.25}
              metalness={0.1}
            />
          </mesh>
        )
      })}

      {/* ── Gold signal pulses ─────────────────────────────────────────── */}
      {edges.map(([i, j], k) => {
        if (!activeEdge[k]) return null
        const isAD = neuronStatus[i] === 'AD' || neuronStatus[j] === 'AD'
        return (
          <mesh
            key={`dot_${k}`}
            ref={(el) => { pulseMeshes.current[k] = el }}
            position={neurons[i].toArray()}
          >
            <sphereGeometry args={[0.052, 8, 8]} />
            <meshStandardMaterial
              color={isAD ? '#ff5533' : '#ffd700'}
              emissive={isAD ? '#ff2200' : '#ff8800'}
              emissiveIntensity={isAD ? 1.8 : 4.5}
              transparent
              opacity={1}
            />
          </mesh>
        )
      })}
    </group>
  )
}

// ── Legend ─────────────────────────────────────────────────────────────────────
function Legend({ regions }) {
  const hasAD  = regions?.some((r) => r.status === 'AD')
  const hasMCI = regions?.some((r) => r.status === 'MCI')
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-1.5 justify-center mt-2 px-2 text-xs text-slate-400 select-none">
      <span className="flex items-center gap-1.5">
        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: '#22ff55', boxShadow: '0 0 6px #22ff55' }} />
        Healthy neuron
      </span>
      {hasMCI && (
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: '#ffbb22', boxShadow: '0 0 6px #ffbb22' }} />
          MCI neuron
        </span>
      )}
      {hasAD && (
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: '#ff3333', boxShadow: '0 0 6px #ff3333' }} />
          Degraded neuron
        </span>
      )}
      <span className="flex items-center gap-1.5">
        <span className="w-2 h-0.5 flex-shrink-0" style={{ background: '#ffffff', opacity: 0.7 }} />
        Connection
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: '#ffd700', boxShadow: '0 0 8px #ffd700' }} />
        Signal pulse
      </span>
    </div>
  )
}

// ── Public component ──────────────────────────────────────────────────────────
export default function AbstractBrainViz({ regions = [], connectivity = 1.0 }) {
  return (
    <div>
      <div
        className="w-full h-80 rounded-card overflow-hidden relative"
        style={{
          background: 'radial-gradient(ellipse at center, #020d1f 0%, #010710 70%, #000408 100%)',
          border: '1px solid rgba(139,92,246,0.2)',
          boxShadow: '0 0 0 0.5px rgba(34,211,238,0.1), inset 0 1px 0 rgba(255,255,255,0.06)',
        }}
      >
        {/* Subtle scan-line overlay for hologram feel */}
        <div
          className="absolute inset-0 pointer-events-none z-10"
          style={{
            backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,100,200,0.025) 3px, rgba(0,100,200,0.025) 4px)',
          }}
        />
        <Canvas camera={{ position: [0, 0.5, 6.4], fov: 44 }}>
          <ambientLight intensity={0.20} />
          <pointLight position={[5, 5, 5]} intensity={0.80} color="#ffffff" />
          <pointLight position={[-4, -3, -4]} intensity={0.45} color="#4466ff" />
          <pointLight position={[0, 0, 4]} intensity={0.30} color="#22aaff" />
          <BrainHologram regions={regions} connectivity={connectivity} />
          <OrbitControls
            enableZoom={true}
            enablePan={false}
            minDistance={0.4}
            maxDistance={10}
            zoomSpeed={0.7}
          />
        </Canvas>
      </div>
      <p className="text-center text-xs text-slate-600 mt-1 select-none">
        Scroll to zoom &middot; drag to rotate &middot; scroll in to enter the brain
      </p>
      <Legend regions={regions} />
    </div>
  )
}
