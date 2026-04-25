import { clamp, getStatusFromHealth } from './formatters';

export function buildEmptyAxis(durationHours, stepHours) {
  const steps = Math.max(1, Math.floor(durationHours / stepHours));
  return Array.from({ length: steps + 1 }, (_, index) => ({
    t: index * stepHours,
    health: null,
    damage: null,
    status: null
  }));
}

function degradationBaseByComponent(componentId) {
  return {
    recoater_blade: 0.0042,
    nozzle_plate: 0.0036,
    heating_elements: 0.0024
  }[componentId] || 0.003;
}

export function simulateNextPoint({ componentId, previousHealth, config, stepIndex, runId }) {
  // Future Python integration:
  // POST /api/simulation/step
  // Python should return the same shape produced here.

  const t = stepIndex * config.stepHours;
  const temperaturePenalty = Math.abs(config.temperatureStressC - 35) * 0.00065;
  const humidityPenalty = config.humidity * 0.003;
  const contaminationPenalty = config.contamination * 0.010;
  const loadPenalty = config.operationalLoad * 0.0065;
  const maintenanceRelief = config.maintenanceLevel * 0.0048;
  const stochasticShock = (Math.random() - 0.42) * config.stochasticity * 0.011;

  const degradation = Math.max(
    0.0004,
    degradationBaseByComponent(componentId) +
      temperaturePenalty +
      humidityPenalty +
      contaminationPenalty +
      loadPenalty -
      maintenanceRelief +
      stochasticShock
  );

  const health = clamp(previousHealth - degradation, 0, 1);
  const status = getStatusFromHealth(health);
  const timestamp = new Date(Date.now() + t * 60 * 60 * 1000).toISOString();

  return {
    run_id: runId,
    t,
    timestamp,
    component_id: componentId,
    health,
    damage: clamp(1 - health, 0, 1),
    status,
    drivers: {
      temperature_stress_c: config.temperatureStressC,
      humidity: config.humidity,
      contamination: config.contamination,
      operational_load: config.operationalLoad,
      maintenance_level: config.maintenanceLevel,
      stochasticity: config.stochasticity
    }
  };
}
