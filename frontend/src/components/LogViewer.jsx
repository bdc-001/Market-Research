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
      backgroundColor: "#0d1117",
      border: "1px solid var(--border-strong)",
      borderRadius: "var(--r-md)",
      padding: "16px",
      fontFamily: "'JetBrains Mono', monospace",
      fontSize: "0.85rem",
      color: "#8892b0",
      boxShadow: "inset 0 4px 10px rgba(0,0,0,0.5)",
      height: "220px",
      overflowY: "auto",
      display: "flex",
      flexDirection: "column",
      gap: "6px"
    }}>
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        paddingBottom: "8px",
        marginBottom: "8px",
        color: "var(--ink)"
      }}>
        <span style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: "bold" }}>
          Council Pipeline Logs
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          {isRunning ? (
            <>
              <span className="spinner-dot" style={{
                width: "8px",
                height: "8px",
                backgroundColor: "var(--brand)",
                borderRadius: "50%",
                display: "inline-block",
                animation: "pulse 1s infinite alternate"
              }}></span>
              <span style={{ fontSize: "0.7rem", color: "var(--brand)" }}>EXECUTING</span>
            </>
          ) : (
            <span style={{ fontSize: "0.7rem", color: "var(--ink-muted)" }}>IDLE</span>
          )}
        </div>
      </div>
      
      <div className="logs-body" style={{ flexGrow: 1, display: "flex", flexDirection: "column", gap: "4px" }}>
        {logs.length === 0 ? (
          <div style={{ color: "var(--ink-subtle)", fontStyle: "italic", textAlign: "center", padding: "20px 0" }}>
            No logs generated yet. Trigger a fresh run.
          </div>
        ) : (
          logs.map((log, index) => (
            <div key={index} style={{
              lineHeight: "1.4",
              display: "flex",
              gap: "8px",
              color: log.includes("Error") ? "#f43f5e" : log.includes("Complete") || log.includes("Ready") ? "var(--green)" : "#8892b0"
            }}>
              <span style={{ color: "var(--brand)", userSelect: "none" }}>&gt;</span>
              <span>{log}</span>
            </div>
          ))
        )}
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
}
