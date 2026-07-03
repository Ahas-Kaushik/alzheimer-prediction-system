import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Plus, Users, Brain, Activity, CheckCircle, Clock,
  RefreshCw, TrendingUp, AlertTriangle, Zap,
} from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import { motion, AnimatePresence } from 'framer-motion'
import PageWrapper from '../components/layout/PageWrapper'
import Modal from '../components/ui/Modal'
import PatientForm from '../components/patient/PatientForm'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'
import Badge from '../components/ui/Badge'
import { usePatients } from '../hooks/usePatient'
import { getLatestPrediction } from '../api/predictionApi'
import usePatientStore from '../store/patientStore'

// ── helpers ────────────────────────────────────────────────────────────────────

function calcAge(dob) {
  if (!dob) return null
  const d = new Date(dob)
  const today = new Date()
  let age = today.getFullYear() - d.getFullYear()
  if (today.getMonth() < d.getMonth() || (today.getMonth() === d.getMonth() && today.getDate() < d.getDate())) age--
  return age
}

function relativeTime(dateStr) {
  if (!dateStr) return null
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString()
}

const STAGE_GLOW = {
  Normal: 'rgba(52,211,153,0.3)',
  MCI:    'rgba(251,191,36,0.3)',
  AD:     'rgba(248,113,113,0.3)',
}
const STAGE_COLOR_HEX = { Normal: '#34d399', MCI: '#fbbf24', AD: '#f87171' }
const STAGE_PIE_COLOR  = { Normal: '#34d399', MCI: '#fbbf24', AD: '#f87171', Pending: '#374151' }

// ── Stat Card ──────────────────────────────────────────────────────────────────

function StatCard({ label, value, icon: Icon, color, glow, loading }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="card flex items-center gap-4 py-4"
      style={glow ? { boxShadow: `0 4px 28px rgba(0,0,0,0.38), inset 0 1px 0 rgba(255,255,255,0.1), 0 0 20px ${glow}` } : undefined}
    >
      <div className="w-11 h-11 rounded-full flex items-center justify-center shrink-0"
        style={{ background: `${color}18`, border: `1px solid ${color}30` }}>
        <Icon size={20} style={{ color }} />
      </div>
      <div>
        {loading ? (
          <div className="h-7 w-10 bg-white/10 rounded animate-pulse mb-1" />
        ) : (
          <p className="text-2xl font-bold font-mono" style={{ color }}>{value}</p>
        )}
        <p className="text-xs text-muted">{label}</p>
      </div>
    </motion.div>
  )
}

// ── Patient Row Card ───────────────────────────────────────────────────────────

function PatientRowCard({ patient, pred, onSelect }) {
  const age = patient.age ?? calcAge(patient.dob)
  const stage = pred?.stage
  const glow = stage ? STAGE_GLOW[stage] : undefined

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      whileHover={{
        scale: 1.008,
        boxShadow: glow
          ? `0 6px 32px rgba(0,0,0,0.45), 0 0 0 1px ${stage ? STAGE_COLOR_HEX[stage] + '30' : 'rgba(129,140,248,0.25)'}, inset 0 1px 0 rgba(255,255,255,0.12)`
          : '0 6px 32px rgba(0,0,0,0.45), 0 0 0 1px rgba(129,140,248,0.25), inset 0 1px 0 rgba(255,255,255,0.12)',
      }}
      whileTap={{ scale: 0.992 }}
      onClick={onSelect}
      className="card p-4 cursor-pointer flex items-center gap-4 transition-all duration-200"
    >
      {/* Avatar with stage glow */}
      <div className="w-10 h-10 rounded-full flex items-center justify-center shrink-0"
        style={{
          background: stage ? `${STAGE_COLOR_HEX[stage]}18` : 'rgba(129,140,248,0.15)',
          border: `1.5px solid ${stage ? STAGE_COLOR_HEX[stage] + '40' : 'rgba(129,140,248,0.25)'}`,
          boxShadow: glow ? `0 0 10px ${glow}` : undefined,
        }}>
        <Users size={16} style={{ color: stage ? STAGE_COLOR_HEX[stage] : '#818cf8' }} />
      </div>

      {/* Name + ID */}
      <div className="flex-1 min-w-0">
        <p className="font-medium text-white text-sm truncate">{patient.name}</p>
        <p className="text-xs text-muted font-mono">{patient.patient_id}</p>
      </div>

      {/* Age + gender */}
      <div className="text-xs text-muted text-center hidden sm:block">
        <p className="text-white/70">{age != null ? `${age} yr` : '—'}</p>
        <p>{patient.gender}</p>
      </div>

      {/* Last prediction */}
      <div className="text-xs text-right hidden md:block min-w-[90px]">
        {pred ? (
          <>
            <p className="text-white/50">{relativeTime(pred.run_date)}</p>
            <p className="text-muted">CI {pred.cognitive_index != null ? Number(pred.cognitive_index).toFixed(0) : '—'}</p>
          </>
        ) : (
          <p className="text-muted italic">No prediction</p>
        )}
      </div>

      {/* Stage badge */}
      <div className="shrink-0">
        {stage ? <Badge stage={stage} /> : (
          <span className="text-xs text-muted/60 italic">Pending</span>
        )}
      </div>
    </motion.div>
  )
}

