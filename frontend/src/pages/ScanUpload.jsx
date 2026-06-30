/**
 * Tab 1 — Brain MRI Upload.
 * Only handles uploading. PET synthesis lives in Tab 2 (MRIToPET.jsx).
 * Shows previously uploaded scans so returning patients don't lose history.
 */
import { useCallback, useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { Upload, Info, X, CheckCircle, Brain, Trash2 } from 'lucide-react'
import PageWrapper from '../components/layout/PageWrapper'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'
import { uploadMRI, getAllScans, deleteScan } from '../api/scanApi'

function toImageUrl(filePath) {
  if (!filePath) return null
  const norm = filePath.replace(/\\/g, '/')
  if (norm.startsWith('http')) return norm
  return `http://localhost:8000/uploads/${norm.replace(/^.*uploads\//, '')}`
}

export default function ScanUpload() {
  const { id: patientId } = useParams()
  const navigate = useNavigate()

  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [newlyUploaded, setNewlyUploaded] = useState([])

  // Previously uploaded scans (persist across visits)
  const [existingScans, setExistingScans] = useState([])
  const [loadingScans, setLoadingScans] = useState(true)

  const loadExisting = useCallback(() => {
    setLoadingScans(true)
    getAllScans(patientId)
      .then(setExistingScans)
      .catch(() => setExistingScans([]))
      .finally(() => setLoadingScans(false))
  }, [patientId])

  useEffect(() => { loadExisting() }, [loadExisting])

  const onDrop = useCallback((accepted) => {
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name))
      return [...prev, ...accepted.filter(f => !existing.has(f.name))]
    })
    setNewlyUploaded([])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg'],
      'application/octet-stream': ['.nii', '.gz'],
      'application/dicom': ['.dcm'],
    },
    multiple: true,
  })

  const handleUploadAll = async () => {
    if (!files.length) return
    setUploading(true)
    setUploadError(null)
    setNewlyUploaded([])
    try {
      const results = []
      for (const file of files) {
        results.push(await uploadMRI(patientId, file))
      }
      setNewlyUploaded(results)
      setFiles([])
      loadExisting()         // refresh existing scans list
    } catch (e) {
      setUploadError(e.message)
    } finally {
      setUploading(false)
    }
  }

  const [deletingId, setDeletingId] = useState(null)

  const handleDelete = async (scan) => {
    if (!window.confirm(`Delete scan "${scan.file_path.replace(/\\/g, '/').split('/').pop()}"? This cannot be undone.`)) return
    setDeletingId(scan.scan_id)
    try {
      await deleteScan(scan.scan_id, patientId)
      loadExisting()
    } catch (e) {
      alert(`Delete failed: ${e.message}`)
    } finally {
      setDeletingId(null)
    }
  }

  const allScans = existingScans  // already newest-first from backend

  return (
    <PageWrapper>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white">Brain MRI Upload</h2>
        <p className="text-sm text-muted mt-1">
          Upload T1-weighted structural MRI scans for this patient.
          Multiple slices can be uploaded — all are factored into the prediction.
          To generate a synthetic PET, go to the{' '}
          <button
            className="text-primary underline underline-offset-2"
            onClick={() => navigate(`/patient/${patientId}/mri-to-pet`)}
          >
            MRI → PET Synthesis tab
          </button>.
        </p>
      </div>

      {/* Upload card */}
      <Card className="mb-6">
        <div className="flex items-start gap-2 mb-4">
          <Info size={14} className="text-primary mt-0.5 shrink-0" />
          <p className="text-xs text-muted">
            Accepted: <span className="text-white">PNG · JPG</span> (single axial slice),{' '}
            <span className="text-white">NIfTI (.nii / .nii.gz)</span> (3D volume — max-variance slice extracted),{' '}
            <span className="text-white">DICOM (.dcm)</span> (clinical scanner export).
            Max 50 MB each.
          </p>
        </div>

        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-card p-10 text-center cursor-pointer transition-colors ${
            isDragActive ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/40'
          }`}
        >
          <input {...getInputProps()} />
          <Upload size={32} className="mx-auto mb-3 text-muted" />
          <p className="text-white font-medium">Drop T1-weighted Brain MRI scan(s) here, or click to browse</p>
          <p className="text-sm text-muted mt-1">PNG · JPG · NIfTI · DICOM — multiple files supported</p>
        </div>

        {files.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {files.map((f) => (
              <div key={f.name} className="flex items-center justify-between bg-background rounded-md px-3 py-1.5 text-sm">
                <span className="text-white truncate max-w-xs">{f.name}</span>
                <button
                  onClick={() => setFiles(p => p.filter(x => x.name !== f.name))}
                  className="text-muted hover:text-danger ml-3 shrink-0"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-3 mt-4">
          <Button onClick={handleUploadAll} disabled={!files.length || uploading}>
            {uploading ? <Spinner size="sm" /> : <Upload size={14} />}
            {uploading ? 'Uploading…' : `Upload ${files.length} file${files.length !== 1 ? 's' : ''}`}
          </Button>
        </div>

        {uploadError && <p className="text-danger text-sm mt-3">{uploadError}</p>}

        {newlyUploaded.length > 0 && (
          <div className="flex items-center gap-2 mt-3 text-sm text-success">
            <CheckCircle size={14} />
            {newlyUploaded.length} scan{newlyUploaded.length > 1 ? 's' : ''} uploaded successfully and saved.
          </div>
        )}
      </Card>

      {/* All uploaded scans for this patient */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Brain size={15} className="text-indigo-400" />
            Uploaded Brain MRI Scans
            {allScans.length > 0 && (
              <span className="text-xs text-muted font-normal ml-1">({allScans.length} total)</span>
            )}
          </h3>
          {allScans.length > 0 && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => navigate(`/patient/${patientId}/mri-to-pet`)}
            >
              Generate PET from these →
            </Button>
          )}
        </div>

        {loadingScans ? (
          <div className="flex justify-center py-8"><Spinner size="sm" /></div>
        ) : allScans.length === 0 ? (
          <div className="text-center py-8 text-muted text-sm border border-dashed border-border rounded-card">
            No MRI scans uploaded yet. Upload scans above to get started.
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {allScans.map((scan, i) => (
              <div key={scan.scan_id} className="relative rounded-card border border-border overflow-hidden bg-black group">
                <img
                  src={toImageUrl(scan.file_path)}
                  alt={`Scan ${i + 1}`}
                  className="w-full aspect-square object-cover"
                  onError={(e) => { e.target.style.display = 'none' }}
                />
                {/* Delete overlay — appears on hover */}
                <button
                  className="absolute top-1.5 right-1.5 p-1 rounded-md bg-black/70 text-red-400 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-950/80 disabled:opacity-40"
                  title="Remove this scan"
                  disabled={deletingId === scan.scan_id}
                  onClick={() => handleDelete(scan)}
                >
                  {deletingId === scan.scan_id
                    ? <Spinner size="sm" />
                    : <Trash2 size={13} />}
                </button>
                <div className="p-2">
                  <p className="text-xs text-muted truncate">
                    {scan.file_path.replace(/\\/g, '/').split('/').pop()}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {new Date(scan.upload_date).toLocaleDateString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </PageWrapper>
  )
}
