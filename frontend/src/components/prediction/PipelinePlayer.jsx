/**
 * PipelinePlayer — lightweight animated indicator for the multimodal pipeline.
 *
 * This is intentionally a *background* progress animation, not a gated step the
 * user must wait out. The parent shows it only while the request is in flight
 * (`running`) and unmounts it the instant real results arrive — so it never
 * blocks or delays the results.
 */
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Brain, Sparkles, Layers, GitMerge, Activity, Cpu, Network, Boxes,
} from 'lucide-react'

const STAGES = [
  { key: 'mri',   icon: Brain,    title: 'Loading Brain MRI',              data: 'T1-weighted · 256×256' },
  { key: 'pet',   icon: Sparkles, title: 'Synthesizing PET (GAN)',         data: 'MRI → FDG-PET' },
  { key: 'feats', icon: Layers,   title: 'Extracting Deep Features',       data: 'ResNet-18 → 512-d ×2' },
  { key: 'fuse',  icon: GitMerge, title: 'Fusing Multimodal Vector',       data: 'MRI + PET + clinical + cognitive' },
  { key: 'bio',   icon: Activity, title: 'Biomarker & Cognitive Analysis', data: 'ATN markers · cognitive index' },
  { key: 'clf',   icon: Cpu,      title: 'Neural Classifier Inference',    data: 'MLP → Normal / MCI / AD' },
  { key: 'kg',    icon: Network,  title: 'Knowledge Graph Reasoning',      data: 'medication rules' },
  { key: 'twin',  icon: Boxes,    title: 'Generating Digital Twin',        data: 'per-region severity map' },
]

const ADVANCE_MS = 600

export default function PipelinePlayer() {
  const [active, setActive] = useState(0)

  // Cycle through the stages; once at the last stage, keep it "processing".
  useEffect(() => {
    const id = setInterval(() => {
      setActive((i) => Math.min(i + 1, STAGES.length - 1))
    }, ADVANCE_MS)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="relative overflow-hidden rounded-card border border-indigo-500/40 bg-gradient-to-br from-slate-900 via-[#0c1222] to-indigo-950/60 px-5 py-6 shadow-xl shadow-indigo-950/40">
      {/* moving shimmer for a subtle "processing" feel */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 bg-gradient-to-r from-transparent via-indigo-400/10 to-transparent"
        animate={{ x: ['0%', '450%'] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: 'linear' }}
      />

      <div className="relative flex items-center gap-2.5 mb-5">
        <span className="relative flex h-3 w-3">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-400" />
        </span>
        <h3 className="text-base font-semibold text-white">Running Multimodal Pipeline…</h3>
        <span className="ml-auto text-xs text-indigo-300/80">this runs in the background</span>
      </div>

      {/* Pipeline rail */}
      <div className="relative">
        <div className="absolute left-[23px] top-5 bottom-5 w-0.5 bg-white/10" />
        <motion.div
          className="absolute left-[23px] top-5 w-0.5 bg-gradient-to-b from-indigo-400 to-emerald-400"
          initial={{ height: 0 }}
          animate={{ height: `${(active / (STAGES.length - 1)) * 100}%` }}
          transition={{ ease: 'easeOut', duration: 0.4 }}
          style={{ maxHeight: 'calc(100% - 2.5rem)' }}
        />

        <div className="space-y-1">
          {STAGES.map((s, i) => {
            const Icon = s.icon
            const state = i < active ? 'done' : i === active ? 'active' : 'pending'
            return (
              <div key={s.key} className="relative flex items-center gap-4 py-1.5">
                <div className="relative z-10 shrink-0">
                  <motion.div
                    animate={
                      state === 'active'
                        ? { scale: [1, 1.15, 1] }
                        : { scale: 1 }
                    }
                    transition={{ repeat: state === 'active' ? Infinity : 0, duration: 1 }}
                    className={`flex items-center justify-center w-12 h-12 rounded-full border-2 transition-colors ${
                      state === 'done'
                        ? 'bg-emerald-500/20 border-emerald-400 text-emerald-300'
                        : state === 'active'
                        ? 'bg-indigo-500/25 border-indigo-400 text-indigo-200 shadow-lg shadow-indigo-500/30'
                        : 'bg-white/5 border-white/15 text-slate-500'
                    }`}
                  >
                    <Icon size={20} />
                  </motion.div>
                </div>

                <div className="min-w-0 flex-1">
                  <p className={`text-sm font-semibold transition-colors ${
                    state === 'pending' ? 'text-slate-500' : 'text-white'
                  }`}>
                    {s.title}
                  </p>
                  {state !== 'pending' && (
                    <p className="text-xs text-indigo-200/70 font-mono truncate">{s.data}</p>
                  )}
                </div>

                {state === 'active' && (
                  <span className="text-xs font-medium text-indigo-300 shrink-0 animate-pulse">processing…</span>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
