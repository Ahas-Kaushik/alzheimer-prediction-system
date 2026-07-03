import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Upload, FlaskConical, BarChart3, Brain, FileText,
  Download, Activity, AlertTriangle, CheckCircle, Info, Pill,
} from 'lucide-react'
import { motion } from 'framer-motion'
import PageWrapper from '../components/layout/PageWrapper'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'
import StageIndicator from '../components/prediction/StageIndicator'
import ConfidenceBar from '../components/prediction/ConfidenceBar'
import AbstractBrainViz from '../components/twin/AbstractBrainViz'
import TimelineChart from '../components/twin/TimelineChart'
import AskAIPanel from '../components/rag/AskAIPanel'
import { usePatient } from '../hooks/usePatient'
import { usePrediction } from '../hooks/usePrediction'
import { useDigitalTwin } from '../hooks/useDigitalTwin'
import axiosClient from '../api/axiosClient'

// ── helpers ────────────────────────────────────────────────────────────────────

function toImageUrl(filePath) {
  if (!filePath) return null
  const norm = filePath.replace(/\\/g, '/')
  if (norm.startsWith('http')) return norm
  return `http://localhost:8000/uploads/${norm.replace(/^.*uploads\//, '')}`
}

const STAGE_COLORS = { Normal: '#22c55e', MCI: '#f59e0b', AD: '#ef4444' }
const STAGE_BG = {
  Normal: 'bg-green-900/20 border border-green-800/40',
  MCI: 'bg-yellow-900/20 border border-yellow-800/40',
  AD: 'bg-red-900/20 border border-red-800/40',
}
const DELTA_ICON = { improved: '↑ Improving', stable: '→ Stable', declined: '↓ Declining' }
const DELTA_COLOR = { improved: 'text-green-400', stable: 'text-slate-400', declined: 'text-red-400' }

function buildReasoning(stage, factors, cognitiveIndex, ssimScore) {
  const context = {
    Normal:
      'No significant biomarker abnormalities or structural changes were identified. Brain metabolism, volume, and cognitive performance all fall within normal limits for the patient\'s age group.',
    MCI:
      'Mild but measurable changes in cognitive biomarkers and/or neuroimaging suggest early-stage neurodegeneration. This is a transitional state — intervention at this point can meaningfully slow progression.',
    AD:
      'Multiple convergent indicators — including neuroimaging atrophy patterns, amyloid/tau burden, and cognitive deficits — are consistent with established Alzheimer\'s Disease pathology. A multidisciplinary care plan is recommended.',
  }
  const factorLine = factors?.length
    ? `The model\'s primary contributing factors were: ${factors.join(', ')}.`
    : 'Clinical features, imaging biomarkers, and cognitive scores were all factored into the decision.'

  const cogLine = cognitiveIndex
    ? ` The cognitive assessment yielded a composite score of ${Number(cognitiveIndex).toFixed(1)}/100.`
    : ''

  const petLine =
    ' PET was synthesized via physics-based tissue classification from the MRI. The classifier was trained without PET data (OASIS), so PET features have minimal weight in the prediction — the decision is driven by MRI features and clinical data.'

  return `${context[stage] || ''} ${factorLine}${cogLine}${petLine}`
}

function RiskBadge({ stage }) {
  if (stage === 'Normal') return <span className="flex items-center gap-1 text-xs text-green-400"><CheckCircle size={12} /> Low Risk</span>
  if (stage === 'MCI') return <span className="flex items-center gap-1 text-xs text-yellow-400"><AlertTriangle size={12} /> Moderate Risk</span>
  return <span className="flex items-center gap-1 text-xs text-red-400"><AlertTriangle size={12} /> High Risk</span>
}

// ── component ──────────────────────────────────────────────────────────────────

