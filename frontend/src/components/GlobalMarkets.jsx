import React, { useState } from 'react';
import LogViewer from './LogViewer';
import CouncilChamber from './CouncilChamber';
import { getApiUrl } from './api';

export default function GlobalMarkets() {
  const [marketType, setMarketType] = useState('Emerging Markets');
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState([]);
  const [report, setReport] = useState(null);
  const [filename, setFilename] = useState('');
  const [pdfGenerating, setPdfGenerating] = useState(false);

  const handleRunAnalysis = () => {
    setIsRunning(true);
    setLogs([]);
    setReport(null);
    setFilename('');

    const eventSource = new EventSource(getApiUrl(`/api/run/global-markets?market_type=${encodeURIComponent(marketType)}`));

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'progress') {
        setLogs(prev => [...prev, data.message]);
      } else if (data.type === 'complete') {
        setLogs(prev => [...prev, "Complete! Global Market Macroeconomic analysis generated."]);
        setReport(data.report);
        setFilename(data.filename);
        setIsRunning(false);
        eventSource.close();
      } else if (data.type === 'error') {
        setLogs(prev => [...prev, `Error: ${data.message}`]);
        setIsRunning(false);
        eventSource.close();
      }
    };

    eventSource.onerror = (err) => {
      console.error("SSE Error:", err);
      setLogs(prev => [...prev, "Connection error. Terminating pipeline."]);
      setIsRunning(false);
      eventSource.close();
    };
  };

  const handleDownloadPdf = () => {
    if (!filename) return;
    setPdfGenerating(true);
    window.open(getApiUrl(`/api/reports/pdf/${filename}`), '_blank');
    setPdfGenerating(false);
  };

  return (
    <div className="report-section">
      <div className="action-panel">
        <div className="control-group">
          <label className="control-label">Market Region Scope</label>
          <div style={{ display: "flex", gap: "16px" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.85rem", cursor: "pointer" }}>
              <input 
                type="radio" 
                name="region" 
                value="Emerging Markets" 
                checked={marketType === 'Emerging Markets'}
                onChange={() => setMarketType('Emerging Markets')}
                disabled={isRunning}
              />
              Emerging Markets
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.85rem", cursor: "pointer" }}>
              <input 
                type="radio" 
                name="region" 
                value="Developed Markets" 
                checked={marketType === 'Developed Markets'}
                onChange={() => setMarketType('Developed Markets')}
                disabled={isRunning}
              />
              Developed Markets
            </label>
          </div>
        </div>
        <button 
          className="btn btn-primary" 
          onClick={handleRunAnalysis} 
          disabled={isRunning}
          style={{ alignSelf: "flex-end", height: "42px" }}
        >
          <span className="material-symbols-rounded">public</span>
          Generate Macro Report
        </button>
      </div>

      <div style={{ padding: "10px 14px", backgroundColor: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--r-md)", fontSize: "0.8rem", color: "var(--ink-secondary)", marginBottom: "20px" }}>
        {marketType === 'Emerging Markets' ? (
          <span><strong>Regions Covered:</strong> India, China, Brazil, Indonesia, Turkey macro data indexes</span>
        ) : (
          <span><strong>Regions Covered:</strong> United States, Europe, Japan, United Kingdom macro data indexes</span>
        )}
      </div>

      <CouncilChamber logs={logs} isRunning={isRunning} subject={marketType} report={report} headline="Arsalaan’s Office" />
      <LogViewer logs={logs} isRunning={isRunning} />

      {report && (
        <div className="report-card" style={{ marginTop: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: "bold" }}>Macroeconomic Intelligence Memorandum Preview</h3>
            <button className="btn btn-primary" onClick={handleDownloadPdf} disabled={pdfGenerating}>
              <span className="material-symbols-rounded">download</span>
              Download Report (PDF)
            </button>
          </div>
          <div className="markdown-body" style={{ maxHeight: "500px", overflowY: "auto", border: "1px solid var(--border)", borderRadius: "var(--r-md)", padding: "16px", backgroundColor: "var(--bg-surface)" }}>
            <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: "0.85rem", color: "var(--ink-secondary)" }}>
              {report}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
