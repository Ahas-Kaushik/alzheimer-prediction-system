import { AlertCircle } from 'lucide-react'

export default function ClinicalSummary({ factors = [], cognitiveIndex, ssimScore }) {
  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold text-muted uppercase tracking-wider">Key Contributing Factors</h3>
      {factors.length === 0 && (
        <p className="text-sm text-muted italic">No factors available</p>
      )}
      {factors.map((f, i) => (
        <div key={i} className="flex items-center gap-2 text-sm">
          <AlertCircle size={14} className="text-warning shrink-0" />
          <span className="text-white/80">{f}</span>
        </div>
      ))}
      <div className="pt-2 grid grid-cols-2 gap-3 text-xs">
        {cognitiveIndex != null && (
          <div className="rounded-md p-2.5" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)', backdropFilter: 'blur(8px)' }}>
            <p className="text-muted mb-0.5">Cognitive Index</p>
            <p className="font-mono font-semibold text-white">{cognitiveIndex.toFixed(1)} / 100</p>
          </div>
        )}
        {ssimScore != null && (
          <div className="rounded-md p-2.5" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)', backdropFilter: 'blur(8px)' }}>
            <p className="text-muted mb-0.5">PET Quality (SSIM)</p>
            <p className="font-mono font-semibold text-white">{(ssimScore * 100).toFixed(1)}%</p>
          </div>
        )}
      </div>
    </div>
  )
}
