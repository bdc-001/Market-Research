import React, { useEffect, useRef } from 'react';

export default function LogViewer({ logs = [], isRunning = false }) {
  const terminalEndRef = useRef(null);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  return (
    <div className="terminal-container" style={{
      background: 'linear-gradient(180deg, #ffffff 0%, #f6f7fc 100%)',
      border: '1px solid var(--border)',
      borderRadius: '16px',
      padding: '16px',
      fontFamily: "'JetBrains Mono', monospace",
      fontSize: '0.8rem',
      color: 'var(--ink-secondary)',
      height: '200px',
      overflowY: 'auto',
      display: 'flex',
      flexDirection: 'column',
      gap: '6px',
      boxShadow: 'var(--shadow-apple)',
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        borderBottom: '1px solid var(--border)',
        paddingBottom: '8px',
        marginBottom: '8px',
      }}>
        <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 800, color: 'var(--ink)' }}>
          Desk transcript
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {isRunning ? (
            <>
              <span className="animate-pulse-dot" style={{ backgroundColor: 'var(--brand)' }} />
              <span style={{ fontSize: '0.68rem', color: 'var(--brand)', fontWeight: 700 }}>AGENTS SPEAKING</span>
            </>
          ) : (
            <span style={{ fontSize: '0.68rem', color: 'var(--ink-muted)' }}>IDLE</span>
          )}
        </div>
      </div>

      <div style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {logs.length === 0 ? (
          <div style={{ color: 'var(--ink-subtle)', textAlign: 'center', padding: '24px 0' }}>
            Run a briefing to hear the committee.
          </div>
        ) : (
          logs.map((log, index) => (
            <div key={index} style={{
              lineHeight: 1.45,
              display: 'flex',
              gap: '8px',
              animation: 'fade-up 0.25s ease both',
              color: log.includes('Error') ? 'var(--red)' : log.includes('Complete') || log.includes('Ready') ? 'var(--green)' : 'var(--ink-secondary)',
            }}>
              <span style={{ color: 'var(--brand)', userSelect: 'none' }}>▸</span>
              <span>{log}</span>
            </div>
          ))
        )}
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
}
