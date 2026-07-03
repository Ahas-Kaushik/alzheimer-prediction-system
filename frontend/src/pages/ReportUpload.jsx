/**
 * Blood Reports upload page — hybrid OCR pre-fill + full manual form.
 *
 * Matches Project Knowledge spec: user uploads a printed blood report image/PDF,
 * backend OCR extracts recognisable fields, form shows ALL fields with
 * extracted values pre-filled, empty slots remain for manual entry.
 */
import { useCallback, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { FileText, Check, Upload, Info, ChevronDown, ChevronUp } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import PageWrapper from '../components/layout/PageWrapper'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'
import axiosClient from '../api/axiosClient'

// Reuse field definitions from ClinicalDataForm (same schema)
const FIELD_DEFS = [
  { key: 'age', label: 'Age (years)', type: 'number', placeholder: 'e.g. 72', group: 'Demographics' },
  { key: 'education_years', label: 'Education (years)', type: 'number', placeholder: 'e.g. 16', group: 'Demographics' },
  { key: 'gender', label: 'Gender', type: 'select', options: ['', 'male', 'female', 'other'], group: 'Demographics' },
  { key: 'mmse_score', label: 'MMSE Score (0–30)', type: 'number', placeholder: 'e.g. 24', group: 'Cognitive' },
  { key: 'moca_score', label: 'MoCA Score (0–30)', type: 'number', placeholder: 'e.g. 22', group: 'Cognitive' },
  { key: 'cdr_score', label: 'CDR Score', type: 'number', placeholder: '0 / 0.5 / 1 / 2 / 3', group: 'Cognitive' },
  { key: 'amyloid_level', label: 'Amyloid Level (pg/mL)', type: 'number', placeholder: 'e.g. 1800', group: 'Biomarkers' },
  { key: 'tau_level', label: 'Tau (pg/mL)', type: 'number', placeholder: 'e.g. 400', group: 'Biomarkers' },
  { key: 'ptau_level', label: 'pTau (pg/mL)', type: 'number', placeholder: 'e.g. 52', group: 'Biomarkers' },
  { key: 'hemoglobin', label: 'Haemoglobin (g/dL)', type: 'number', placeholder: 'e.g. 13.5', group: 'Blood Panel' },
  { key: 'glucose', label: 'Fasting Glucose (mg/dL)', type: 'number', placeholder: 'e.g. 95', group: 'Blood Panel' },
  { key: 'cholesterol', label: 'Total Cholesterol (mg/dL)', type: 'number', placeholder: 'e.g. 200', group: 'Blood Panel' },
  { key: 'hdl', label: 'HDL Cholesterol (mg/dL)', type: 'number', placeholder: 'e.g. 55', group: 'Blood Panel' },
  { key: 'ldl', label: 'LDL Cholesterol (mg/dL)', type: 'number', placeholder: 'e.g. 120', group: 'Blood Panel' },
  { key: 'triglycerides', label: 'Triglycerides (mg/dL)', type: 'number', placeholder: 'e.g. 150', group: 'Blood Panel' },
  { key: 'vit_b12', label: 'Vitamin B12 (pg/mL)', type: 'number', placeholder: 'e.g. 350', group: 'Blood Panel' },
  { key: 'tsh', label: 'TSH (mIU/L)', type: 'number', placeholder: 'e.g. 2.5', group: 'Blood Panel' },
  { key: 'hippocampal_volume', label: 'Hippocampal Volume (mm³)', type: 'number', placeholder: 'e.g. 3200', group: 'MRI Volumetrics' },
  { key: 'cortical_thickness', label: 'Cortical Thickness (mm)', type: 'number', placeholder: 'e.g. 2.4', group: 'MRI Volumetrics' },
  { key: 'wmh_volume', label: 'WMH Volume (mm³)', type: 'number', placeholder: 'e.g. 500', group: 'MRI Volumetrics' },
  { key: 'apoe4_status', label: 'APOE4 Carrier', type: 'boolean', group: 'Risk Factors' },
  { key: 'smoking', label: 'Smoker', type: 'boolean', group: 'Risk Factors' },
  { key: 'diabetes', label: 'Diabetes', type: 'boolean', group: 'Risk Factors' },
  { key: 'hypertension', label: 'Hypertension', type: 'boolean', group: 'Risk Factors' },
  { key: 'depression', label: 'Depression', type: 'boolean', group: 'Risk Factors' },
  { key: 'family_history_ad', label: 'Family History of AD', type: 'boolean', group: 'Risk Factors' },
]

const GROUPS = [...new Set(FIELD_DEFS.map(f => f.group))]

// The backend OCR parser emits clinical field names (e.g. `glucose_fasting`)
// that differ from this form's field keys (e.g. `glucose`). Map parser keys →
// form keys so every extracted value visibly pre-fills the correct field.
const OCR_KEY_ALIASES = {
  glucose_fasting: 'glucose',
  cholesterol_total: 'cholesterol',
  vitamin_b12: 'vit_b12',
  thyroid_tsh: 'tsh',
  amyloid_beta_42: 'amyloid_level',
  tau_protein: 'tau_level',
  p_tau_181: 'ptau_level',
  smoking_history: 'smoking',
  depression_history: 'depression',
}

export default function ReportUpload() {
  const { id: patientId } = useParams()
  const [ocrFile, setOcrFile] = useState(null)
  const [extracting, setExtracting] = useState(false)
  const [rawTextPreview, setRawTextPreview] = useState(null)
  const [ocrError, setOcrError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  // Initialise from localStorage so returning patients see their previous values.
  const [values, setValues] = useState(() => {
    try {
      const saved = localStorage.getItem(`clinical_data_${patientId}`)
      if (saved) return JSON.parse(saved)
    } catch {}
    return {}
  })
  const [expandedGroups, setExpandedGroups] = useState(new Set(GROUPS))
  const [showRaw, setShowRaw] = useState(false)

  const setField = (key, val) => setValues(prev => ({ ...prev, [key]: val }))

  const onDrop = useCallback((accepted) => {
    if (accepted[0]) {
      setOcrFile(accepted[0])
      setSaved(false)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': [], 'application/pdf': ['.pdf'] },
    maxFiles: 1,
  })

  const handleExtract = async () => {
    if (!ocrFile) return
    setExtracting(true)
    setOcrError(null)
    try {
      const form = new FormData()
      form.append('patient_id', patientId)
      form.append('source_type', 'blood_report')
      form.append('file', ocrFile)
      // OCR on CPU can take ~30s; override the default 60s client timeout.
      const { data } = await axiosClient.post('/reports/upload', form, { timeout: 180000 })
      setRawTextPreview(data.raw_text_preview)
      // Pre-fill only fields that were actually extracted (non-null, non-empty)
      const extracted = data.extracted_fields || {}
      setValues(prev => {
        const merged = { ...prev }
        for (const [k, v] of Object.entries(extracted)) {
          if (v === null || v === '' || v === undefined) continue
          const formKey = OCR_KEY_ALIASES[k] || k
          // Booleans come back as true/false → the form's selects expect 'true'/'false'.
          merged[formKey] = typeof v === 'boolean' ? String(v) : String(v)
        }
        return merged
      })
    } catch (e) {
      setOcrError(e.message || 'OCR failed')
    } finally {
      setExtracting(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await axiosClient.post('/reports/confirm', {
        patient_id: patientId,
        visit_id: 'latest',
        file_path: ocrFile?.name ?? 'manual_entry',
        source_type: 'blood_report',
        confirmed_fields: values,
      })
      // Persist so the Prediction tab and future visits see this data.
      try { localStorage.setItem(`clinical_data_${patientId}`, JSON.stringify(values)) } catch {}
      setSaved(true)
    } catch (e) {
      setOcrError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const toggleGroup = (group) => {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      next.has(group) ? next.delete(group) : next.add(group)
      return next
    })
  }

  const filledCount = FIELD_DEFS.filter(f => values[f.key] !== undefined && values[f.key] !== '').length

  return (
    <PageWrapper>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white">Blood &amp; Clinical Reports</h2>
        <p className="text-sm text-muted mt-1">
          Upload a printed/scanned blood report and the system will auto-extract values.
          Review all fields, fill in any missing data, then save to patient record.
        </p>
      </div>

      {/* Upload + OCR */}
      <Card className="mb-6">
        <div className="flex items-start gap-2 mb-4">
          <Info size={14} className="text-primary mt-0.5 shrink-0" />
          <p className="text-xs text-muted">
            Accepts <span className="text-white">scanned or photographed blood reports</span> (PNG · JPG · PDF).
            The system reads haemoglobin, glucose, lipid panel, vitamin B12, TSH, MMSE, tau/amyloid biomarkers, and risk factors.
          </p>
        </div>

        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-card p-8 text-center cursor-pointer transition-colors ${
            isDragActive ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/40'
          }`}
        >
          <input {...getInputProps()} />
          <FileText size={28} className="mx-auto mb-3 text-muted" />
          {ocrFile ? (
            <p className="text-white font-medium">{ocrFile.name}</p>
          ) : (
            <>
              <p className="text-white font-medium">
                Drop Blood Report / Lab Report image here
              </p>
              <p className="text-sm text-muted mt-1">
                PNG · JPG · PDF (printed lab results, blood panels, neuropsychological reports)
              </p>
            </>
          )}
        </div>

        <div className="flex items-center gap-3 mt-4">
          <Button onClick={handleExtract} disabled={!ocrFile || extracting}>
            {extracting ? <Spinner size="sm" /> : <Upload size={14} />}
            {extracting ? 'Reading with OCR...' : 'Extract Fields with OCR'}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setValues({})}>
            Clear all
          </Button>
        </div>
        {ocrError && <p className="text-danger text-sm mt-3">{ocrError}</p>}

        {rawTextPreview && (
          <div className="mt-3">
            <button
              className="text-xs text-muted flex items-center gap-1 hover:text-white transition-colors"
              onClick={() => setShowRaw(v => !v)}
            >
              {showRaw ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              Raw OCR text preview
            </button>
            <AnimatePresence>
              {showRaw && (
                <motion.pre
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="text-xs text-muted mt-2 bg-background p-3 rounded-md overflow-x-auto whitespace-pre-wrap"
                >
                  {rawTextPreview}
                </motion.pre>
              )}
            </AnimatePresence>
          </div>
        )}
      </Card>

      {/* Full editable form — always visible, OCR pre-fills it */}
      <div className="space-y-4 mb-6">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white">
            Clinical Data —{' '}
            <span className="text-muted font-normal">{filledCount} / {FIELD_DEFS.length} fields filled</span>
          </h3>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setExpandedGroups(new Set(GROUPS))}
          >
            Expand all
          </Button>
        </div>

        {GROUPS.map(group => {
          const fields = FIELD_DEFS.filter(f => f.group === group)
          const expanded = expandedGroups.has(group)
          const groupFilled = fields.filter(f => values[f.key] !== undefined && values[f.key] !== '').length
          return (
            <Card key={group} className="overflow-hidden">
              <button
                className="w-full flex items-center justify-between text-left"
                onClick={() => toggleGroup(group)}
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-white">{group}</span>
                  <span className="text-xs text-muted">({groupFilled}/{fields.length})</span>
                </div>
                {expanded ? <ChevronUp size={14} className="text-muted" /> : <ChevronDown size={14} className="text-muted" />}
              </button>

              <AnimatePresence initial={false}>
                {expanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
                      {fields.map(def => (
                        <div key={def.key}>
                          <label className="block text-xs text-muted mb-1">{def.label}</label>
                          {def.type === 'boolean' ? (
                            <select
                              className="input w-full"
                              value={values[def.key] ?? ''}
                              onChange={e => setField(def.key, e.target.value)}
                            >
                              <option value="">— unknown —</option>
                              <option value="false">No</option>
                              <option value="true">Yes</option>
                            </select>
                          ) : def.type === 'select' ? (
                            <select
                              className="input w-full"
                              value={values[def.key] ?? ''}
                              onChange={e => setField(def.key, e.target.value)}
                            >
                              {def.options.map(o => (
                                <option key={o} value={o}>{o || '— select —'}</option>
                              ))}
                            </select>
                          ) : (
                            <input
                              type="number"
                              step="any"
                              className={`input w-full transition-colors ${
                                values[def.key] !== undefined && values[def.key] !== ''
                                  ? 'border-primary/50'
                                  : ''
                              }`}
                              placeholder={def.placeholder}
                              value={values[def.key] ?? ''}
                              onChange={e => setField(def.key, e.target.value)}
                            />
                          )}
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </Card>
          )
        })}
      </div>

      {/* Save */}
      {saved ? (
        <div className="flex items-center gap-2 text-success text-sm">
          <Check size={16} /> Report saved — clinical data stored to patient record
        </div>
      ) : (
        <Button onClick={handleSave} disabled={saving || filledCount === 0}>
          {saving ? <Spinner size="sm" /> : <Check size={14} />}
          {saving ? 'Saving...' : `Confirm & Save ${filledCount} Field${filledCount !== 1 ? 's' : ''}`}
        </Button>
      )}
    </PageWrapper>
  )
}
