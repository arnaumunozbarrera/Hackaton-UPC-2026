export const HUMAN_DEPENDENCIES = [
  {
    source: 'recoater_blade',
    target: 'nozzle_plate',
    impact: 'high',
    description: 'Recoater blade wear can increase powder irregularity, which may increase nozzle contamination risk.'
  },
  {
    source: 'heating_elements',
    target: 'nozzle_plate',
    impact: 'medium',
    description: 'Thermal instability can accelerate nozzle clogging and reduce jetting efficiency.'
  },
  {
    source: 'nozzle_plate',
    target: 'recoater_blade',
    impact: 'low',
    description: 'Reduced jetting uniformity can increase downstream powder handling corrections and inspection load.'
  },
  {
    source: 'heating_elements',
    target: 'recoater_blade',
    impact: 'low',
    description: 'Thermal instability can indirectly alter powder behavior and slightly worsen blade wear conditions.'
  }
];
