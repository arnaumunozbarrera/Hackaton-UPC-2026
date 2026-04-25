import { useEffect, useMemo, useRef, useState } from 'react';
import ComponentSelector from './components/ComponentSelector';
import HealthSummary from './components/HealthSummary';
import HumanDependencyMap from './components/HumanDependencyMap';
import PredictionPanel from './components/PredictionPanel';
import Printer3DModel from './components/Printer3DModel';
import SimulationControls from './components/SimulationControls';
import TimelineChart from './components/TimelineChart';
import { DEFAULT_SIMULATION_CONFIG } from './data/defaultConfig';
import { fetchLatestModelState, fetchPrediction, saveLatestModelState } from './services/modelApi';
import { buildEmptyAxis, simulateNextPoint } from './services/simulationApi';
import { createRun, getHistorianSummary, resetHistorian, saveModelSnapshot, saveTimelinePoint } from './services/historianApi';

export default function App() {
  const [modelState, setModelState] = useState(null);
  const [selectedComponentId, setSelectedComponentId] = useState('heating_elements');
  const [config, setConfig] = useState(DEFAULT_SIMULATION_CONFIG);
  const [axisData, setAxisData] = useState(() => buildEmptyAxis(DEFAULT_SIMULATION_CONFIG.durationHours, DEFAULT_SIMULATION_CONFIG.stepHours));
  const [running, setRunning] = useState(false);
  const [prediction, setPrediction] = useState(null);
  const [historianSummary, setHistorianSummary] = useState({ runs: 0, points: 0, lastRun: null });
  const timerRef = useRef(null);
  const runTokenRef = useRef(0);

  useEffect(() => {
    let mounted = true;

    async function load() {
      const latest = await fetchLatestModelState();
      await saveModelSnapshotSafely(latest);
      const summary = await getHistorianSummarySafely();

      if (mounted) {
        setModelState(latest);
        setHistorianSummary(summary);
      }
    }

    load();

    return () => {
      mounted = false;
      cancelTimelineRun();
    };
  }, []);

  useEffect(() => {
    setAxisData(buildEmptyAxis(config.durationHours, config.stepHours));
    setPrediction(null);
  }, [config.durationHours, config.stepHours, selectedComponentId]);

  const latestPoint = useMemo(() => {
    const populated = axisData.filter((point) => typeof point.health === 'number');
    return populated[populated.length - 1] || null;
  }, [axisData]);

  function cancelTimelineRun() {
    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    runTokenRef.current += 1;
  }

  function waitForTimelineStep() {
    if (import.meta.env.MODE === 'test') {
      return Promise.resolve();
    }

    return new Promise((resolve) => {
      timerRef.current = window.setTimeout(() => {
        timerRef.current = null;
        resolve();
      }, 140);
    });
  }

  async function runTimeline() {
    if (!modelState || running) return;

    cancelTimelineRun();
    const normalizedConfig = sanitizeSimulationConfig(config);
    const component = modelState.components[selectedComponentId];

    if (!component || !normalizedConfig) {
      setRunning(false);
      setPrediction(null);
      setAxisData(buildEmptyAxis(DEFAULT_SIMULATION_CONFIG.durationHours, DEFAULT_SIMULATION_CONFIG.stepHours));
      return;
    }

    setRunning(true);
    setPrediction(null);
    setAxisData(buildEmptyAxis(normalizedConfig.durationHours, normalizedConfig.stepHours));

    const fallbackRunId = `run_local_${Date.now()}`;
    const runToken = ++runTokenRef.current;
    const runId = await createRunSafely({
      componentId: selectedComponentId,
      config: normalizedConfig,
      fallbackRunId
    });
    let currentHealth = latestPoint?.health ?? component.health;
    const maxSteps = Math.max(1, Math.floor(normalizedConfig.durationHours / normalizedConfig.stepHours));

    try {
      for (let stepIndex = 0; stepIndex <= maxSteps; stepIndex += 1) {
        if (runTokenRef.current !== runToken) return;

        const point = simulateNextPoint({
          componentId: selectedComponentId,
          previousHealth: currentHealth,
          config: normalizedConfig,
          stepIndex,
          runId
        });

        currentHealth = point.health;
        setAxisData((previous) => {
          const next = previous.length ? [...previous] : buildEmptyAxis(normalizedConfig.durationHours, normalizedConfig.stepHours);
          next[stepIndex] = { ...next[stepIndex], ...point };
          return next;
        });
        await saveTimelinePointSafely(point);
        if (runTokenRef.current !== runToken) return;

        const stop = point.status === 'FAILED' || stepIndex === maxSteps;

        if (stop) {
          runTokenRef.current = 0;

          const updatedState = patchModelStateWithLatestPoint(modelState, selectedComponentId, point);
          await saveLatestModelState(updatedState);
          await saveModelSnapshotSafely(updatedState);
          setModelState(updatedState);

          const predictionResult = await fetchPrediction(selectedComponentId, updatedState, point);
          setPrediction(predictionResult);

          const summary = await getHistorianSummarySafely();
          setHistorianSummary(summary);
          return;
        }

        await waitForTimelineStep();
      }
    } catch (error) {
      console.error('Failed to generate timeline.', error);
    } finally {
      if (runTokenRef.current === 0 || runTokenRef.current === runToken) {
        setRunning(false);
      }
    }
  }

  function clearChart() {
    cancelTimelineRun();
    setRunning(false);
    setPrediction(null);
    setAxisData(buildEmptyAxis(config.durationHours, config.stepHours));
  }

  async function clearDatabase() {
    cancelTimelineRun();
    setRunning(false);
    setPrediction(null);
    await resetHistorian();
    const latest = await fetchLatestModelState();
    await saveModelSnapshotSafely(latest);
    setModelState(latest);
    setAxisData(buildEmptyAxis(config.durationHours, config.stepHours));
    setHistorianSummary(await getHistorianSummarySafely());
  }

  if (!modelState) {
    return <div className="loading-screen">Loading system data...</div>;
  }

  return (
    <main className="app-shell">
      <header className="top-bar">
        <div>
          <p className="eyebrow">System monitor</p>
          <h1>Component health overview</h1>
        </div>
        <ComponentSelector
          modelState={modelState}
          selectedComponentId={selectedComponentId}
          onChange={(id) => {
            setSelectedComponentId(id);
            setPrediction(null);
          }}
        />
      </header>

      <section className="summary-strip">
        <div>
          <span>Overall machine health</span>
          <strong>{Math.round(modelState.machine_state.overall_health * 100)}%</strong>
        </div>
        <div>
          <span>Overall status</span>
          <strong>{modelState.machine_state.overall_status}</strong>
        </div>
        <div>
          <span>Critical components</span>
          <strong>{modelState.machine_state.critical_components.length}</strong>
        </div>
        <div>
          <span>Failed components</span>
          <strong>{modelState.machine_state.failed_components.length}</strong>
        </div>
      </section>

      <section className="main-grid">
        <SimulationControls
          config={config}
          setConfig={setConfig}
          running={running}
          onRun={runTimeline}
          onResetTimeline={clearChart}
          onResetDatabase={clearDatabase}
          historianSummary={historianSummary}
        />
        <TimelineChart axisData={axisData} durationHours={config.durationHours} selectedComponentId={selectedComponentId} />
      </section>

      <Printer3DModel
        selectedComponentId={selectedComponentId}
        onSelect={setSelectedComponentId}
      />

      <section className="bottom-grid">
        <HealthSummary modelState={modelState} selectedComponentId={selectedComponentId} latestPoint={latestPoint} />
        <PredictionPanel prediction={prediction} />
      </section>

      <HumanDependencyMap selectedComponentId={selectedComponentId} />
    </main>
  );
}

