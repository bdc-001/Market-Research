import React, { useState, useEffect } from 'react';
import LogViewer from './LogViewer';
import CouncilChamber from './CouncilChamber';
import { ConveneButton } from './Loader';
import { useCouncilRun } from './useCouncilRun';
import { getApiUrl } from './api';

export default function TopPicks() {
  const [sectors, setSectors] = useState([]);
  const [selectedSector, setSelectedSector] = useState('');
  const [filename, setFilename] = useState('');
  const [pdfGenerating, setPdfGenerating] = useState(false);
  const run = useCouncilRun();

  useEffect(() => {
    fetch(getApiUrl('/api/sectors'))
      .then((res) => res.json())
      .then((data) => {
        setSectors(data);
        if (data.length > 0) setSelectedSector(data[0]);
      })
      .catch((err) => console.error('Error loading sectors', err));
  }, []);

  const handleRunAnalysis = () => {
    if (!selectedSector) return;
    setFilename('');
    run.start({
      url: `/api/run/top-picks?sector=${encodeURIComponent(selectedSector)}`,
      subject: selectedSector,
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
      <p className="sense-note">Ask Itachi to convene a screening desk. He opens the sector, then the committee ranks the names.</p>
      <div className="action-panel">
        <div className="control-group">
          <label className="control-label">Industry to Screen</label>
          <select
            className="form-select"
            value={selectedSector}
            onChange={(e) => setSelectedSector(e.target.value)}
            disabled={run.isRunning}
          >
            {sectors.map((sec, i) => (
              <option key={i} value={sec}>{sec}</option>
            ))}
          </select>
        </div>
        <ConveneButton running={run.isRunning} disabled={!selectedSector} onClick={handleRunAnalysis} />
      </div>

      <CouncilChamber
        logs={run.logs}
        isRunning={run.isRunning}
        subject={selectedSector}
        report={run.report}
        headline="Arsalaan’s Office"
        loading={run.isRunning && run.logs.length < 2}
      />
      <LogViewer logs={run.logs} isRunning={run.isRunning} />

      {run.report && (
        <div className="report-card" style={{ marginTop: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 'bold' }}>Top Picks Analysis Report</h3>
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
