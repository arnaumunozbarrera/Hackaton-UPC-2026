import { Suspense, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Clone, Html, OrbitControls, useGLTF } from '@react-three/drei';
import { COMPONENT_LABELS } from '../data/modelState';

const PARTS = [
  {
    id: 'heating_elements',
    label: 'Heating elements',
    position: [0, -0.55, 0],
    scale: [4.6, 0.34, 2.3],
    color: '#1f2937'
  },
  {
    id: 'recoater_blade',
    label: 'Recoater blade',
    position: [-1.15, 0.18, 0],
    scale: [1.55, 0.34, 2.5],
    color: '#0056D1'
  },
  {
    id: 'nozzle_plate',
    label: 'Nozzle plate',
    position: [1.05, 0.33, 0],
    scale: [1.42, 0.52, 1.72],
    color: '#334155'
  },
  {
    id: 'frame',
    label: 'Printer frame',
    position: [0, 1.05, 0],
    scale: [4.8, 0.2, 2.55],
    color: '#475569'
  }
];

function Part({ part, selectedComponentId, onSelect }) {
  const ref = useRef();
  const selected = part.id === selectedComponentId;

  useFrame(() => {
    if (ref.current && selected) ref.current.rotation.y += 0.004;
  });

  return (
    <mesh
      ref={ref}
      position={part.position}
      scale={part.scale}
      onClick={(event) => {
        event.stopPropagation();
        if (part.id !== 'frame') onSelect(part.id);
      }}
    >
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color={selected ? '#00E771' : part.color} roughness={0.5} metalness={0.15} />
      {selected ? (
        <Html position={[0, 0.85, 0]} center>
          <div className="model-label">{part.label}</div>
        </Html>
      ) : null}
    </mesh>
  );
}

function LoadedModelAsset({ modelUrl }) {
  const gltf = useGLTF(modelUrl);
  const scene = useMemo(() => gltf.scene.clone(true), [gltf.scene]);

  return <Clone object={scene} scale={1.2} position={[0, -1.1, 0]} />;
}

function PlaceholderModel({ selectedComponentId, onSelect }) {
  return (
    <group>
      {PARTS.map((part) => (
        <Part key={part.id} part={part} selectedComponentId={selectedComponentId} onSelect={onSelect} />
      ))}
    </group>
  );
}

export default function Printer3DModel({ selectedComponentId, onSelect, modelUrl = null }) {
  const supportsExternalModel = typeof modelUrl === 'string' && /\.(gltf|glb)(\?.*)?$/i.test(modelUrl);

  return (
    <section className="panel model-panel">
      <div className="section-title-row compact">
        <div>
          <p className="eyebrow">3D view</p>
          <h2>Printer layout</h2>
          <p className="muted">
            {supportsExternalModel ? 'Displaying the supplied 3D asset.' : 'Rotate and inspect the main subcomponents.'}
          </p>
        </div>
        <span className="axis-chip">
          {supportsExternalModel ? `Asset: ${modelUrl.split('/').pop()}` : `Selected: ${COMPONENT_LABELS[selectedComponentId]}`}
        </span>
      </div>

      <div className="model-canvas">
        <Canvas camera={{ position: [4.6, 3.2, 5.2], fov: 45 }}>
          <color attach="background" args={['#060b13']} />
          <ambientLight intensity={0.75} />
          <directionalLight position={[5, 6, 3]} intensity={1.35} />
          <pointLight position={[-3, 2, -4]} intensity={0.6} />
          <Suspense fallback={null}>
            {supportsExternalModel ? (
              <LoadedModelAsset modelUrl={modelUrl} />
            ) : (
              <PlaceholderModel selectedComponentId={selectedComponentId} onSelect={onSelect} />
            )}
          </Suspense>
          <OrbitControls enableDamping dampingFactor={0.08} />
        </Canvas>
      </div>
    </section>
  );
}
