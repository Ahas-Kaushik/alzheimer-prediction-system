import { useState, useEffect } from 'react'
import MRIViewer from './MRIViewer'
import PETViewer from './PETViewer'
import Button from '../ui/Button'

export default function ScanComparison({ mriPath, petPath, ssimScore, heatmapPath }) {
  const defaultMode = heatmapPath ? 'all' : 'side-by-side'
  const [mode, setMode] = useState(defaultMode)

  // Switch to 3-panel automatically once heatmap arrives after initial render
  useEffect(() => {
    if (heatmapPath) setMode('all')
  }, [heatmapPath])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {heatmapPath && (
          <Button size="sm" variant={mode === 'all' ? 'primary' : 'ghost'} onClick={() => setMode('all')}>
            MRI + PET + Heatmap
          </Button>
        )}
        <Button size="sm" variant={mode === 'side-by-side' ? 'primary' : 'ghost'} onClick={() => setMode('side-by-side')}>
          Side by Side
        </Button>
        <Button size="sm" variant={mode === 'mri' ? 'primary' : 'ghost'} onClick={() => setMode('mri')}>
          MRI Only
        </Button>
        <Button size="sm" variant={mode === 'pet' ? 'primary' : 'ghost'} onClick={() => setMode('pet')}>
          PET Only
        </Button>
        {heatmapPath && (
          <Button size="sm" variant={mode === 'heatmap' ? 'primary' : 'ghost'} onClick={() => setMode('heatmap')}>
            Activity Heatmap
          </Button>
        )}
      </div>

      {/* 3-panel: MRI | Physics PET (detection) | GAN Activity Heatmap (viz) */}
      {mode === 'all' && (
        <div className="grid grid-cols-3 gap-3">
          <MRIViewer src={mriPath} />
          <PETViewer
            src={petPath}
            ssimScore={ssimScore}
            label="Synthetic PET (Detection)"
            badge="Detection"
          />
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted uppercase tracking-wider">Activity Heatmap</p>
              <span className="text-xs text-amber-400">Viz only</span>
            </div>
            <div className="relative">
              <PETViewer
                src={heatmapPath}
                label=""
                badge={null}
                colorFilter="none"
              />
              <span className="absolute top-2 right-2 text-xs bg-amber-500/80 text-white px-1.5 py-0.5 rounded">
                GAN
              </span>
            </div>
            <p className="text-xs text-muted leading-relaxed">
              GAN-synthesized activity pattern. Used for visualization only — not used in diagnosis.
            </p>
          </div>
        </div>
      )}

      {/* Original 2-panel or single-panel modes */}
      {mode !== 'all' && (
        <div className={`grid gap-4 ${mode === 'side-by-side' ? 'grid-cols-2' : 'grid-cols-1 max-w-sm'}`}>
          {(mode === 'side-by-side' || mode === 'mri') && <MRIViewer src={mriPath} />}
          {(mode === 'side-by-side' || mode === 'pet') && (
            <PETViewer src={petPath} ssimScore={ssimScore} label="Synthetic PET (Detection)" badge="Detection" />
          )}
          {mode === 'heatmap' && (
            <PETViewer
              src={heatmapPath}
              label="GAN Activity Heatmap (Visualization)"
              badge="GAN"
              colorFilter="none"
            />
          )}
        </div>
      )}
    </div>
  )
}
