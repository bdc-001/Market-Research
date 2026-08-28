import React, { useState, useEffect } from 'react';
import LogViewer from './LogViewer';
import CouncilChamber from './CouncilChamber';
import { getApiUrl } from './api';

export default function Sectors() {
  const [sectors, setSectors] = useState([]);
  const [selectedSector, setSelectedSector] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState([]);
  const [report, setReport] = useState(null);
  const [filename, setFilename] = useState('');
  const [pdfGenerating, setPdfGenerating] = useState(false);

  useEffect(() => {
    fetch(getApiUrl('/api/sectors'))
      .then(res => res.json())
      .then(data => {
        setSectors(data);
        if (data.length > 0) {
          setSelectedSector(data[0]);
        }
      })
      .catch(err => console.error("Error loading sectors", err));
  }, []);

  const handleRunAnalysis = () => {
    if (!selectedSector) return;
    setIsRunning(true);
    setLogs([]);
    setReport(null);
    setFilename('');

    const eventSource = new EventSource(getApiUrl(`/api/run/sector?sector=${encodeURIComponent(selectedSector)}`));

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'progress') {
        setLogs(prev => [...prev, data.message]);
      } else if (data.type === 'complete') {
        setLogs(prev => [...prev, "Complete! Report generated successfully."]);
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
          <label className="control-label">Industry Sector</label>
          <select 
            className="form-select" 
            value={selectedSector} 
            onChange={(e) => setSelectedSector(e.target.value)}
            disabled={isRunning}
          >
            {sectors.map((sec, i) => (
              <option key={i} value={sec}>{sec}</option>
            ))}
          </select>
        </div>
        <button 
          className="btn btn-primary" 
          onClick={handleRunAnalysis} 
          disabled={isRunning || !selectedSector}
          style={{ alignSelf: "flex-end", height: "42px" }}
        >
          <span className="material-symbols-rounded">analytics</span>
          Generate Sector Report
        </button>
      </div>

      <CouncilChamber logs={logs} isRunning={isRunning} headline="Sector desk" />
      <LogViewer logs={logs} isRunning={isRunning} />

      {report && (
        <div className="report-card" style={{ marginTop: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: "bold" }}>Generated Memo Preview</h3>
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
