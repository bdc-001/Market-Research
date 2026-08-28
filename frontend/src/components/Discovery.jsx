import React, { useEffect, useMemo, useState } from 'react';
import { getApiUrl } from './api';
import CouncilChamber, { turnsFromPredictions } from './CouncilChamber';
import LogViewer from './LogViewer';
import { ConveneButton, MetricSkeletons, SenseLoader } from './Loader';
import { useCouncilRun } from './useCouncilRun';

const AGENT_ORDER = ['research', 'financial', 'bull', 'bear', 'technical', 'editor'];
const AGENT_LABELS = {
  research: 'Hashirama · Historian',
  financial: 'Sasuke · Quant',
  bull: 'Naruto · Bull',
  bear: 'Madara · Bear',
  technical: 'Minato · Chartist',
  editor: 'Itachi · Editor',
};

function decisionClass(decision) {
  const d = (decision || 'watch').toLowerCase();
  if (d === 'buy') return 'status-active';
  if (d === 'reject') return 'status-warning';
  return 'status-info';
}

function fmtPct(value) {
  if (value === null || value === undefined || value === '') return 'pending';
  const n = Number(value);
  if (Number.isNaN(n)) return 'pending';
  const sign = n >= 0 ? '+' : '';
  return `${sign}${(n * 100).toFixed(2)}%`;
}

function fmtPrice(value) {
  if (value === null || value === undefined || value === '') return '—';
  const n = Number(value);
  if (Number.isNaN(n)) return '—';
  return `₹${n.toFixed(2)}`;
}

