import { motion } from 'framer-motion'

const STAGE_CONFIG = {
  Normal: { color: '#22c55e', label: 'Normal', description: 'No significant cognitive impairment detected' },
  MCI: { color: '#f59e0b', label: 'Mild Cognitive Impairment', description: 'Early-stage cognitive decline detected' },
  AD: { color: '#ef4444', label: "Alzheimer's Disease", description: 'Significant neurodegenerative changes detected' },
}

export default function StageIndicator({ stage, confidence }) {
  const config = STAGE_CONFIG[stage] || STAGE_CONFIG.Normal
  const pct = Math.round((confidence || 0) * 100)

  return (
    <div className="flex flex-col items-center gap-4 py-6">
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 200, damping: 15 }}
        className="relative w-36 h-36 flex items-center justify-center rounded-full"
        style={{
          background: `radial-gradient(circle at 35% 35%, ${config.color}28 0%, ${config.color}0a 50%, transparent 70%)`,
          boxShadow: `0 0 60px ${config.color}55, 0 0 120px ${config.color}22, inset 0 1px 0 rgba(255,255,255,0.18)`,
          border: `1.5px solid ${config.color}60`,
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
        }}
      >
        <div className="text-center">
          <span className="font-mono text-3xl font-bold" style={{ color: config.color }}>
            {pct}%
          </span>
        </div>
      </motion.div>
      <div className="text-center">
        <motion.h2
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="text-2xl font-semibold"
          style={{ color: config.color }}
        >
          {config.label}
        </motion.h2>
        <p className="text-sm text-muted mt-1">{config.description}</p>
      </div>
    </div>
  )
}
