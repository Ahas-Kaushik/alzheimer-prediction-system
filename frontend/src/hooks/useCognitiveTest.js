import { useCallback, useEffect, useRef, useState } from 'react'
import { startTest, submitResponse } from '../api/cognitiveApi'

export function useCognitiveTest(patientId) {
  const [sessionId, setSessionId] = useState(null)
  const [currentStimulus, setCurrentStimulus] = useState(null)
  const [scores, setScores] = useState(null)
  const [status, setStatus] = useState('idle') // idle | warmup | running | completed
  const [error, setError] = useState(null)
  const [resetNotice, setResetNotice] = useState(null) // set when the test auto-resets
  // Browser gaze metrics collected from GazeTracker component
  const [gazeMetrics, setGazeMetrics] = useState({
    gaze_stability: 1.0, saccade_count: 0, gaze_on_screen: true,
  })
  const timerRef = useRef(null)
  const gazeRef = useRef(gazeMetrics)      // always-current gaze for event handlers
  const shownAtRef = useRef(0)             // timestamp the current stimulus appeared
  const submittingRef = useRef(false)      // guard against double submits / key repeat

  const start = useCallback(async () => {
    try {
      setResetNotice(null)
      const data = await startTest(patientId)
      setSessionId(data.session_id)
      shownAtRef.current = Date.now()
      setCurrentStimulus(data.current_stimulus)
      setStatus(data.current_stimulus?.is_warmup ? 'warmup' : 'running')
    } catch (e) {
      setError(e.message)
    }
  }, [patientId])

  // Called by GazeTracker component with live metrics
  const updateGazeMetrics = useCallback((metrics) => {
    const next = {
      gaze_stability: metrics.gaze_stability ?? 1.0,
      saccade_count: metrics.saccade_count ?? 0,
      gaze_on_screen: metrics.gaze_on_screen ?? true,
    }
    gazeRef.current = next
    setGazeMetrics(next)
  }, [])

  const respond = useCallback(async (correct) => {
    if (!sessionId) return
    if (submittingRef.current) return       // ignore key-repeat / rapid double taps
    submittingRef.current = true
    if (timerRef.current) clearTimeout(timerRef.current)

    const reaction_time_ms = Math.max(0, Date.now() - shownAtRef.current)
    try {
      const result = await submitResponse(
        sessionId, correct, gazeRef.current, { reaction_time_ms },
      )
      if (result.status === 'completed') {
        setScores(result.scores)
        setStatus('completed')
        setCurrentStimulus(null)
      } else if (result.status === 'reset') {
        // Spam / not-reading detected — the backend restarted with a longer test.
        setResetNotice(result.reason || 'Test restarted — please answer carefully.')
        shownAtRef.current = Date.now()
        setCurrentStimulus(result.current_stimulus)
        setStatus(result.current_stimulus?.is_warmup ? 'warmup' : 'running')
      } else {
        const next = result.next_stimulus
        shownAtRef.current = Date.now()
        setCurrentStimulus(next)
        setStatus(next?.is_warmup ? 'warmup' : 'running')
      }
    } catch (e) {
      setError(e.message)
    } finally {
      submittingRef.current = false
    }
  }, [sessionId])

  // Auto-advance on timeout (treated as "did not recognize")
  useEffect(() => {
    if (!currentStimulus) return
    submittingRef.current = false
    timerRef.current = setTimeout(() => {
      respond(false)
    }, currentStimulus.duration_ms + 500)
    return () => clearTimeout(timerRef.current)
  }, [currentStimulus, respond])

  // Keyboard handler — ignores auto-repeat so holding a key does not spam responses
  useEffect(() => {
    if (status !== 'running' && status !== 'warmup') return
    const handler = (e) => {
      if (e.repeat) return
      if (e.code === 'Space') { e.preventDefault(); respond(true) }
      if (e.code === 'Enter') { e.preventDefault(); respond(false) }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [status, respond])

  return {
    sessionId, currentStimulus, scores, status, error, gazeMetrics, resetNotice,
    start, respond, updateGazeMetrics,
  }
}
