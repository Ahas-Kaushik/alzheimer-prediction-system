export const colors = {
  background: '#0a0f1e',
  surface: '#111827',
  border: '#1f2937',
  primary: '#6366f1',
  success: '#22c55e',
  warning: '#f59e0b',
  danger: '#ef4444',
  text: '#f9fafb',
  muted: '#6b7280',
}

export const stageColors = {
  Normal: colors.success,
  MCI: colors.warning,
  AD: colors.danger,
}

export const stageClasses = {
  Normal: 'stage-normal',
  MCI: 'stage-mci',
  AD: 'stage-ad',
}

export const shadows = {
  card: '0 4px 24px rgba(0,0,0,0.4)',
  glow: {
    primary: '0 0 20px rgba(99,102,241,0.3)',
    success: '0 0 20px rgba(34,197,94,0.3)',
    warning: '0 0 20px rgba(245,158,11,0.3)',
    danger: '0 0 20px rgba(239,68,68,0.3)',
  },
}
