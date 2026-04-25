import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import { COMPONENT_LABELS } from '../data/modelState';
import { formatLabel } from '../services/formatters';

export default function TimelineChart({ chartData, axisTemplate, totalUsages, selectedComponentId, loading, error }) {
  const ticks = buildTicks(totalUsages);
  const data = chartData.length ? chartData : axisTemplate;
  const componentLabel = COMPONENT_LABELS[selectedComponentId] ?? formatLabel(selectedComponentId);

  return (
    <section className="panel chart-panel">
      <div className="section-title-row compact">
        <div>
          <p className="eyebrow">Runtime timeline</p>
          <h2>{componentLabel} health</h2>
        </div>
        <span className="axis-chip">Normalized axis</span>
      </div>

      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 18, right: 14, left: 6, bottom: 12 }}>
            <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="usage_count"
              type="number"
              domain={[0, totalUsages]}
              ticks={ticks}
              stroke="#6e7681"
              tick={{ fill: '#8b949e', fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: '#30363d' }}
              label={{ value: 'Usage count', position: 'insideBottom', offset: -2, fill: '#6e7681', fontSize: 11 }}
            />
            <YAxis
              domain={[0, 1]}
              ticks={[0, 0.25, 0.5, 0.75, 1]}
              stroke="#6e7681"
              tick={{ fill: '#8b949e', fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: '#30363d' }}
              width={34}
            />
            <Tooltip
              contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 10, color: '#c9d1d9', fontSize: 12 }}
              formatter={(value, name) => [typeof value === 'number' ? value.toFixed(3) : 'pending', name]}
              labelFormatter={(value) => `Usage = ${value}`}
            />
            <ReferenceLine y={0.4} stroke="#d29922" strokeDasharray="4 4" label={{ value: 'critical', fill: '#d29922', fontSize: 11 }} />
            <ReferenceLine y={0.15} stroke="#f85149" strokeDasharray="4 4" label={{ value: 'failed', fill: '#f85149', fontSize: 11 }} />
            <Line
              type="monotone"
              dataKey="health"
              name="Health index"
              stroke="#58a6ff"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
              strokeLinecap="round"
              strokeLinejoin="round"
              activeDot={{ r: 3, fill: '#58a6ff', stroke: '#0d1117', strokeWidth: 1 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {!loading && !error && !chartData.length ? <p className="muted chart-note">Run the simulation to render the health curve.</p> : null}
      {loading ? <p className="muted chart-note">Running backend simulation...</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
    </section>
  );
}

function buildTicks(totalUsages) {
  const divisions = 6;
  return Array.from({ length: divisions + 1 }, (_, index) => Math.round((totalUsages / divisions) * index));
}
