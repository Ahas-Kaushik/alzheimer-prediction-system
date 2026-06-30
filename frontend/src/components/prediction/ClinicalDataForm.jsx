/**
 * ClinicalDataForm — hybrid OCR pre-fill + manual entry.
 *
 * 1. User can optionally upload a blood report image/PDF.
 * 2. Backend OCR extracts fields and pre-fills the form.
 * 3. Empty / unrecognised fields remain blank for manual entry.
 * 4. User completes the form and submits — all fields go into the prediction.
 */
import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { FileText, Upload, ChevronDown, ChevronUp, Info } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import Button from '../ui/Button'
import Spinner from '../ui/Spinner'
import Card from '../ui/Card'
import axiosClient from '../../api/axiosClient'

// All clinical fields shown in the form with their metadata
const FIELD_DEFS = [
  // Demographics / cognitive
  { key: 'age', label: 'Age (years)', type: 'number', placeholder: 'e.g. 72', group: 'Demographics' },
  { key: 'education_years', label: 'Education (years)', type: 'number', placeholder: 'e.g. 16', group: 'Demographics' },
  { key: 'mmse_score', label: 'MMSE Score (0-30)', type: 'number', placeholder: 'e.g. 24', group: 'Cognitive' },
  { key: 'moca_score', label: 'MoCA Score (0-30)', type: 'number', placeholder: 'e.g. 22', group: 'Cognitive' },
  { key: 'cdr_score', label: 'CDR Score', type: 'number', placeholder: '0 / 0.5 / 1 / 2 / 3', group: 'Cognitive' },
  // Biomarkers
  { key: 'amyloid_level', label: 'Amyloid Level (pg/mL)', type: 'number', placeholder: 'e.g. 1800', group: 'Biomarkers' },
  { key: 'tau_level', label: 'Tau (pg/mL)', type: 'number', placeholder: 'e.g. 400', group: 'Biomarkers' },
  { key: 'ptau_level', label: 'pTau (pg/mL)', type: 'number', placeholder: 'e.g. 52', group: 'Biomarkers' },
  // Blood panel
  { key: 'hemoglobin', label: 'Haemoglobin (g/dL)', type: 'number', placeholder: 'e.g. 13.5', group: 'Blood Panel' },
  { key: 'glucose', label: 'Fasting Glucose (mg/dL)', type: 'number', placeholder: 'e.g. 95', group: 'Blood Panel' },
  { key: 'cholesterol', label: 'Total Cholesterol (mg/dL)', type: 'number', placeholder: 'e.g. 200', group: 'Blood Panel' },
  { key: 'hdl', label: 'HDL (mg/dL)', type: 'number', placeholder: 'e.g. 55', group: 'Blood Panel' },
  { key: 'ldl', label: 'LDL (mg/dL)', type: 'number', placeholder: 'e.g. 120', group: 'Blood Panel' },
  { key: 'triglycerides', label: 'Triglycerides (mg/dL)', type: 'number', placeholder: 'e.g. 150', group: 'Blood Panel' },
  { key: 'vit_b12', label: 'Vitamin B12 (pg/mL)', type: 'number', placeholder: 'e.g. 350', group: 'Blood Panel' },
  { key: 'tsh', label: 'TSH (mIU/L)', type: 'number', placeholder: 'e.g. 2.5', group: 'Blood Panel' },
  // MRI volumetrics
  { key: 'hippocampal_volume', label: 'Hippocampal Volume (mm³)', type: 'number', placeholder: 'e.g. 3200', group: 'MRI Volumetrics' },
  { key: 'cortical_thickness', label: 'Cortical Thickness (mm)', type: 'number', placeholder: 'e.g. 2.4', group: 'MRI Volumetrics' },
  { key: 'wmh_volume', label: 'WMH Volume (mm³)', type: 'number', placeholder: 'e.g. 500', group: 'MRI Volumetrics' },
  // Risk factors (boolean)
  { key: 'apoe4_status', label: 'APOE4 Carrier', type: 'boolean', group: 'Risk Factors' },
  { key: 'smoking', label: 'Smoker', type: 'boolean', group: 'Risk Factors' },
  { key: 'diabetes', label: 'Diabetes', type: 'boolean', group: 'Risk Factors' },
  { key: 'hypertension', label: 'Hypertension', type: 'boolean', group: 'Risk Factors' },
  { key: 'depression', label: 'Depression', type: 'boolean', group: 'Risk Factors' },
  { key: 'family_history_ad', label: 'Family History of AD', type: 'boolean', group: 'Risk Factors' },
  // Demographics (selects)
  { key: 'gender', label: 'Gender', type: 'select', options: ['', 'male', 'female', 'other'], group: 'Demographics' },
]

