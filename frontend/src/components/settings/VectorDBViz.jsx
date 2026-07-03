import { useState } from 'react'
import { ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const CAT_COLOR = {
  staging: '#818cf8',
  biomarker: '#22d3ee',
  cognitive: '#fbbf24',
  medication: '#f472b6',
  risk: '#ef4444',
  lifestyle: '#34d399',
  system: '#a78bfa',
}

// ── Table: the actual stored vectors ────────────────────────────────────────────
function VectorTable({ chunks, dim }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="text-muted border-b border-border">
            <th className="text-left py-2 pr-3 font-medium">#</th>
            <th className="text-left py-2 pr-3 font-medium">Knowledge chunk</th>
            <th className="text-left py-2 pr-3 font-medium">Category</th>
            <th className="text-right py-2 pr-3 font-medium">‖v‖</th>
            <th className="text-left py-2 font-medium">Embedding (first 8 of {dim} dims)</th>
          </tr>
        </thead>
        <tbody className="font-mono">
          {chunks.map((c, i) => (
            <tr key={c.id} className="border-b border-border/40 hover:bg-white/5">
              <td className="py-1.5 pr-3 text-muted">{i}</td>
              <td className="py-1.5 pr-3 text-white/90 font-sans max-w-[220px] truncate" title={c.title}>{c.title}</td>
              <td className="py-1.5 pr-3">
                <span className="inline-flex items-center gap-1 font-sans">
                  <span className="w-2 h-2 rounded-full" style={{ background: CAT_COLOR[c.category] || '#9ca3af' }} />
                  {c.category}
                </span>
              </td>
              <td className="py-1.5 pr-3 text-right text-white/70">{c.norm.toFixed(3)}</td>
              <td className="py-1.5 text-aurora-cyan/80 whitespace-nowrap">
                [{c.preview.map((v) => v.toFixed(3)).join(', ')}, …]
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Cosine-similarity heatmap ───────────────────────────────────────────────────
function SimilarityHeatmap({ similarity, labels }) {
  const [hover, setHover] = useState(null)
  const n = similarity.length
  const short = (t) => (t.length > 22 ? t.slice(0, 20) + '…' : t)
  return (
    <div>
      <div className="overflow-x-auto">
        <div className="inline-block">
          <div className="grid" style={{ gridTemplateColumns: `160px repeat(${n}, 22px)` }}>
            <div />
            {labels.map((l, j) => (
              <div key={j} className="h-[22px] flex items-end justify-center">
                <span className="text-[9px] text-muted origin-bottom-left rotate-[-60deg] translate-y-1 whitespace-nowrap"
                  style={{ transformOrigin: 'center' }}>{j}</span>
              </div>
            ))}
            {similarity.map((row, i) => (
              <div key={i} className="contents">
                <div className="text-[10px] text-muted pr-2 h-[22px] flex items-center justify-end truncate" title={labels[i]}>
                  <span className="text-white/40 mr-1">{i}</span>{short(labels[i])}
                </div>
                {row.map((v, j) => (
                  <div
                    key={j}
                    onMouseEnter={() => setHover({ i, j, v })}
                    onMouseLeave={() => setHover(null)}
                    className="w-[22px] h-[22px] border border-black/30"
                    style={{ background: `rgba(99,102,241,${Math.max(0, v).toFixed(3)})`, cursor: 'crosshair' }}
                    title={`${labels[i]} × ${labels[j]} = ${v.toFixed(3)}`}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3 mt-3 text-xs text-muted">
        <span>cosine similarity</span>
        <span className="flex items-center gap-1">
          0 <span className="w-24 h-2 rounded" style={{ background: 'linear-gradient(90deg, rgba(99,102,241,0), rgba(99,102,241,1))' }} /> 1
        </span>
        {hover && (
          <span className="text-white/80 font-mono">
            [{hover.i}]×[{hover.j}] = {hover.v.toFixed(3)}
          </span>
        )}
      </div>
    </div>
  )
}

// ── 2D projection scatter ───────────────────────────────────────────────────────
function ProjTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="px-3 py-2 rounded-lg text-xs max-w-[240px]"
      style={{ background: 'rgba(6,11,23,0.95)', border: '1px solid rgba(255,255,255,0.12)' }}>
      <span className="text-white/60">{p.category}</span>
      <p className="text-white font-medium leading-snug">{p.title}</p>
    </div>
  )
}
function Projection({ points }) {
  const categories = [...new Set(points.map((p) => p.category))]
  return (
    <div className="w-full h-[380px]">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 16, right: 16, bottom: 16, left: 16 }}>
          <XAxis type="number" dataKey="x" domain={[-1.15, 1.15]} hide />
          <YAxis type="number" dataKey="y" domain={[-1.15, 1.15]} hide />
          <ZAxis range={[110, 110]} />
          <Tooltip content={<ProjTooltip />} />
          {categories.map((cat) => (
            <Scatter key={cat} data={points.filter((p) => p.category === cat)} fill={CAT_COLOR[cat] || '#9ca3af'}>
              {points.filter((p) => p.category === cat).map((_, i) => <Cell key={i} />)}
            </Scatter>
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Main ────────────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'table', label: 'Table' },
  { id: 'heatmap', label: 'Similarity matrix' },
  { id: 'projection', label: '2D projection' },
]

export default function VectorDBViz({ data }) {
  const [tab, setTab] = useState('table')
  if (!data || !data.count) {
    return <div className="text-sm text-muted py-8 text-center">No vectors to display — seed the vector store first.</div>
  }
  const categories = [...new Set((data.chunks || []).map((c) => c.category))]

  return (
    <div>
      {/* tab switcher */}
      <div className="flex gap-1 mb-4">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`text-xs px-3 py-1.5 rounded-btn transition-colors ${tab === t.id ? 'text-white' : 'text-muted hover:text-white'}`}
            style={tab === t.id
              ? { background: 'rgba(129,140,248,0.15)', border: '1px solid rgba(129,140,248,0.3)' }
              : { background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)' }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'table' && <VectorTable chunks={data.chunks} dim={data.dim} />}
      {tab === 'heatmap' && <SimilarityHeatmap similarity={data.similarity} labels={data.labels} />}
      {tab === 'projection' && <Projection points={data.points} />}

      {/* legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-4 pt-3 border-t border-border justify-center">
        {categories.map((cat) => (
          <span key={cat} className="flex items-center gap-1.5 text-xs text-white/70">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: CAT_COLOR[cat] || '#9ca3af' }} />
            {cat}
          </span>
        ))}
      </div>
    </div>
  )
}
