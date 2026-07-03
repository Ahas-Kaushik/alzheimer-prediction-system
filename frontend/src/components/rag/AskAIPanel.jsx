import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles, Send, BookOpen, Cpu, FileText } from 'lucide-react'
import Card from '../ui/Card'
import Button from '../ui/Button'
import Spinner from '../ui/Spinner'
import { askAI, explainPrediction } from '../../api/ragApi'

const SUGGESTIONS = [
  'Why is this patient at this stage?',
  'What should we monitor going forward?',
  'Which medications are appropriate?',
  'What do the blood biomarkers indicate?',
]

/**
 * GraphRAG "Ask AI" panel — asks questions grounded in the patient's Neo4j
 * knowledge-graph facts + vector-retrieved clinical guidelines (Gemini or a
 * templated fallback). Shown on the Patient profile.
 */
export default function AskAIPanel({ patientId }) {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const run = async (fn) => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      setResult(await fn())
    } catch (e) {
      setError(e.message || 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  const handleAsk = (q) => {
    const query = (q ?? question).trim()
    if (!query) return
    if (q) setQuestion(q)
    run(() => askAI(patientId, query))
  }

  return (
    <Card>
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={15} className="text-fuchsia-400" />
        <h3 className="text-sm font-semibold text-white">Ask AI about this patient</h3>
        <span className="text-xs text-muted ml-1">(GraphRAG · knowledge graph + guidelines)</span>
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          className="input flex-1"
          placeholder="Ask a clinical question about this patient…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
          disabled={loading}
        />
        <Button onClick={() => handleAsk()} disabled={loading || !question.trim()}>
          {loading ? <Spinner size="sm" /> : <Send size={14} />}
          Ask
        </Button>
      </div>

      {/* Quick actions */}
      <div className="flex flex-wrap gap-2 mt-3">
        <Button variant="ghost" size="sm" onClick={() => run(() => explainPrediction(patientId))} disabled={loading}>
          <BookOpen size={13} /> Explain latest prediction
        </Button>
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => handleAsk(s)}
            disabled={loading}
            className="text-xs px-2.5 py-1 rounded-full text-muted hover:text-white transition-colors disabled:opacity-40"
            style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}
          >
            {s}
          </button>
        ))}
      </div>

      {error && <p className="text-danger text-sm mt-3">{error}</p>}

      {/* Answer */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-4 rounded-lg p-4"
            style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}
          >
            <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{result.answer}</p>

            <div className="flex items-center gap-2 mt-3 flex-wrap">
              <span
                className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                style={{
                  background: result.used_llm ? 'rgba(217,70,239,0.15)' : 'rgba(107,114,128,0.15)',
                  border: `1px solid ${result.used_llm ? 'rgba(217,70,239,0.35)' : 'rgba(107,114,128,0.3)'}`,
                  color: result.used_llm ? '#e879f9' : '#9ca3af',
                }}
              >
                <Cpu size={11} /> {result.used_llm ? 'Gemini' : 'Templated'}
              </span>
              {result.sources?.map((s) => (
                <span key={s.title} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full text-muted"
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <FileText size={10} /> {s.title}
                  {typeof s.score === 'number' && <span className="font-mono text-white/50">{s.score}</span>}
                </span>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  )
}
