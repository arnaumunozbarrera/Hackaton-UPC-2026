import { Component, Suspense, useEffect, useMemo } from 'react';
import './Printer3DModel.css';
import { Canvas, useThree } from '@react-three/fiber';
import { Environment, Html, OrbitControls, ContactShadows, useGLTF } from '@react-three/drei';
import { Box3, Color, MeshStandardMaterial, Vector3 } from 'three';
import { COMPONENT_LABELS } from '../data/modelState';
import { formatLabel } from '../services/formatters';

const MODEL_VIEW_SIZE = 2.1;
const INDUSTRIAL_PALETTE = ['#eadfc9', '#dbc8a7', '#cfb891', '#f3e9d7', '#bca786'];

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

export default function Printer3DModel({ modelState, selectedComponentId, onSelect, className = '' }) {
  const selectedLabel = COMPONENT_LABELS[selectedComponentId] ?? formatLabel(selectedComponentId);
  const componentEntries = Object.keys(modelState?.components || COMPONENT_LABELS).map((componentId) => [
    componentId,
    COMPONENT_LABELS[componentId] ?? formatLabel(componentId)
  ]);

  return (
    <section className={`panel model-panel ${className}`.trim()}>
      <div className="section-title-row compact">
        <div>
          <p className="eyebrow">3D view</p>
          <h2>Selected component</h2>
        </div>
        <span className="axis-chip">{selectedLabel}</span>
      </div>

      <div className="model-canvas solidworks">
        <Canvas
          shadows
          gl={{ alpha: true, toneMappingExposure: 1.18 }}
          camera={{ position: [3.2, 2.3, 5.6], fov: 34, near: 0.01, far: 1000 }}
        >
          <ambientLight intensity={0.52} color="#dfe7f1" />
          <hemisphereLight args={['#d9e4f2', '#607086', 0.95]} />
          <directionalLight
            position={[5.5, 7.5, 4.5]}
            intensity={2.65}
            color="#f7f3ea"
            castShadow
            shadow-mapSize-width={2048}
            shadow-mapSize-height={2048}
            shadow-camera-near={0.5}
            shadow-camera-far={20}
            shadow-camera-left={-4}
            shadow-camera-right={4}
            shadow-camera-top={4}
            shadow-camera-bottom={-4}
          />
          <directionalLight position={[-4, 2, -3]} intensity={0.78} color="#d8dde6" />
          <directionalLight position={[0, -2, 4]} intensity={0.42} color="#f7f7f7" />
          <Environment preset="warehouse" intensity={0.82} />
          <Suspense fallback={<ModelLoading />}>
            <ModelLoadBoundary key={selectedComponentId} fallback={<MissingModel selectedLabel={selectedLabel} />}>
              <SelectedComponentModel selectedComponentId={selectedComponentId} />
            </ModelLoadBoundary>
          </Suspense>
          <ContactShadows
            position={[0, -0.98, 0]}
            opacity={0.34}
            scale={8}
            blur={2.8}
            far={3.2}
            resolution={1024}
            color="#39485c"
          />
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
  const normalizedScene = useMemo(
    () => normalizeModelScene(scene, selectedComponentId),
    [scene, selectedComponentId]
  );

  return <primitive object={normalizedScene} />;
}

/**
 * Clones, centers, scales, and restyles a loaded GLB scene for consistent viewing.
 *
 * @param {object} scene - Loaded Three.js scene from useGLTF.
 * @param {string} selectedComponentId - Component identifier associated with the model.
 * @returns {object} Normalized scene clone ready for rendering.
 */
function normalizeModelScene(scene, selectedComponentId) {
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
  clone.position.set(-center.x * scale, -center.y * scale, -center.z * scale);

  let materialIndex = 0;
  clone.traverse((child) => {
    if (child.isMesh) {
      if (selectedComponentId === 'thermal_firing_resistors' && !child.geometry.attributes.normal) {
        child.geometry.computeVertexNormals();
      }
      child.castShadow = true;
      child.receiveShadow = true;
      const paletteColor = INDUSTRIAL_PALETTE[materialIndex % INDUSTRIAL_PALETTE.length];
      const material = new MeshStandardMaterial({
        color: new Color(paletteColor),
        metalness: 0.08,
        roughness: 0.68,
        side: 2
      });
      if (Array.isArray(child.material)) {
        child.material = child.material.map(() => material.clone());
      } else {
        child.material = material;
      }
      materialIndex += 1;
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
        <meshStandardMaterial color="#9e9686" metalness={0.14} roughness={0.76} />
      </mesh>
    </>
  );
}

/**
 * Contains GLB loading failures so the 3D panel can render a fallback model.
 */
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