const GROUPS = [...new Set(FIELD_DEFS.map(f => f.group))]

export default function ClinicalDataForm({ patientId, onSubmit, disabled }) {
  // Initialise from localStorage so returning patients see their previous values
  const [values, setValues] = useState(() => {
    try {
      const saved = localStorage.getItem(`clinical_data_${patientId}`)
      if (saved) return JSON.parse(saved)
    } catch {}
    return {}
  })
  const [ocrFile, setOcrFile] = useState(null)
  const [extracting, setExtracting] = useState(false)
  const [ocrDone, setOcrDone] = useState(false)
  const [ocrError, setOcrError] = useState(null)
  const [expandedGroups, setExpandedGroups] = useState(new Set(GROUPS))

  const setField = (key, val) => setValues(prev => ({ ...prev, [key]: val }))

  // OCR upload & pre-fill
  const onDrop = useCallback((accepted) => {
    if (accepted[0]) { setOcrFile(accepted[0]); setOcrDone(false) }
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
      const { data } = await axiosClient.post('/reports/upload', form)
      // Pre-fill only extracted (non-null) fields; leave others empty
      const extracted = data.extracted_fields || {}
      setValues(prev => {
        const merged = { ...prev }
        for (const [k, v] of Object.entries(extracted)) {
          if (v !== null && v !== '' && v !== undefined) {
            merged[k] = String(v)
          }
        }
        return merged
      })
      setOcrDone(true)
    } catch (e) {
      setOcrError(e.message || 'OCR failed')
    } finally {
      setExtracting(false)
    }
  }

  const toggleGroup = (group) => {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      next.has(group) ? next.delete(group) : next.add(group)
      return next
    })
  }

  const handleSubmit = () => {
    const payload = {}
    for (const def of FIELD_DEFS) {
      const raw = values[def.key]
      if (raw === undefined || raw === '') continue
      if (def.type === 'number') {
        const n = parseFloat(raw)
        if (!isNaN(n)) payload[def.key] = n
      } else if (def.type === 'boolean') {
        payload[def.key] = raw === 'true' || raw === true
      } else {
        payload[def.key] = raw
      }
    }
    // Persist for return visits — patient only changes what's different next time
    try { localStorage.setItem(`clinical_data_${patientId}`, JSON.stringify(values)) } catch {}
    onSubmit(payload)
  }

  const filledCount = FIELD_DEFS.filter(f => values[f.key] !== undefined && values[f.key] !== '').length

  return (
    <div className="space-y-4">
      {/* OCR upload section */}
      <Card>
        <div className="flex items-start gap-2 mb-3">
          <Info size={14} className="text-primary mt-0.5 shrink-0" />
          <p className="text-xs text-muted">
            <span className="text-white font-medium">Optional:</span> Upload a blood report image or PDF.
            Recognised fields will auto-fill the form below. Empty fields remain blank — enter them manually.
          </p>
        </div>

        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-card p-6 text-center cursor-pointer transition-colors ${
            isDragActive ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/40'
          }`}
        >
          <input {...getInputProps()} />
          <FileText size={24} className="mx-auto mb-2 text-muted" />
          {ocrFile ? (
            <p className="text-white text-sm font-medium">{ocrFile.name}</p>
          ) : (
            <>
              <p className="text-white text-sm font-medium">
                Drop Blood Report / Lab Report here
              </p>
              <p className="text-xs text-muted mt-1">
                Accepts printed/scanned reports: PNG · JPG · PDF
              </p>
            </>
          )}
        </div>

        <div className="flex items-center gap-3 mt-3">
          <Button
            size="sm"
            variant="ghost"
            onClick={handleExtract}
            disabled={!ocrFile || extracting}
          >
            {extracting ? <Spinner size="sm" /> : <Upload size={12} />}
            {extracting ? 'Reading report…' : 'Extract with OCR'}
          </Button>
          {ocrDone && (
            <span className="text-xs text-success">
              OCR complete — {filledCount} field(s) pre-filled
            </span>
          )}
          {ocrError && <span className="text-xs text-danger">{ocrError}</span>}
        </div>
      </Card>

      {/* Field groups */}
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
                            className={`input w-full ${
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

      {/* Submit */}
      <div className="flex items-center gap-3">
        <Button onClick={handleSubmit} disabled={disabled}>
          Run Prediction with {filledCount} clinical field{filledCount !== 1 ? 's' : ''}
        </Button>
        {filledCount === 0 ? (
          <span className="text-xs text-muted">
            You can also run without clinical data — imaging features will still be used.
          </span>
        ) : (
          <span className="text-xs text-muted">
            Values saved from your last visit. Change any fields above before submitting.
          </span>
        )}
      </div>
    </div>
  )
}
