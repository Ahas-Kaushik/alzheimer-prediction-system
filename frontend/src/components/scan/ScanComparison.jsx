import { useState } from 'react'
import MRIViewer from './MRIViewer'
import PETViewer from './PETViewer'
import Button from '../ui/Button'

export default function ScanComparison({ mriPath, petPath, ssimScore }) {
  const [mode, setMode] = useState('side-by-side')

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant={mode === 'side-by-side' ? 'primary' : 'ghost'} onClick={() => setMode('side-by-side')}>
          Side by Side
        </Button>
        <Button size="sm" variant={mode === 'mri' ? 'primary' : 'ghost'} onClick={() => setMode('mri')}>
          MRI Only
        </Button>
        <Button size="sm" variant={mode === 'pet' ? 'primary' : 'ghost'} onClick={() => setMode('pet')}>
          PET Only
        </Button>
      </div>

      <div className={`grid gap-4 ${mode === 'side-by-side' ? 'grid-cols-2' : 'grid-cols-1 max-w-sm'}`}>
        {(mode === 'side-by-side' || mode === 'mri') && <MRIViewer src={mriPath} />}
        {(mode === 'side-by-side' || mode === 'pet') && (
          <PETViewer src={petPath} ssimScore={ssimScore} label="Synthetic PET (Detection)" badge="Detection" />
        )}
      </div>
    </div>
  )
}
