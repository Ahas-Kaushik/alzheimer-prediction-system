import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  ScanLine,
  ArrowRightLeft,
  FlaskConical,
  BarChart3,
  Brain,
  FileText,
  Settings,
} from 'lucide-react'
import usePatientStore from '../../store/patientStore'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/patients', icon: Users, label: 'Patients' },
]

// Shared active / inactive Tailwind classes for nav links
const linkBase = 'flex items-center gap-3 px-3 py-2 rounded-btn text-sm transition-all duration-200'
const activeClass = `${linkBase} text-aurora-indigo`
const inactiveClass = `${linkBase} text-muted hover:text-white`

// Inline active styles that Tailwind can't express (glass tint + glow)
const activeStyle = {
  background: 'rgba(129, 140, 248, 0.13)',
  boxShadow: 'inset 0 0 0 1px rgba(129, 140, 248, 0.22), 0 0 12px rgba(99,102,241,0.15)',
}
const inactiveHoverStyle = {}

export default function Sidebar() {
  const currentPatient = usePatientStore((s) => s.currentPatient)
  const patientId = currentPatient?.patient_id

  const patientLinks = patientId
    ? [
        { to: `/patient/${patientId}/scan`,        icon: ScanLine,     label: 'Brain MRI Upload',    hint: 'T1-weighted MRI (.nii / PNG)' },
        { to: `/patient/${patientId}/mri-to-pet`,  icon: ArrowRightLeft,label: 'MRI → PET Synthesis', hint: 'Generate synthetic FDG-PET from MRI' },
        { to: `/patient/${patientId}/reports`,     icon: FileText,     label: 'Blood Reports',       hint: 'Lab results, blood panel, biomarkers' },
        { to: `/patient/${patientId}/cognitive`,   icon: FlaskConical, label: 'Cognitive Test',      hint: 'MMSE-equivalent assessment' },
        { to: `/patient/${patientId}/prediction`,  icon: BarChart3,    label: 'Predictions',         hint: 'Run AI pipeline & view results' },
        { to: `/patient/${patientId}/twin`,        icon: Brain,        label: 'Digital Twin',        hint: '3D brain model + longitudinal view' },
      ]
    : []

  return (
    <aside className="w-64 shrink-0 flex flex-col glass-sidebar h-full">
      {/* Logo / brand */}
      <div className="flex items-center gap-2.5 px-5 py-5"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
        <div className="relative">
          <Brain size={22} className="text-aurora-indigo drop-shadow-[0_0_8px_rgba(129,140,248,0.6)]" />
        </div>
        <span className="font-semibold text-white text-sm tracking-wide"
          style={{ textShadow: '0 0 20px rgba(129,140,248,0.4)' }}>
          NeuroScan AI
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} end
            className={({ isActive }) => isActive ? activeClass : inactiveClass}
            style={({ isActive }) => isActive ? activeStyle : inactiveHoverStyle}
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}

        {patientLinks.length > 0 && (
          <>
            <div className="pt-4 pb-1 px-3 text-xs uppercase tracking-widest truncate"
              style={{ color: 'rgba(167,139,250,0.6)', letterSpacing: '0.12em' }}>
              {currentPatient.name}
            </div>
            {patientLinks.map(({ to, icon: Icon, label, hint }) => (
              <NavLink key={to} to={to} title={hint}
                className={({ isActive }) => isActive ? activeClass : inactiveClass}
                style={({ isActive }) => isActive ? activeStyle : inactiveHoverStyle}
              >
                <Icon size={16} className="shrink-0" />
                <span className="truncate">{label}</span>
              </NavLink>
            ))}
          </>
        )}
      </nav>

      {/* Footer */}
      <div className="px-3 py-3" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
        <NavLink to="/settings"
          className={inactiveClass}
          style={inactiveHoverStyle}
        >
          <Settings size={16} />
          Settings
        </NavLink>
      </div>
    </aside>
  )
}
