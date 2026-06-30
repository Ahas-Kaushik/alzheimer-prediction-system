import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Brain, Plus, TrendingDown, TrendingUp, Minus } from 'lucide-react'
import PageWrapper from '../components/layout/PageWrapper'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'
import Modal from '../components/ui/Modal'
import PatientForm from '../components/patient/PatientForm'
import { usePatients } from '../hooks/usePatient'
import axiosClient from '../api/axiosClient'

const STAGE_COLOR = { Normal: '#22c55e', MCI: '#f59e0b', AD: '#ef4444' }
const STAGE_BG = {
  Normal: 'border-green-800/30 bg-green-950/10',
  MCI: 'border-yellow-800/30 bg-yellow-950/10',
  AD: 'border-red-800/30 bg-red-950/10',
}

function TrendIcon({ delta }) {
  if (delta === 'improved') return <TrendingUp size={14} className="text-green-400" />
  if (delta === 'declined') return <TrendingDown size={14} className="text-red-400" />
  return <Minus size={14} className="text-slate-500" />
}

function PatientRow({ patient }) {
  const navigate = useNavigate()
  const [pred, setPred] = useState(null)
  const [twin, setTwin] = useState(null)

  useEffect(() => {
    axiosClient.get(`/predictions/${patient.patient_id}/latest`)
      .then((r) => setPred(r.data)).catch(() => {})
    axiosClient.get(`/twin/${patient.patient_id}`)
      .then((r) => setTwin(r.data)).catch(() => {})
  }, [patient.patient_id])

  const age = patient.dob
    ? Math.floor((Date.now() - new Date(patient.dob).getTime()) / 3.156e10)
    : patient.age

  return (
    <Card
      className={`cursor-pointer hover:border-primary/40 transition-colors ${pred ? STAGE_BG[pred.stage] : ''}`}
      onClick={() => navigate(`/patient/${patient.patient_id}`)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold text-white truncate">{patient.name}</p>
          <p className="text-xs font-mono text-muted mt-0.5">{patient.patient_id}</p>
          <p className="text-xs text-muted mt-1">
            {age ? `Age ${age}` : ''}
            {patient.gender ? ` · ${patient.gender}` : ''}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          {pred ? (
            <>
              <Badge stage={pred.stage} />
              <div className="flex items-center gap-1 text-xs text-slate-400">
                <TrendIcon delta={twin?.delta_from_last} />
                {(Number(pred.confidence) * 100).toFixed(0)}% confidence
              </div>
            </>
          ) : (
            <span className="text-xs text-muted italic">No prediction</span>
          )}
        </div>
      </div>

      {pred && (
        <div className="mt-3 pt-3 border-t border-border grid grid-cols-3 gap-2 text-center">
          {['Normal', 'MCI', 'AD'].map((s) => {
            const pct = pred.probabilities?.[s]
            return (
              <div key={s}>
                <p className="text-xs text-muted">{s}</p>
                <p
                  className="text-sm font-mono font-bold"
                  style={{ color: STAGE_COLOR[s] }}
                >
                  {pct != null ? `${(Number(pct) * 100).toFixed(0)}%` : '—'}
                </p>
              </div>
            )
          })}
        </div>
      )}

      {pred?.cognitive_index && (
        <div className="mt-2">
          <div className="flex items-center justify-between text-xs text-muted mb-0.5">
            <span>Cognitive Index</span>
            <span className="font-mono text-white">{Number(pred.cognitive_index).toFixed(1)}/100</span>
          </div>
          <div className="h-1.5 bg-border rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${Number(pred.cognitive_index)}%`,
                background: STAGE_COLOR[pred.stage] || '#6366f1',
              }}
            />
          </div>
        </div>
      )}
    </Card>
  )
}

export default function Patients() {
  const navigate = useNavigate()
  const { patients, loading, refetch } = usePatients()
  const [showForm, setShowForm] = useState(false)

  return (
    <PageWrapper>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-white">All Patients</h1>
          <p className="text-sm text-muted mt-0.5">{patients.length} registered</p>
        </div>
        <Button onClick={() => setShowForm(true)}>
          <Plus size={15} /> New Patient
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Spinner size="lg" /></div>
      ) : patients.length === 0 ? (
        <Card className="text-center py-16">
          <Brain size={40} className="mx-auto text-muted mb-4 opacity-30" />
          <p className="text-muted mb-4">No patients registered yet.</p>
          <Button onClick={() => setShowForm(true)}>
            <Plus size={14} /> Add First Patient
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {patients.map((p) => (
            <PatientRow key={p.patient_id} patient={p} />
          ))}
        </div>
      )}

      <Modal open={showForm} onClose={() => setShowForm(false)} title="New Patient">
        <PatientForm
          onSuccess={(p) => {
            setShowForm(false)
            refetch()
            navigate(`/patient/${p.patient_id}`)
          }}
        />
      </Modal>
    </PageWrapper>
  )
}
