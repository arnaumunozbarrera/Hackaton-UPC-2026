import {
  CartesianGrid,
  Legend,
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

export default function TimelineChart({
  chartData,
  predictionCurve = [],
  axisTemplate,
  totalUsages,
  selectedComponentId,
  loading,
  loadingAiPrediction = false,
  aiPredictionError = '',
  error
}) {
  const data = mergeSeries(chartData.length ? chartData : axisTemplate, predictionCurve);
  const maxUsage = getMaxUsage(data, totalUsages);
  const domainMax = getDomainMax(maxUsage);
  const ticks = buildTicks(maxUsage);
  const componentLabel = COMPONENT_LABELS[selectedComponentId] ?? formatLabel(selectedComponentId);
  const renderUsageTick = (tickProps) => <UsageTick {...tickProps} maxUsage={maxUsage} />;

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
          <LineChart data={data} margin={{ top: 18, right: 38, left: 6, bottom: 12 }}>
            <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="usage_count"
              type="number"
              domain={[0, domainMax]}
              ticks={ticks}
              interval={0}
              stroke="#6e7681"
              tick={renderUsageTick}
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
              labelFormatter={(value) => `Usage = ${formatUsageValue(value)}`}
            />
            <Legend
              verticalAlign="top"
              align="right"
              wrapperStyle={{ color: '#8b949e', fontSize: 11, paddingBottom: 6 }}
            />
            <ReferenceLine y={0.4} stroke="#d29922" strokeDasharray="4 4" label={{ value: 'critical', position: 'insideTopLeft', fill: '#d29922', fontSize: 11 }} />
            <ReferenceLine y={0.15} stroke="#f85149" strokeDasharray="4 4" label={{ value: 'failed', position: 'insideTopLeft', fill: '#f85149', fontSize: 11 }} />
            <Line
              type="linear"
              dataKey="health"
              name="Mathematical model"
              stroke="#58a6ff"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
              strokeLinecap="round"
              strokeLinejoin="round"
              activeDot={{ r: 3, fill: '#58a6ff', stroke: '#0d1117', strokeWidth: 1 }}
            />
            <Line
              type="linear"
              dataKey="ai_health"
              name="AI prediction"
              stroke="#3fb950"
              strokeWidth={2}
              strokeDasharray="7 5"
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
              strokeLinecap="round"
              strokeLinejoin="round"
              activeDot={{ r: 3, fill: '#3fb950', stroke: '#0d1117', strokeWidth: 1 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {!loading && !error && !chartData.length ? <p className="muted chart-note">Run the simulation to render the health curve.</p> : null}
      {loading ? <p className="muted chart-note">Running backend simulation...</p> : null}
      {!loading && loadingAiPrediction ? <p className="muted chart-note">Loading AI prediction...</p> : null}
      {!loading && aiPredictionError ? <p className="error-text">{aiPredictionError}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
    </section>
  );
}

function mergeSeries(modelData, predictionCurve) {
  const pointsByUsage = new Map();

  for (const point of modelData) {
    const usageCount = Number(point.usage_count);
    if (!Number.isFinite(usageCount)) continue;
    pointsByUsage.set(toUsageKey(usageCount), {
      ...point,
      usage_count: usageCount
    });
  }

  for (const point of predictionCurve) {
    const usageCount = Number(point.usage_count);
    const aiHealth = Number(point.ai_health);
    if (!Number.isFinite(usageCount) || !Number.isFinite(aiHealth)) continue;
    const key = toUsageKey(usageCount);
    pointsByUsage.set(key, {
      ...(pointsByUsage.get(key) || { usage_count: usageCount }),
      usage_count: usageCount,
      ai_health: aiHealth
    });
  }

  return Array.from(pointsByUsage.values()).sort((first, second) => first.usage_count - second.usage_count);
}

function toUsageKey(value) {
  return Number(value).toFixed(6);
}

function UsageTick({ x, y, payload, maxUsage }) {
  const value = Number(payload.value);
  const isFirstTick = Math.abs(value) < 0.001;
  const isLastTick = Math.abs(value - maxUsage) < 0.001;
  const textAnchor = isFirstTick ? 'start' : isLastTick ? 'end' : 'middle';

  return (
    <text x={x} y={y} dy={16} textAnchor={textAnchor} fill="#8b949e" fontSize={11}>
      {formatUsageTick(value)}
    </text>
  );
}

function getMaxUsage(data, fallbackTotalUsages) {
  const usageValues = data
    .map((point) => Number(point.usage_count))
    .filter(Number.isFinite);
  const dataMaxUsage = usageValues.length ? Math.max(...usageValues) : 0;
  const fallbackUsage = Number(fallbackTotalUsages);
  const maxUsage = Math.max(
    dataMaxUsage,
    Number.isFinite(fallbackUsage) ? fallbackUsage : 0
  );

  return Number.isFinite(maxUsage) && maxUsage > 0 ? maxUsage : 1;
}

function buildTicks(maxUsage) {
  const divisions = 6;
  const ticks = Array.from({ length: divisions + 1 }, (_, index) => normalizeUsageTick((maxUsage / divisions) * index));
  ticks[ticks.length - 1] = normalizeUsageTick(maxUsage);
  return [...new Set(ticks)];
}

function getDomainMax(maxUsage) {
  return normalizeUsageTick(maxUsage * 1.04);
}

function normalizeUsageTick(value) {
  return Number(Number(value).toFixed(2));
}

function formatUsageValue(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return value;
  return numericValue.toLocaleString(undefined, {
    maximumFractionDigits: 2
  });
}

function formatUsageTick(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return value;
  if (Math.abs(numericValue) < 1000) return formatUsageValue(numericValue);

  const compactValue = numericValue / 1000;
  return `${Number(compactValue.toFixed(1)).toLocaleString(undefined, { maximumFractionDigits: 1 })}k`;
}
