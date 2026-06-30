import { useState } from 'react'
import Button from '../ui/Button'
import Spinner from '../ui/Spinner'
import { createPatient } from '../../api/patientApi'
import usePatientStore from '../../store/patientStore'

const INITIAL = { name: '', dob: '', gender: 'Male', notes: '' }

export default function PatientForm({ onSuccess }) {
  const [form, setForm] = useState(INITIAL)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const setCurrentPatient = usePatientStore((s) => s.setCurrentPatient)

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const patient = await createPatient(form)
      setCurrentPatient(patient)
      setForm(INITIAL)
      onSuccess?.(patient)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-xs text-muted mb-1">Full Name</label>
        <input className="input w-full" value={form.name} onChange={set('name')} required placeholder="John Doe" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-muted mb-1">Date of Birth</label>
          <input type="date" className="input w-full" value={form.dob} onChange={set('dob')} required />
        </div>
        <div>
          <label className="block text-xs text-muted mb-1">Gender</label>
          <select className="input w-full" value={form.gender} onChange={set('gender')}>
            <option>Male</option>
            <option>Female</option>
            <option>Other</option>
          </select>
        </div>
      </div>
      <div>
        <label className="block text-xs text-muted mb-1">Notes (optional)</label>
        <textarea className="input w-full h-20 resize-none" value={form.notes} onChange={set('notes')} placeholder="Referral notes..." />
      </div>
      {error && <p className="text-danger text-sm">{error}</p>}
      <Button type="submit" disabled={loading} className="w-full justify-center">
        {loading ? <Spinner size="sm" /> : 'Create Patient'}
      </Button>
    </form>
  )
}
