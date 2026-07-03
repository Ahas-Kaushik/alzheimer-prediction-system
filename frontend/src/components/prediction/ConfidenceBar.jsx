import { motion } from 'framer-motion'

const STAGE_COLORS = { Normal: '#22c55e', MCI: '#f59e0b', AD: '#ef4444' }

export default function ConfidenceBar({ probabilities }) {
  // API may send `null` (not just `undefined`), which skips default params.
  const probs = probabilities || {}
  return (
    <div className="space-y-2.5">
      {['Normal', 'MCI', 'AD'].map((stage) => {
        const pct = Math.round((probs[stage] || 0) * 100)
        const color = STAGE_COLORS[stage]
        return (
          <div key={stage}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted">{stage}</span>
              <span className="font-mono font-medium" style={{ color }}>{pct}%</span>
            </div>
            <div className="h-2 bg-border rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
                className="h-full rounded-full"
                style={{ background: color }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
