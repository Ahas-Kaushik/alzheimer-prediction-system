import { ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

// One colour per knowledge category.
const CAT_COLOR = {
  staging: '#818cf8',
  biomarker: '#22d3ee',
  cognitive: '#fbbf24',
  medication: '#f472b6',
  risk: '#ef4444',
  lifestyle: '#34d399',
  system: '#a78bfa',
}

function PointTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="px-3 py-2 rounded-lg text-xs max-w-[240px]"
      style={{ background: 'rgba(6,11,23,0.95)', border: '1px solid rgba(255,255,255,0.12)', backdropFilter: 'blur(16px)' }}>
      <div className="flex items-center gap-1.5 mb-0.5">
        <span className="w-2 h-2 rounded-full" style={{ background: CAT_COLOR[p.category] || '#9ca3af' }} />
        <span className="text-white/60">{p.category}</span>
      </div>
      <p className="text-white font-medium leading-snug">{p.title}</p>
    </div>
  )
}

export default function VectorDBViz({ points = [] }) {
  if (!points.length) {
    return <div className="text-sm text-muted py-8 text-center">No vectors to display — seed the vector store first.</div>
  }
  const categories = [...new Set(points.map((p) => p.category))]

  return (
    <div>
      <div className="w-full h-[420px] rounded-lg"
        style={{ background: 'radial-gradient(ellipse at center, #0a1120 0%, #060b17 100%)', border: '1px solid rgba(255,255,255,0.08)' }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 24, right: 24, bottom: 24, left: 24 }}>
            <XAxis type="number" dataKey="x" domain={[-1.15, 1.15]} hide />
            <YAxis type="number" dataKey="y" domain={[-1.15, 1.15]} hide />
            <ZAxis range={[120, 120]} />
            <Tooltip content={<PointTooltip />} cursor={{ strokeDasharray: '3 3', stroke: 'rgba(255,255,255,0.2)' }} />
            {categories.map((cat) => (
              <Scatter
                key={cat}
                name={cat}
                data={points.filter((p) => p.category === cat)}
                fill={CAT_COLOR[cat] || '#9ca3af'}
              >
                {points.filter((p) => p.category === cat).map((_, i) => (
                  <Cell key={i} style={{ filter: `drop-shadow(0 0 6px ${(CAT_COLOR[cat] || '#9ca3af')}aa)` }} />
                ))}
              </Scatter>
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3 justify-center">
        {categories.map((cat) => (
          <span key={cat} className="flex items-center gap-1.5 text-xs text-white/70">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: CAT_COLOR[cat] || '#9ca3af' }} />
            {cat}
          </span>
        ))}
      </div>
      <p className="text-xs text-muted text-center mt-2">
        Each point is a clinical knowledge chunk — 384-dim embedding projected to 2D (PCA).
        Semantically similar chunks cluster together.
      </p>
    </div>
  )
}
