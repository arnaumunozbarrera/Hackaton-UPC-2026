import { Component, Suspense, useEffect, useMemo } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { Html, OrbitControls, useGLTF } from '@react-three/drei';
import { Box3, Vector3 } from 'three';
import { COMPONENT_LABELS } from '../data/modelState';
import { formatLabel } from '../services/formatters';

const MODEL_VIEW_SIZE = 2.1;
const MODEL_GROUND_Y = -0.95;

const MODEL_ASSETS = {
  recoater_blade: '/Blade.glb',
  linear_guide: '/linear_guide.glb',
  recoater_drive_motor: '/Stepper%20Motor.glb',
  nozzle_plate: '/Nozzle_Plate.glb',
  thermal_firing_resistors: '/Axial%20Thermal%20Fuse%20Horizontal.glb',
  cleaning_interface: '/brusher.glb',
  heating_elements: '/Heating_Element.glb',
  temperature_sensors: '/temperature_sensor.glb',
  insulation_panels: '/isolatingPanel.glb'
};

export default function Printer3DModel({ modelState, selectedComponentId, onSelect }) {
  const selectedLabel = COMPONENT_LABELS[selectedComponentId] ?? formatLabel(selectedComponentId);
  const componentEntries = Object.keys(modelState?.components || COMPONENT_LABELS).map((componentId) => [
    componentId,
    COMPONENT_LABELS[componentId] ?? formatLabel(componentId)
  ]);

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
        <Canvas camera={{ position: [3.2, 2.3, 5.6], fov: 34, near: 0.01, far: 1000 }}>
          <color attach="background" args={['#05080d']} />
          <ambientLight intensity={0.55} />
          <hemisphereLight args={['#f0f6fc', '#0d1117', 1.1]} />
          <directionalLight position={[5, 7, 4]} intensity={1.8} />
          <directionalLight position={[-4, 2, -3]} intensity={0.65} />
          <Suspense fallback={<ModelLoading />}>
            <ModelLoadBoundary key={selectedComponentId} fallback={<MissingModel selectedLabel={selectedLabel} />}>
              <SelectedComponentModel selectedComponentId={selectedComponentId} />
            </ModelLoadBoundary>
          </Suspense>
          <gridHelper args={[4, 16, '#1f6feb', '#30363d']} position={[0, MODEL_GROUND_Y - 0.02, 0]} />
          <CameraLookAt />
          <OrbitControls makeDefault enablePan={false} minDistance={0.4} maxDistance={12} target={[0, 0, 0]} />
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

function CameraLookAt() {
  const { camera } = useThree();

  useEffect(() => {
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();
  }, [camera]);

  return null;
}

function SelectedComponentModel({ selectedComponentId }) {
  const modelUrl = MODEL_ASSETS[selectedComponentId] || MODEL_ASSETS.heating_elements;
  const { scene } = useGLTF(modelUrl);
  const normalizedScene = useMemo(() => normalizeModelScene(scene), [scene]);

  return <primitive object={normalizedScene} />;
}

function normalizeModelScene(scene) {
  const clone = scene.clone(true);
  const bounds = new Box3().setFromObject(clone);
  const size = bounds.getSize(new Vector3());
  const center = bounds.getCenter(new Vector3());
  const maxDimension = Math.max(size.x, size.y, size.z);

  let scale = 1;
  if (Number.isFinite(maxDimension) && maxDimension > 0) {
    scale = MODEL_VIEW_SIZE / maxDimension;
  }

  clone.scale.setScalar(scale);
  clone.position.set(
    -center.x * scale,
    MODEL_GROUND_Y - bounds.min.y * scale,
    -center.z * scale
  );

  clone.traverse((child) => {
    if (child.isMesh) {
      child.castShadow = true;
      child.receiveShadow = true;
    }
  });

  return clone;
}

function ModelLoading() {
  return (
    <Html center className="model-status">
      Loading model
    </Html>
  );
}

function MissingModel({ selectedLabel }) {
  return (
    <>
      <Html center className="model-status error">
        {selectedLabel} model unavailable
      </Html>
      <mesh rotation={[0.45, -0.45, 0.2]}>
        <boxGeometry args={[1.5, 0.7, 0.7]} />
        <meshStandardMaterial color="#58a6ff" metalness={0.35} roughness={0.45} />
      </mesh>
    </>
  );
}

class ModelLoadBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    console.error('Failed to load 3D component model.', error);
  }

  render() {
    if (this.state.failed) {
      return this.props.fallback;
    }

    return this.props.children;
  }
}
