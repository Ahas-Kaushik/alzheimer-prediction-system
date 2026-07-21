import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Brain, Download, ChevronDown, ChevronUp, Pill, BookOpen,
  Activity, CheckCircle, XCircle, ArrowRight,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import PageWrapper from '../components/layout/PageWrapper'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'
import StageIndicator from '../components/prediction/StageIndicator'
import PipelinePlayer from '../components/prediction/PipelinePlayer'
import ConfidenceBar from '../components/prediction/ConfidenceBar'
import ClinicalSummary from '../components/prediction/ClinicalSummary'
import ClinicalDataForm from '../components/prediction/ClinicalDataForm'
import { usePrediction } from '../hooks/usePrediction'
import { getAllScans } from '../api/scanApi'
import axiosClient from '../api/axiosClient'

function toImageUrl(filePath) {
  if (!filePath) return null
  const norm = filePath.replace(/\\/g, '/')
  if (norm.startsWith('http')) return norm
  return `http://localhost:8000/uploads/${norm.replace(/^.*uploads\//, '')}`
}

const STAGE_COLORS = { Normal: '#22c55e', MCI: '#f59e0b', AD: '#ef4444' }

// ── Pre-flight checklist ──────────────────────────────────────────────────────

function CheckRow({ label, description, checked, navigateTo, navigate }) {
  return (
    <div className={`flex items-start gap-3 rounded-lg border px-4 py-3 ${
      checked ? 'border-green-800/40 bg-green-950/20' : 'border-border bg-surface'
    }`}>
      {checked
        ? <CheckCircle size={18} className="text-green-400 mt-0.5 shrink-0" />
        : <XCircle size={18} className="text-red-400 mt-0.5 shrink-0" />}
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium ${checked ? 'text-green-300' : 'text-white'}`}>{label}</p>
        <p className="text-xs text-muted mt-0.5">{description}</p>
      </div>
      {!checked && navigateTo && (
        <Button size="sm" variant="ghost" onClick={() => navigate(navigateTo)}>
          Go <ArrowRight size={12} />
        </Button>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function PredictionResult() {
  const { id: patientId } = useParams()
  const navigate = useNavigate()
  const { latestPrediction, loading, error, run, fetchLatest } = usePrediction(patientId)

  const [running, setRunning] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [runError, setRunError] = useState(null)
  const [downloadError, setDownloadError] = useState(null)

  // Supplementary data
  const [medications, setMedications] = useState([])
  const [medsLoading, setMedsLoading] = useState(false)
  const [evidenceSources, setEvidenceSources] = useState([])
  const [imgTab, setImgTab] = useState('mri')

  // Pre-flight checklist state
  const [hasMRI, setHasMRI] = useState(false)
  const [hasClinical, setHasClinical] = useState(false)
  const [hasCognitive, setHasCognitive] = useState(false)
  const [checksDone, setChecksDone] = useState(false)

  // ── load latest prediction ──────────────────────────────────────────────────
  useEffect(() => { fetchLatest() }, [fetchLatest])

  // ── pre-flight checks ───────────────────────────────────────────────────────
  const runChecks = useCallback(async () => {
    try {
      const scans = await getAllScans(patientId)
      setHasMRI(scans.length > 0)
    } catch { setHasMRI(false) }

    try {
      const saved = localStorage.getItem(`clinical_data_${patientId}`)
      setHasClinical(!!saved && Object.keys(JSON.parse(saved)).length > 0)
    } catch { setHasClinical(false) }

    try {
      const history = await axiosClient.get(`/cognitive/history/${patientId}`)
      setHasCognitive((history.data || []).length > 0)
    } catch { setHasCognitive(false) }

    setChecksDone(true)
  }, [patientId])

  // Run checks on every mount and whenever the patient changes.
  // Do NOT gate on latestPrediction — if the user completes the cognitive test and
  // comes back here, latestPrediction hasn't changed so the old effect wouldn't re-fire.
  useEffect(() => { runChecks() }, [runChecks]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── fetch meds + evidence after prediction ─────────────────────────────────
  useEffect(() => {
    if (!latestPrediction) return
    setMedsLoading(true)
    Promise.all([
      axiosClient.get(`/reports/medications/${patientId}`).catch(() => ({ data: [] })),
      axiosClient.get('/reports/evidence-sources').catch(() => ({ data: [] })),
    ]).then(([medsRes, srcRes]) => {
      setMedications(medsRes.data || [])
      setEvidenceSources(srcRes.data || [])
    }).finally(() => setMedsLoading(false))
  }, [patientId, latestPrediction?.pred_id])

  // ── handlers ────────────────────────────────────────────────────────────────
  const handleRun = async (clinicalData = {}) => {
    setRunning(true)
    setRunError(null)
    try {
      await run({ skip_cognitive_test: true, clinical_features: clinicalData })
      setShowForm(false)
    } catch (e) {
      setRunError(e.message || 'Prediction failed. Make sure an MRI scan is uploaded first.')
    } finally {
      // Always drop out of the running state — this unmounts the animation and
      // reveals the results (or the error) immediately.
      setRunning(false)
    }
  }

  const handleDownloadReport = async () => {
    setDownloading(true)
    setDownloadError(null)
    try {
      const resp = await axiosClient.get(`/reports/medical/${patientId}`, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([resp.data], { type: 'application/pdf' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `alzheimer_report_${patientId}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      let msg = 'Failed to generate PDF.'
      if (e.response?.data) {
        try { msg = JSON.parse(await e.response.data.text()).detail || msg } catch {}
      }
      setDownloadError(msg)
    } finally {
      setDownloading(false)
    }
  }

  // ── derived image urls ──────────────────────────────────────────────────────
  const mriUrl = toImageUrl(latestPrediction?.mri_path)
  const petUrl = toImageUrl(latestPrediction?.pet_path)
  const gradcamUrl = toImageUrl(latestPrediction?.gradcam_path)

  const availableTabs = [
    mriUrl && { key: 'mri', label: 'MRI' },
    petUrl && { key: 'pet', label: 'Synthetic PET' },
    gradcamUrl && { key: 'gradcam', label: 'Grad-CAM' },
  ].filter(Boolean)

  // ── render ──────────────────────────────────────────────────────────────────
  return (
    <PageWrapper>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-white">Prediction</h2>
        <div className="flex gap-2">
          {latestPrediction && (
            <>
              <Button variant="ghost" size="sm" onClick={() => setShowForm(f => !f)} disabled={running}>
                {showForm ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                {showForm ? 'Hide Form' : 'Update Clinical Data & Re-run'}
              </Button>
              <Button variant="ghost" size="sm" onClick={handleDownloadReport} disabled={downloading}>
                {downloading ? <Spinner size="sm" /> : <Download size={14} />}
                Download Report
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Errors */}
      {runError && (
        <div className="mb-4 rounded-lg border border-red-800/60 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          <strong>Pipeline error:</strong> {runError}
        </div>
      )}
      {downloadError && (
        <div className="mb-4 rounded-lg border border-orange-800/60 bg-orange-950/30 px-4 py-3 text-sm text-orange-400">
          <strong>Download error:</strong> {downloadError}
        </div>
      )}

      {/* Animated pipeline — background indicator only while the request is in
          flight. It unmounts the instant `running` flips false, so results
          appear immediately without waiting on the animation. */}
      {running && (
        <div className="mb-6">
          <PipelinePlayer />
        </div>
      )}

      {loading && !latestPrediction && !running && (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      )}

      {/* ── No prediction yet: pre-flight checklist ─────────────────────────── */}
      {!latestPrediction && !loading && !running && (
        <div className="space-y-6">
          <Card>
            <h3 className="text-sm font-semibold text-white mb-1">Before Running Prediction</h3>
            <p className="text-xs text-muted mb-4">
              Complete the checklist below. Clinical data and cognitive test are optional but improve accuracy.
            </p>

            {!checksDone ? (
              <div className="flex justify-center py-6"><Spinner size="sm" /></div>
            ) : (
              <div className="space-y-2.5">
                <CheckRow
                  label="Brain MRI Uploaded"
                  description="At least one T1-weighted MRI scan must be uploaded in Tab 1."
                  checked={hasMRI}
                  navigateTo={`/patient/${patientId}/scan`}
                  navigate={navigate}
                />
                <CheckRow
                  label="Clinical & Blood Report Data"
                  description="Blood panel, biomarkers, and risk factors. Optional — improves medication recommendations."
                  checked={hasClinical}
                  navigateTo={null}
                  navigate={navigate}
                />
                <CheckRow
                  label="Cognitive Test Completed"
                  description="Memory and reaction-time test with target/foil discrimination. Scores are automatically factored into the prediction — no extra steps needed after completing it."
                  checked={hasCognitive}
                  navigateTo={`/patient/${patientId}/cognitive`}
                  navigate={navigate}
                />
              </div>
            )}

            {checksDone && (
              <div className="mt-5 pt-4 border-t border-border">
                {!hasMRI ? (
                  <p className="text-sm text-red-400">
                    An MRI scan is required. Please upload one in{' '}
                    <button
                      className="underline text-primary"
                      onClick={() => navigate(`/patient/${patientId}/scan`)}
                    >
                      Tab 1 — Brain MRI Upload
                    </button>.
                  </p>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <button
                        className="text-sm text-primary underline underline-offset-2"
                        onClick={() => setShowForm(f => !f)}
                      >
                        {showForm ? '▲ Hide clinical data form' : '▼ Enter / review clinical data (optional)'}
                      </button>
                      <Button onClick={() => handleRun({})} disabled={running}>
                        {running ? <Spinner size="sm" /> : <Activity size={14} />}
                        Run Prediction
                      </Button>
                    </div>

                    <AnimatePresence>
                      {showForm && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          className="overflow-hidden"
                        >
                          <ClinicalDataForm
                            patientId={patientId}
                            onSubmit={handleRun}
                            disabled={running}
                          />
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ── Re-run form (shown when prediction already exists and user clicks update) */}
      {latestPrediction && (
        <AnimatePresence>
          {showForm && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-6 overflow-hidden"
            >
              <ClinicalDataForm patientId={patientId} onSubmit={handleRun} disabled={running} />
            </motion.div>
          )}
        </AnimatePresence>
      )}

      {/* ── Prediction results ───────────────────────────────────────────────── */}
      {latestPrediction && !running && (
        <motion.div
          className="space-y-6"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        >

          {/* Row 1: Stage ring + Probabilities + Clinical summary */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2">
              <StageIndicator stage={latestPrediction.stage} confidence={latestPrediction.confidence} />
            </Card>
            <div className="space-y-4">
              <Card>
                <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Stage Probabilities</h3>
                <ConfidenceBar probabilities={latestPrediction.probabilities} />
              </Card>
              <Card>
                <ClinicalSummary
                  factors={latestPrediction.contributing_factors}
                  cognitiveIndex={latestPrediction.cognitive_index}
                  ssimScore={latestPrediction.ssim_score}
                />
              </Card>
            </div>
          </div>

          {/* Row 2: Brain Imaging (MRI / Synthetic PET / Grad-CAM) */}
          {availableTabs.length > 0 && (
            <Card>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <Activity size={15} className="text-indigo-400" />
                  Brain Imaging
                </h3>
                <div className="flex gap-1.5">
                  {availableTabs.map(t => (
                    <button
                      key={t.key}
                      onClick={() => setImgTab(t.key)}
                      className={`text-xs px-3 py-1 rounded-full transition-colors ${
                        imgTab === t.key
                          ? 'bg-primary text-white'
                          : 'text-muted hover:text-white border border-border'
                      }`}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex gap-6 items-start">
                <div className="w-56 shrink-0">
                  {imgTab === 'mri' && mriUrl && (
                    <img src={mriUrl} alt="MRI" className="w-full aspect-square object-cover rounded-card border border-border bg-black" />
                  )}
                  {imgTab === 'pet' && petUrl && (
                    <img src={petUrl} alt="Synthetic PET" className="w-full aspect-square object-cover rounded-card border border-border bg-black" />
                  )}
                  {imgTab === 'gradcam' && gradcamUrl && (
                    <img src={gradcamUrl} alt="Grad-CAM" className="w-full aspect-square object-cover rounded-card border border-border bg-black" />
                  )}
                </div>

                <div className="text-sm space-y-3 flex-1">
                  {imgTab === 'mri' && (
                    <>
                      <p className="text-slate-300">T1-weighted structural MRI. ResNet-18 extracts a 512-d feature vector representing structural brain patterns used as primary input to the prediction pipeline.</p>
                      <p className="text-xs text-muted">Grayscale axial slice, 256×256.</p>
                    </>
                  )}
                  {imgTab === 'pet' && (
                    <>
                      <p className="text-slate-300">Physics-based synthetic PET derived from the MRI via tissue classification. Warm colors = higher metabolic activity. Cool/dark = reduced glucose uptake.</p>
                      <p className="text-xs text-muted mt-1">
                        <span className="text-yellow-400 font-medium">Clinical note:</span> Structural approximation only.
                        The prediction is driven by <span className="text-white">MRI features + clinical data + cognitive scores</span>.
                      </p>
                    </>
                  )}
                  {imgTab === 'gradcam' && (
                    <>
                      <p className="text-slate-300">
                        Grad-CAM heatmap showing which brain regions most influenced the{' '}
                        <span className="font-semibold" style={{ color: STAGE_COLORS[latestPrediction.stage] }}>
                          {latestPrediction.stage}
                        </span>{' '}
                        prediction. Red/yellow = high influence.
                      </p>
                      <p className="text-xs text-muted">Gradient-weighted Class Activation Mapping on ResNet-18 layer4, overlaid at 50% opacity on the MRI.</p>
                    </>
                  )}
                </div>
              </div>
            </Card>
          )}

          {/* Row 3: Prescribed Medications */}
          <Card>
            <h3 className="text-sm font-semibold text-white mb-1 flex items-center gap-2">
              <Pill size={15} className="text-violet-400" />
              Prescribed Medications
              <span className="text-xs font-normal text-muted ml-1">(confirm with physician before use)</span>
            </h3>

            {medsLoading ? (
              <div className="flex justify-center py-6"><Spinner size="sm" /></div>
            ) : medications.length === 0 ? (
              <p className="text-xs text-muted py-4">
                No medications determined. Enter clinical data (blood reports, comorbidities) to get personalized recommendations.
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
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
                    <p className="text-xs text-muted"><span className="text-slate-300 font-medium">Dosage:</span> {med.dosage}</p>
                    <p className="text-xs text-muted"><span className="text-slate-300 font-medium">Indication:</span> {med.indication}</p>
                    {med.notes && <p className="text-xs text-slate-500 italic">{med.notes}</p>}
                    {med.contraindications?.length > 0 && (
                      <p className="text-xs text-red-400/80"><span className="font-medium">Contraindications:</span> {med.contraindications.join(', ')}</p>
                    )}
                    {med.monitoring?.length > 0 && (
                      <p className="text-xs text-yellow-400/80"><span className="font-medium">Monitor:</span> {med.monitoring.join(', ')}</p>
                    )}
                  </motion.div>
                ))}
              </div>
            )}
          </Card>

          {/* Row 4: Clinical Evidence Base */}
          {evidenceSources.length > 0 && (
            <Card>
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <BookOpen size={15} className="text-blue-400" />
                Clinical Evidence Base
                <span className="text-xs font-normal text-muted ml-1">— sources backing the medication knowledge graph</span>
              </h3>
              <div className="space-y-2">
                {evidenceSources.map((src, i) => (
                  <motion.div
                    key={src.name}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="flex items-start gap-3 rounded-lg border border-border bg-white/[0.03] px-3 py-2.5"
                  >
                    <span className="text-xs bg-blue-900/40 text-blue-300 px-1.5 py-0.5 rounded font-mono shrink-0 mt-0.5">
                      {src.year}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-white">{src.name}</p>
                      <p className="text-xs text-slate-300 mt-0.5 leading-relaxed">{src.description}</p>
                      <span className="inline-block mt-1 text-xs text-primary/70 bg-primary/10 px-1.5 py-0.5 rounded">{src.type}</span>
                    </div>
                  </motion.div>
                ))}
              </div>
              <p className="text-xs text-muted mt-3 pt-3 border-t border-border">
                All medication rules are derived from the above peer-reviewed guidelines. No AI-generated drug information is used.
                Final prescription must be confirmed by a licensed physician.
              </p>
            </Card>
          )}

          {/* Actions */}
          <Card className="flex flex-wrap gap-3">
            <Button onClick={() => navigate(`/patient/${patientId}/twin`)}>
              <Brain size={14} /> View Digital Twin
            </Button>
            <Button variant="ghost" onClick={handleDownloadReport} disabled={downloading}>
              {downloading ? <Spinner size="sm" /> : <Download size={14} />}
              Download Medical Report (PDF)
            </Button>
            <Button variant="ghost" onClick={() => navigate(`/patient/${patientId}`)}>
              Back to Profile
            </Button>
          </Card>
        </motion.div>
      )}
    </PageWrapper>
  )
}
