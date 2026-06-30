import { motion } from 'framer-motion'

export default function Card({ children, className = '', animate = true, glow }) {
  const glowStyles = glow
    ? { boxShadow: `0 4px 28px rgba(0,0,0,0.38), inset 0 1px 0 rgba(255,255,255,0.1), 0 0 24px ${glow}` }
    : undefined

  if (!animate) {
    return (
      <div className={`card ${className}`} style={glowStyles}>
        {children}
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
      className={`card ${className}`}
      style={glowStyles}
    >
      {children}
    </motion.div>
  )
}
