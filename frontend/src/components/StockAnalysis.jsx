import React, { useState } from 'react';
import TradingViewChart from './TradingViewChart';
import LogViewer from './LogViewer';
import { getApiUrl } from './api';

export default function StockAnalysis() {
  const [ticker, setTicker] = useState('');
  const [activeChartSymbol, setActiveChartSymbol] = useState('TATAMOTORS');
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

  const handleCardClick = (symbol) => {
    setActiveChartSymbol(symbol);
    setTicker(symbol);
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

      <div className="card-grid">
        <div 
          className="dashboard-card" 
          onClick={() => handleCardClick('TATAMOTORS')}
          style={{ cursor: "pointer", border: activeChartSymbol === 'TATAMOTORS' ? "1px solid var(--brand)" : "1px solid var(--border)" }}
        >
          <div className="card-header">
            <span className="card-title">TATAMOTORS</span>
            <span className="card-status status-active">● High Conviction</span>
          </div>
          <div className="card-metrics">
            <div className="metric-item"><div className="metric-label">SCORE</div><div className="metric-value">88 / 100</div></div>
            <div className="metric-item"><div className="metric-label">TECHNICALS</div><div className="metric-value">RSI 56.4 (MACD +)</div></div>
            <div className="metric-item"><div className="metric-label">ROE</div><div className="metric-value">24.8%</div></div>
          </div>
          <div className="card-tags">
            <span className="card-tag active">● EV Transition</span>
            <span className="card-tag">● JLR Margins</span>
          </div>
        </div>

        <div 
          className="dashboard-card" 
          onClick={() => handleCardClick('RELIANCE')}
          style={{ cursor: "pointer", border: activeChartSymbol === 'RELIANCE' ? "1px solid var(--brand)" : "1px solid var(--border)" }}
        >
          <div className="card-header">
            <span className="card-title">RELIANCE</span>
            <span className="card-status status-warning">● Consolidation</span>
          </div>
          <div className="card-metrics">
            <div className="metric-item"><div className="metric-label">SCORE</div><div className="metric-value">76 / 100</div></div>
            <div className="metric-item"><div className="metric-label">TECHNICALS</div><div className="metric-value">Near SMA200</div></div>
            <div className="metric-item"><div className="metric-label">P/E</div><div className="metric-value">26.1</div></div>
          </div>
          <div className="card-tags">
            <span className="card-tag active">● Jio Growth</span>
            <span className="card-tag">● Retail Monetisation</span>
          </div>
        </div>

        <div 
          className="dashboard-card" 
          onClick={() => handleCardClick('INFY')}
          style={{ cursor: "pointer", border: activeChartSymbol === 'INFY' ? "1px solid var(--brand)" : "1px solid var(--border)" }}
        >
          <div className="card-header">
            <span className="card-title">INFY</span>
            <span className="card-status status-info">● Accumulate</span>
          </div>
          <div className="card-metrics">
            <div className="metric-item"><div className="metric-label">SCORE</div><div className="metric-value">82 / 100</div></div>
            <div className="metric-item"><div className="metric-label">TECHNICALS</div><div className="metric-value">Above SMA50</div></div>
            <div className="metric-item"><div className="metric-label">YIELD</div><div className="metric-value">Div 2.6%</div></div>
          </div>
          <div className="card-tags">
            <span className="card-tag active">● GenAI Deals</span>
            <span className="card-tag">● Large Deal TCV</span>
          </div>
        </div>
      </div>

      <div style={{ marginBottom: "24px" }}>
        <h3 style={{ fontSize: "1rem", fontWeight: "bold", marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
          <span className="material-symbols-rounded" style={{ color: "var(--brand)" }}>monitoring</span>
          Technical Chart: {activeChartSymbol}
        </h3>
        <TradingViewChart symbol={activeChartSymbol} />
      </div>

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
