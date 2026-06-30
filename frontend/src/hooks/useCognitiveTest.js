import { useCallback, useEffect, useRef, useState } from 'react'
import { startTest, submitResponse } from '../api/cognitiveApi'

export function useCognitiveTest(patientId) {
  const [sessionId, setSessionId] = useState(null)
  const [currentStimulus, setCurrentStimulus] = useState(null)
  const [scores, setScores] = useState(null)
  const [status, setStatus] = useState('idle') // idle | warmup | running | completed
  const [error, setError] = useState(null)
  // Browser gaze metrics collected from GazeTracker component
  const [gazeMetrics, setGazeMetrics] = useState({ gaze_stability: 1.0, saccade_count: 0 })
  const timerRef = useRef(null)

  const start = useCallback(async () => {
    try {
      const data = await startTest(patientId)
      setSessionId(data.session_id)
      setCurrentStimulus(data.current_stimulus)
      setStatus(data.current_stimulus?.is_warmup ? 'warmup' : 'running')
    } catch (e) {
      setError(e.message)
    }
  }, [patientId])

  // Called by GazeTracker component with live metrics
  const updateGazeMetrics = useCallback((metrics) => {
    setGazeMetrics({
      gaze_stability: metrics.gaze_stability ?? 1.0,
      saccade_count: metrics.saccade_count ?? 0,
    })
  }, [])

  const respond = useCallback(async (correct) => {
    if (!sessionId) return
    try {
      const result = await submitResponse(sessionId, correct, gazeMetrics)
      if (result.status === 'completed') {
        setScores(result.scores)
        setStatus('completed')
        setCurrentStimulus(null)
      } else {
        const next = result.next_stimulus
        setCurrentStimulus(next)
        setStatus(next?.is_warmup ? 'warmup' : 'running')
      }
    } catch (e) {
      setError(e.message)
    }
  }, [sessionId, gazeMetrics])

  // Auto-advance on timeout
  useEffect(() => {
    if (!currentStimulus) return
    timerRef.current = setTimeout(() => {
      respond(false) // treat timeout as incorrect
    }, currentStimulus.duration_ms + 500)
    return () => clearTimeout(timerRef.current)
  }, [currentStimulus, respond])

  // Keyboard handler
  useEffect(() => {
    if (status !== 'running' && status !== 'warmup') return
    const handler = (e) => {
      if (e.code === 'Space') { e.preventDefault(); respond(true) }
      if (e.code === 'Enter') { e.preventDefault(); respond(false) }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [status, respond])

  return { sessionId, currentStimulus, scores, status, error, gazeMetrics, start, respond, updateGazeMetrics }
}
