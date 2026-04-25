import { useEffect } from 'react';
import { COMPONENT_LABELS } from '../data/modelState';

const MODEL_VIEWER_SCRIPT_ID = 'model-viewer-web-component';
const MODEL_VIEWER_SCRIPT_SRC = 'https://ajax.googleapis.com/ajax/libs/model-viewer/3.4.0/model-viewer.min.js';

const MODEL_PATHS = {
  recoater_blade: '/Blade.glb',
  nozzle_plate: '/Blade.glb',
  heating_elements: '/Blade.glb'
};

function ensureModelViewerScript() {
  if (typeof window === 'undefined' || customElements.get('model-viewer')) {
    return;
  }

  const existingScript = document.getElementById(MODEL_VIEWER_SCRIPT_ID);
  if (existingScript) {
    return;
  }

  const script = document.createElement('script');
  script.id = MODEL_VIEWER_SCRIPT_ID;
  script.type = 'module';
  script.src = MODEL_VIEWER_SCRIPT_SRC;
  document.head.appendChild(script);
}

export default function Printer3DModel({ selectedComponentId, onSelect }) {
  useEffect(() => {
    ensureModelViewerScript();
  }, []);

  const selectedLabel = COMPONENT_LABELS[selectedComponentId] ?? 'Recoater Blade';
  const modelUrl = MODEL_PATHS[selectedComponentId] ?? MODEL_PATHS.recoater_blade;
  const componentEntries = Object.entries(COMPONENT_LABELS).filter(([componentId]) => MODEL_PATHS[componentId]);

  return (
    <section className="panel model-panel">
      <div className="section-title-row compact">
        <div>
          <p className="eyebrow">3D view</p>
          <h2>HP Metal Jet S100: {selectedLabel}</h2>
        </div>
        <span className="axis-chip">Selected: {selectedLabel}</span>
      </div>

      <div className="model-canvas">
        <model-viewer
          id="component-viewer"
          src={modelUrl}
          alt={`3D model of ${selectedLabel}`}
          auto-rotate
          camera-controls
          shadow-intensity="1"
          exposure="1"
          environment-image="neutral"
        />
      </div>

      <div className="controls">
        {componentEntries.map(([componentId, label]) => (
          <button
            key={componentId}
            type="button"
            className={componentId === selectedComponentId ? 'primary-button' : 'secondary-button'}
            onClick={() => onSelect?.(componentId)}
          >
            {label}
          </button>
        ))}
      </div>
    </section>
  );
}
