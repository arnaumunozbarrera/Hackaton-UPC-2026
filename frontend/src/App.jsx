import { useEffect, useMemo, useState } from 'react';
import ChatbotPanel from './components/ChatbotPanel';
import ComponentSelector from './components/ComponentSelector';
import HealthSummary from './components/HealthSummary';
import HumanDependencyMap from './components/HumanDependencyMap';
import MessagesPanel from './components/MessagesPanel';
import PredictionPanel from './components/PredictionPanel';
import Printer3DModel from './components/Printer3DModel';
import SimulationControls from './components/SimulationControls';
import TimelineChart from './components/TimelineChart';
import { HUMAN_DEPENDENCIES } from './data/dependencies';
import { DEFAULT_SIMULATION_CONFIG } from './data/defaultConfig';
import { getRunTimeline, listRuns } from './services/historianApi';
import { fetchRunMessages } from './services/messagesApi';
import { fetchAiPrediction, fetchCurrentModel, fetchPrediction } from './services/modelApi';
import { buildAxisTemplate, runSimulation } from './services/simulationApi';

const AI_COMPONENT_IDS = new Set([
  'cleaning_interface',
  'heating_elements',
  'insulation_panels',
  'linear_guide',
  'nozzle_plate',
  'recoater_blade',
  'recoater_drive_motor',
  'temperature_sensors',
  'thermal_firing_resistors'
]);

