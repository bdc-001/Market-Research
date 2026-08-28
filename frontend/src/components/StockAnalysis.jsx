import React, { useState } from 'react';
import TradingViewChart from './TradingViewChart';
import LogViewer from './LogViewer';
import CouncilChamber from './CouncilChamber';
import { getApiUrl } from './api';

export default function StockAnalysis() {
  const [ticker, setTicker] = useState('');
  const [activeChartSymbol, setActiveChartSymbol] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState([]);
  const [report, setReport] = useState(null);
  const [filename, setFilename] = useState('');
  const [pdfGenerating, setPdfGenerating] = useState(false);

  const triggerAnalysis = (symbolToAnalyze) => {
    if (!symbolToAnalyze) return;
    const cleanSymbol = symbolToAnalyze.toUpperCase().trim();
    setTicker(cleanSymbol);
    setActiveChartSymbol(cleanSymbol);
    setIsRunning(true);
    setLogs([]);
    setReport(null);
    setFilename('');

    const eventSource = new EventSource(getApiUrl(`/api/run/stock?ticker=${encodeURIComponent(cleanSymbol)}`));

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'progress') {
        setLogs(prev => [...prev, data.message]);
      } else if (data.type === 'complete') {
        setLogs(prev => [...prev, "Complete! 7-Agent Council Stock analysis completed."]);
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

  const handleRunAnalysis = () => {
    triggerAnalysis(ticker);
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
          <label className="control-label">Ticker Symbol (NSE)</label>
          <input 
            type="text" 
            className="form-input" 
            placeholder="e.g. TATAMOTORS, RELIANCE, INFY" 
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            disabled={isRunning}
            onKeyDown={(e) => e.key === 'Enter' && handleRunAnalysis()}
          />
        </div>
        <button 
          className="btn btn-primary" 
          onClick={handleRunAnalysis} 
          disabled={isRunning || !ticker}
          style={{ alignSelf: "flex-end", height: "42px" }}
        >
          <span className="material-symbols-rounded">forum</span>
          Run Council Analysis
        </button>
      </div>

      {activeChartSymbol && (
      <div style={{ marginBottom: "24px" }}>
        <h3 style={{ fontSize: "1rem", fontWeight: "bold", marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
          <span className="material-symbols-rounded" style={{ color: "var(--brand)" }}>monitoring</span>
          Technical Chart: {activeChartSymbol}
        </h3>
        <TradingViewChart symbol={activeChartSymbol} />
      </div>
      )}

      <CouncilChamber logs={logs} isRunning={isRunning} subject={ticker} report={report} headline="Arsalaan’s Office" />
      <LogViewer logs={logs} isRunning={isRunning} />

      {report && (
        <div className="report-card" style={{ marginTop: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: "bold" }}>Agent Council Memorandum Preview</h3>
            <button className="btn btn-primary" onClick={handleDownloadPdf} disabled={pdfGenerating}>
              <span className="material-symbols-rounded">download</span>
              Download Report (PDF)
            </button>
          </div>
          <div className="markdown-body" style={{ maxHeight: "600px", overflowY: "auto", border: "1px solid var(--border)", borderRadius: "var(--r-md)", padding: "20px", backgroundColor: "var(--bg-surface)" }}>
            <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: "0.85rem", color: "var(--ink-secondary)" }}>
              {report}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
