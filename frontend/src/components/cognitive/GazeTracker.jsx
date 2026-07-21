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
// Eye-corner / lid landmarks used to estimate gaze direction (is the iris
// centred in the eye → looking forward at the screen, or deviated → looking away)
const LEFT_EYE = { outer: 33, inner: 133, top: 159, bottom: 145, iris: 468 }
const RIGHT_EYE = { outer: 263, inner: 362, top: 386, bottom: 374, iris: 473 }
const H_TOLERANCE = 0.30   // how far the iris may sit from eye-centre horizontally
const V_TOLERANCE = 0.34   // …and vertically, before we call it "looking away"
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
  const onScreenRef = useRef(true)          // current instantaneous on-screen state
  const onScreenSamplesRef = useRef(0)      // samples where the patient looked at screen
  const totalSamplesRef = useRef(0)         // total gaze samples
  const [onScreen, setOnScreen] = useState(true)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState(null)

  // Compute normalised iris center from landmarks
  const getIrisCenter = (landmarks) => {
    const l = landmarks[LEFT_IRIS_CENTER]
    const r = landmarks[RIGHT_IRIS_CENTER]
    if (!l || !r) return null
    return { x: (l.x + r.x) / 2, y: (l.y + r.y) / 2 }
  }

  // Estimate whether one eye is looking forward (iris centred within the eye).
  const eyeLooksForward = (lm, eye) => {
    const outer = lm[eye.outer], inner = lm[eye.inner]
    const top = lm[eye.top], bottom = lm[eye.bottom], iris = lm[eye.iris]
    if (!outer || !inner || !top || !bottom || !iris) return null
    const w = outer.x - inner.x
    const h = bottom.y - top.y
    if (Math.abs(w) < 1e-4 || Math.abs(h) < 1e-4) return null
    const hRatio = (iris.x - inner.x) / w    // ~0.5 when centred
    const vRatio = (iris.y - top.y) / h      // ~0.5 when centred
    return Math.abs(hRatio - 0.5) < H_TOLERANCE && Math.abs(vRatio - 0.5) < V_TOLERANCE
  }

  const onResults = useCallback((results) => {
    // No face in frame → the patient is not looking at the screen.
    if (!results.multiFaceLandmarks?.length) {
      onScreenRef.current = false
      totalSamplesRef.current += 1
      return
    }
    const landmarks = results.multiFaceLandmarks[0]
    const center = getIrisCenter(landmarks)
    if (!center) return

    const now = Date.now()

    // Gaze-direction / on-screen estimation (average both eyes)
    const leftFwd = eyeLooksForward(landmarks, LEFT_EYE)
    const rightFwd = eyeLooksForward(landmarks, RIGHT_EYE)
    const forwardVotes = [leftFwd, rightFwd].filter((v) => v !== null)
    const isOnScreen = forwardVotes.length === 0
      ? true
      : forwardVotes.some((v) => v === true)   // either eye forward ⇒ on screen
    onScreenRef.current = isOnScreen
    totalSamplesRef.current += 1
    if (isOnScreen) onScreenSamplesRef.current += 1

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
      const total = totalSamplesRef.current || 1
      const ratio = onScreenSamplesRef.current / total
      setOnScreen(onScreenRef.current)
      if (onMetricsUpdate) {
        onMetricsUpdate({
          gaze_stability: parseFloat(stability.toFixed(4)),
          saccade_count: saccadeCountRef.current,
          gaze_on_screen: onScreenRef.current,
          on_screen_ratio: parseFloat(ratio.toFixed(4)),
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
            error ? 'bg-danger'
              : !ready ? 'bg-warning'
              : onScreen ? 'bg-success animate-pulse'
              : 'bg-danger animate-pulse'
          }`}
        />
        <span className="text-xs text-white/70">
          {error ? 'Error' : !ready ? 'Loading…' : onScreen ? 'Gaze Active' : 'Look at screen'}
        </span>
      </div>
      {error && (
        <p className="text-xs text-danger mt-1">{error}</p>
      )}
    </div>
  )
}
