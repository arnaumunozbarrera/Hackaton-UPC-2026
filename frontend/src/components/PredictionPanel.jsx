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
        <span className={`status-pill ${prediction.predicted_status.toLowerCase()}`}>{prediction.predicted_status}</span>
      </div>

      <div className="prediction-grid">
        <div>
          <span>Predicted failure timestamp</span>
          <strong>{prediction.predicted_failure_timestamp}</strong>
        </div>
        <div>
          <span>Confidence</span>
          <strong>{Math.round(prediction.confidence * 100)}%</strong>
        </div>
      </div>

      <h3>Suggested actions</h3>
      <ul className="measure-list">
        {prediction.recommended_measures.map((measure) => (
          <li key={measure}>{measure}</li>
        ))}
      </ul>

      <h3>Affected dependencies</h3>
      <div className="dependency-tags">
        {prediction.affected_dependencies.map((dependencyId) => (
          <span key={dependencyId}>{COMPONENT_LABELS[dependencyId]}</span>
        ))}
      </div>

      <div className="evidence-box">
        <strong>Evidence:</strong> {prediction.evidence.timestamp}, health {prediction.evidence.health.toFixed(3)}, status {prediction.evidence.status}
      </div>
    </section>
  );
}
