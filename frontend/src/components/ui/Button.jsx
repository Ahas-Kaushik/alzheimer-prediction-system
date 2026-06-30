import { motion } from 'framer-motion'

const BASE = 'inline-flex items-center gap-2 font-medium rounded-btn transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed'

// Tailwind classes (colour tokens etc.)
const VARIANT_CLASS = {
  primary: 'text-white',
  ghost:   'text-gray-300',
  danger:  'text-red-400',
  success: 'text-emerald-400',
}

// Raw glass styles per variant — backdrop-filter can't be done in Tailwind @apply
const VARIANT_STYLE = {
  primary: {
    background:      'linear-gradient(135deg, rgba(99,102,241,0.75), rgba(139,92,246,0.75))',
    backdropFilter:  'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    border:          '1px solid rgba(139,92,246,0.38)',
    borderTopColor:  'rgba(180,160,255,0.32)',
    boxShadow:       '0 4px 18px rgba(99,102,241,0.3), inset 0 1px 0 rgba(255,255,255,0.16)',
    textShadow:      '0 1px 2px rgba(0,0,0,0.25)',
  },
  ghost: {
    background:      'rgba(255,255,255,0.04)',
    backdropFilter:  'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    border:          '1px solid rgba(255,255,255,0.1)',
  },
  danger: {
    background:      'rgba(248,113,113,0.1)',
    backdropFilter:  'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    border:          '1px solid rgba(248,113,113,0.22)',
    boxShadow:       'inset 0 1px 0 rgba(255,255,255,0.06)',
  },
  success: {
    background:      'rgba(52,211,153,0.1)',
    backdropFilter:  'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    border:          '1px solid rgba(52,211,153,0.22)',
    boxShadow:       'inset 0 1px 0 rgba(255,255,255,0.06)',
  },
}

const SIZE = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled,
  onClick,
  className = '',
  type = 'button',
  style = {},
}) {
  return (
    <motion.button
      type={type}
      whileTap={{ scale: disabled ? 1 : 0.96 }}
      onClick={onClick}
      disabled={disabled}
      className={`${BASE} ${VARIANT_CLASS[variant] ?? ''} ${SIZE[size]} ${className}`}
      style={{ ...VARIANT_STYLE[variant], ...style }}
    >
      {children}
    </motion.button>
  )
}
