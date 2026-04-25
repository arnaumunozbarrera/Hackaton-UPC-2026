import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { COMPONENT_LABELS } from '../data/modelState';

const COLORS = {
  recoater_blade: '#58a6ff',
  nozzle_plate: '#f59e0b',
  heating_elements: '#ef4444'
};

export default function Printer3DModel({ selectedComponentId, onSelect }) {
  const selectedLabel = COMPONENT_LABELS[selectedComponentId] ?? 'Component';
  const componentEntries = Object.entries(COMPONENT_LABELS);

  return (
    <section className="panel model-panel">
      <div className="section-title-row compact">
        <div>
          <p className="eyebrow">3D view</p>
          <h2>Isolated selected component</h2>
        </div>
        <span className="axis-chip">{selectedLabel}</span>
      </div>

      <div className="model-canvas dark">
        <Canvas camera={{ position: [0, 0, 4.8], fov: 42 }}>
          <color attach="background" args={['#05080d']} />
          <ambientLight intensity={0.75} />
          <directionalLight position={[4, 6, 5]} intensity={1.2} />
          <directionalLight position={[-4, -2, 3]} intensity={0.35} />
          <SelectedComponentMesh selectedComponentId={selectedComponentId} />
          <OrbitControls enablePan={false} />
        </Canvas>
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

function SelectedComponentMesh({ selectedComponentId }) {
  const color = COLORS[selectedComponentId] || '#58a6ff';

  if (selectedComponentId === 'recoater_blade') {
    return (
      <mesh rotation={[0.3, 0.5, -0.1]}>
        <boxGeometry args={[3.2, 0.24, 0.7]} />
        <meshStandardMaterial color={color} metalness={0.4} roughness={0.35} />
      </mesh>
    );
  }

  if (selectedComponentId === 'nozzle_plate') {
    return (
      <mesh rotation={[0.4, 0.55, 0]}>
        <boxGeometry args={[2.1, 1.2, 0.28]} />
        <meshStandardMaterial color={color} metalness={0.3} roughness={0.45} />
      </mesh>
    );
  }

  return (
    <mesh rotation={[0.5, -0.4, 0.3]}>
      <cylinderGeometry args={[0.8, 0.8, 2.4, 32]} />
      <meshStandardMaterial color={color} metalness={0.35} roughness={0.4} />
    </mesh>
  );
}