export default function Discovery() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');
  const [typeFilter, setTypeFilter] = useState('All');
  const [selectedId, setSelectedId] = useState('');
  const [detail, setDetail] = useState(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [callTicker, setCallTicker] = useState('');
  const [replayKey, setReplayKey] = useState(0);
  const run = useCouncilRun();

  const loadEpisodes = (preferId) => {
    setLoadingList(true);
    return fetch(getApiUrl('/api/discovery/episodes'))
      .then((res) => {
        if (!res.ok) throw new Error('Could not load Discovery episodes');
        return res.json();
      })
      .then((data) => {
        setSummary(data);
        const ids = (data.episodes || []).map((e) => e.id);
        if (preferId && ids.includes(preferId)) setSelectedId(preferId);
        else if (data.episodes?.length && !selectedId) setSelectedId(data.episodes[0].id);
      })
      .catch((err) => setError(err.message || 'Discovery unavailable'))
      .finally(() => setLoadingList(false));
  };

  useEffect(() => {
    loadEpisodes();
  }, []);

  const filtered = useMemo(() => {
    const rows = summary?.episodes || [];
    if (typeFilter === 'All') return rows;
    return rows.filter((ep) => (ep.event_type || 'unclassified') === typeFilter);
  }, [summary, typeFilter]);

  useEffect(() => {
    if (!filtered.length) {
      setSelectedId('');
      return;
    }
    if (!filtered.some((ep) => ep.id === selectedId)) {
      setSelectedId(filtered[0].id);
    }
  }, [filtered, selectedId]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return undefined;
    }
    setLoadingDetail(true);
    fetch(getApiUrl(`/api/discovery/episodes/${selectedId}`))
      .then((res) => {
        if (!res.ok) throw new Error('Episode not found');
        return res.json();
      })
      .then((data) => {
        setDetail(data);
        if (data.episode?.ticker && !callTicker) setCallTicker(data.episode.ticker);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoadingDetail(false));
  }, [selectedId]);

  const types = Object.keys(summary?.event_types || {}).sort();
  const ep = detail?.episode;
  const predictions = [...(detail?.predictions || [])].sort((a, b) => {
    const ia = AGENT_ORDER.indexOf(a.agent_name);
    const ib = AGENT_ORDER.indexOf(b.agent_name);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  const officeScript = useMemo(
    () => (detail?.episode ? turnsFromPredictions(detail.predictions || [], detail.episode) : []),
    [detail, replayKey],
  );

  const handleConvene = () => {
    const ticker = (callTicker || ep?.ticker || '').toUpperCase().trim();
    if (!ticker) return;
    setError('');
    setCallTicker(ticker);
    run.start({
      url: `/api/run/discovery?ticker=${encodeURIComponent(ticker)}`,
      subject: ticker,
      onComplete: (data) => {
        if (data.episode_id) loadEpisodes(data.episode_id);
      },
    });
  };

  return (
    <div className="report-section">
      <div className="disc-pipe">
        {['Editor', 'Evidence', 'Council', 'Predictions'].map((step) => (
          <React.Fragment key={step}>
            <span className="disc-step on">{step}</span>
            <span className="disc-arrow">→</span>
          </React.Fragment>
        ))}
        <span className="disc-step">Outcomes (pending)</span>
      </div>

      <p className="sense-note">
        Ask Itachi to convene. He loads the evidence pack, then Historian → Quant → Bull → Bear → Chartist brief, then he puts the memo on your desk.
        Agents are not taught. Lessons stay empty. CHAVDA is episode #1, not a rule.
      </p>

      {error && <div className="alert-box alert-error">{error}</div>}

      {loadingList && !summary ? (
        <MetricSkeletons />
      ) : (
        <div className="sense-metric-grid">
          {[
            { label: 'Database', value: summary?.turso ? 'Turso' : 'Local empty', hint: 'Cloud ledger' },
            { label: 'Council episodes', value: summary?.count ?? '—', hint: 'Filed memos' },
            { label: 'Event types', value: types.length || '—', hint: 'Filing classes' },
            { label: '30D still pending', value: summary?.pending_30 ?? '—', hint: 'Awaiting tape' },
            { label: 'Lessons written', value: 0, hint: 'Learning off' },
          ].map((card, i) => (
            <article key={card.label} className="sense-metric-card" style={{ animationDelay: `${i * 70}ms` }}>
              <div className="metric-label">{card.label}</div>
              <div className="disc-metric">{card.value}</div>
              <p className="sense-metric-hint">{card.hint}</p>
            </article>
          ))}
        </div>
      )}

      <div className="action-panel">
        <div className="control-group">
          <label className="control-label">Ask Itachi · ticker</label>
          <input
            className="form-input"
            value={callTicker}
            onChange={(e) => setCallTicker(e.target.value.toUpperCase())}
            placeholder="e.g. CHAVDA, EXCELSOFT"
            disabled={run.isRunning}
            onKeyDown={(e) => e.key === 'Enter' && handleConvene()}
          />
        </div>
        <ConveneButton
          running={run.isRunning}
          disabled={!callTicker.trim()}
          onClick={handleConvene}
        />
      </div>

      <div className="action-panel">
        <div className="control-group">
          <label className="control-label">Event type</label>
          <select className="form-select" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option>All</option>
            {types.map((t) => <option key={t}>{t}</option>)}
          </select>
        </div>
        <div className="control-group" style={{ flexGrow: 2 }}>
          <label className="control-label">Stored episode</label>
          <select className="form-select" value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
            {filtered.map((row, i) => (
              <option key={row.id} value={row.id}>
                {i + 1}. {row.ticker} · {row.event_type || '—'} · {(row.final_decision || 'watch').toUpperCase()}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loadingList && !summary && <SenseLoader label="Loading Discovery ledger…" />}

      {!loadingList && !summary?.episodes?.length && !error && (
        <div className="report-card">
          <h3 style={{ fontSize: '1.05rem', fontWeight: 800, marginBottom: 8 }}>No Discovery episodes in the connected database</h3>
          <p style={{ color: 'var(--ink-secondary)', lineHeight: 1.55 }}>
            Ask Itachi to convene on a ticker that already has an evidence pack, or sync Turso so stored episodes appear.
          </p>
        </div>
      )}

      <CouncilChamber
        key={run.isRunning ? 'live' : `${ep?.id || 'empty'}-${replayKey}`}
        logs={run.logs}
        isRunning={run.isRunning}
        script={!run.isRunning && officeScript.length ? officeScript : null}
        subject={run.isRunning ? callTicker : (ep?.ticker || callTicker)}
        decision={run.payload?.decision || ep?.final_decision}
        headline="Arsalaan’s Office"
        loading={loadingDetail && !ep}
      />
      {(run.isRunning || run.logs.length > 0) && (
        <LogViewer logs={run.logs} isRunning={run.isRunning} />
      )}

      {ep && !run.isRunning && (
        <button
          className="btn"
          style={{ marginBottom: 16, alignSelf: 'flex-start' }}
          onClick={() => setReplayKey((n) => n + 1)}
        >
          Replay stored briefing
        </button>
      )}

      {ep && (
        <div className="report-card">
          <div className="card-header" style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>
              {ep.ticker}{' '}
              <span className={`card-status ${decisionClass(ep.final_decision)}`}>
                {(ep.final_decision || 'watch').toUpperCase()}
              </span>
            </h3>
            <span className="card-tag">#{(summary?.episodes || []).findIndex((r) => r.id === ep.id) + 1}</span>
          </div>

          {loadingDetail && <SenseLoader label="Loading committee file…" />}

          <div className="card-metrics" style={{ border: 'none', marginBottom: 18 }}>
            <div className="metric-item">
              <div className="metric-label">EVENT TYPE</div>
              <div className="metric-value">{ep.event_type || '—'}</div>
            </div>
            <div className="metric-item">
              <div className="metric-label">ENTRY</div>
              <div className="metric-value">{fmtPrice(ep.entry_price)}</div>
            </div>
            <div className="metric-item">
              <div className="metric-label">ENTRY DATE</div>
              <div className="metric-value">{ep.entry_date || '—'}</div>
            </div>
            <div className="metric-item">
              <div className="metric-label">30D DUE</div>
              <div className="metric-value">{ep.due_30 || '—'}</div>
            </div>
          </div>

          <h4 style={{ fontSize: '0.9rem', marginBottom: 10 }}>Stored predictions</h4>
          <p style={{ fontSize: '0.75rem', color: 'var(--ink-muted)', marginBottom: 10 }}>
            Not interchangeable with the Council decision. Editor decided <b>{(ep.final_decision || 'watch').toUpperCase()}</b>.
          </p>
          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Agent</th>
                  <th>Prediction</th>
                  <th>Confidence</th>
                  <th>Recommendation</th>
                </tr>
              </thead>
              <tbody>
                {predictions.length === 0 ? (
                  <tr><td colSpan={4} style={{ color: 'var(--ink-muted)' }}>No predictions stored.</td></tr>
                ) : predictions.map((pred) => (
                  <tr key={pred.id || pred.agent_name}>
                    <td style={{ fontWeight: 700 }}>{AGENT_LABELS[pred.agent_name] || pred.agent_name}</td>
                    <td>{pred.prediction_direction || '—'}</td>
                    <td>{pred.confidence == null || pred.confidence === '' ? '—' : Number(pred.confidence).toFixed(2)}</td>
                    <td>{pred.recommendation || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h4 style={{ fontSize: '0.9rem', margin: '20px 0 10px' }}>Horizons</h4>
          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Horizon</th>
                  <th>Status</th>
                  <th>Abs return</th>
                  <th>NIFTY</th>
                  <th>Relative</th>
                </tr>
              </thead>
              <tbody>
                {(detail?.horizons || []).length === 0 ? (
                  <tr><td colSpan={5} style={{ color: 'var(--ink-muted)' }}>Pending 30/60/90/180/365D slots. First CHAVDA 30D is 2026-09-25.</td></tr>
                ) : detail.horizons.map((h) => (
                  <tr key={h.horizon_days}>
                    <td>{h.horizon_days}D</td>
                    <td>{h.status || 'pending'}</td>
                    <td>{fmtPct(h.absolute_return)}</td>
                    <td>{fmtPct(h.nifty_return)}</td>
                    <td>{fmtPct(h.relative_return)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
