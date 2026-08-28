import React, { useState } from 'react';
import TradingViewChart from './TradingViewChart';
import LogViewer from './LogViewer';
import CouncilChamber from './CouncilChamber';
import { ConveneButton } from './Loader';
import { useCouncilRun } from './useCouncilRun';
import { getApiUrl } from './api';

export default function StockAnalysis() {
  const [ticker, setTicker] = useState('');
  const [activeChartSymbol, setActiveChartSymbol] = useState('');
  const [filename, setFilename] = useState('');
  const [pdfGenerating, setPdfGenerating] = useState(false);
  const run = useCouncilRun();

  const handleRunAnalysis = () => {
    const cleanSymbol = ticker.toUpperCase().trim();
    if (!cleanSymbol) return;
    setTicker(cleanSymbol);
    setActiveChartSymbol(cleanSymbol);
    setFilename('');
    run.start({
      url: `/api/run/stock?ticker=${encodeURIComponent(cleanSymbol)}`,
      subject: cleanSymbol,
      onComplete: (data) => setFilename(data.filename || ''),
    });
  };

  const handleDownloadPdf = () => {
    if (!filename) return;
    setPdfGenerating(true);
    window.open(getApiUrl(`/api/reports/pdf/${filename}`), '_blank');
    setPdfGenerating(false);
  };

  return (
    <div className="report-section">
      <p className="sense-note">Ask Itachi to convene. He opens the desk, then the committee briefs you on the name.</p>
      <div className="action-panel">
        <div className="control-group">
          <label className="control-label">Ticker Symbol (NSE)</label>
          <input
            type="text"
            className="form-input"
            placeholder="e.g. TATAMOTORS, RELIANCE, INFY"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            disabled={run.isRunning}
            onKeyDown={(e) => e.key === 'Enter' && handleRunAnalysis()}
          />
        </div>
        <ConveneButton running={run.isRunning} disabled={!ticker} onClick={handleRunAnalysis} />
      </div>

      {activeChartSymbol && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 'bold', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="material-symbols-rounded" style={{ color: 'var(--brand)' }}>monitoring</span>
            Technical Chart: {activeChartSymbol}
          </h3>
          <TradingViewChart symbol={activeChartSymbol} />
        </div>
      )}

      <CouncilChamber
        logs={run.logs}
        isRunning={run.isRunning}
        subject={ticker}
        report={run.report}
        headline="Arsalaan’s Office"
        loading={run.isRunning && run.logs.length < 2}
      />
      <LogViewer logs={run.logs} isRunning={run.isRunning} />

      {run.report && (
        <div className="report-card" style={{ marginTop: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 'bold' }}>Agent Council Memorandum Preview</h3>
            <button className="btn btn-primary" onClick={handleDownloadPdf} disabled={pdfGenerating}>
              <span className="material-symbols-rounded">download</span>
              Download Report (PDF)
            </button>
          </div>
          <div className="markdown-body" style={{ maxHeight: '600px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', padding: '20px', backgroundColor: 'var(--bg-surface)' }}>
            <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: '0.85rem', color: 'var(--ink-secondary)' }}>
              {run.report}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
