// colorFilter default is 'none' — the backend already bakes the clinical hot colormap
// into the PNG. Applying an extra CSS hue-rotate would shift the colors and invert
// the clinical meaning (high activity ↔ low activity).
export default function PETViewer({ src, ssimScore, label = 'Synthetic PET', badge = 'AI', colorFilter = 'none' }) {
  if (!src) {
    return (
      <div className="aspect-square bg-black/30 border border-border rounded-card flex items-center justify-center text-muted text-sm">
        PET not generated
      </div>
    )
  }
  const normalised = src.replace(/\\/g, '/')
  const url = normalised.startsWith('http')
    ? normalised
    : `http://localhost:8000/uploads/${normalised.replace(/^.*uploads\//, '')}`
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted uppercase tracking-wider">{label}</p>
        {ssimScore != null && (
          <span className="text-xs font-mono text-primary">SSIM {(ssimScore * 100).toFixed(1)}%</span>
        )}
      </div>
      <div className="relative">
        <img
          src={url}
          alt={label}
          className="w-full aspect-square object-cover rounded-card border border-border bg-black"
          style={{ filter: colorFilter }}
          onError={(e) => { e.target.style.display = 'none' }}
        />
        {badge && (
          <span className="absolute top-2 right-2 text-xs bg-primary/80 text-white px-1.5 py-0.5 rounded">{badge}</span>
        )}
      </div>
    </div>
  )
}
