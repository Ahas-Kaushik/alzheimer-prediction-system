import { useParams, useNavigate } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import PageWrapper from '../components/layout/PageWrapper'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import TestDisplay from '../components/cognitive/TestDisplay'
import GazeTracker from '../components/cognitive/GazeTracker'
import TestResultCard from '../components/cognitive/TestResultCard'
import { useCognitiveTest } from '../hooks/useCognitiveTest'

export default function CognitiveTest() {
  const { id: patientId } = useParams()
  const navigate = useNavigate()
  const {
    currentStimulus, scores, status, error, gazeMetrics,
    start, respond, updateGazeMetrics,
  } = useCognitiveTest(patientId)

  const isActive = status === 'running' || status === 'warmup'

  return (
    <PageWrapper>
      <h2 className="text-xl font-semibold text-white mb-6">Cognitive Assessment</h2>

      {status === 'idle' && (
        <Card className="text-center py-10">
          <h3 className="text-lg font-semibold text-white mb-2">Patient Cognitive Assessment</h3>
          <p className="text-sm text-muted mb-4 max-w-md mx-auto">
            You will see <strong className="text-white">10 items</strong> — everyday words and
            objects mixed with a few unfamiliar/nonsense items. Two warmup rounds come first.
          </p>
          <div className="max-w-md mx-auto mb-6 text-left space-y-2">
            <div className="flex items-start gap-3 rounded-lg bg-green-900/20 border border-green-800/40 px-4 py-2.5 text-sm">
              <kbd className="bg-slate-700 text-slate-200 px-2 py-0.5 rounded font-mono text-xs shrink-0 mt-0.5">Space</kbd>
              <span className="text-slate-300">
                <span className="text-green-300 font-medium">Recognize</span> — press this if you clearly
                recognize the item as something common and familiar.
              </span>
            </div>
            <div className="flex items-start gap-3 rounded-lg bg-slate-800/60 border border-border px-4 py-2.5 text-sm">
              <kbd className="bg-slate-700 text-slate-200 px-2 py-0.5 rounded font-mono text-xs shrink-0 mt-0.5">Enter</kbd>
              <span className="text-slate-300">
                <span className="text-slate-200 font-medium">Skip</span> — press this if the item looks
                unfamiliar or like a made-up word.
              </span>
            </div>
          </div>
          <p className="text-xs text-muted mb-6 max-w-sm mx-auto">
            Gaze tracking runs via your webcam in the browser — no data leaves your device.
            Allow camera access when prompted.
          </p>
          <Button onClick={start}>Begin Test</Button>
        </Card>
      )}

      {isActive && (
        <div className="relative">
          {/* Browser-side gaze tracker — webcam never leaves the browser */}
          <div className="absolute top-4 right-4 z-10">
            <GazeTracker active={isActive} onMetricsUpdate={updateGazeMetrics} />
            {isActive && (
              <div className="mt-1 text-xs text-muted text-right">
                Stability: {(gazeMetrics.gaze_stability * 100).toFixed(0)}%
                &nbsp;|&nbsp;Saccades: {gazeMetrics.saccade_count}
              </div>
            )}
          </div>

          <Card animate={false}>
            <AnimatePresence mode="wait">
              <TestDisplay key={currentStimulus?.index} stimulus={currentStimulus} />
            </AnimatePresence>
            <div className="flex justify-center gap-3 mt-4">
              <Button variant="success" onClick={() => respond(true)}>Recognize (Space)</Button>
              <Button variant="ghost" onClick={() => respond(false)}>Skip (Enter)</Button>
            </div>
          </Card>
        </div>
      )}

      {status === 'completed' && scores && (
        <div className="space-y-4">
          <TestResultCard scores={scores} />
          {scores.derived_mmse !== undefined && (
            <Card>
              <p className="text-sm text-white">
                Estimated MMSE equivalent:{' '}
                <span className="font-mono font-bold text-primary">
                  {scores.derived_mmse} / 30
                </span>
                <span className="text-xs text-muted ml-2">
                  (derived from cognitive test index — factored into final prediction)
                </span>
              </p>
            </Card>
          )}
          <div className="flex gap-3">
            <Button onClick={() => navigate(`/patient/${patientId}/prediction`)}>
              Proceed to Prediction
            </Button>
            <Button variant="ghost" onClick={() => navigate(`/patient/${patientId}`)}>
              Back to Profile
            </Button>
          </div>
        </div>
      )}

      {error && <p className="text-danger text-sm mt-4">{error}</p>}
    </PageWrapper>
  )
}
