import { useCallback, useEffect, useState } from 'react'
import { getTwin, getTwinHistory } from '../api/predictionApi'
import usePredictionStore from '../store/predictionStore'

export function useDigitalTwin(patientId) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [vizMode, setVizMode] = useState('abstract') // 'abstract' | 'anatomical'
  const { twinData, setTwinData } = usePredictionStore()

  // Clear stale twin data when switching patients.
  useEffect(() => {
    setTwinData(null)
  }, [patientId]) // eslint-disable-line react-hooks/exhaustive-deps

  const fetchTwin = useCallback(async () => {
    if (!patientId) return
    setLoading(true)
    setError(null)
    try {
      const data = await getTwin(patientId)
      setTwinData(data)
    } catch (e) {
      setTwinData(null)
      if (!e.message?.toLowerCase().includes('no prediction') && !e.message?.includes('404')) {
        setError(e.message)
      }
    } finally {
      setLoading(false)
    }
  }, [patientId, setTwinData])

  return { twinData, loading, error, vizMode, setVizMode, fetchTwin }
}
