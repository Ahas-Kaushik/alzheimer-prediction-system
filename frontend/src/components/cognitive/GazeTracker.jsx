/**
 * GazeTracker — browser-side gaze tracking using MediaPipe FaceMesh.
 *
 * Loaded from CDN in index.html. Accesses the webcam directly in the browser,
 * computes iris position → gaze stability and saccade count, then calls
 * onMetricsUpdate(metrics) periodically.
 *
 * Landmark indices:
 *   Left iris:  468-472  (center = 468)
 *   Right iris: 473-477  (center = 473)
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import Webcam from 'react-webcam'

const LEFT_IRIS_CENTER = 468
const RIGHT_IRIS_CENTER = 473
const SACCADE_THRESHOLD_PX = 30   // normalised * 640px equivalent
const SAMPLE_INTERVAL_MS = 100    // collect a sample every 100 ms

export default function GazeTracker({ onMetricsUpdate, active = true }) {
  const webcamRef = useRef(null)
  const faceMeshRef = useRef(null)
  const cameraRef = useRef(null)
  const gazeHistoryRef = useRef([])   // { x, y, ts }[]
  const saccadeCountRef = useRef(0)
  const lastGazeRef = useRef(null)
  const intervalRef = useRef(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState(null)

  // Compute normalised iris center from landmarks
  const getIrisCenter = (landmarks) => {
    const l = landmarks[LEFT_IRIS_CENTER]
    const r = landmarks[RIGHT_IRIS_CENTER]
    if (!l || !r) return null
    return { x: (l.x + r.x) / 2, y: (l.y + r.y) / 2 }
  }

  const onResults = useCallback((results) => {
    if (!results.multiFaceLandmarks?.length) return
    const landmarks = results.multiFaceLandmarks[0]
    const center = getIrisCenter(landmarks)
    if (!center) return

    const now = Date.now()

    // Saccade detection: large displacement since last sample
    if (lastGazeRef.current) {
      const dx = (center.x - lastGazeRef.current.x) * 640
      const dy = (center.y - lastGazeRef.current.y) * 480
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist > SACCADE_THRESHOLD_PX) {
        saccadeCountRef.current += 1
      }
    }

    lastGazeRef.current = center
    gazeHistoryRef.current.push({ ...center, ts: now })
  }, [])

  // Compute gaze stability: 1 - normalised variance of gaze positions
  const computeGazeStability = (history) => {
    if (history.length < 2) return 1.0
    const xs = history.map(p => p.x)
    const ys = history.map(p => p.y)
    const meanX = xs.reduce((a, b) => a + b, 0) / xs.length
    const meanY = ys.reduce((a, b) => a + b, 0) / ys.length
    const varX = xs.reduce((a, b) => a + (b - meanX) ** 2, 0) / xs.length
    const varY = ys.reduce((a, b) => a + (b - meanY) ** 2, 0) / ys.length
    const combinedStd = Math.sqrt(varX + varY)
    // Map std 0→0.05 to stability 1→0
    return Math.max(0, Math.min(1, 1 - combinedStd / 0.05))
  }

  useEffect(() => {
    if (!active) return
    if (!window.FaceMesh) {
      setError('MediaPipe not loaded. Check CDN scripts in index.html.')
      return
    }

    const faceMesh = new window.FaceMesh({
      locateFile: (file) =>
        `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`,
    })

    faceMesh.setOptions({
      maxNumFaces: 1,
      refineLandmarks: true,   // required for iris landmarks 468+
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5,
    })

    faceMesh.onResults(onResults)
    faceMeshRef.current = faceMesh

    // Periodic metrics reporting
    intervalRef.current = setInterval(() => {
      const history = gazeHistoryRef.current.slice()
      const stability = computeGazeStability(history)
      if (onMetricsUpdate) {
        onMetricsUpdate({
          gaze_stability: parseFloat(stability.toFixed(4)),
          saccade_count: saccadeCountRef.current,
          sample_count: history.length,
        })
      }
    }, 1000)

    setReady(true)

    return () => {
      faceMesh.close()
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [active, onResults, onMetricsUpdate])

  // Process webcam frames via MediaPipe Camera utility
  useEffect(() => {
    if (!ready || !webcamRef.current?.video || !faceMeshRef.current) return
    if (!window.Camera) return

    const camera = new window.Camera(webcamRef.current.video, {
      onFrame: async () => {
        if (webcamRef.current?.video) {
          await faceMeshRef.current.send({ image: webcamRef.current.video })
        }
      },
      width: 320,
      height: 240,
    })
    camera.start()
    cameraRef.current = camera

    return () => { camera.stop() }
  }, [ready])

  return (
    <div className="relative">
      <Webcam
        ref={webcamRef}
        width={160}
        height={120}
        className="rounded-md opacity-80"
        mirrored
        videoConstraints={{ width: 320, height: 240, facingMode: 'user' }}
      />
      <div className="absolute top-1 left-1 flex items-center gap-1">
        <span
          className={`w-2 h-2 rounded-full ${
            error ? 'bg-danger' : ready ? 'bg-success animate-pulse' : 'bg-warning'
          }`}
        />
        <span className="text-xs text-white/70">
          {error ? 'Error' : ready ? 'Gaze Active' : 'Loading…'}
        </span>
      </div>
      {error && (
        <p className="text-xs text-danger mt-1">{error}</p>
      )}
    </div>
  )
}
