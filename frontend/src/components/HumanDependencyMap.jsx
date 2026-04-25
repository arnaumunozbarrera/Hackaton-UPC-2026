import { COMPONENT_LABELS } from '../data/modelState';
import { formatLabel } from '../services/formatters';

export default function HumanDependencyMap({ selectedComponentId, dependencies }) {
  const related = (dependencies || []).filter(
    (item) => item.source === selectedComponentId || item.target === selectedComponentId
  );

  if (!related.length) {
    return (
      <section className="panel human-map-panel">
        <div className="section-title-row compact">
          <div>
            <p className="eyebrow">Dependencies</p>
            <h2>Impact map</h2>
          </div>
        </div>
        <p className="muted">Run the simulation to load natural-language dependency impacts.</p>
      </section>
    );
  }

  return (
    <section className="panel human-map-panel">
      <div className="section-title-row compact">
        <div>
          <p className="eyebrow">Dependencies</p>
          <h2>Impact map</h2>
        </div>
      </div>

      <div className="dependency-list">
        {related.map((item) => (
          <article key={`${item.source}-${item.target}`} className="dependency-card">
            <div className="dependency-header">
              <span>{COMPONENT_LABELS[item.source] ?? formatLabel(item.source)}</span>
              <span className="arrow">causes risk on</span>
              <span>{COMPONENT_LABELS[item.target] ?? formatLabel(item.target)}</span>
              <strong className={`level ${item.impact.toLowerCase()}`}>{item.impact}</strong>
            </div>
            <p>{item.description}</p>
            <div className="action-line">
              <strong>Interpretation:</strong> monitor this dependency when reviewing the selected component trend.
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
