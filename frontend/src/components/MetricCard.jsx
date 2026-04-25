export default function MetricCard({ label, value, helper }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {helper ? <div className="metric-helper">{helper}</div> : null}
    </div>
  );
}
