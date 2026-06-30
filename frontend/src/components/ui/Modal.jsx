import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'

const OVERLAY_STYLE = {
  background: 'rgba(6, 11, 23, 0.72)',
  backdropFilter: 'blur(12px)',
  WebkitBackdropFilter: 'blur(12px)',
}

const PANEL_STYLE = {
  background: 'linear-gradient(135deg, rgba(139,92,246,0.06) 0%, rgba(34,211,238,0.04) 50%, rgba(244,114,182,0.03) 100%), rgba(255,255,255,0.05)',
  backdropFilter: 'blur(48px) saturate(200%)',
  WebkitBackdropFilter: 'blur(48px) saturate(200%)',
  border: '1px solid rgba(255,255,255,0.09)',
  borderTopColor: 'rgba(255,255,255,0.16)',
  boxShadow: '0 20px 60px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.12), 0 0 0 0.5px rgba(139,92,246,0.1)',
}

export default function Modal({ open, onClose, title, children }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={OVERLAY_STYLE}
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.94, opacity: 0, y: 8 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.94, opacity: 0, y: 8 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className="rounded-card p-6 w-full max-w-lg mx-4"
            style={PANEL_STYLE}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">{title}</h2>
              <button
                onClick={onClose}
                className="text-muted hover:text-white transition-colors p-1 rounded-btn"
                style={{ background: 'rgba(255,255,255,0.06)' }}
              >
                <X size={18} />
              </button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
