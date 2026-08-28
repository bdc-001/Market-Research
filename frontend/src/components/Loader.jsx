import React from 'react';

export function SenseSpinner({ light = false }) {
  return <span className={`sense-spinner ${light ? 'light' : ''}`} aria-hidden="true" />;
}

export function SenseLoader({ label = 'Loading' }) {
  return (
    <div className="sense-loader" role="status">
      <SenseSpinner />
      <span>{label}</span>
    </div>
  );
}

export function MetricSkeletons({ count = 5 }) {
  return (
    <div className="sense-metric-grid">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="sense-skeleton-card" style={{ animationDelay: `${i * 70}ms` }} />
      ))}
    </div>
  );
}

export function ConveneButton({
  running,
  disabled,
  onClick,
  label = 'Ask Itachi to convene',
  busyLabel = 'Convening…',
}) {
  return (
    <button
      className="btn btn-primary"
      onClick={onClick}
      disabled={disabled || running}
      style={{ alignSelf: 'flex-end', height: '42px', minWidth: '220px' }}
    >
      {running ? (
        <>
          <SenseSpinner light />
          {busyLabel}
        </>
      ) : (
        <>
          <span className="material-symbols-rounded">forum</span>
          {label}
        </>
      )}
    </button>
  );
}
