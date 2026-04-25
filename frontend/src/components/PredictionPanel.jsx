import './PredictionPanel.css';
import { COMPONENT_LABELS } from '../data/modelState';
import { formatLabel } from '../services/formatters';

export default function PredictionPanel({ prediction, className = '' }) {
  if (!prediction) {
    return (
      <section className={`panel prediction-panel empty ${className}`.trim()}>
        <p className="eyebrow">Prediction</p>
        <h2>No forecast yet</h2>
        <p className="muted">Run the timeline to generate an updated estimate.</p>
      </section>
    );
  }
  const componentLabel = COMPONENT_LABELS[prediction.component_id] ?? formatLabel(prediction.component_id);
  const modelLabel = prediction.model_family
    ? prediction.model_family.replaceAll('_', ' ')
    : 'linear trend';
  const topFactors = prediction.explanation?.top_factors ?? [];

  return (
    <section className={`panel prediction-panel ${className}`.trim()}>
      <div className="section-title-row compact">
        <div>
          <p className="eyebrow">Predictions</p>
          <h2>{componentLabel}</h2>
        </div>
        <span className="axis-chip">Confidence {Math.round((prediction.confidence || 0) * 100)}%</span>
      </div>

      <div className="prediction-grid">
        <div>
          <span>Predicted failure usage</span>
          <strong>{prediction.predicted_failure_usage ?? (prediction.reason || 'Unavailable')}</strong>
        </div>
        <div>
          <span>Predicted timestamp</span>
          <strong>{prediction.predicted_failure_timestamp || 'Usage-based estimate'}</strong>
        </div>
      </div>

      <div className="evidence-box">
        <strong>Evidence:</strong>{' '}
        {prediction.evidence
          ? `${prediction.evidence.timestamp}, usage ${prediction.evidence.usage_count ?? 'N/A'}, health ${prediction.evidence.health.toFixed(3)}, status ${prediction.evidence.status}`
          : prediction.reason || 'Not enough historical evidence.'}
        <br />
        <strong>Method:</strong> {modelLabel}
        {topFactors.length > 0 ? (
          <>
            <br />
            <strong>Top factors:</strong>{' '}
            {topFactors.map((factor) => formatLabel(factor.name)).join(', ')}
          </>
        ) : null}
      </div>
    </section>
  );
}
