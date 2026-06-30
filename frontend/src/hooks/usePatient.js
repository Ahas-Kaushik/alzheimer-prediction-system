import { useCallback, useEffect, useState } from 'react'
import { getPatient, listPatients } from '../api/patientApi'
import usePatientStore from '../store/patientStore'

export function usePatients() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const { patients, setPatients } = usePatientStore()

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listPatients()
      setPatients(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [setPatients])

  useEffect(() => { fetch() }, [fetch])

  return { patients, loading, error, refetch: fetch }
}

export function usePatient(id) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const { currentPatient, setCurrentPatient, clearCurrentPatient } = usePatientStore()

  useEffect(() => {
    if (!id) return
    // Clear stale data from the previous patient immediately.
    clearCurrentPatient()
    setLoading(true)
    setError(null)
    getPatient(id)
      .then(setCurrentPatient)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Only return patient data if it matches the requested id.
  const patient = currentPatient?.patient_id === id ? currentPatient : null
  return { patient, loading, error }
}
