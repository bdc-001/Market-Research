import React, { useState } from 'react';
import LogViewer from './LogViewer';
import CouncilChamber from './CouncilChamber';
import { ConveneButton } from './Loader';
import { useCouncilRun } from './useCouncilRun';
import { getApiUrl } from './api';

export default function GlobalMarkets() {
  const [marketType, setMarketType] = useState('Emerging Markets');
  const [filename, setFilename] = useState('');
  const [pdfGenerating, setPdfGenerating] = useState(false);
  const run = useCouncilRun();

  const handleRunAnalysis = () => {
    setFilename('');
    run.start({
      url: `/api/run/global-markets?market_type=${encodeURIComponent(marketType)}`,
      subject: marketType,
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
      <p className="sense-note">Ask Itachi to convene a macro desk. He opens the region, then the committee files the memo.</p>
      <div className="action-panel">
        <div className="control-group">
          <label className="control-label">Market Region Scope</label>
          <div style={{ display: 'flex', gap: '16px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', cursor: 'pointer' }}>
              <input
                type="radio"
                name="region"
                value="Emerging Markets"
                checked={marketType === 'Emerging Markets'}
                onChange={() => setMarketType('Emerging Markets')}
                disabled={run.isRunning}
              />
              Emerging Markets
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', cursor: 'pointer' }}>
              <input
                type="radio"
                name="region"
                value="Developed Markets"
                checked={marketType === 'Developed Markets'}
                onChange={() => setMarketType('Developed Markets')}
                disabled={run.isRunning}
              />
              Developed Markets
            </label>
          </div>
        </div>
        <ConveneButton running={run.isRunning} onClick={handleRunAnalysis} />
      </div>

      <div style={{ padding: '10px 14px', backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', fontSize: '0.8rem', color: 'var(--ink-secondary)', marginBottom: '20px' }}>
        {marketType === 'Emerging Markets' ? (
          <span><strong>Regions Covered:</strong> India, China, Brazil, Indonesia, Turkey macro data indexes</span>
        ) : (
          <span><strong>Regions Covered:</strong> United States, Europe, Japan, United Kingdom macro data indexes</span>
        )}
      </div>

      <CouncilChamber
        logs={run.logs}
        isRunning={run.isRunning}
        subject={marketType}
        report={run.report}
        headline="Arsalaan’s Office"
        loading={run.isRunning && run.logs.length < 2}
      />
      <LogViewer logs={run.logs} isRunning={run.isRunning} />

      {run.report && (
        <div className="report-card" style={{ marginTop: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 'bold' }}>Macroeconomic Intelligence Memorandum Preview</h3>
            <button className="btn btn-primary" onClick={handleDownloadPdf} disabled={pdfGenerating}>
              <span className="material-symbols-rounded">download</span>
              Download Report (PDF)
            </button>
          </div>
          <div className="markdown-body" style={{ maxHeight: '500px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', padding: '16px', backgroundColor: 'var(--bg-surface)' }}>
            <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: '0.85rem', color: 'var(--ink-secondary)' }}>
              {run.report}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
