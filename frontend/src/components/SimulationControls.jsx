export default function SimulationControls({ config, setConfig, running, onRun, onResetTimeline, onResetDatabase, historianSummary }) {
  const updateNumber = (field, value) => {
    setConfig((previous) => ({ ...previous, [field]: Number(value) }));
  };

  return (
    <section className="panel simulation-panel">
      <div className="section-title-row compact">
        <div>
          <p className="eyebrow">Simulation</p>
          <h2>Run settings</h2>
        </div>
        <div className="db-chip">Points: {historianSummary.points}</div>
      </div>

      <div className="form-grid">
        <label className="field">
          <span>Duration [h]</span>
          <input type="number" min="1" value={config.durationHours} onChange={(event) => updateNumber('durationHours', event.target.value)} />
        </label>
        <label className="field">
          <span>Step [h]</span>
          <input type="number" min="1" value={config.stepHours} onChange={(event) => updateNumber('stepHours', event.target.value)} />
        </label>
        <label className="field">
          <span>Temperature [C]</span>
          <input type="number" value={config.temperatureStressC} onChange={(event) => updateNumber('temperatureStressC', event.target.value)} />
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
        <label className="field">
          <span>Stochasticity</span>
          <input type="number" min="0" max="1" step="0.05" value={config.stochasticity} onChange={(event) => updateNumber('stochasticity', event.target.value)} />
        </label>
      </div>

      <div className="button-row">
        <button className="primary-button" type="button" disabled={running} onClick={onRun}>
          {running ? 'Running...' : 'Run timeline'}
        </button>
        <button className="secondary-button" type="button" disabled={running} onClick={onResetTimeline}>
          Clear chart
        </button>
        <button className="ghost-button" type="button" disabled={running} onClick={onResetDatabase}>
          Reset SQLite
        </button>
      </div>

      <div className="historian-note">
        <strong>Local history:</strong> generated points are stored in browser SQLite and persisted in local storage.
      </div>
    </section>
  );
}