export default function PatientProfile() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { patient, loading: patientLoading } = usePatient(id)
  const { latestPrediction, predictionHistory, fetchLatest, fetchHistory } = usePrediction(id)
  const { twinData, fetchTwin } = useDigitalTwin(id)
  const [downloading, setDownloading] = useState(false)
  const [imgTab, setImgTab] = useState('pet') // 'mri' | 'pet'
  const [medications, setMedications] = useState([])
  const [medsLoading, setMedsLoading] = useState(false)

  useEffect(() => {
    fetchLatest()
    fetchHistory()
    fetchTwin()
  }, [fetchLatest, fetchHistory, fetchTwin])

  // Fetch medications whenever a prediction exists
  useEffect(() => {
    if (!latestPrediction) return
    setMedsLoading(true)
    axiosClient.get(`/reports/medications/${id}`)
      .then((r) => setMedications(r.data || []))
      .catch(() => setMedications([]))
      .finally(() => setMedsLoading(false))
  }, [id, latestPrediction?.pred_id])

  const petUrl = useMemo(() => toImageUrl(latestPrediction?.pet_path), [latestPrediction?.pet_path])
  const mriUrl = useMemo(() => toImageUrl(latestPrediction?.mri_path), [latestPrediction?.mri_path])

  const longitudinalAlert = useMemo(() => {
    if (predictionHistory.length < 2) return null
    const sorted = [...predictionHistory].sort((a, b) => new Date(a.run_date) - new Date(b.run_date))
    const last = sorted[sorted.length - 1]
    const prev = sorted[sorted.length - 2]
    const lastCI = last.cognitive_index != null ? Number(last.cognitive_index) : null
    const prevCI = prev.cognitive_index != null ? Number(prev.cognitive_index) : null
    if (lastCI !== null && prevCI !== null && prevCI - lastCI > 15) {
      return { drop: (prevCI - lastCI).toFixed(1), from: prevCI.toFixed(1), to: lastCI.toFixed(1) }
    }
    return null
  }, [predictionHistory])

  const factors = useMemo(() => {
    try {
      const raw = latestPrediction?.contributing_factors
      if (!raw) return []
      if (Array.isArray(raw)) return raw
      return JSON.parse(raw.replace(/'/g, '"'))
    } catch { return [] }
  }, [latestPrediction?.contributing_factors])

  const reasoning = useMemo(() => {
    if (!latestPrediction) return null
    return buildReasoning(
      latestPrediction.stage,
      factors,
      latestPrediction.cognitive_index,
      latestPrediction.ssim_score,
    )
  }, [latestPrediction, factors])

  const handleDownloadReport = async () => {
    setDownloading(true)
    try {
      const resp = await axiosClient.get(`/reports/medical/${id}`, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([resp.data], { type: 'application/pdf' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `alzheimer_report_${id}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('Report generation failed. Run a prediction first.')
    } finally {
      setDownloading(false)
    }
  }

  if (patientLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>
  if (!patient) return <div className="text-center py-20 text-muted">Patient not found.</div>

  const dob = patient.dob ? new Date(patient.dob) : null
  const age = dob ? Math.floor((Date.now() - dob.getTime()) / 3.156e10) : patient.age

  const quickActions = [
    { label: 'Upload Brain MRI', icon: Upload, path: `/patient/${id}/scan` },
    { label: 'MRI → PET', icon: Activity, path: `/patient/${id}/mri-to-pet` },
    { label: 'Blood Reports', icon: FileText, path: `/patient/${id}/reports` },
    { label: 'Cognitive Test', icon: FlaskConical, path: `/patient/${id}/cognitive` },
    { label: 'Run Prediction', icon: BarChart3, path: `/patient/${id}/prediction` },
    { label: 'Digital Twin', icon: Brain, path: `/patient/${id}/twin` },
  ]

  return (
    <PageWrapper>

      {/* ── Patient header ─────────────────────────────────────────────────── */}
      <Card className="mb-5">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h2 className="text-2xl font-bold text-white">{patient.name}</h2>
            <p className="text-xs font-mono text-muted mt-0.5">{patient.patient_id}</p>
            <p className="text-sm text-muted mt-1">
              {age ? `Age ${age}` : ''}
              {patient.gender ? ` · ${patient.gender}` : ''}
              {dob ? ` · DOB ${dob.toLocaleDateString()}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            {latestPrediction && (
              <>
                <Badge stage={latestPrediction.stage} />
                <RiskBadge stage={latestPrediction.stage} />
              </>
            )}
            <Button
              size="sm"
              onClick={handleDownloadReport}
              disabled={downloading || !latestPrediction}
            >
              {downloading ? <Spinner size="sm" /> : <Download size={14} />}
              Download Report (PDF)
            </Button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-border">
          {quickActions.map(({ label, icon: Icon, path }) => (
            <Button key={label} variant="ghost" size="sm" onClick={() => navigate(path)}>
              <Icon size={13} /> {label}
            </Button>
          ))}
        </div>
      </Card>

      {/* ── Longitudinal deterioration alert ──────────────────────────────── */}
      {longitudinalAlert && (
        <div className="mb-5 rounded-lg border border-red-700/60 bg-red-950/40 px-4 py-3 flex items-start gap-3">
          <AlertTriangle size={18} className="text-red-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-red-300">
              Significant Cognitive Decline Detected
            </p>
            <p className="text-xs text-red-400/80 mt-0.5">
              Cognitive index dropped <span className="font-mono font-bold">{longitudinalAlert.drop} points</span> between
              the last two assessments ({longitudinalAlert.from} → {longitudinalAlert.to}).
              A drop of &gt;15 points warrants urgent clinical review.
            </p>
          </div>
        </div>
      )}

      {/* ── No prediction state ────────────────────────────────────────────── */}
      {!latestPrediction && (
        <Card className="text-center py-12">
          <Brain size={40} className="mx-auto text-muted mb-3" />
          <p className="text-muted mb-4">No prediction run yet. Upload an MRI scan and run the pipeline.</p>
          <div className="flex justify-center gap-3 flex-wrap">
            <Button onClick={() => navigate(`/patient/${id}/scan`)}>Upload Brain MRI</Button>
            <Button variant="ghost" onClick={() => navigate(`/patient/${id}/prediction`)}>Run Prediction</Button>
          </div>
        </Card>
      )}

      {latestPrediction && (
        <>
          {/* ── Row 1: Stage + Probabilities + Images ──────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-5">

            {/* Stage ring */}
            <Card className="flex flex-col items-center justify-center">
              <StageIndicator
                stage={latestPrediction.stage}
                confidence={latestPrediction.confidence}
              />
              <p className="text-xs text-muted text-center mt-2">
                Last run: {new Date(latestPrediction.run_date).toLocaleString()}
              </p>
              {latestPrediction.cognitive_index && (
                <p className="text-xs text-muted text-center mt-1">
                  Cognitive Index: <span className="font-mono text-white">{Number(latestPrediction.cognitive_index).toFixed(1)}/100</span>
                </p>
              )}
            </Card>

            {/* Stage probabilities */}
            <Card>
              <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-4">Stage Probabilities</h3>
              <ConfidenceBar probabilities={latestPrediction.probabilities} />
              <div className="mt-4 pt-4 border-t border-border space-y-1.5">
                {factors.map((f) => (
                  <div key={f} className="flex items-center gap-2 text-xs">
                    <div
                      className="w-1.5 h-1.5 rounded-full shrink-0"
                      style={{ background: STAGE_COLORS[latestPrediction.stage] }}
                    />
                    <span className="text-muted">{f}</span>
                  </div>
                ))}
                {factors.length === 0 && (
                  <p className="text-xs text-muted italic">Run a prediction to see contributing factors.</p>
                )}
              </div>
            </Card>

            {/* Brain scans */}
            <Card>
              <div className="flex gap-2 mb-3">
                <button
                  onClick={() => setImgTab('pet')}
                  className={`text-xs px-2.5 py-1 rounded ${imgTab === 'pet' ? 'bg-accent text-white' : 'text-muted hover:text-white'}`}
                >
                  Synthetic PET
                </button>
                <button
                  onClick={() => setImgTab('mri')}
                  className={`text-xs px-2.5 py-1 rounded ${imgTab === 'mri' ? 'bg-accent text-white' : 'text-muted hover:text-white'}`}
                >
                  MRI
                </button>
              </div>
              <div className="aspect-square w-full bg-black/40 rounded-lg overflow-hidden flex items-center justify-center">
                {imgTab === 'pet' && petUrl ? (
                  <img src={petUrl} alt="Synthetic PET" className="w-full h-full object-contain" />
                ) : imgTab === 'mri' && mriUrl ? (
                  <img src={mriUrl} alt="MRI" className="w-full h-full object-contain" />
                ) : (
                  <p className="text-xs text-muted">
                    {imgTab === 'pet' ? 'PET not generated yet' : 'MRI not uploaded yet'}
                  </p>
                )}
              </div>
              <p className="text-xs text-muted mt-2 text-center">
                Physics-based approximation · visual indicator only
                {latestPrediction.ssim_score && Number(latestPrediction.ssim_score) > 0 && (
                  <span className="ml-2 font-mono text-white">SSIM {Number(latestPrediction.ssim_score).toFixed(3)}</span>
                )}
              </p>
            </Card>
          </div>

          {/* ── Row 2: Reasoning + Digital Twin ────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">

            {/* Clinical reasoning */}
            <Card>
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Info size={15} className="text-blue-400" />
                Clinical Reasoning
              </h3>
              <div className={`rounded-lg p-4 text-sm leading-relaxed ${STAGE_BG[latestPrediction.stage] || ''}`}>
                <span className="font-semibold" style={{ color: STAGE_COLORS[latestPrediction.stage] }}>
                  {latestPrediction.stage}
                </span>
                {' — '}
                <span className="text-slate-300">{reasoning}</span>
              </div>

              {/* Factor breakdown */}
              {factors.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs text-muted uppercase tracking-wider mb-2 font-semibold">Top Contributing Factors</p>
                  <div className="space-y-2">
                    {factors.map((f, i) => (
                      <motion.div
                        key={f}
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.08 }}
                        className="flex items-center gap-3 text-xs"
                      >
                        <div
                          className="w-6 h-6 rounded-full flex items-center justify-center text-white font-bold shrink-0"
                          style={{ background: STAGE_COLORS[latestPrediction.stage] }}
                        >
                          {i + 1}
                        </div>
                        <span className="text-slate-200">{f}</span>
                      </motion.div>
                    ))}
                  </div>
                </div>
              )}

              {/* Cognitive index bar */}
              {latestPrediction.cognitive_index && (
                <div className="mt-4 pt-4 border-t border-border">
                  <p className="text-xs text-muted mb-1.5">Cognitive Index</p>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-2 bg-border rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${Number(latestPrediction.cognitive_index)}%` }}
                        transition={{ duration: 0.8, ease: 'easeOut' }}
                        className="h-full rounded-full"
                        style={{ background: STAGE_COLORS[latestPrediction.stage] }}
                      />
                    </div>
                    <span className="font-mono text-xs text-white shrink-0">
                      {Number(latestPrediction.cognitive_index).toFixed(1)}/100
                    </span>
                  </div>
                </div>
              )}
            </Card>

            {/* Digital Twin mini-view */}
            <Card>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-white">Digital Brain Twin</h3>
                {twinData && (
                  <span className={`text-xs font-semibold ${DELTA_COLOR[twinData.delta_from_last]}`}>
                    {DELTA_ICON[twinData.delta_from_last]}
                  </span>
                )}
              </div>
              {twinData ? (
                <>
                  <AbstractBrainViz
                    regions={twinData.regions}
                    connectivity={twinData.neuron_connectivity}
                  />
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    {twinData.regions?.slice(0, 4).map((r) => (
                      <div key={r.name} className="text-xs">
                        <span className="text-muted block truncate">{r.name}</span>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <div className="flex-1 h-1 bg-border rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${r.severity * 100}%`,
                                background: { Normal: '#22c55e', MCI: '#f59e0b', AD: '#ef4444' }[r.status],
                              }}
                            />
                          </div>
                          <span className="font-mono text-white w-6 text-right">
                            {(r.severity * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full mt-3"
                    onClick={() => navigate(`/patient/${id}/twin`)}
                  >
                    <Brain size={13} /> Full Twin View
                  </Button>
                </>
              ) : (
                <div className="py-8 text-center text-muted text-sm">
                  Digital twin not generated yet.
                  <br />
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-3"
                    onClick={() => navigate(`/patient/${id}/prediction`)}
                  >
                    Run Prediction
                  </Button>
                </div>
              )}
            </Card>
          </div>

          {/* ── Row 3: Cognitive history chart ─────────────────────────────── */}
          <Card>
            <h3 className="text-sm font-semibold text-white mb-1 flex items-center gap-2">
              <Activity size={15} className="text-indigo-400" />
              Cognitive Memory History
            </h3>
            <p className="text-xs text-muted mb-3">
              Composite cognitive index over prediction runs. Green band = Normal (75-100), Yellow = MCI (45-75), Red = AD (0-45).
            </p>
            <TimelineChart
              data={predictionHistory.map((p) => ({
                visit_date: p.run_date,
                cognitive_index: p.cognitive_index ? Number(p.cognitive_index) : null,
              }))}
            />
            {predictionHistory.length > 1 && (
              <div className="overflow-x-auto mt-4 pt-4 border-t border-border">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-muted border-b border-border">
                      <th className="text-left py-1.5 pr-4">Date</th>
                      <th className="text-left py-1.5 pr-4">Stage</th>
                      <th className="text-left py-1.5 pr-4">Confidence</th>
                      <th className="text-left py-1.5">Cognitive Index</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...predictionHistory].reverse().map((p) => (
                      <tr key={p.pred_id} className="border-b border-border/40 hover:bg-white/5">
                        <td className="py-1.5 pr-4 font-mono text-muted">
                          {new Date(p.run_date).toLocaleDateString()}
                        </td>
                        <td className="py-1.5 pr-4 font-semibold" style={{ color: STAGE_COLORS[p.stage] }}>
                          {p.stage}
                        </td>
                        <td className="py-1.5 pr-4 font-mono text-white">
                          {(Number(p.confidence) * 100).toFixed(1)}%
                        </td>
                        <td className="py-1.5 font-mono text-white">
                          {p.cognitive_index ? Number(p.cognitive_index).toFixed(1) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {/* ── Row 4: Medications ──────────────────────────────────────────── */}
          <Card>
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Pill size={15} className="text-violet-400" />
              Recommended Medications
              <span className="text-xs font-normal text-muted ml-1">
                (evidence-based, confirm with physician)
              </span>
            </h3>

            {medsLoading ? (
              <div className="flex justify-center py-6"><Spinner size="sm" /></div>
            ) : medications.length === 0 ? (
              <p className="text-xs text-muted py-4 text-center">
                No medications determined yet — enter blood report data and run the prediction pipeline.
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {medications.map((med, i) => (
                  <motion.div
                    key={med.name}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.06 }}
                    className="rounded-lg border border-border bg-surface p-3 space-y-1.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-semibold text-sm text-white">{med.name}</p>
                      <span className="text-xs text-violet-400 bg-violet-900/30 px-2 py-0.5 rounded-full shrink-0">
                        {med.drug_class}
                      </span>
                    </div>
                    <p className="text-xs text-muted">
                      <span className="text-slate-300 font-medium">Dosage:</span> {med.dosage}
                    </p>
                    <p className="text-xs text-muted">
                      <span className="text-slate-300 font-medium">Indication:</span> {med.indication}
                    </p>
                    {med.notes && (
                      <p className="text-xs text-slate-500 italic">{med.notes}</p>
                    )}
                    {med.contraindications?.length > 0 && (
                      <p className="text-xs text-red-400/80">
                        <span className="font-medium">Contraindications:</span> {med.contraindications.join(', ')}
                      </p>
                    )}
                    {med.monitoring?.length > 0 && (
                      <p className="text-xs text-yellow-400/80">
                        <span className="font-medium">Monitor:</span> {med.monitoring.join(', ')}
                      </p>
                    )}
                  </motion.div>
                ))}
              </div>
            )}
          </Card>

          {/* ── Ask AI (GraphRAG) ───────────────────────────────────────────── */}
          <div className="mt-5">
            <AskAIPanel patientId={id} />
          </div>

          {/* ── Actions footer ──────────────────────────────────────────────── */}
          <Card className="mt-5 flex flex-wrap gap-3">
            <Button onClick={handleDownloadReport} disabled={downloading}>
              {downloading ? <Spinner size="sm" /> : <Download size={14} />}
              Download Medical Report (PDF)
            </Button>
            <Button variant="ghost" onClick={() => navigate(`/patient/${id}/prediction`)}>
              <BarChart3 size={14} /> Re-run Prediction
            </Button>
            <Button variant="ghost" onClick={() => navigate(`/patient/${id}/twin`)}>
              <Brain size={14} /> Full Digital Twin
            </Button>
          </Card>
        </>
      )}
    </PageWrapper>
  )
}
