import MetricCard from './MetricCard';
import { COMPONENT_LABELS, SUBSYSTEM_LABELS } from '../data/modelState';
import { formatLabel, formatMetricValue } from '../services/formatters';

export default function HealthSummary({ modelState, selectedComponentId, latestPoint }) {
  const component = modelState.components[selectedComponentId];
  const health = latestPoint?.health ?? component.health;
  const status = latestPoint?.status ?? component.status;
  const damage = latestPoint?.damage ?? component.damage.total;

  return (
    <section className="panel component-summary">
      <div className="section-title-row">
        <div>
          <p className="eyebrow">Selected subsystem</p>
          <h2>{COMPONENT_LABELS[selectedComponentId]}</h2>
          <p className="muted">{SUBSYSTEM_LABELS[component.subsystem]}</p>
        </div>
        <span className={`status-pill ${status.toLowerCase()}`}>{status}</span>
      </div>

      <div className="health-bar-block">
        <div className="health-header">
          <span>Health index</span>
          <strong>{Math.round(health * 100)}%</strong>
        </div>
        <div className="health-track">
          <div className="health-fill" style={{ width: `${Math.round(health * 100)}%` }} />
        </div>
      </div>

      <div className="metrics-grid three">
        <MetricCard label="Machine health" value={`${Math.round(modelState.machine_state.overall_health * 100)}%`} helper={modelState.machine_state.overall_status} />
        <MetricCard label="Component damage" value={`${Math.round(damage * 100)}%`} helper="Accumulated degradation" />
        <MetricCard label="Alerts" value={component.alerts.length} helper="Reported by model" />
      </div>

      <div className="data-grid two-columns">
        <div>
          <h3>Damage breakdown</h3>
          <div className="key-value-list">
            {Object.entries(component.damage).map(([key, value]) => (
              <div key={key} className="key-value-row">
                <span>{formatLabel(key)}</span>
                <strong>{formatMetricValue(value)}</strong>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3>Model metrics</h3>
          <div className="key-value-list">
            {Object.entries(component.metrics).map(([key, value]) => (
              <div key={key} className="key-value-row">
                <span>{formatLabel(key)}</span>
                <strong>{formatMetricValue(value)}</strong>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
