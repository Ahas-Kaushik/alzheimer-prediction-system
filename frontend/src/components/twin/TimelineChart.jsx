import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer, Legend } from 'recharts'

const STAGE_BANDS = [
  { y1: 75, y2: 100, fill: '#22c55e22', label: 'Normal' },
  { y1: 45, y2: 75, fill: '#f59e0b22', label: 'MCI' },
  { y1: 0, y2: 45, fill: '#ef444422', label: 'AD' },
]

export default function TimelineChart({ data = [] }) {
  if (data.length === 0) {
    return <div className="h-48 flex items-center justify-center text-muted text-sm">No longitudinal data yet</div>
  }

  const chartData = data.map((d) => ({
    date: new Date(d.visit_date).toLocaleDateString(),
    cognitive_index: d.cognitive_index,
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#6b7280' }} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#6b7280' }} />
        <Tooltip
          contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8 }}
          labelStyle={{ color: '#f9fafb' }}
          itemStyle={{ color: '#6366f1' }}
        />
        <ReferenceLine y={75} stroke="#22c55e44" strokeDasharray="4 4" />
        <ReferenceLine y={45} stroke="#f59e0b44" strokeDasharray="4 4" />
        <Line
          type="monotone"
          dataKey="cognitive_index"
          stroke="#6366f1"
          strokeWidth={2}
          dot={{ fill: '#6366f1', r: 4 }}
          activeDot={{ r: 6 }}
          name="Cognitive Index"
        />
        <Legend wrapperStyle={{ fontSize: 12, color: '#6b7280' }} />
      </LineChart>
    </ResponsiveContainer>
  )
}