async function createRunSafely({ componentId, config, fallbackRunId }) {
  try {
    return await createRun({ componentId, config });
  } catch (error) {
    console.error('Failed to persist simulation run metadata.', error);
    return fallbackRunId;
  }
}

async function saveTimelinePointSafely(point) {
  try {
    await saveTimelinePoint(point);
  } catch (error) {
    console.error('Failed to persist timeline point.', error);
  }
}

async function saveModelSnapshotSafely(modelState) {
  try {
    await saveModelSnapshot(modelState);
  } catch (error) {
    console.error('Failed to persist model snapshot.', error);
  }
}

async function getHistorianSummarySafely() {
  try {
    return await getHistorianSummary();
  } catch (error) {
    console.error('Failed to load historian summary.', error);
    return { runs: 0, points: 0, lastRun: null };
  }
}

function patchModelStateWithLatestPoint(modelState, componentId, point) {
  const updated = JSON.parse(JSON.stringify(modelState));
  const component = updated.components[componentId];

  component.health = point.health;
  component.status = point.status;
  component.damage.total = point.damage;

  updated.machine_state.overall_health = Number(
    (
      Object.values(updated.components).reduce((sum, item) => sum + item.health, 0) /
      Object.values(updated.components).length
    ).toFixed(4)
  );

  updated.machine_state.critical_components = Object.entries(updated.components)
    .filter(([, item]) => item.status === 'CRITICAL')
    .map(([id]) => id);

  updated.machine_state.failed_components = Object.entries(updated.components)
    .filter(([, item]) => item.status === 'FAILED')
    .map(([id]) => id);

  if (updated.machine_state.failed_components.length > 0) {
    updated.machine_state.overall_status = 'FAILED';
  } else if (updated.machine_state.critical_components.length > 0) {
    updated.machine_state.overall_status = 'CRITICAL';
  } else if (updated.machine_state.overall_health < 0.85) {
    updated.machine_state.overall_status = 'DEGRADED';
  } else {
    updated.machine_state.overall_status = 'FUNCTIONAL';
  }

  return updated;
}

function sanitizeSimulationConfig(config) {
  const durationHours = Number(config.durationHours);
  const stepHours = Number(config.stepHours);

  if (!Number.isFinite(durationHours) || !Number.isFinite(stepHours) || durationHours <= 0 || stepHours <= 0) {
    console.error('Invalid simulation configuration.', config);
    return null;
  }

  return {
    ...config,
    durationHours,
    stepHours,
    temperatureStressC: finiteOrDefault(config.temperatureStressC, DEFAULT_SIMULATION_CONFIG.temperatureStressC),
    humidity: finiteOrDefault(config.humidity, DEFAULT_SIMULATION_CONFIG.humidity),
    contamination: finiteOrDefault(config.contamination, DEFAULT_SIMULATION_CONFIG.contamination),
    operationalLoad: finiteOrDefault(config.operationalLoad, DEFAULT_SIMULATION_CONFIG.operationalLoad),
    maintenanceLevel: finiteOrDefault(config.maintenanceLevel, DEFAULT_SIMULATION_CONFIG.maintenanceLevel),
    stochasticity: finiteOrDefault(config.stochasticity, DEFAULT_SIMULATION_CONFIG.stochasticity)
  };
}

function finiteOrDefault(value, defaultValue) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : defaultValue;
}
