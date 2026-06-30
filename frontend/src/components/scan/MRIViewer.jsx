export default function MRIViewer({ src, label = 'MRI Scan' }) {
  if (!src) {
    return (
      <div className="aspect-square bg-black/30 border border-border rounded-card flex items-center justify-center text-muted text-sm">
        No MRI uploaded
      </div>
    )
  }
  // Normalize Windows backslashes → forward slashes, then strip any prefix up to /uploads/
  const normalised = src.replace(/\\/g, '/')
  const url = normalised.startsWith('http')
    ? normalised
    : `http://localhost:8000/uploads/${normalised.replace(/^.*uploads\//, '')}`
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted uppercase tracking-wider">{label}</p>
      <img
        src={url}
        alt={label}
        className="w-full aspect-square object-cover rounded-card border border-border bg-black"
        onError={(e) => { e.target.style.display = 'none' }}
      />
    </div>
  )
}
