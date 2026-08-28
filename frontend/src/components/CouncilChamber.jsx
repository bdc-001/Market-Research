import React, { useEffect, useMemo, useState } from 'react';
import './CouncilChamber.css';

export const CEO = {
  id: 'ceo',
  name: 'Arsalaan Mohammed',
  role: 'CEO',
  title: 'Quantum Corporation',
  skin: '#d4a574',
  hair: '#1a120c',
  suit: '#111827',
  hairStyle: 'short',
};

export const COUNCIL = [
  { id: 'historian', name: 'Priya Mehta', role: 'Historian', title: 'Research', match: /historian|research|business|filings|verif/i, skin: '#e8b89a', hair: '#2c1810', suit: '#1e3a5f', hairStyle: 'bob', store: 'research' },
  { id: 'scout', name: 'Arjun Shah', role: 'Scout', title: 'News desk', match: /scout|news|catalyst|headline|rss|ingest/i, skin: '#c68642', hair: '#1a120c', suit: '#0f766e', hairStyle: 'short', store: 'scout' },
  { id: 'quant', name: 'Neha Kapoor', role: 'Quant', title: 'Valuation', match: /quant|valuat|factor|score|pe\b|roe|number|financial/i, skin: '#f1c27d', hair: '#3b2218', suit: '#4338ca', hairStyle: 'long', store: 'financial' },
  { id: 'bull', name: 'Rohan Iyer', role: 'Bull', title: 'Upside', match: /bull|upside|conviction|buy|opportun/i, skin: '#d8a07a', hair: '#4a2c1a', suit: '#047857', hairStyle: 'short', store: 'bull' },
  { id: 'bear', name: 'Meera Das', role: 'Bear', title: 'Risk', match: /bear|risk|downside|caution|reject|npa|debt/i, skin: '#edc4a3', hair: '#111827', suit: '#9f1239', hairStyle: 'bob', store: 'bear' },
  { id: 'chartist', name: 'Vikram Rao', role: 'Chartist', title: 'Technicals', match: /chart|technic|rsi|macd|sma|price action/i, skin: '#c58c5c', hair: '#0b0b0b', suit: '#1d4ed8', hairStyle: 'short', store: 'technical' },
  { id: 'editor', name: 'Ananya Krishnan', role: 'Editor', title: 'Chief of Staff', match: /editor|memo|synthes|complet|recommend|final|council/i, skin: '#e0ac86', hair: '#5c3317', suit: '#4c1d95', hairStyle: 'long', store: 'editor' },
];

export const STORE_TO_AGENT = Object.fromEntries(COUNCIL.map((a) => [a.store, a.id]));

export function speakerFromLogs(logs) {
  if (!logs?.length) return 'historian';
  const last = logs[logs.length - 1];
  for (const agent of COUNCIL) {
    if (agent.match.test(last)) return agent.id;
  }
  return COUNCIL[logs.length % COUNCIL.length].id;
}

export function turnsFromPredictions(predictions = [], episode = {}) {
  const ticker = episode.ticker || 'the name';
  const ordered = [...predictions].sort((a, b) => {
    const order = COUNCIL.map((c) => c.store);
    return order.indexOf(a.agent_name) - order.indexOf(b.agent_name);
  });
  const turns = ordered.map((pred) => {
    const agent = COUNCIL.find((c) => c.store === pred.agent_name) || COUNCIL[0];
    const dir = pred.prediction_direction || 'unspecified';
    const rec = pred.recommendation || 'watch';
    return {
      agentId: agent.id,
      text: `${agent.role} on ${ticker}: tape call ${dir}, desk view ${rec}.`,
    };
  });
  const decision = (episode.final_decision || 'watch').toUpperCase();
  turns.push({
    agentId: 'editor',
    text: `Sir, the committee has finished ${ticker}. Council decision: ${decision}. I am placing the memo on your desk.`,
    reportToCeo: true,
  });
  return turns;
}