// ── Custom Pie tooltip ─────────────────────────────────────────────────────────

function PieTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const { name, value } = payload[0]
  return (
    <div className="px-3 py-2 rounded-lg text-xs"
      style={{ background: 'rgba(6,11,23,0.9)', border: '1px solid rgba(255,255,255,0.1)', backdropFilter: 'blur(16px)' }}>
      <span style={{ color: STAGE_PIE_COLOR[name] }}>{name}</span>
      <span className="text-white ml-2 font-mono font-semibold">{value}</span>
    </div>
  )
}

// ── Dashboard ──────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const navigate = useNavigate()
  const { patients, loading: patientsLoading, refetch: refetchPatients } = usePatients()
  const setCurrentPatient = usePatientStore((s) => s.setCurrentPatient)
  const [showForm, setShowForm] = useState(false)
  const [predLookup, setPredLookup] = useState({})   // patient_id → prediction object
  const [stagesLoading, setStagesLoading] = useState(false)
  const [refreshCount, setRefreshCount] = useState(0)

  // Parallel fetch of latest predictions for all patients
  const fetchAllPredictions = useCallback(async (pts) => {
    if (!pts.length) return
    setStagesLoading(true)
    const settled = await Promise.allSettled(
      pts.map((p) =>
        getLatestPrediction(p.patient_id).then((pred) => ({ patientId: p.patient_id, pred }))
      )
    )
    const lookup = {}
    settled.forEach((r) => {
      if (r.status === 'fulfilled') lookup[r.value.patientId] = r.value.pred
    })
    setPredLookup(lookup)
    setStagesLoading(false)
  }, [])

  // Re-fetch whenever patients list changes OR a manual refresh is triggered
  useEffect(() => {
    if (patients.length > 0) fetchAllPredictions(patients)
  }, [patients, refreshCount, fetchAllPredictions])

  const handleRefresh = () => {
    refetchPatients()
    setRefreshCount((c) => c + 1)
  }

  // ── Stats ──────────────────────────────────────────────────────────────────
  const stageCounts = {
    AD:      Object.values(predLookup).filter((p) => p.stage === 'AD').length,
    MCI:     Object.values(predLookup).filter((p) => p.stage === 'MCI').length,
    Normal:  Object.values(predLookup).filter((p) => p.stage === 'Normal').length,
    Pending: patients.length - Object.keys(predLookup).length,
  }

  const chartData = Object.entries(stageCounts)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }))

  // Sort patients: those with predictions first (by recency), then pending
  const sortedPatients = [...patients].sort((a, b) => {
    const pa = predLookup[a.patient_id], pb = predLookup[b.patient_id]
    if (pa && !pb) return -1
    if (!pa && pb) return 1
    if (pa && pb) {
      return new Date(pb.run_date || 0) - new Date(pa.run_date || 0)
    }
    return 0
  })

  const handlePatientSelect = (patient) => {
    setCurrentPatient(patient)
    navigate(`/patient/${patient.patient_id}`)
  }

  const totalLoading = patientsLoading || stagesLoading

  return (
    <PageWrapper>
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <Brain size={22} className="text-aurora-indigo"
              style={{ filter: 'drop-shadow(0 0 8px rgba(129,140,248,0.6))' }} />
            <h1 className="text-2xl font-bold text-white tracking-tight"
              style={{ textShadow: '0 0 30px rgba(129,140,248,0.3)' }}>
              NeuroScan AI
            </h1>
          </div>
          <p className="text-sm text-muted">
            {patients.length} patient{patients.length !== 1 ? 's' : ''} registered
            {totalLoading && <span className="ml-2 text-aurora-indigo/70">· syncing…</span>}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <motion.button
            whileTap={{ scale: 0.94 }}
            onClick={handleRefresh}
            disabled={totalLoading}
            className="p-2 rounded-btn text-muted hover:text-white transition-colors disabled:opacity-40"
            style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', backdropFilter: 'blur(12px)' }}
          >
            <RefreshCw size={16} className={totalLoading ? 'animate-spin' : ''} />
          </motion.button>
          <Button onClick={() => setShowForm(true)}>
            <Plus size={16} /> New Patient
          </Button>
        </div>
      </div>

      {/* ── Stat Cards ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Patients"     value={patients.length}    icon={Users}        color="#818cf8"  loading={patientsLoading} />
        <StatCard label="Alzheimer's (AD)"   value={stageCounts.AD}     icon={AlertTriangle} color="#f87171" glow="rgba(248,113,113,0.2)"  loading={stagesLoading} />
        <StatCard label="Mild Cognitive (MCI)" value={stageCounts.MCI}  icon={Activity}      color="#fbbf24" glow="rgba(251,191,36,0.2)"   loading={stagesLoading} />
        <StatCard label="Normal / Healthy"   value={stageCounts.Normal} icon={CheckCircle}   color="#34d399" glow="rgba(52,211,153,0.2)"  loading={stagesLoading} />
      </div>

      {/* ── Main content row ────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">

        {/* Stage distribution donut ─────────────────────────────────────── */}
        <div className="card p-5 flex flex-col">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={15} className="text-aurora-indigo" />
            <h2 className="text-sm font-semibold text-white/80">Stage Distribution</h2>
          </div>

          {chartData.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-muted text-xs">
              <Zap size={28} className="mb-2 opacity-20" />
              Run predictions to see distribution
            </div>
          ) : (
            <>
              <div className="flex-1 h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={chartData}
                      cx="50%" cy="50%"
                      innerRadius={44} outerRadius={68}
                      paddingAngle={3}
                      dataKey="value"
                      stroke="none"
                    >
                      {chartData.map(({ name }) => (
                        <Cell key={name} fill={STAGE_PIE_COLOR[name]}
                          style={{ filter: `drop-shadow(0 0 6px ${STAGE_PIE_COLOR[name]}66)` }} />
                      ))}
                    </Pie>
                    <Tooltip content={<PieTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex flex-wrap gap-3 justify-center mt-3">
                {chartData.map(({ name, value }) => (
                  <span key={name} className="flex items-center gap-1.5 text-xs text-white/70">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: STAGE_PIE_COLOR[name] }} />
                    {name} <span className="font-mono font-semibold text-white">{value}</span>
                  </span>
                ))}
              </div>
            </>
          )}
        </div>

        {/* System status card ───────────────────────────────────────────── */}
        <div className="card p-5 flex flex-col gap-3">
          <div className="flex items-center gap-2 mb-1">
            <Zap size={15} className="text-aurora-cyan" />
            <h2 className="text-sm font-semibold text-white/80">Pipeline Status</h2>
          </div>

          {[
            { label: 'MRI Upload', detail: 'GAN synthesis ready', color: '#34d399' },
            { label: 'Cognitive Test', detail: 'Foil-gated SDT scorer', color: '#818cf8' },
            { label: 'AI Classifier', detail: '1058-dim MLP · OASIS', color: '#22d3ee' },
            { label: 'PDF Report', detail: 'ReportLab generator', color: '#fbbf24' },
            { label: 'Digital Twin', detail: '3D neuron viz + timeline', color: '#f472b6' },
          ].map(({ label, detail, color }) => (
            <div key={label} className="flex items-center gap-3">
              <span className="w-2 h-2 rounded-full shrink-0 animate-pulse"
                style={{ background: color, boxShadow: `0 0 6px ${color}` }} />
              <div>
                <p className="text-xs font-medium text-white/80">{label}</p>
                <p className="text-xs text-muted">{detail}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Quick stats ─────────────────────────────────────────────────── */}
        <div className="card p-5 flex flex-col gap-3">
          <div className="flex items-center gap-2 mb-1">
            <Activity size={15} className="text-aurora-pink" />
            <h2 className="text-sm font-semibold text-white/80">Cohort Summary</h2>
          </div>

          {[
            { label: 'Diagnosed', value: Object.keys(predLookup).length, sub: `of ${patients.length} patients`, color: '#818cf8' },
            { label: 'Pending Prediction', value: stageCounts.Pending, sub: 'awaiting analysis', color: '#6b7280' },
            {
              label: 'AD + MCI Combined',
              value: stageCounts.AD + stageCounts.MCI,
              sub: patients.length ? `${Math.round(((stageCounts.AD + stageCounts.MCI) / Math.max(patients.length, 1)) * 100)}% of cohort` : '—',
              color: '#f87171',
            },
          ].map(({ label, value, sub, color }) => (
            <div key={label} className="flex items-center justify-between rounded-lg px-3 py-2.5"
              style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }}>
              <div>
                <p className="text-xs text-muted">{label}</p>
                <p className="text-xs text-white/50">{sub}</p>
              </div>
              <p className="text-xl font-bold font-mono" style={{ color }}>{stagesLoading ? '…' : value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Patient list ────────────────────────────────────────────────── */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Users size={15} className="text-aurora-indigo" />
            <h2 className="text-sm font-semibold text-white/80">Patients</h2>
            {stageCounts.Pending > 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full font-mono"
                style={{ background: 'rgba(107,114,128,0.15)', border: '1px solid rgba(107,114,128,0.25)', color: '#9ca3af' }}>
                {stageCounts.Pending} pending
              </span>
            )}
          </div>
          {stagesLoading && <Spinner size="sm" />}
        </div>

        {patientsLoading ? (
          <div className="flex justify-center py-12"><Spinner size="lg" /></div>
        ) : sortedPatients.length === 0 ? (
          <div className="text-center py-12 text-muted">
            <Brain size={38} className="mx-auto mb-4 opacity-20" />
            <p className="text-sm">No patients yet. Click <strong className="text-white/70">New Patient</strong> to begin.</p>
          </div>
        ) : (
          <AnimatePresence>
            <div className="space-y-2">
              {sortedPatients.map((p, i) => (
                <motion.div key={p.patient_id} transition={{ delay: i * 0.04 }}>
                  <PatientRowCard
                    patient={p}
                    pred={predLookup[p.patient_id]}
                    onSelect={() => handlePatientSelect(p)}
                  />
                </motion.div>
              ))}
            </div>
          </AnimatePresence>
        )}
      </div>

      {/* ── New Patient modal ──────────────────────────────────────────── */}
      <Modal open={showForm} onClose={() => setShowForm(false)} title="New Patient">
        <PatientForm
          onSuccess={(p) => {
            setShowForm(false)
            refetchPatients()
            navigate(`/patient/${p.patient_id}`)
          }}
        />
      </Modal>
    </PageWrapper>
  )
}
