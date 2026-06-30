import { useNavigate } from 'react-router-dom'
import { User, Calendar } from 'lucide-react'
import { motion } from 'framer-motion'
import Badge from '../ui/Badge'
import usePatientStore from '../../store/patientStore'

export default function PatientCard({ patient, latestStage }) {
  const navigate = useNavigate()
  const setCurrentPatient = usePatientStore((s) => s.setCurrentPatient)

  const handleClick = () => {
    setCurrentPatient(patient)
    navigate(`/patient/${patient.patient_id}`)
  }

  return (
    <motion.div
      onClick={handleClick}
      className="card p-4 cursor-pointer transition-all duration-200"
      whileHover={{
        scale: 1.015,
        boxShadow: '0 6px 32px rgba(0,0,0,0.45), 0 0 0 1px rgba(129,140,248,0.28), inset 0 1px 0 rgba(255,255,255,0.14)',
      }}
      whileTap={{ scale: 0.985 }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full flex items-center justify-center"
            style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.2)' }}>
            <User size={16} className="text-aurora-indigo" />
          </div>
          <div>
            <p className="font-medium text-white text-sm">{patient.name}</p>
            <p className="text-xs text-muted font-mono">{patient.patient_id}</p>
          </div>
        </div>
        {latestStage && <Badge stage={latestStage} />}
      </div>
      <div className="flex items-center gap-1 text-xs text-muted">
        <Calendar size={12} />
        <span>Age {patient.age} · {patient.gender}</span>
      </div>
    </motion.div>
  )
}
