/**
 * Abstract Digital Twin — particle point-cloud brain.
 *
 * Thousands of glowing points sampled inside the brain volume form a stippled
 * brain (inspired by a particle-scan render). Points are white-cyan by default
 * and blend toward amber/red where a region's severity is high, so pathology
 * shows up as coloured clusters. A faint neuron-signal layer adds life.
 */
import { useMemo, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import {
  sampleBrainPoints, regionMap, nearestRegion, pointColor, makeSprite,
} from './brainGeometry'

const N_POINTS = 6500

function ParticleBrain({ regions, connectivity = 1 }) {
  const ref = useRef()
  const rmap = useMemo(() => regionMap(regions), [regions])
  const sprite = useMemo(() => makeSprite(), [])

  const { geometry } = useMemo(() => {
    const pts = sampleBrainPoints(N_POINTS)
    const n = pts.length
    const positions = new Float32Array(n * 3)
    const colors = new Float32Array(n * 3)
    for (let i = 0; i < n; i++) {
      const p = pts[i]
      positions[i * 3] = p[0]
      positions[i * 3 + 1] = p[1]
      positions[i * 3 + 2] = p[2]
      const c = pointColor(nearestRegion(p, rmap))
      colors[i * 3] = c[0]; colors[i * 3 + 1] = c[1]; colors[i * 3 + 2] = c[2]
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    g.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    return { geometry: g }
  }, [rmap])

  // Lower connectivity → sparser twinkle (fewer bright points), so the twin
  // visibly "thins out" as the brain deteriorates.
  useFrame((state) => {
    if (ref.current) {
      ref.current.rotation.y = state.clock.elapsedTime * 0.12
      const pulse = 0.85 + Math.sin(state.clock.elapsedTime * 1.5) * 0.06
      ref.current.material.opacity = (0.55 + 0.4 * connectivity) * pulse
    }
  })

  return (
    <points ref={ref} geometry={geometry}>
      <pointsMaterial
        size={0.055}
        map={sprite}
        vertexColors
        transparent
        opacity={0.9}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}

export default function AbstractBrainViz({ regions = [], connectivity = 1.0 }) {
  const worst = regions.reduce(
    (acc, r) => (r.severity > acc.severity ? r : acc),
    { severity: 0, status: 'Normal' },
  )
  return (
    <div>
      <div
        className="w-full h-80 rounded-card overflow-hidden relative"
        style={{
          background: 'radial-gradient(ellipse at center, #050a14 0%, #02040a 70%, #000104 100%)',
          border: '1px solid rgba(34,211,238,0.18)',
        }}
      >
        <div className="absolute inset-0 pointer-events-none z-10"
          style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,120,200,0.02) 3px, rgba(0,120,200,0.02) 4px)' }} />
        <Canvas camera={{ position: [0, 0.3, 5.6], fov: 44 }} dpr={[1, 2]}>
          <ambientLight intensity={0.4} />
          <ParticleBrain regions={regions} connectivity={connectivity} />
          <OrbitControls enableZoom enablePan={false} minDistance={2.5} maxDistance={9} zoomSpeed={0.7} autoRotate={false} />
        </Canvas>
        <div className="absolute bottom-2 left-3 text-[10px] text-cyan-200/40 select-none pointer-events-none">
          {N_POINTS.toLocaleString()} particles · drag to rotate · scroll to zoom
        </div>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1.5 justify-center mt-2 text-xs text-slate-400 select-none">
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: '#d3ecff', boxShadow: '0 0 6px #d3ecff' }} /> Healthy tissue</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: '#f59e0b', boxShadow: '0 0 6px #f59e0b' }} /> MCI region</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: '#ef4444', boxShadow: '0 0 6px #ef4444' }} /> Atrophied region</span>
        {worst.severity > 0.15 && (
          <span className="text-white/60">· highest severity: <span style={{ color: { Normal: '#22c55e', MCI: '#f59e0b', AD: '#ef4444' }[worst.status] }}>{worst.name} {(worst.severity * 100).toFixed(0)}%</span></span>
        )}
      </div>
    </div>
  )
}
