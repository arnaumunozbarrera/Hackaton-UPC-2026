import { COMPONENT_LABELS, SUBSYSTEM_LABELS } from '../data/modelState';

export default function ComponentSelector({ modelState, selectedComponentId, onChange }) {
  return (
    <label className="field compact-field">
      <span>Component</span>
      <select className="selector-input" value={selectedComponentId} onChange={(event) => onChange(event.target.value)}>
        {Object.entries(modelState.components).map(([id, component]) => (
          <option key={id} value={id}>
            {COMPONENT_LABELS[id]} - {SUBSYSTEM_LABELS[component.subsystem]}
          </option>
        ))}
      </select>
    </label>
  );
}