export default function App() {
  const [modelState, setModelState] = useState(null);
  const [selectedComponentId, setSelectedComponentId] = useState('heating_elements');
  const [config, setConfig] = useState(DEFAULT_SIMULATION_CONFIG);
  const [timeline, setTimeline] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [aiPrediction, setAiPrediction] = useState(null);
  const [loadingAiPrediction, setLoadingAiPrediction] = useState(false);
  const [aiPredictionError, setAiPredictionError] = useState('');
  const [messages, setMessages] = useState([]);
  const [dependencies, setDependencies] = useState([]);
  const [historianState, setHistorianState] = useState({ runs: [], latestRun: null });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    document.title = 'Component health index estimation';
  }, []);

  useEffect(() => {
    let active = true;

    async function loadSelectedComponentContext() {
      if (!timeline.length) return;
      const activeRunId = timeline[0]?.run_id || historianState.latestRun?.run_id;
      setDependencies(extractDependenciesFromTimeline(timeline, selectedComponentId));
      setAiPrediction(null);
      setAiPredictionError('');
      setLoadingAiPrediction(false);

      if (!activeRunId) {
        setPrediction(null);
        return;
      }

      try {
        const selectedPrediction = await fetchPrediction(activeRunId, selectedComponentId);
        if (active) {
          setPrediction(selectedPrediction);
        }
      } catch (predictionError) {
        if (active) {
          setPrediction(null);
        }
      }

      if (!AI_COMPONENT_IDS.has(selectedComponentId)) return;

      setLoadingAiPrediction(true);
      try {
        const selectedAiPrediction = await fetchAiPrediction(activeRunId, selectedComponentId);
        if (active) {
          setAiPrediction(selectedAiPrediction);
        }
      } catch (predictionError) {
        if (active) {
          setAiPredictionError(predictionError.message || 'AI prediction failed.');
        }
      } finally {
        if (active) {
          setLoadingAiPrediction(false);
        }
      }
    }

    loadSelectedComponentContext();
    return () => {
      active = false;
    };
  }, [selectedComponentId, timeline, historianState.latestRun?.run_id]);

  useEffect(() => {
    let active = true;

    async function loadInitialData() {
      try {
        const [currentModel, runsPayload] = await Promise.all([fetchCurrentModel(), listRuns()]);
        if (!active) return;

        const latestRun = selectInitialRun(runsPayload);
        setModelState(currentModel);
        setHistorianState({
          runs: runsPayload.runs || [],
          latestRun
        });

        if (!latestRun) return;
        setConfig(configFromRun(latestRun));

        const [latestTimeline, latestMessages] = await Promise.all([
          getRunTimeline(latestRun.run_id),
          fetchRunMessages(latestRun.run_id)
        ]);
        if (!active) return;

        const normalizedTimeline = normalizeTimelineForUi(latestTimeline);
        const latestSelectedComponent = latestRun.selected_component || 'heating_elements';
        setTimeline(normalizedTimeline);
        setMessages(latestMessages);
        setSelectedComponentId(latestSelectedComponent);
        setDependencies(extractDependenciesFromTimeline(normalizedTimeline, latestSelectedComponent));
        if (latestSelectedComponent) {
          const latestPrediction = await fetchPrediction(latestRun.run_id, latestSelectedComponent);
          if (!active) return;
          setPrediction(latestPrediction);
        }
      } catch (loadError) {
        if (!active) return;
        setError(loadError.message || 'Failed to load application data.');
      }
    }

    loadInitialData();
    return () => {
      active = false;
    };
  }, []);

  const latestOutput = timeline.length > 0 ? timeline[timeline.length - 1].model_output : modelState;
  const displayModelState = useMemo(
    () => mergeModelStates(modelState, latestOutput),
    [modelState, latestOutput]
  );

  const chartData = useMemo(() => {
    if (!timeline.length) return [];

    return timeline
      .map((point) => {
        const component = point.model_output?.components?.[selectedComponentId];
        if (!component) return null;
        return {
          usage_count: point.usage_count,
          health: component.health,
          status: component.status
        };
      })
      .filter(Boolean);
  }, [timeline, selectedComponentId]);
  const predictionCurve = useMemo(() => {
    const aiCurve = aiPrediction?.ai_prediction_curve ?? [];
    if (aiPrediction?.component_id !== selectedComponentId || !Array.isArray(aiCurve)) {
      return [];
    }

    return aiCurve
      .map((point) => ({
        usage_count: Number(point.usage_count),
        ai_health: Number(point.health)
      }))
      .filter((point) => Number.isFinite(point.usage_count) && Number.isFinite(point.ai_health));
  }, [aiPrediction, selectedComponentId]);

  const effectiveUsageStep = useMemo(
    () => getEffectiveUsageStep(config.totalUsages, config.usageStep),
    [config.totalUsages, config.usageStep]
  );
  const axisTemplate = useMemo(
    () => buildAxisTemplate(config.totalUsages, effectiveUsageStep),
    [config.totalUsages, effectiveUsageStep]
  );

  async function handleRunTimeline() {
    setLoading(true);
    setError('');
    setPrediction(null);
    setAiPrediction(null);
    setAiPredictionError('');
    setLoadingAiPrediction(false);
    setMessages([]);
    setDependencies([]);
    setTimeline([]);

    let payload;
    try {
      payload = toBackendSimulationConfig(config, selectedComponentId);
    } catch (configError) {
      setLoading(false);
      setError(configError.message);
      return;
    }

    try {
      const response = await runSimulation(payload);
      if (!response.timeline || response.timeline.length === 0) {
        throw new Error('Simulation returned no timeline points.');
      }
      const normalizedTimeline = normalizeTimelineForUi(response.timeline);

      const mappedData = normalizedTimeline.map((point) => {
        const component = point.model_output?.components?.[selectedComponentId];
        if (!component) {
          throw new Error('Selected component was not found in model output.');
        }
        return {
          usage_count: point.usage_count,
          health: component.health,
          status: component.status
        };
      });

      if (mappedData.length === 0) {
        throw new Error('Simulation returned no timeline points.');
      }

      setTimeline(normalizedTimeline);
      setPrediction(response.prediction || null);
      setMessages(response.messages || []);
      setDependencies(response.dependencies || []);
      setModelState(normalizedTimeline.at(-1).model_output);

      const runsPayload = await listRuns();
      setHistorianState({
        runs: runsPayload.runs || [],
        latestRun: runsPayload.latest_run || null
      });
    } catch (runError) {
      setError(runError.message || 'Simulation request failed.');
    } finally {
      setLoading(false);
    }
  }

  if (!modelState) {
    return <div className="loading-screen">{error || 'Loading system data...'}</div>;
  }

  return (
    <main className="app-shell">
      <header className="top-bar">
        <div>
          <p className="eyebrow">Digital twin backend connected</p>
          <h1>Component health index estimation</h1>
        </div>
        <ComponentSelector
          modelState={displayModelState}
          selectedComponentId={selectedComponentId}
          onChange={setSelectedComponentId}
        />
      </header>

      <section className="summary-strip">
        <div>
          <span>Overall machine health</span>
          <strong>{Math.round((displayModelState?.machine_state?.overall_health || 0) * 100)}%</strong>
        </div>
        <div>
          <span>Overall status</span>
          <strong>{displayModelState?.machine_state?.overall_status || 'UNKNOWN'}</strong>
        </div>
        <div>
          <span>Critical components</span>
          <strong>{displayModelState?.machine_state?.critical_components?.length || 0}</strong>
        </div>
        <div>
          <span>Stored runs</span>
          <strong>{historianState.runs.length}</strong>
        </div>
      </section>

      <section className="main-grid">
        <SimulationControls
          config={config}
          setConfig={setConfig}
          running={loading}
          onRun={handleRunTimeline}
          historianSummary={{
            runs: historianState.runs.length,
            points: timeline.length,
            lastRun: historianState.latestRun
          }}
          error={error}
        />
        <TimelineChart
          chartData={chartData}
          predictionCurve={predictionCurve}
          axisTemplate={axisTemplate}
          totalUsages={config.totalUsages}
          selectedComponentId={selectedComponentId}
          loading={loading}
          loadingAiPrediction={loadingAiPrediction}
          aiPredictionError={aiPredictionError}
          error={error}
        />
      </section>

      <Printer3DModel
        modelState={displayModelState}
        selectedComponentId={selectedComponentId}
        onSelect={setSelectedComponentId}
      />

      <section className="bottom-grid">
        <HealthSummary modelState={displayModelState} selectedComponentId={selectedComponentId} />
        <PredictionPanel prediction={aiPrediction || prediction} />
      </section>

      <section className="bottom-grid stacked-grid">
        <MessagesPanel messages={messages} />
        <HumanDependencyMap selectedComponentId={selectedComponentId} dependencies={dependencies} />
      </section>

      <section className="bottom-grid full-width-grid">
        <ChatbotPanel
          runId={historianState.latestRun?.run_id || null}
          selectedComponentId={selectedComponentId}
          disabled={!historianState.latestRun?.run_id}
        />
      </section>
    </main>
  );
}

