import { useMemo, useState } from 'react'

const TYPE_COLOR = {
  Patient: '#818cf8',
  Visit: '#64748b',
  Prediction: '#f472b6',
  Report: '#34d399',
  CognitiveTest: '#fbbf24',
  DigitalTwin: '#a78bfa',
  MRIScan: '#22d3ee',
}
const TYPE_RADIUS = { Patient: 13 }

const W = 720
const H = 480

/** Deterministic Fruchterman–Reingold-style force layout (runs once per data). */
function computeLayout(nodes, edges) {
  const N = nodes.length
  if (!N) return []
  const idx = Object.fromEntries(nodes.map((n, i) => [n.id, i]))
  // Deterministic initial placement on a circle.
  const pos = nodes.map((_, i) => ({
    x: W / 2 + Math.cos((i / N) * 2 * Math.PI) * W * 0.32,
    y: H / 2 + Math.sin((i / N) * 2 * Math.PI) * H * 0.32,
  }))
  const k = Math.sqrt((W * H) / N) * 0.9
  const ITERS = 300
  for (let it = 0; it < ITERS; it++) {
    const disp = pos.map(() => ({ x: 0, y: 0 }))
    for (let i = 0; i < N; i++) {
      for (let j = i + 1; j < N; j++) {
        let dx = pos[i].x - pos[j].x
        let dy = pos[i].y - pos[j].y
        const d = Math.hypot(dx, dy) || 0.01
        const rep = (k * k) / d
        const ux = dx / d, uy = dy / d
        disp[i].x += ux * rep; disp[i].y += uy * rep
        disp[j].x -= ux * rep; disp[j].y -= uy * rep
      }
    }
    for (const e of edges) {
      const a = idx[e.source], b = idx[e.target]
      if (a == null || b == null) continue
      let dx = pos[a].x - pos[b].x
      let dy = pos[a].y - pos[b].y
      const d = Math.hypot(dx, dy) || 0.01
      const att = (d * d) / k
      const ux = dx / d, uy = dy / d
      disp[a].x -= ux * att; disp[a].y -= uy * att
      disp[b].x += ux * att; disp[b].y += uy * att
    }
    const temp = (1 - it / ITERS) * (W * 0.05)
    for (let i = 0; i < N; i++) {
      const dl = Math.hypot(disp[i].x, disp[i].y) || 0.01
      pos[i].x += (disp[i].x / dl) * Math.min(dl, temp)
      pos[i].y += (disp[i].y / dl) * Math.min(dl, temp)
      pos[i].x += (W / 2 - pos[i].x) * 0.012
      pos[i].y += (H / 2 - pos[i].y) * 0.012
      pos[i].x = Math.max(24, Math.min(W - 24, pos[i].x))
      pos[i].y = Math.max(24, Math.min(H - 24, pos[i].y))
    }
  }
  return pos
}

export default function KnowledgeGraphViz({ nodes = [], edges = [] }) {
  const [hover, setHover] = useState(null)
  const pos = useMemo(() => computeLayout(nodes, edges), [nodes, edges])
  const posById = useMemo(() => {
    const m = {}
    nodes.forEach((n, i) => { m[n.id] = pos[i] })
    return m
  }, [nodes, pos])

  if (!nodes.length) {
    return <div className="text-sm text-muted py-8 text-center">No graph data.</div>
  }

  const legendTypes = [...new Set(nodes.map((n) => n.type))]

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded-lg"
        style={{ background: 'radial-gradient(ellipse at center, #0a1120 0%, #060b17 100%)', border: '1px solid rgba(255,255,255,0.08)' }}>
        {/* edges */}
        {edges.map((e, i) => {
          const a = posById[e.source], b = posById[e.target]
          if (!a || !b) return null
          return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
            stroke="rgba(255,255,255,0.14)" strokeWidth={1} />
        })}
        {/* nodes */}
        {nodes.map((n, i) => {
          const p = pos[i]
          const color = TYPE_COLOR[n.type] || '#9ca3af'
          const r = TYPE_RADIUS[n.type] || 8
          const isHover = hover === n.id
          return (
            <g key={n.id} onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)}
              style={{ cursor: 'pointer' }}>
              <circle cx={p.x} cy={p.y} r={r} fill={color}
                stroke={isHover ? '#fff' : `${color}`} strokeWidth={isHover ? 2 : 0.5}
                style={{ filter: `drop-shadow(0 0 ${isHover ? 8 : 4}px ${color}aa)` }} />
              {(n.type === 'Patient' || isHover) && (
                <text x={p.x} y={p.y - r - 4} textAnchor="middle"
                  fill={isHover ? '#fff' : 'rgba(255,255,255,0.7)'} fontSize={isHover ? 12 : 10}
                  style={{ pointerEvents: 'none', fontWeight: n.type === 'Patient' ? 600 : 400 }}>
                  {n.type === 'Patient' ? n.caption : `${n.type}: ${n.caption}`}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {/* legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3 justify-center">
        {legendTypes.map((t) => (
          <span key={t} className="flex items-center gap-1.5 text-xs text-white/70">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: TYPE_COLOR[t] || '#9ca3af' }} />
            {t}
          </span>
        ))}
      </div>
    </div>
  )
}
