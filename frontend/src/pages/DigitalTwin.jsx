import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import PageWrapper from '../components/layout/PageWrapper'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'
import Badge from '../components/ui/Badge'
import AbstractBrainViz from '../components/twin/AbstractBrainViz'
import AnatomicalBrainViz from '../components/twin/AnatomicalBrainViz'
import TimelineChart from '../components/twin/TimelineChart'
import { useDigitalTwin } from '../hooks/useDigitalTwin'

const DELTA_ICONS = { improved: '↑', stable: '→', declined: '↓' }
const DELTA_COLORS = { improved: 'text-success', stable: 'text-muted', declined: 'text-danger' }

export default function DigitalTwin() {
  const { id: patientId } = useParams()
  const { twinData, loading, error, vizMode, setVizMode, fetchTwin } = useDigitalTwin(patientId)

  useEffect(() => { fetchTwin() }, [fetchTwin])

  return (
    <PageWrapper>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-white">Digital Brain Twin</h2>
        <div className="flex gap-2">
          <Button size="sm" variant={vizMode === 'abstract' ? 'primary' : 'ghost'} onClick={() => setVizMode('abstract')}>Abstract</Button>
          <Button size="sm" variant={vizMode === 'anatomical' ? 'primary' : 'ghost'} onClick={() => setVizMode('anatomical')}>Anatomical</Button>
        </div>
      </div>

      {loading && <div className="flex justify-center py-16"><Spinner size="lg" /></div>}
      {error && <Card className="text-center py-8 text-muted">{error}</Card>}

      {twinData && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            {vizMode === 'abstract' ? (
              <AbstractBrainViz regions={twinData.regions} connectivity={twinData.neuron_connectivity} />
            ) : (
              <AnatomicalBrainViz regions={twinData.regions} />
            )}
            <Card>
              <h3 className="text-sm font-semibold text-white mb-4">Longitudinal Timeline</h3>
              <TimelineChart data={twinData.longitudinal} />
            </Card>
          </div>

          <div className="space-y-4">
            <Card>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-white">Current Status</h3>
                <span className={`text-lg font-bold ${DELTA_COLORS[twinData.delta_from_last]}`}>
                  {DELTA_ICONS[twinData.delta_from_last]}
                </span>
              </div>
              <Badge stage={twinData.current_stage} />
              <p className="text-xs text-muted mt-2">
                Confidence: <span className="font-mono text-white">{(twinData.current_confidence * 100).toFixed(1)}%</span>
              </p>
              <p className="text-xs text-muted mt-1">
                Connectivity: <span className="font-mono text-white">{(twinData.neuron_connectivity * 100).toFixed(0)}%</span>
              </p>
            </Card>

            <Card>
              <h3 className="text-sm font-semibold text-white mb-3">Region Severity</h3>
              <div className="space-y-2">
                {twinData.regions.map((r) => (
                  <div key={r.name} className="flex items-center justify-between text-xs">
                    <span className="text-muted truncate">{r.name}</span>
                    <div className="flex items-center gap-2 ml-2 shrink-0">
                      <div className="w-16 h-1.5 bg-border rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${r.severity * 100}%`,
                            background: { Normal: '#22c55e', MCI: '#f59e0b', AD: '#ef4444' }[r.status],
                          }}
                        />
                      </div>
                      <span className="font-mono text-white w-8 text-right">{(r.severity * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}
    </PageWrapper>
  )
}
