/**
 * Tab 2 — MRI → PET Synthesis.
 * No upload here. Selects from scans already uploaded in Tab 1.
 * Shows the 3-panel view (MRI | Physics PET | GAN Heatmap) after synthesis.
 */
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Zap, ArrowRight, AlertTriangle, Upload, CheckCircle } from 'lucide-react'
import PageWrapper from '../components/layout/PageWrapper'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'
import ScanComparison from '../components/scan/ScanComparison'
import { getAllScans, synthesizePET } from '../api/scanApi'

function toImageUrl(filePath) {
  if (!filePath) return null
  const norm = filePath.replace(/\\/g, '/')
  if (norm.startsWith('http')) return norm
  return `http://localhost:8000/uploads/${norm.replace(/^.*uploads\//, '')}`
}

export default function MRIToPET() {
  const { id: patientId } = useParams()
  const navigate = useNavigate()

  const [scans, setScans] = useState([])
  const [loadingScans, setLoadingScans] = useState(true)
  const [selectedScanId, setSelectedScanId] = useState(null)

  const [petResult, setPetResult] = useState(null)
  const [synthesizing, setSynthesizing] = useState(false)
  const [error, setError] = useState(null)
  const [ganWarning, setGanWarning] = useState(false)

  useEffect(() => {
    setLoadingScans(true)
    getAllScans(patientId)
      .then(data => {
        setScans(data)
        if (data.length > 0) setSelectedScanId(data[0].scan_id)  // auto-select latest
      })
      .catch(() => setScans([]))
      .finally(() => setLoadingScans(false))
  }, [patientId])

  const selectedScan = scans.find(s => s.scan_id === selectedScanId)

  const handleSynthesize = async () => {
    if (!selectedScanId) return
    setSynthesizing(true)
    setError(null)
    setPetResult(null)
    try {
      const result = await synthesizePET(selectedScanId, patientId)
      setPetResult(result)
      if (result.ssim_score !== null && result.ssim_score < 0.1) setGanWarning(true)
    } catch (e) {
      setError(e.message)
    } finally {
      setSynthesizing(false)
    }
  }

  return (
    <PageWrapper>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white">MRI → PET Synthesis</h2>
        <p className="text-sm text-muted mt-1">
          Select a previously uploaded MRI scan and generate a synthetic FDG-PET image.
          The 3-panel view (MRI · Physics PET · Activity Heatmap) is shown below after synthesis.
        </p>
      </div>

      {/* Scan selector */}
      <Card className="mb-6">
        <h3 className="text-sm font-semibold text-white mb-3">Select MRI Scan to Synthesize From</h3>

        {loadingScans ? (
          <div className="flex justify-center py-6"><Spinner size="sm" /></div>
        ) : scans.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-8 text-center">
            <p className="text-muted text-sm">No MRI scans found for this patient.</p>
            <Button onClick={() => navigate(`/patient/${patientId}/scan`)}>
              <Upload size={14} /> Go to MRI Upload (Tab 1)
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {scans.map((scan) => {
              const selected = scan.scan_id === selectedScanId
              return (
                <button
                  key={scan.scan_id}
                  onClick={() => { setSelectedScanId(scan.scan_id); setPetResult(null) }}
                  className={`rounded-card border overflow-hidden text-left transition-all ${
                    selected
                      ? 'border-primary ring-1 ring-primary/50 bg-primary/5'
                      : 'border-border hover:border-primary/40'
                  }`}
                >
                  <img
                    src={toImageUrl(scan.file_path)}
                    alt="MRI"
                    className="w-full aspect-square object-cover bg-black"
                    onError={(e) => { e.target.style.display = 'none' }}
                  />
                  <div className="p-2">
                    <p className="text-xs text-white truncate">
                      {scan.file_path.replace(/\\/g, '/').split('/').pop()}
                    </p>
                    <p className="text-xs text-muted mt-0.5">
                      {new Date(scan.upload_date).toLocaleDateString()}
                    </p>
                    {selected && (
                      <p className="text-xs text-primary mt-0.5 flex items-center gap-1">
                        <CheckCircle size={10} /> Selected
                      </p>
                    )}
                  </div>
                </button>
              )
            })}
          </div>
        )}

        {scans.length > 0 && (
          <div className="flex gap-3 mt-4">
            <Button onClick={handleSynthesize} disabled={!selectedScanId || synthesizing}>
              {synthesizing ? <Spinner size="sm" /> : <Zap size={14} />}
              {synthesizing ? 'Generating PET…' : 'Generate Synthetic PET'}
            </Button>
          </div>
        )}

        {error && <p className="text-danger text-sm mt-3">{error}</p>}
      </Card>

      {/* GAN not trained warning */}
      {ganWarning && (
        <div className="mb-4 flex items-start gap-3 bg-yellow-900/20 border border-yellow-800/40 rounded-card p-4">
          <AlertTriangle size={16} className="text-yellow-400 mt-0.5 shrink-0" />
          <div className="text-sm">
            <p className="text-yellow-400 font-medium">GAN model not trained — showing physics-based PET</p>
            <p className="text-muted mt-1">
              The Pix2Pix GAN has no trained checkpoint. PET is generated via physics-based tissue
              intensity mapping, which is used for detection regardless. This is sufficient for
              clinical prediction; the visual quality improves after GAN training.
            </p>
          </div>
        </div>
      )}

      {/* 3-panel view — only shown after synthesis */}
      {petResult && selectedScan && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-white">Scan Analysis — 3-Panel View</h3>
              <div className="flex gap-2 text-xs text-muted">
                <span className="bg-surface border border-border px-2 py-0.5 rounded">
                  SSIM {petResult.ssim_score != null ? petResult.ssim_score.toFixed(3) : 'N/A'}
                </span>
                <span className="bg-surface border border-border px-2 py-0.5 rounded">
                  PSNR {petResult.psnr_score != null ? `${petResult.psnr_score.toFixed(1)} dB` : 'N/A'}
                </span>
              </div>
            </div>

            <ScanComparison
              mriPath={selectedScan.file_path}
              petPath={petResult.file_path}
              ssimScore={petResult.ssim_score}
              heatmapPath={petResult.heatmap_file_path}
            />
          </Card>

          <div className="flex gap-3">
            <Button onClick={() => navigate(`/patient/${patientId}/prediction`)}>
              <ArrowRight size={14} /> Proceed to Prediction
            </Button>
            <Button variant="ghost" onClick={() => navigate(`/patient/${patientId}/scan`)}>
              Back to MRI Upload
            </Button>
          </div>
        </motion.div>
      )}
    </PageWrapper>
  )
}
