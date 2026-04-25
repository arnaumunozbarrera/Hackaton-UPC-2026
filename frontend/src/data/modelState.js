export const INITIAL_MODEL_STATE = {
  machine_state: {
    overall_health: 0.82,
    overall_status: 'DEGRADED',
    critical_components: [],
    failed_components: []
  },
  components: {
    recoater_blade: {
      subsystem: 'recoating_system',
      health: 0.78,
      status: 'DEGRADED',
      damage: {
        total: 0.22,
        abrasive_wear: 0.18,
        contamination_damage: 0.04
      },
      metrics: {
        thickness_mm: 1.56,
        roughness_index: 0.31,
        wear_rate: 0.0024
      },
      alerts: []
    },
    nozzle_plate: {
      subsystem: 'printhead_array',
      health: 0.86,
      status: 'FUNCTIONAL',
      damage: {
        total: 0.14,
        clogging: 0.09,
        thermal_fatigue: 0.05
      },
      metrics: {
        clogging_ratio: 0.12,
        blocked_nozzles_pct: 4.8,
        jetting_efficiency: 0.91
      },
      alerts: []
    },
    heating_elements: {
      subsystem: 'thermal_control',
      health: 0.91,
      status: 'FUNCTIONAL',
      damage: {
        total: 0.09,
        electrical_degradation: 0.07,
        thermal_overload: 0.02
      },
      metrics: {
        resistance_ohm: 10.9,
        energy_factor: 1.06,
        thermal_stability: 0.94
      },
      alerts: []
    }
  }
};

export const COMPONENT_LABELS = {
  recoater_blade: 'Recoater blade',
  nozzle_plate: 'Nozzle plate',
  heating_elements: 'Heating elements'
};

export const SUBSYSTEM_LABELS = {
  recoating_system: 'Recoating system',
  printhead_array: 'Printhead array',
  thermal_control: 'Thermal control'
};
