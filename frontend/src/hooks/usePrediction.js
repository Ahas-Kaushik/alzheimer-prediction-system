import { useCallback, useEffect, useState } from 'react'
import { getLatestPrediction, getPredictions, runPrediction } from '../api/predictionApi'
import usePredictionStore from '../store/predictionStore'

export function usePrediction(patientId) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const {
    latestPrediction: rawLatest,
    setLatestPrediction,
    predictionHistory: rawHistory,
    setPredictionHistory,
    clearAll,
  } = usePredictionStore()

  // Only expose data that belongs to this patient — prevents flashing stale data
  // from a previously viewed patient while the new fetch is in flight.
  const latestPrediction = rawLatest?.patient_id === patientId ? rawLatest : null
  const predictionHistory = rawHistory.filter((p) => p.patient_id === patientId)

  // Clear store when switching patients so nothing leaks between profiles.
  useEffect(() => {
    clearAll()
  }, [patientId]) // eslint-disable-line react-hooks/exhaustive-deps

  const fetchLatest = useCallback(async () => {
    if (!patientId) return
    setLoading(true)
    setError(null)
    try {
      const data = await getLatestPrediction(patientId)
      setLatestPrediction(data)
    } catch (e) {
      // 404 means no prediction yet for this patient — clear stale data silently.
      setLatestPrediction(null)
      if (!e.message?.toLowerCase().includes('no prediction') && !e.message?.includes('404')) {
        setError(e.message)
      }
    } finally {
      setLoading(false)
    }
  }, [patientId, setLatestPrediction])

  const fetchHistory = useCallback(async () => {
    if (!patientId) return
    try {
      const data = await getPredictions(patientId)
      setPredictionHistory(data)
    } catch {
      setPredictionHistory([])
    }
  }, [patientId, setPredictionHistory])

  const run = useCallback(async (payload) => {
    setLoading(true)
    setError(null)
    try {
      const result = await runPrediction({ patient_id: patientId, ...payload })
      setLatestPrediction(result)
      return result
    } catch (e) {
      setError(e.message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [patientId, setLatestPrediction])

  return { latestPrediction, predictionHistory, loading, error, fetchLatest, fetchHistory, run }
}
