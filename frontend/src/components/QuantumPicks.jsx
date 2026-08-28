import React, { useState, useEffect } from 'react';
import LogViewer from './LogViewer';
import CouncilChamber from './CouncilChamber';
import { ConveneButton } from './Loader';
import { useCouncilRun } from './useCouncilRun';
import { getApiUrl } from './api';

export default function QuantumPicks() {
  const [mode, setMode] = useState('fast');
  const [activeTab, setActiveTab] = useState('week'); // 'week', 'year', 'fiveyear'
  const [weekPicks, setWeekPicks] = useState([]);
  const [yearPicks, setYearPicks] = useState([]);
  const [fiveyearPicks, setFiveyearPicks] = useState([]);
  const [headlines, setHeadlines] = useState([]);
  const [report, setReport] = useState('');
  const [filename, setFilename] = useState('');
  const [createdTime, setCreatedTime] = useState('');
  const [pdfGenerating, setPdfGenerating] = useState(false);
  const run = useCouncilRun();
  const isRunning = run.isRunning;
  const logs = run.logs;

  useEffect(() => {
    // Load initial cached results immediately
    fetch(getApiUrl('/api/reports/cached/quantum'))
      .then(res => {
        if (res.ok) return res.json();
        throw new Error("No cached reports");
      })
      .then(data => {
        setCreatedTime(data.created);
        setReport(data.markdown);
        setMode(data.mode || 'fast');
        if (data.picks) {
          setWeekPicks(data.picks.week || []);
          setYearPicks(data.picks.year || []);
          setFiveyearPicks(data.picks.fiveyear || []);
        }
      })
      .catch((err) => console.log('Init cache empty', err));
  }, []);

  const handleRunEngine = () => {
    run.start({
      url: `/api/run/quantum?mode=${mode}`,
      subject: `QuanTum ${mode}`,
      onComplete: (data) => {
        setReport(data.report || '');
        setFilename(data.report_path ? data.report_path.replace(/^reports\//, '') : '');
        setWeekPicks(data.week_picks || []);
        setYearPicks(data.year_picks || []);
        setFiveyearPicks(data.fiveyear_picks || []);
        setHeadlines(data.headlines || []);
        setCreatedTime(new Date().toISOString().replace('T', ' ').substring(0, 16));
      },
    });
  };

  const handleDownloadPdf = () => {
    if (!report) return;
    setPdfGenerating(true);
    fetch(getApiUrl('/api/pdf'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ markdown: report })
    })
      .then(res => res.blob())
      .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `QuanTum_Picks_${new Date().toISOString().slice(0, 10)}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      })
      .catch(err => console.error("PDF generation error", err))
      .finally(() => setPdfGenerating(false));
  };

  const renderTable = (picks) => {
    if (picks.length === 0) {
      return (
        <div style={{ textAlign: "center", color: "var(--ink-subtle)", padding: "24px 0", fontSize: "0.85rem" }}>
          No pick records returned. Trigger a fresh Quant run.
        </div>
      );
    }

    return (
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Stock</th>
              <th>Score</th>
              <th>Price (₹)</th>
              <th>RSI</th>
              <th>P/E</th>
              <th>ROE (%)</th>
              <th>Entry Trigger</th>
            </tr>
          </thead>
          <tbody>
            {picks.map((row, idx) => (
              <tr key={idx}>
                <td style={{ fontWeight: "700", color: "var(--ink)" }}>{row.ticker}</td>
                <td>
                  <span className="score-badge" style={{
                    backgroundColor: row.composite_score >= 85 ? "var(--green-subtle)" : row.composite_score >= 70 ? "var(--brand-subtle)" : "var(--bg-surface)",
                    color: row.composite_score >= 85 ? "var(--green)" : row.composite_score >= 70 ? "var(--brand)" : "var(--ink-secondary)"
                  }}>
                    {row.composite_score ? row.composite_score.toFixed(1) : row.composite_score}
                  </span>
                </td>
                <td style={{ fontFamily: "monospace" }}>{row.close ? row.close.toFixed(2) : '-'}</td>
                <td style={{ color: row.rsi > 70 ? "var(--red)" : row.rsi < 30 ? "var(--green)" : "inherit" }}>
                  {row.rsi ? row.rsi.toFixed(1) : '-'}
                </td>
                <td>{row.pe_ratio ? row.pe_ratio.toFixed(1) : 'N/A'}</td>
                <td style={{ color: row.roe > 20 ? "var(--green)" : "inherit" }}>
                  {row.roe ? row.roe.toFixed(1) : '-'}
                </td>
                <td style={{ fontSize: "0.75rem", fontStyle: "italic" }}>{row.entry_status || 'Wait'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="report-section">
      <div style={{ borderBottom: "1px solid var(--border)", paddingBottom: "12px", marginBottom: "16px", fontSize: "0.8rem", color: "var(--ink-muted)" }}>
        <strong>Scoring Architecture weights:</strong> Technical Setup (35%), RSS News Sentiment (35%), Moat Fundamentals (15%), Price Momentum (15%).
      </div>

      <p className="sense-note">Ask Itachi to convene the QuanTum desk. He opens the engine, then the committee ranks the tape.</p>
      <div className="action-panel">
        <div className="control-group" style={{ minWidth: "150px" }}>
          <label className="control-label">Execution Mode</label>
          <div style={{ display: "flex", gap: "12px" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.82rem", cursor: "pointer" }}>
              <input type="radio" name="mode" value="fast" checked={mode === 'fast'} onChange={() => setMode('fast')} disabled={isRunning} />
              Fast (discovery)
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.82rem", cursor: "pointer" }}>
              <input type="radio" name="mode" value="full" checked={mode === 'full'} onChange={() => setMode('full')} disabled={isRunning} />
              Full (80+ Nifty Universe)
            </label>
          </div>
        </div>
        <ConveneButton running={isRunning} onClick={handleRunEngine} label="Ask Itachi to convene" />
      </div>

      <div className="card-grid">
        <div className="dashboard-card">
          <div className="card-header">
            <span className="card-title">Weekly Alpha Screener</span>
            <span className="card-status status-active">● Active</span>
          </div>
          <div className="card-metrics">
            <div className="metric-item"><div className="metric-label">WEIGHTS</div><div className="metric-value">Tech 35% + News 35%</div></div>
            <div className="metric-item"><div className="metric-label">HORIZON</div><div className="metric-value">1 - 5 Trading Days</div></div>
            <div className="metric-item"><div className="metric-label">UNIVERSE</div><div className="metric-value">Nifty 500 + RSS</div></div>
          </div>
          <div className="card-tags">
            <span className="card-tag active">● Swing Breakouts</span>
            <span className="card-tag">● Crossover Timings</span>
          </div>
        </div>

        <div className="dashboard-card">
          <div className="card-header">
            <span className="card-title">1-Year Compounders</span>
            <span className="card-status status-active">● Active</span>
          </div>
          <div className="card-metrics">
            <div className="metric-item"><div className="metric-label">WEIGHTS</div><div className="metric-value">Fund 50% + Mom 25%</div></div>
            <div className="metric-item"><div className="metric-label">HORIZON</div><div className="metric-value">6 - 12 Months</div></div>
            <div className="metric-item"><div className="metric-label">METRICS</div><div className="metric-value">ROE &gt; 18%, P/E Fair</div></div>
          </div>
          <div className="card-tags">
            <span className="card-tag active">● Quality Growth</span>
            <span className="card-tag">● Institutional Inflows</span>
          </div>
        </div>

        <div className="dashboard-card">
          <div className="card-header">
            <span className="card-title">5-Year Structural Wealth</span>
            <span className="card-status status-info">● Compounding</span>
          </div>
          <div className="card-metrics">
            <div className="metric-item"><div className="metric-label">WEIGHTS</div><div className="metric-value">Fund 60% + Moat 40%</div></div>
            <div className="metric-item"><div className="metric-label">HORIZON</div><div className="metric-value">3 - 5 Years Buy</div></div>
            <div className="metric-item"><div className="metric-label">RISK</div><div className="metric-value">Low Debt / High ROCE</div></div>
          </div>
          <div className="card-tags">
            <span className="card-tag active">● Moat Monopolies</span>
            <span className="card-tag">● Multi-Baggers</span>
          </div>
        </div>
      </div>

      {createdTime && (
        <div style={{
          backgroundColor: "var(--brand-subtle)",
          border: "1px solid var(--brand-border)",
          color: "var(--brand)",
          padding: "10px 14px",
          borderRadius: "var(--r-md)",
          fontSize: "0.8rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "16px"
        }}>
          <span><strong>Last Engine Execution:</strong> {createdTime} ({mode.toUpperCase()} mode)</span>
          <span style={{ fontSize: "0.7rem", fontWeight: "bold", textTransform: "uppercase" }}>CACHED & READY</span>
        </div>
      )}

      <CouncilChamber logs={logs} isRunning={isRunning} report={report} headline="Arsalaan’s Office" loading={isRunning && logs.length < 2} />
      <LogViewer logs={logs} isRunning={isRunning} />

      <div style={{ marginTop: "24px" }}>
        <div className="tab-group">
          <button className={`tab-item ${activeTab === 'week' ? 'active' : ''}`} onClick={() => setActiveTab('week')}>This Week</button>
          <button className={`tab-item ${activeTab === 'year' ? 'active' : ''}`} onClick={() => setActiveTab('year')}>This Year</button>
          <button className={`tab-item ${activeTab === 'fiveyear' ? 'active' : ''}`} onClick={() => setActiveTab('fiveyear')}>5 Years</button>
        </div>

        {activeTab === 'week' && (
          <div>
            <p style={{ fontSize: "0.75rem", color: "var(--ink-muted)", marginBottom: "10px" }}>Top picks for short term swing trading this week (technical + news sentiment dominant)</p>
            {renderTable(weekPicks)}
          </div>
        )}

        {activeTab === 'year' && (
          <div>
            <p style={{ fontSize: "0.75rem", color: "var(--ink-muted)", marginBottom: "10px" }}>Top quality compounders for 6-12 month positional holds</p>
            {renderTable(yearPicks)}
          </div>
        )}

        {activeTab === 'fiveyear' && (
          <div>
            <p style={{ fontSize: "0.75rem", color: "var(--ink-muted)", marginBottom: "10px" }}>Structural wealth compounders — buy and hold 5 years</p>
            {renderTable(fiveyearPicks)}
          </div>
        )}
      </div>

      {headlines.length > 0 && (
        <div className="report-card" style={{ marginTop: "16px" }}>
          <h4 style={{ fontSize: "0.9rem", fontWeight: "bold", marginBottom: "12px" }}>Ingested Sentiment RSS Headlines</h4>
          <div style={{ maxHeight: "150px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "6px" }}>
            {headlines.map((hl, i) => (
              <div key={i} style={{ fontSize: "0.78rem", color: "var(--ink-secondary)", paddingBottom: "4px", borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                <span style={{ color: "var(--brand)", marginRight: "6px" }}>[{hl.source}]</span>
                {hl.title}
              </div>
            ))}
          </div>
        </div>
      )}

      {report && (
        <div className="report-card" style={{ marginTop: "20px" }}>
          <div style={{ display: "flex", justifySelf: "stretch", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", width: "100%" }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: "bold" }}>Recommendation Report Summary</h3>
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
