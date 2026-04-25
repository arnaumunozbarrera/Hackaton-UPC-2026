import { HUMAN_DEPENDENCIES } from '../data/dependencies';
import { COMPONENT_LABELS } from '../data/modelState';

export default function HumanDependencyMap({ selectedComponentId }) {
  const related = HUMAN_DEPENDENCIES.filter(
    (item) => item.source === selectedComponentId || item.target === selectedComponentId
  );

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
              <span>{COMPONENT_LABELS[item.source]}</span>
              <span className="arrow">causes risk on</span>
              <span>{COMPONENT_LABELS[item.target]}</span>
              <strong className={`level ${item.level.toLowerCase()}`}>{item.level}</strong>
            </div>
            <p>{item.sentence}</p>
            <div className="action-line">
              <strong>Operator action:</strong> {item.operatorAction}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
