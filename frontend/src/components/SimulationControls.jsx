export default function SimulationControls({ config, setConfig, running, onRun, historianSummary, error, className = '' }) {
  const updateNumber = (field, value) => {
    setConfig((previous) => ({ ...previous, [field]: Number(value) }));
  };

  return (
    <section className={`panel simulation-panel ${className}`.trim()}>
      <div className="section-title-row compact">
        <div>
          <p className="eyebrow">Simulation</p>
          <h2>Run settings</h2>
        </div>
        <div className="run-meta-row">
          <span className="db-chip">Run status: {historianSummary.status || 'Ready'}</span>
          <span className="db-chip">Progress: {historianSummary.progress || '0%'}</span>
          <span className="db-chip">Stored runs: {historianSummary.runs}</span>
        </div>
      </div>

      <div className="form-grid">
        <label className="field">
          <span>Total usages</span>
          <input type="number" min="1" value={config.totalUsages} onChange={(event) => updateNumber('totalUsages', event.target.value)} />
        </label>
        <label className="field">
          <span>Temperature [C]</span>
          <input type="number" value={config.temperatureC} onChange={(event) => updateNumber('temperatureC', event.target.value)} />
        </label>
        <label className="field">
          <span>Humidity</span>
          <input type="number" min="0" max="1" step="0.05" value={config.humidity} onChange={(event) => updateNumber('humidity', event.target.value)} />
        </label>
        <label className="field">
          <span>Contamination</span>
          <input type="number" min="0" max="1" step="0.05" value={config.contamination} onChange={(event) => updateNumber('contamination', event.target.value)} />
        </label>
        <label className="field">
          <span>Operational load</span>
          <input type="number" min="0" max="1" step="0.05" value={config.operationalLoad} onChange={(event) => updateNumber('operationalLoad', event.target.value)} />
        </label>
        <label className="field">
          <span>Maintenance</span>
          <input type="number" min="0" max="1" step="0.05" value={config.maintenanceLevel} onChange={(event) => updateNumber('maintenanceLevel', event.target.value)} />
        </label>
      </div>

      <div className="button-row">
        <button className="primary-button" type="button" disabled={running} onClick={onRun}>
          {running ? 'Running...' : 'Run timeline'}
        </button>
      </div>

      <div className="historian-note">
        <strong>SQLite historian:</strong> runs are stored by the Python backend and can be reloaded after refresh.
      </div>
      {error ? <div className="error-banner">{error}</div> : null}
    </section>
  );
}
