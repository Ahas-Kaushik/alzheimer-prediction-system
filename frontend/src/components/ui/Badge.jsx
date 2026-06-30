const STAGE_STYLES = {
  Normal: {
    className: 'text-emerald-400',
    style: {
      background:     'rgba(52,211,153,0.09)',
      border:         '1px solid rgba(52,211,153,0.25)',
      backdropFilter: 'blur(8px)',
      boxShadow:      '0 0 8px rgba(52,211,153,0.12)',
    },
  },
  MCI: {
    className: 'text-amber-400',
    style: {
      background:     'rgba(251,191,36,0.09)',
      border:         '1px solid rgba(251,191,36,0.25)',
      backdropFilter: 'blur(8px)',
      boxShadow:      '0 0 8px rgba(251,191,36,0.12)',
    },
  },
  AD: {
    className: 'text-red-400',
    style: {
      background:     'rgba(248,113,113,0.09)',
      border:         '1px solid rgba(248,113,113,0.25)',
      backdropFilter: 'blur(8px)',
      boxShadow:      '0 0 8px rgba(248,113,113,0.12)',
    },
  },
}

export default function Badge({ label, stage, className = '', style = {} }) {
  const stageConfig = stage ? STAGE_STYLES[stage] : null
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${stageConfig?.className ?? ''} ${className}`}
      style={{ ...stageConfig?.style, ...style }}
    >
      {label || stage}
    </span>
  )
}