function toBackendSimulationConfig(config, selectedComponentId) {
  const totalUsages = Number(config.totalUsages);
  const temperatureC = Number(config.temperatureC);
  const humidity = Number(config.humidity);
  const contamination = Number(config.contamination);
  const operationalLoad = Number(config.operationalLoad);
  const maintenanceLevel = Number(config.maintenanceLevel);
  const stochasticity = getFiniteNumber(config.stochasticity, DEFAULT_SIMULATION_CONFIG.stochasticity);
  const seed = getFiniteNumber(config.seed, DEFAULT_SIMULATION_CONFIG.seed);
  const scenarioId = String(config.scenarioId || DEFAULT_SIMULATION_CONFIG.scenarioId || '').trim();

  if (!Number.isFinite(totalUsages) || totalUsages <= 0) {
    throw new Error('Invalid simulation config: total_usages must be greater than 0.');
  }
  if (!scenarioId) {
    throw new Error('Invalid simulation config: scenario_id is required.');
  }

  const usageStep = getEffectiveUsageStep(totalUsages, config.usageStep);

  return {
    run_id: `run_${Date.now()}`,
    scenario_id: scenarioId,
    total_usages: totalUsages,
    usage_step: usageStep,
    initial_conditions: {
      temperature_c: temperatureC,
      humidity,
      contamination,
      operational_load: operationalLoad,
      maintenance_level: maintenanceLevel,
      stochasticity
    },
    selected_component: selectedComponentId,
    seed
  };
}

function selectInitialRun(runsPayload) {
  const runs = runsPayload?.runs || [];
  const defaultTotalUsages = Number(DEFAULT_SIMULATION_CONFIG.totalUsages);
  const completeRun = runs.find((run) => Number(run.total_usages) >= defaultTotalUsages);

  return completeRun || runsPayload?.latest_run || null;
}

