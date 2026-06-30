import { useLocation } from 'react-router-dom'
import usePatientStore from '../../store/patientStore'

const PAGE_TITLES = {
  '/':          'Dashboard',
  '/patients':  'Patients',
  'scan':       'Upload Scan',
  'mri-to-pet': 'MRI → PET Synthesis',
  'cognitive':  'Cognitive Test',
  'prediction': 'Prediction Results',
  'twin':       'Digital Brain Twin',
  'reports':    'Clinical Reports',
}

function resolveTitle(pathname) {
  const last = pathname.split('/').pop()
  return PAGE_TITLES[last] || PAGE_TITLES[pathname] || 'NeuroScan AI'
}

export default function Navbar() {
  const { pathname } = useLocation()
  const currentPatient = usePatientStore((s) => s.currentPatient)
  const title = resolveTitle(pathname)

  return (
    <header className="h-14 shrink-0 flex items-center justify-between px-6 glass-nav">
      <h1 className="text-sm font-semibold text-white/90 tracking-wide">{title}</h1>
      <div className="flex items-center gap-4 text-sm">
        {currentPatient && (
          <span className="text-white/50">
            Patient:{' '}
            <span className="text-aurora-indigo font-medium"
              style={{ textShadow: '0 0 12px rgba(129,140,248,0.5)' }}>
              {currentPatient.name}
            </span>
          </span>
        )}
        <span className="font-mono text-xs"
          style={{ color: 'rgba(167,139,250,0.55)' }}>
          {new Date().toLocaleDateString()}
        </span>
      </div>
    </header>
  )
}