function Portrait({ agent, speaking, ceo }) {
  const { skin, hair, suit, hairStyle } = agent;
  return (
    <svg viewBox="0 0 88 108" className={`portrait ${speaking ? 'is-talking' : ''} ${ceo ? 'is-ceo' : ''}`} aria-hidden="true">
      <ellipse cx="44" cy="98" rx="34" ry="16" fill={suit} />
      <path d="M18 98 C22 78 30 70 44 70 C58 70 66 78 70 98" fill={suit} />
      {ceo && <path d="M40 78 L44 70 L48 78 Z" fill="#d4af37" />}
      <rect x="38" y="62" width="12" height="14" rx="5" fill={skin} />
      <circle cx="44" cy="42" r="22" fill={skin} />
      {hairStyle === 'bob' && (
        <path d="M22 40 C22 18 32 16 44 16 C56 16 66 18 66 40 L64 52 C60 44 54 42 44 42 C34 42 28 44 24 52 Z" fill={hair} />
      )}
      {hairStyle === 'long' && (
        <>
          <path d="M20 38 C22 16 32 14 44 14 C56 14 66 16 68 38 L70 70 C62 58 54 52 44 52 C34 52 26 58 18 70 Z" fill={hair} />
          <path d="M22 54 C20 68 22 82 26 90 C30 78 32 64 34 54 Z" fill={hair} />
          <path d="M66 54 C68 68 66 82 62 90 C58 78 56 64 54 54 Z" fill={hair} />
        </>
      )}
      {hairStyle === 'short' && (
        <path d="M23 38 C24 18 34 14 44 14 C54 14 64 18 65 38 C62 28 54 24 44 24 C34 24 26 28 23 38 Z" fill={hair} />
      )}
      <g className="eyes">
        <ellipse cx="36" cy="42" rx="3.2" ry="3.6" fill="#1f2937" />
        <ellipse cx="52" cy="42" rx="3.2" ry="3.6" fill="#1f2937" />
        <circle cx="37" cy="41" r="0.9" fill="#fff" />
        <circle cx="53" cy="41" r="0.9" fill="#fff" />
      </g>
      <path className="brow" d="M31 36 Q36 33 41 36" stroke="#1f2937" strokeWidth="1.4" fill="none" />
      <path className="brow" d="M47 36 Q52 33 57 36" stroke="#1f2937" strokeWidth="1.4" fill="none" />
      <ellipse className="mouth" cx="44" cy="54" rx="5.5" ry="2.2" fill="#b4534a" />
    </svg>
  );
}