function configFromRun(run) {
  const rawConfig = run?.config || {};
  const initialConditions = rawConfig.initial_conditions || {};

  return {
    ...DEFAULT_SIMULATION_CONFIG,
    scenarioId: rawConfig.scenario_id || run?.scenario_id || DEFAULT_SIMULATION_CONFIG.scenarioId,
    totalUsages: getFiniteNumber(
      rawConfig.total_usages ?? run?.total_usages,
      DEFAULT_SIMULATION_CONFIG.totalUsages
    ),
    usageStep: getFiniteNumber(
      rawConfig.usage_step ?? run?.usage_step,
      DEFAULT_SIMULATION_CONFIG.usageStep
    ),
    temperatureC: getFiniteNumber(
      initialConditions.temperature_c,
      DEFAULT_SIMULATION_CONFIG.temperatureC
    ),
    humidity: getFiniteNumber(initialConditions.humidity, DEFAULT_SIMULATION_CONFIG.humidity),
    contamination: getFiniteNumber(
      initialConditions.contamination,
      DEFAULT_SIMULATION_CONFIG.contamination
    ),
    operationalLoad: getFiniteNumber(
      initialConditions.operational_load,
      DEFAULT_SIMULATION_CONFIG.operationalLoad
    ),
    maintenanceLevel: getFiniteNumber(
      initialConditions.maintenance_level,
      DEFAULT_SIMULATION_CONFIG.maintenanceLevel
    ),
    stochasticity: getFiniteNumber(initialConditions.stochasticity, DEFAULT_SIMULATION_CONFIG.stochasticity),
    seed: getFiniteNumber(rawConfig.seed, DEFAULT_SIMULATION_CONFIG.seed)
  };
}

function getFiniteNumber(value, fallback) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : fallback;
}

function getEffectiveUsageStep(totalUsages, configuredUsageStep) {
  const total = Number(totalUsages);
  const configuredStep = Number(configuredUsageStep);
  const defaultStep = Number(DEFAULT_SIMULATION_CONFIG.usageStep);
  const usageStep = Number.isFinite(configuredStep) && configuredStep > 0 ? configuredStep : defaultStep;
  const positiveUsageStep = Math.max(1, usageStep);

  if (!Number.isFinite(total) || total <= 0) {
    return positiveUsageStep;
  }

  return Math.max(1, Math.min(positiveUsageStep, total));
}

function extractDependenciesFromTimeline(timeline, selectedComponentId) {
  if (!timeline?.length) return [];
  const finalPoint = timeline[timeline.length - 1];
  const components = finalPoint.model_output?.components || {};
  if (!components[selectedComponentId]) return [];
  return HUMAN_DEPENDENCIES.filter(
    (dependency) => dependency.source === selectedComponentId || dependency.target === selectedComponentId
  );
}

function normalizeTimelineForUi(timeline) {
  return (timeline || []).map((point) => {
    if (point.model_output?.components) {
      return point;
    }

    const components = Object.fromEntries(
      Object.entries(point.components || {}).map(([componentId, component]) => [
        componentId,
        {
          subsystem: component.subsystem,
          health: component.health_index,
          status: component.status,
          damage: component.damage || {},
          metrics: component.metrics || {},
          alerts: component.alerts || []
        }
      ])
    );

    return {
      ...point,
      model_output: {
        machine_state: buildMachineStateFromComponents(components),
        components
      }
    };
  });
}

function mergeModelStates(baseModelState, latestModelState) {
  const components = {
    ...(baseModelState?.components || {}),
    ...(latestModelState?.components || {})
  };

  return {
    machine_state: buildMachineStateFromComponents(components),
    components
  };
}

function buildMachineStateFromComponents(components) {
  const componentValues = Object.values(components);
  const overallHealth = componentValues.length
    ? componentValues.reduce((sum, component) => sum + component.health, 0) / componentValues.length
    : 1;
  const criticalComponents = Object.entries(components)
    .filter(([, component]) => component.status === 'CRITICAL')
    .map(([componentId]) => componentId);
  const failedComponents = Object.entries(components)
    .filter(([, component]) => component.status === 'FAILED')
    .map(([componentId]) => componentId);

  let overallStatus = 'FUNCTIONAL';
  if (failedComponents.length) {
    overallStatus = 'FAILED';
  } else if (criticalComponents.length) {
    overallStatus = 'CRITICAL';
  } else if (componentValues.some((component) => component.status === 'DEGRADED')) {
    overallStatus = 'DEGRADED';
  }

  return {
    overall_health: Number(overallHealth.toFixed(4)),
    overall_status: overallStatus,
    critical_components: criticalComponents,
    failed_components: failedComponents
  };
}
