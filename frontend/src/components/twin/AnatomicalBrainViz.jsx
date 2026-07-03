import { useState } from 'react'
import Tooltip from '../ui/Tooltip'

const STAGE_COLORS = { Normal: '#22c55e', MCI: '#f59e0b', AD: '#ef4444' }

// Simplified SVG paths for 7 brain regions (lateral view approximation)
const REGIONS_SVG = [
  { name: 'Prefrontal Cortex', d: 'M60,40 Q90,20 120,30 Q130,50 110,70 Q80,80 60,60 Z' },
  { name: 'Temporal Lobe', d: 'M40,100 Q60,90 90,100 Q100,130 80,150 Q50,140 40,120 Z' },
  { name: 'Parietal Lobe', d: 'M110,40 Q150,30 180,50 Q185,80 160,90 Q130,85 110,65 Z' },
  { name: 'Occipital Lobe', d: 'M170,80 Q200,70 210,100 Q200,130 175,130 Q160,110 165,90 Z' },
  { name: 'Hippocampus', d: 'M85,110 Q100,105 115,115 Q118,130 105,135 Q88,132 85,118 Z' },
  { name: 'Entorhinal Cortex', d: 'M65,125 Q80,120 90,130 Q88,145 72,148 Q60,142 62,130 Z' },
  { name: 'Cerebellum', d: 'M130,140 Q170,130 185,155 Q178,175 150,178 Q125,170 125,155 Z' },
]

function regionColor(name, regions) {
  const r = regions.find((r) => r.name === name)
  if (!r) return '#22c55e'
  return STAGE_COLORS[r.status] || '#22c55e'
}

function regionOpacity(name, regions) {
  const r = regions.find((r) => r.name === name)
  if (!r) return 0.2
  return 0.2 + r.severity * 0.7
}

export default function AnatomicalBrainViz({ regions = [] }) {
  const [hovered, setHovered] = useState(null)

  return (
    <div className="relative w-full rounded-card border border-border bg-black/30 overflow-hidden p-4">
      <svg viewBox="0 0 260 200" className="w-full max-h-72">
        {/* Brain outline */}
        <ellipse cx="130" cy="100" rx="105" ry="85" fill="none" stroke="#1f2937" strokeWidth="1.5" />
        {REGIONS_SVG.map(({ name, d }) => {
          const color = regionColor(name, regions)
          const opacity = regionOpacity(name, regions)
          return (
            <path
              key={name}
              d={d}
              fill={color}
              fillOpacity={opacity}
              stroke={color}
              strokeOpacity={0.6}
              strokeWidth="1"
              className="cursor-pointer transition-all duration-200"
              onMouseEnter={() => setHovered(name)}
              onMouseLeave={() => setHovered(null)}
            />
          )
        })}
      </svg>
      {hovered && (() => {
        const r = regions.find((r) => r.name === hovered)
        return (
          <div className="absolute bottom-4 left-4 bg-surface border border-border rounded-md px-3 py-2 text-xs">
            <p className="font-medium text-white">{hovered}</p>
            {r && (
              <>
                <p className="text-muted">Severity: {(r.severity * 100).toFixed(0)}%</p>
                <p style={{ color: STAGE_COLORS[r.status] }}>{r.status}</p>
              </>
            )}
          </div>
        )
      })()}
    </div>
  )
}
