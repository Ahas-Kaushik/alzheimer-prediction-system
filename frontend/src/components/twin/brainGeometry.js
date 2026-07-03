/**
 * Shared procedural brain geometry for the Digital-Twin visualisations.
 *
 * A brain silhouette is approximated by two overlapping hemisphere ellipsoids.
 * Both the particle "abstract" twin and the holographic "anatomical" twin reuse
 * this so region colouring stays consistent between them.
 */
import * as THREE from 'three'

export const HX = 0.60 // hemisphere centre X offset
export const AX = 1.50 // X semi-axis
export const AY = 1.20 // Y semi-axis
export const AZ = 1.05 // Z semi-axis

export function insideBrain(x, y, z) {
  const L = ((x + HX) / AX) ** 2 + (y / AY) ** 2 + (z / AZ) ** 2
  const R = ((x - HX) / AX) ** 2 + (y / AY) ** 2 + (z / AZ) ** 2
  return Math.min(L, R) <= 1.0
}

/** Sample `n` points uniformly inside the brain volume. */
export function sampleBrainPoints(n) {
  const pts = []
  let tries = 0
  while (pts.length < n && tries < n * 120) {
    tries++
    const x = (Math.random() - 0.5) * 4.4
    const y = (Math.random() - 0.58) * 3.0
    const z = (Math.random() - 0.5) * 2.4
    if (insideBrain(x, y, z)) pts.push([x, y, z])
  }
  return pts
}

/** Anchor points (brain-space) for the 7 clinical regions — bilateral where relevant. */
export const REGION_ANCHORS = [
  { name: 'Prefrontal Cortex', pos: [0.0, 0.55, 0.95] },
  { name: 'Parietal Lobe', pos: [0.0, 0.85, -0.15] },
  { name: 'Occipital Lobe', pos: [0.0, 0.15, -1.05] },
  { name: 'Cerebellum', pos: [0.0, -0.75, -0.85] },
  { name: 'Temporal Lobe', pos: [1.05, -0.45, 0.15] },
  { name: 'Temporal Lobe', pos: [-1.05, -0.45, 0.15] },
  { name: 'Hippocampus', pos: [0.5, -0.3, 0.05] },
  { name: 'Hippocampus', pos: [-0.5, -0.3, 0.05] },
  { name: 'Entorhinal Cortex', pos: [0.5, -0.5, 0.3] },
  { name: 'Entorhinal Cortex', pos: [-0.5, -0.5, 0.3] },
]

export const STATUS_RGB = {
  Normal: [0.24, 1.0, 0.45],
  MCI: [1.0, 0.73, 0.15],
  AD: [1.0, 0.22, 0.22],
}
const BASE_RGB = [0.82, 0.9, 1.0] // cyan-white, matches the particle reference

/** Build {name: {status, severity}} lookup from the twin regions array. */
export function regionMap(regions = []) {
  const m = {}
  for (const r of regions) m[r.name] = { status: r.status, severity: r.severity }
  return m
}

/** Nearest region anchor to a point → its {name, status, severity}. */
export function nearestRegion(p, rmap) {
  let best = null
  let bestD = Infinity
  for (const a of REGION_ANCHORS) {
    const dx = p[0] - a.pos[0], dy = p[1] - a.pos[1], dz = p[2] - a.pos[2]
    const d = dx * dx + dy * dy + dz * dz
    if (d < bestD) { bestD = d; best = a }
  }
  if (!best) return { name: null, status: 'Normal', severity: 0 }
  const info = rmap[best.name] || { status: 'Normal', severity: 0 }
  return { name: best.name, ...info }
}

/** Colour for a point: white base blended toward the region's status colour by severity. */
export function pointColor(region) {
  const target = STATUS_RGB[region.status] || STATUS_RGB.Normal
  const t = Math.min(Math.max(region.severity || 0, 0), 1) * 0.9
  return [
    BASE_RGB[0] + (target[0] - BASE_RGB[0]) * t,
    BASE_RGB[1] + (target[1] - BASE_RGB[1]) * t,
    BASE_RGB[2] + (target[2] - BASE_RGB[2]) * t,
  ]
}

/** LineSegments float array for gyri fold lines (brain-outline shell). */
export function buildGyriSegments() {
  const segs = []
  for (const side of [-1, 1]) {
    const ox = side * HX
    const phiMid = side < 0 ? Math.PI : 0
    const HALF = Math.PI * 0.98
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
  }
  // Interhemispheric fissure ellipse
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

/** Round soft sprite texture for glowing particles. */
export function makeSprite() {
  const s = 64
  const c = document.createElement('canvas')
  c.width = c.height = s
  const ctx = c.getContext('2d')
  const g = ctx.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2)
  g.addColorStop(0, 'rgba(255,255,255,1)')
  g.addColorStop(0.35, 'rgba(255,255,255,0.7)')
  g.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, s, s)
  const tex = new THREE.CanvasTexture(c)
  return tex
}