export default function CouncilChamber({
  logs = [],
  isRunning = false,
  headline = "Arsalaan's Office",
  script = null,
  subject = '',
  report = '',
  decision = '',
}) {
  const [tick, setTick] = useState(0);
  const [scriptIndex, setScriptIndex] = useState(0);

  const scriptTurns = script && script.length ? script : null;
  const playingScript = Boolean(scriptTurns);

  useEffect(() => {
    setScriptIndex(0);
  }, [scriptTurns, subject]);

  useEffect(() => {
    if (!playingScript) return undefined;
    if (scriptIndex >= scriptTurns.length - 1) return undefined;
    const id = setTimeout(() => setScriptIndex((n) => n + 1), 2400);
    return () => clearTimeout(id);
  }, [playingScript, scriptIndex, scriptTurns]);

  useEffect(() => {
    if (!isRunning && !playingScript) return undefined;
    const id = setInterval(() => setTick((n) => n + 1), 400);
    return () => clearInterval(id);
  }, [isRunning, playingScript]);

  const inferred = useMemo(() => speakerFromLogs(logs), [logs]);
  const scriptTurn = playingScript ? scriptTurns[Math.min(scriptIndex, scriptTurns.length - 1)] : null;
  const speakerId = playingScript
    ? scriptTurn?.agentId
    : (isRunning ? inferred : (report ? 'editor' : null));
  const spokenIds = useMemo(() => {
    const ids = new Set();
    if (playingScript) {
      scriptTurns.slice(0, scriptIndex + 1).forEach((t) => ids.add(t.agentId));
      return ids;
    }
    logs.forEach((line) => {
      COUNCIL.forEach((a) => { if (a.match.test(line)) ids.add(a.id); });
    });
    return ids;
  }, [logs, playingScript, scriptIndex, scriptTurns]);

  const latest = playingScript
    ? (scriptTurn?.text || '')
    : (logs.length ? logs[logs.length - 1] : '');
  const speaker = COUNCIL.find((a) => a.id === speakerId);
  const reporting = Boolean(
    (scriptTurn && scriptTurn.reportToCeo) || (!isRunning && report)
  );
  const live = isRunning || (playingScript && scriptIndex < (scriptTurns?.length || 1) - 1);
  const briefLine = decision
    ? `Council decision: ${String(decision).toUpperCase()}${subject ? ` on ${subject}` : ''}`
    : (report ? String(report).slice(0, 220) : '');

  return (
    <section className={`chamber office ${live ? 'is-live' : ''} ${reporting ? 'is-briefing' : ''}`}>
      <div className="chamber-head">
        <div>
          <p className="chamber-kicker">Quantum Corporation · Arsalaan’s Office</p>
          <h3>{live ? 'Desk in session' : reporting ? 'Memo on the CEO desk' : headline}</h3>
        </div>
        <div className={`session-pill ${live ? 'live' : reporting ? 'brief' : ''}`}>
          <span className="session-dot" />
          {live ? 'LIVE' : reporting ? 'REPORTED' : 'STANDBY'}
        </div>
      </div>

      <div className="ceo-desk">
        <div className={`ceo-card ${reporting ? 'receiving' : ''}`}>
          <div className="avatar-wrap ceo-avatar">
            <Portrait agent={CEO} speaking={false} ceo />
            {reporting && <div className="folder-fly" aria-hidden="true">📄</div>}
          </div>
          <div className="ceo-meta">
            <strong>{CEO.name}</strong>
            <span className="agent-role">CEO · Quantum Corporation</span>
            <span className="agent-title">
              {reporting ? 'Receiving the committee memo' : live ? 'Listening to the desk' : 'Waiting for a briefing'}
            </span>
            {reporting && briefLine && (
              <p className="ceo-brief">{briefLine}</p>
            )}
          </div>
        </div>
        {reporting && (
          <p className="handoff-line">
            <em>Ananya Krishnan</em> (Editor / Chief of Staff) reports to you.
          </p>
        )}
      </div>

      <p className="staff-label">Investment committee</p>
      <div className="chamber-grid">
        {COUNCIL.map((agent, i) => {
          const speaking = speakerId === agent.id;
          const done = spokenIds.has(agent.id) && !speaking && !live;
          const waiting = live && !speaking && !spokenIds.has(agent.id);
          return (
            <article
              key={agent.id}
              className={[
                'agent-seat',
                speaking ? 'speaking' : '',
                done ? 'done' : '',
                waiting ? 'waiting' : '',
                spokenIds.has(agent.id) && live && !speaking ? 'listened' : '',
                agent.id === 'editor' && reporting ? 'reporter' : '',
              ].join(' ')}
              style={{ animationDelay: `${i * 50}ms` }}
            >
              {speaking && latest && (
                <div className="speech-bubble" key={`${latest}-${tick}`}>
                  {latest}
                </div>
              )}
              <div className="avatar-wrap">
                <span className="ring" />
                <Portrait agent={agent} speaking={speaking} />
                {speaking && (
                  <div className="voice-bars" aria-hidden="true">
                    <i /><i /><i /><i /><i />
                  </div>
                )}
              </div>
              <strong>{agent.name}</strong>
              <span className="agent-role">{agent.role}</span>
              <span className="agent-title">
                {speaking ? 'Speaking…' : agent.id === 'editor' && reporting ? 'Reporting to CEO' : done ? 'Filed' : agent.title}
              </span>
            </article>
          );
        })}
      </div>

      <div className="speech-dock" aria-live="polite">
        {latest ? (
          <>
            <span className="dock-who">{speaker ? speaker.role : 'Desk'}</span>
            <span className="dock-text">{latest}</span>
          </>
        ) : (
          <span className="dock-text muted">Tap Replay briefing on an episode, or run an analysis to open the office.</span>
        )}
      </div>
    </section>
  );
}
