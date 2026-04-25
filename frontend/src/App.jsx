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
import {
  createRun,
  getHistorianSummary,
  resetHistorian,
  saveModelSnapshot,
  saveTimelinePoint
} from './services/historianApi';

const PRINTER_MODEL_URL = import.meta.env.VITE_PRINTER_MODEL_URL ?? null;

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
      await saveModelSnapshot(latest);
      const summary = await getHistorianSummary();

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

    const runId = await createRun({ componentId: selectedComponentId, config });
    const component = modelState.components[selectedComponentId];
    let currentHealth = latestPoint?.health ?? component.health;
    const maxSteps = Math.max(1, Math.floor(config.durationHours / config.stepHours));
    const runToken = ++runTokenRef.current;

    setRunning(true);
    setPrediction(null);
    setAxisData(buildEmptyAxis(config.durationHours, config.stepHours));

    for (let stepIndex = 0; stepIndex <= maxSteps; stepIndex += 1) {
      if (runTokenRef.current !== runToken) return;

      const point = simulateNextPoint({
        componentId: selectedComponentId,
        previousHealth: currentHealth,
        config,
        stepIndex,
        runId
      });

      currentHealth = point.health;
      await saveTimelinePoint(point);
      if (runTokenRef.current !== runToken) return;

      setAxisData((previous) => {
        const next = [...previous];
        next[stepIndex] = point;
        return next;
      });

      const stop = point.status === 'FAILED' || stepIndex === maxSteps;

      if (stop) {
        runTokenRef.current = 0;
        setRunning(false);

        const updatedState = patchModelStateWithLatestPoint(modelState, selectedComponentId, point);
        await saveLatestModelState(updatedState);
        await saveModelSnapshot(updatedState);
        setModelState(updatedState);

        const predictionResult = await fetchPrediction(selectedComponentId, updatedState, point);
        setPrediction(predictionResult);

        const summary = await getHistorianSummary();
        setHistorianSummary(summary);
        return;
      }

      await waitForTimelineStep();
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
    await saveModelSnapshot(latest);
    setAxisData(buildEmptyAxis(config.durationHours, config.stepHours));
    setHistorianSummary(await getHistorianSummary());
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
        modelUrl={PRINTER_MODEL_URL}
      />

      <section className="bottom-grid">
        <HealthSummary modelState={modelState} selectedComponentId={selectedComponentId} latestPoint={latestPoint} />
        <PredictionPanel prediction={prediction} />
      </section>

      <HumanDependencyMap selectedComponentId={selectedComponentId} />
    </main>
  );
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
