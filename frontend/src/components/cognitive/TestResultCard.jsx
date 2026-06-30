import { motion } from 'framer-motion'

const METRICS = [
  { key: 'cognitive_index', label: 'Cognitive Index', format: (v) => `${v?.toFixed(1)} / 100`, highlight: true },
  { key: 'hit_rate', label: 'Hit Rate (targets)', format: (v) => v != null ? `${(v * 100).toFixed(0)}%` : '—' },
  { key: 'false_alarm_rate', label: 'False Alarm Rate', format: (v) => v != null ? `${(v * 100).toFixed(0)}%` : '—' },
  { key: 'discriminability', label: 'Discriminability', format: (v) => v != null ? `${(v * 100).toFixed(0)}%` : '—' },
  { key: 'gaze_stability_score', label: 'Gaze Stability', format: (v) => `${((v || 0) * 100).toFixed(0)}%` },
  { key: 'reaction_time_avg_ms', label: 'Avg Recognition RT', format: (v) => v ? `${v.toFixed(0)} ms` : '—' },
  { key: 'correct_count', label: 'Overall Correct / Total', format: (v, s) => `${v} / ${s?.total_stimuli || 10}` },
]

function indexColor(index) {
  if (index >= 75) return '#22c55e'
  if (index >= 45) return '#f59e0b'
  return '#ef4444'
}

export default function TestResultCard({ scores }) {
  if (!scores) return null
  const color = indexColor(scores.cognitive_index)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="card p-5 space-y-4"
    >
      <div className="text-center py-4">
        <p className="text-xs text-muted uppercase tracking-wider mb-1">Cognitive Index</p>
        <p className="text-5xl font-bold font-mono" style={{ color }}>
          {scores.cognitive_index?.toFixed(1)}
        </p>
        <p className="text-sm mt-1" style={{ color }}>
          {scores.cognitive_index >= 75 ? 'Cognitively Normal' : scores.cognitive_index >= 45 ? 'Possible MCI' : 'Significant Impairment'}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {METRICS.slice(1).map(({ key, label, format }) => (
          <div key={key} className="rounded-md p-2.5" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)', backdropFilter: 'blur(8px)' }}>
            <p className="text-xs text-muted mb-0.5">{label}</p>
            <p className="font-mono text-sm font-medium text-white">{format(scores[key], scores)}</p>
          </div>
        ))}
      </div>
      {scores.discriminability != null && scores.discriminability < 0.55 && (
        <p className="text-xs text-amber-400/80 pt-1 border-t border-border">
          Low discriminability — the patient responded similarly to familiar and unfamiliar items.
          This score factors into the prediction automatically.
        </p>
      )}
    </motion.div>
  )
}
