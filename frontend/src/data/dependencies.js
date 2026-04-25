export const HUMAN_DEPENDENCIES = [
  {
    source: 'recoater_blade',
    target: 'nozzle_plate',
    level: 'High',
    score: 0.76,
    sentence: 'If the recoater blade wears down, powder distribution becomes less uniform and the nozzle plate is more likely to clog.',
    operatorAction: 'Inspect blade edge and powder contamination before extending the print run.'
  },
  {
    source: 'heating_elements',
    target: 'nozzle_plate',
    level: 'Medium',
    score: 0.57,
    sentence: 'Unstable heating increases thermal stress around the printhead and can accelerate nozzle fatigue.',
    operatorAction: 'Check thermal stability and reduce aggressive temperature profiles.'
  },
  {
    source: 'nozzle_plate',
    target: 'recoater_blade',
    level: 'Low',
    score: 0.22,
    sentence: 'Nozzle degradation has limited direct impact on the recoater blade, but poor jetting can increase downstream quality issues.',
    operatorAction: 'Prioritize nozzle cleaning; blade inspection is secondary.'
  },
  {
    source: 'heating_elements',
    target: 'recoater_blade',
    level: 'Low',
    score: 0.18,
    sentence: 'Heating element degradation has a weak direct effect on recoater wear, but it may affect powder behavior indirectly.',
    operatorAction: 'Monitor if thermal instability appears together with blade roughness growth.'
  }
];
