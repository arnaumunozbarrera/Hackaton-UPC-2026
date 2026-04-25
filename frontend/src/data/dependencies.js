export const HUMAN_DEPENDENCIES = [
  {
    source: 'linear_guide',
    target: 'recoater_drive_motor',
    impact: 'medium',
    description: 'Guide friction increases drag demand on the recoater drive motor.'
  },
  {
    source: 'temperature_sensors',
    target: 'heating_elements',
    impact: 'medium',
    description: 'Sensor drift can reduce temperature control accuracy and increase heating load.'
  },
  {
    source: 'insulation_panels',
    target: 'heating_elements',
    impact: 'high',
    description: 'Insulation loss raises thermal demand on the heating elements.'
  },
  {
    source: 'heating_elements',
    target: 'thermal_firing_resistors',
    impact: 'medium',
    description: 'Thermal instability accelerates firing resistor fatigue.'
  },
  {
    source: 'recoater_blade',
    target: 'nozzle_plate',
    impact: 'high',
    description: 'Recoater blade wear increases effective contamination at the nozzle plate.'
  },
  {
    source: 'heating_elements',
    target: 'nozzle_plate',
    impact: 'medium',
    description: 'Heating element degradation increases effective thermal stress at the nozzle plate.'
  },
  {
    source: 'cleaning_interface',
    target: 'nozzle_plate',
    impact: 'medium',
    description: 'Reduced cleaning efficiency increases residue and nozzle clogging risk.'
  },
  {
    source: 'thermal_firing_resistors',
    target: 'nozzle_plate',
    impact: 'medium',
    description: 'Firing resistor degradation increases jetting instability at the nozzle plate.'
  }
];
