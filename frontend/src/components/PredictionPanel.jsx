import { COMPONENT_LABELS } from '../data/modelState';

export default function PredictionPanel({ prediction }) {
  if (!prediction) {
    return (
      <section className="panel prediction-panel empty">
        <p className="eyebrow">Prediction</p>
        <h2>No forecast yet</h2>
        <p className="muted">Run the timeline to generate an updated estimate.</p>
      </section>
    );
  }

  return (
    <section className="panel prediction-panel">
      <div className="section-title-row compact">
        <div>
          <p className="eyebrow">Prediction</p>
          <h2>{COMPONENT_LABELS[prediction.component_id]}</h2>
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

      <h3>Suggested actions</h3>
      <ul className="measure-list">
        {(prediction.recommended_measures || [prediction.reason || 'No recommendation available.']).map((measure) => (
          <li key={measure}>{measure}</li>
        ))}
      </ul>

      <h3>Affected dependencies</h3>
      <div className="dependency-tags">
        {(prediction.affected_dependencies || []).map((dependency) => (
          <span key={`${dependency.component_id}-${dependency.impact}`}>
            {COMPONENT_LABELS[dependency.component_id] || dependency.component_id} · {dependency.impact}
          </span>
        ))}
      </div>

      <div className="evidence-box">
        <strong>Evidence:</strong>{' '}
        {prediction.evidence
          ? `${prediction.evidence.timestamp}, usage ${prediction.evidence.usage_count ?? 'N/A'}, health ${prediction.evidence.health.toFixed(3)}, status ${prediction.evidence.status}`
          : prediction.reason || 'Not enough historical evidence.'}
      </div>
    </section>
  );
}
