import React, { useState } from 'react';
import LogViewer from './LogViewer';
import CouncilChamber from './CouncilChamber';
import { ConveneButton } from './Loader';
import { useCouncilRun } from './useCouncilRun';

export default function MarketNews() {
  const [scope, setScope] = useState('Global (India + World)');
  const [highImpact, setHighImpact] = useState([]);
  const [mediumImpact, setMediumImpact] = useState([]);
  const [fetched, setFetched] = useState(false);
  const run = useCouncilRun();
  const isRunning = run.isRunning;
  const logs = run.logs;

  const handleFetchNews = () => {
    const apiScope = scope.includes('Global') ? 'global' : 'india';
    setHighImpact([]);
    setMediumImpact([]);
    setFetched(false);
    run.start({
      url: `/api/run/news?scope=${apiScope}`,
      subject: `news desk (${apiScope})`,
      onComplete: (data) => {
        if (data.news) {
          setHighImpact(data.news.high_impact || []);
          setMediumImpact(data.news.medium_impact || []);
        }
        setFetched(true);
      },
    });
  };

  const getSentimentStyle = (sentiment) => {
    const s = sentiment ? sentiment.toUpperCase() : 'NEUTRAL';
    if (s === 'BULLISH' || s === 'POSITIVE') {
      return { color: "var(--green)", backgroundColor: "var(--green-subtle)", borderColor: "var(--green-border)" };
    }
    if (s === 'BEARISH' || s === 'NEGATIVE') {
      return { color: "var(--red)", backgroundColor: "var(--red-subtle)", borderColor: "var(--red-border)" };
    }
    return { color: "var(--ink-secondary)", backgroundColor: "var(--bg-surface)", borderColor: "var(--border)" };
  };

  return (
    <div className="report-section">
      <p className="sense-note">Ask Itachi to convene the news desk. Kakashi files headlines, then Itachi puts the brief on your desk.</p>
      <div className="action-panel">
        <div className="control-group">
          <label className="control-label">News Feed Scope</label>
          <select 
            className="form-select" 
            value={scope} 
            onChange={(e) => setScope(e.target.value)}
            disabled={isRunning}
          >
            <option>Global (India + World)</option>
            <option>India Only</option>
          </select>
        </div>
        <ConveneButton running={isRunning} onClick={handleFetchNews} />
      </div>

      <CouncilChamber logs={logs} isRunning={isRunning} headline="Arsalaan’s Office" loading={isRunning && logs.length < 2} />
      <LogViewer logs={logs} isRunning={isRunning} />

      {fetched && (
        <div style={{ marginTop: "24px" }}>
          <h3 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="material-symbols-rounded" style={{ color: "var(--red)" }}>campaign</span>
            High-Impact News (Market-Moving)
          </h3>
          
          {highImpact.length === 0 ? (
            <div style={{ padding: "16px", backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--r-md)", textAlign: "center", fontSize: "0.85rem", color: "var(--ink-muted)" }}>
              No high-impact news detected in this window.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "24px" }}>
              {highImpact.map((item, idx) => {
                const badgeStyle = getSentimentStyle(item.sentiment);
                return (
                  <div key={idx} style={{
                    backgroundColor: "var(--bg-card)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--r-md)",
                    padding: "16px"
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", flexWrap: "wrap", gap: "8px" }}>
                      <h4 style={{ fontSize: "0.95rem", fontWeight: "bold", color: "var(--ink)" }}>{item.title}</h4>
                      <span style={{
                        fontSize: "0.65rem",
                        fontWeight: "700",
                        padding: "2px 8px",
                        borderRadius: "var(--r-pill)",
                        border: "1px solid",
                        textTransform: "uppercase",
                        ...badgeStyle
                      }}>
                        {item.sentiment || 'NEUTRAL'}
                      </span>
                    </div>
                    <p style={{ fontSize: "0.85rem", color: "var(--ink-secondary)", lineHeight: "1.5", marginBottom: "10px" }}>
                      {item.summary || item.body || 'No summary text available.'}
                    </p>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.72rem", color: "var(--ink-subtle)" }}>
                      <span>Impact: <strong>{item.impact || 'MEDIUM'}</strong> | Catalyst: <strong>{item.event_type || 'General'}</strong></span>
                      {item.href && (
                        <a href={item.href} target="_blank" rel="noopener noreferrer" style={{ color: "var(--brand)", textDecoration: "none", fontWeight: "600" }}>
                          Read Article ↗
                        </a>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <h3 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="material-symbols-rounded" style={{ color: "var(--ink-subtle)" }}>article</span>
            Medium-Impact News
          </h3>
          
          {mediumImpact.length === 0 ? (
            <div style={{ padding: "16px", backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--r-md)", textAlign: "center", fontSize: "0.85rem", color: "var(--ink-muted)" }}>
              No medium-impact news parsed in this run.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {mediumImpact.map((item, idx) => (
                <div key={idx} style={{
                  backgroundColor: "var(--bg-card)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--r-md)",
                  padding: "12px 16px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: "16px"
                }}>
                  <div style={{ flexGrow: 1 }}>
                    <span style={{ fontSize: "0.85rem", fontWeight: "600", color: "var(--ink)" }}>{item.title}</span>
                    <p style={{ fontSize: "0.75rem", color: "var(--ink-muted)", marginTop: "4px" }}>
                      {item.summary ? item.summary.substring(0, 160) + '...' : ''}
                    </p>
                  </div>
                  <span style={{
                    fontSize: "0.6rem",
                    fontWeight: "700",
                    padding: "2px 8px",
                    borderRadius: "var(--r-pill)",
                    textTransform: "uppercase",
                    ...getSentimentStyle(item.sentiment)
                  }}>
                    {item.sentiment || 'NEUTRAL'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
