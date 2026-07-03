import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Settings as SettingsIcon, Database, Share2, Network, ExternalLink, RefreshCw, Cpu, Server } from 'lucide-react'
import PageWrapper from '../components/layout/PageWrapper'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'
import KnowledgeGraphViz from '../components/settings/KnowledgeGraphViz'
import VectorDBViz from '../components/settings/VectorDBViz'
import { ragStatus, getKnowledgeGraph, getVectorProjection } from '../api/ragApi'

function StatPill({ icon: Icon, label, value, color }) {
  return (
    <div className="flex items-center gap-3 rounded-lg px-3 py-2.5"
      style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }}>
      <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
        style={{ background: `${color}18`, border: `1px solid ${color}30` }}>
        <Icon size={15} style={{ color }} />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-muted">{label}</p>
        <p className="text-sm font-medium text-white truncate">{value}</p>
      </div>
    </div>
  )
}

export default function Settings() {
  const [status, setStatus] = useState(null)
  const [graph, setGraph] = useState(null)
  const [vectors, setVectors] = useState(null)
  const [loadingGraph, setLoadingGraph] = useState(false)
  const [loadingVec, setLoadingVec] = useState(false)
  const [err, setErr] = useState(null)

  useEffect(() => { ragStatus().then(setStatus).catch(() => setStatus(null)) }, [])

  const loadGraph = async () => {
    setLoadingGraph(true); setErr(null)
    try { setGraph(await getKnowledgeGraph(3)) }
    catch (e) { setErr(e.message) }
    finally { setLoadingGraph(false) }
  }
  const loadVectors = async () => {
    setLoadingVec(true); setErr(null)
    try { setVectors(await getVectorProjection()) }
    catch (e) { setErr(e.message) }
    finally { setLoadingVec(false) }
  }

  return (
    <PageWrapper>
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-6">
        <SettingsIcon size={22} className="text-aurora-indigo"
          style={{ filter: 'drop-shadow(0 0 8px rgba(129,140,248,0.6))' }} />
        <h1 className="text-2xl font-bold text-white tracking-tight">Settings & Data Explorer</h1>
      </div>

      {/* System status */}
      <Card className="mb-5">
        <h2 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <Server size={15} className="text-aurora-cyan" /> System Status
        </h2>
        {status ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <StatPill icon={Database} label="Storage backend" value={status.storage_backend === 'neo4j' ? 'Neo4j (graph)' : 'CSV fallback'} color="#22d3ee" />
            <StatPill icon={Network} label="Vector index" value={`${status.vector_index} ${status.vector_store_seeded ? '· seeded' : '· empty'}`} color="#818cf8" />
            <StatPill icon={Cpu} label="LLM provider" value={status.llm_provider === 'gemini' ? `Gemini (${status.llm_model})` : 'Templated fallback'} color="#f472b6" />
            <StatPill icon={Share2} label="Embeddings" value={(status.embedding_model || '').split('/').pop()} color="#34d399" />
          </div>
        ) : (
          <p className="text-sm text-muted">Backend status unavailable (is the API running?).</p>
        )}
      </Card>

      {err && <p className="text-danger text-sm mb-4">{err}</p>}

      {/* Knowledge Graph */}
      <Card className="mb-5">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Share2 size={15} className="text-aurora-indigo" />
            <h2 className="text-sm font-semibold text-white">Knowledge Graph</h2>
            {graph && (
              <span className="text-xs text-muted">
                · {graph.nodes.length} nodes shown ({Object.entries(graph.counts).filter(([, v]) => v).map(([k, v]) => `${v} ${k}`).join(', ')})
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={loadGraph} disabled={loadingGraph}>
              {loadingGraph ? <Spinner size="sm" /> : <Network size={14} />}
              {graph ? 'Refresh' : 'Visualize Knowledge Graph'}
            </Button>
            <a href="http://localhost:7474" target="_blank" rel="noreferrer">
              <Button size="sm" variant="ghost"><ExternalLink size={13} /> Neo4j Browser</Button>
            </a>
          </div>
        </div>
        <AnimatePresence mode="wait">
          {graph ? (
            <motion.div key="g" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <KnowledgeGraphViz nodes={graph.nodes} edges={graph.edges} />
            </motion.div>
          ) : (
            <div className="text-sm text-muted py-8 text-center">
              Click <strong className="text-white/70">Visualize Knowledge Graph</strong> to render the patient graph
              (Patient → Visit / Prediction / Report / Twin …). Hover a node for details.
            </div>
          )}
        </AnimatePresence>
      </Card>

      {/* Vector DB */}
      <Card>
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Database size={15} className="text-aurora-cyan" />
            <h2 className="text-sm font-semibold text-white">Vector Database</h2>
            {vectors && <span className="text-xs text-muted">· {vectors.count} chunks · {vectors.dim}-dim</span>}
          </div>
          <Button size="sm" onClick={loadVectors} disabled={loadingVec}>
            {loadingVec ? <Spinner size="sm" /> : <Database size={14} />}
            {vectors ? 'Refresh' : 'Visualize Vector DB'}
          </Button>
        </div>
        <AnimatePresence mode="wait">
          {vectors ? (
            <motion.div key="v" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <VectorDBViz data={vectors} />
            </motion.div>
          ) : (
            <div className="text-sm text-muted py-8 text-center">
              Click <strong className="text-white/70">Visualize Vector DB</strong> to plot the clinical knowledge
              embeddings (stored in the Neo4j vector index <code className="text-white/70">clinical_chunks</code>).
            </div>
          )}
        </AnimatePresence>
        <div className="text-xs text-muted mt-3 pt-3 border-t border-border space-y-1">
          <p>
            The vector store is <strong className="text-white/70">not a separate file</strong> — embeddings live inside
            Neo4j as <code>(:KnowledgeChunk)</code> nodes indexed by the native vector index <code>clinical_chunks</code>.
          </p>
          <p>
            On disk they persist in the Docker volume <code>alzheimer-prediction-system_neo4j_data</code> →
            <code>/data/databases/neo4j/neostore.propertystore.db.arrays</code> (the raw 384-float vectors) and the vector
            index under <code>/data/databases/neo4j/schema/index/</code>.
          </p>
          <p>
            Explore it in the <strong className="text-white/70">Neo4j Browser</strong> (<code>http://localhost:7474</code>,
            login <code>neo4j</code> / <code>password</code>):
            <code className="ml-1">MATCH (c:KnowledgeChunk) RETURN c</code>
          </p>
        </div>
      </Card>
    </PageWrapper>
  )
}
