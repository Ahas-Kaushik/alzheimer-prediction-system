import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

const WORD_COLORS = [
  '#00f5ff', '#ffd700', '#ff6b35', '#ff2d55',
  '#a8ff00', '#bf5af2', '#ff9f0a', '#30d158',
  '#64d2ff', '#ff453a', '#ffd60a', '#0a84ff',
  '#ff6cff', '#5ac8fa', '#ffcc02', '#34c759',
]

function makePos() {
  return {
    color: WORD_COLORS[Math.floor(Math.random() * WORD_COLORS.length)],
    fontSize: Math.round(30 + Math.random() * 50),   // 30–80 px
    left: Math.round(10 + Math.random() * 68),        // 10–78 %
    top: Math.round(14 + Math.random() * 62),         // 14–76 %
  }
}

export default function TestDisplay({ stimulus }) {
  const [pos, setPos] = useState(makePos)

  useEffect(() => {
    setPos(makePos())
  }, [stimulus?.index])

  if (!stimulus) return null

  // Foil stimuli are always shown without images (nonsense labels only).
  const isKnownFoil = stimulus.kind === 'foil' || stimulus.is_target === false
  const showImage = stimulus.kind === 'object' && stimulus.image_path && !isKnownFoil

  return (
    <div
      className="relative w-full rounded-xl overflow-hidden"
      style={{
        height: '58vh',
        minHeight: '400px',
        background: 'linear-gradient(145deg, #060b18 0%, #0f172a 55%, #0a1120 100%)',
        border: '1px solid #1e293b',
        boxShadow: 'inset 0 0 80px rgba(0,0,0,0.6)',
      }}
    >
      {/* Warmup badge */}
      {stimulus.is_warmup && (
        <span className="absolute top-3 left-3 z-20 text-xs text-yellow-400 bg-yellow-400/10 border border-yellow-400/30 px-3 py-1 rounded-full">
          Practice Round
        </span>
      )}

      {/* Stimulus — image or label at random position */}
      <motion.div
        key={stimulus.index}
        initial={{ opacity: 0, scale: 0.55 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.9 }}
        transition={{ type: 'spring', stiffness: 300, damping: 22 }}
        className="absolute flex flex-col items-center gap-2 select-none pointer-events-none"
        style={{
          left: `${pos.left}%`,
          top: `${pos.top}%`,
          transform: 'translate(-50%, -50%)',
        }}
      >
        {showImage ? (
          <img
            src={`http://localhost:8000/uploads/${stimulus.image_path}`}
            alt={stimulus.label}
            className="max-h-32 max-w-32 object-contain rounded-lg"
            style={{ filter: `drop-shadow(0 0 16px ${pos.color}88)` }}
          />
        ) : null}
        <span
          className="font-extrabold tracking-wide whitespace-nowrap"
          style={{
            fontSize: `${pos.fontSize}px`,
            color: pos.color,
            textShadow: `0 0 28px ${pos.color}99, 0 0 55px ${pos.color}44`,
            lineHeight: 1.1,
          }}
        >
          {stimulus.label}
        </span>
      </motion.div>

      {/* Subtle crosshair at center for gaze calibration reference */}
      <div
        className="absolute pointer-events-none"
        style={{
          left: '50%', top: '50%',
          transform: 'translate(-50%,-50%)',
          width: 8, height: 8,
          borderRadius: '50%',
          background: '#ffffff14',
          boxShadow: '0 0 12px #ffffff22',
        }}
      />

      {/* Bottom instructions */}
      <p className="absolute bottom-3 left-0 right-0 text-center text-xs text-slate-600 select-none">
        <kbd className="bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded text-xs font-mono">Space</kbd>
        &nbsp;to recognize&nbsp;&nbsp;&nbsp;
        <kbd className="bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded text-xs font-mono">Enter</kbd>
        &nbsp;to skip
      </p>
    </div>
  )
}
