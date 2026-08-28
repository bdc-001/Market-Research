import React, { useEffect, useMemo, useState } from 'react';
import './CouncilChamber.css';

export const COUNCIL = [
  { id: 'historian', name: 'Priya Mehta', role: 'Historian', title: 'Fundamental research', match: /historian|research|business|filings|verif/i, skin: '#e8b89a', hair: '#2c1810', suit: '#1e3a5f', hairStyle: 'bob' },
  { id: 'scout', name: 'Arjun Shah', role: 'Scout', title: 'News & catalysts', match: /scout|news|catalyst|headline|rss|ingest/i, skin: '#c68642', hair: '#1a120c', suit: '#0f766e', hairStyle: 'short' },
  { id: 'quant', name: 'Neha Kapoor', role: 'Quant', title: 'Valuation & factors', match: /quant|valuat|factor|score|pe\b|roe|number/i, skin: '#f1c27d', hair: '#3b2218', suit: '#4338ca', hairStyle: 'long' },
  { id: 'bull', name: 'Rohan Iyer', role: 'Bull', title: 'Upside case', match: /bull|upside|conviction|buy|opportun/i, skin: '#d8a07a', hair: '#4a2c1a', suit: '#047857', hairStyle: 'short' },
  { id: 'bear', name: 'Meera Das', role: 'Bear', title: 'Risk & downside', match: /bear|risk|downside|caution|reject|npa|debt/i, skin: '#edc4a3', hair: '#111827', suit: '#9f1239', hairStyle: 'bob' },
  { id: 'chartist', name: 'Vikram Rao', role: 'Chartist', title: 'Technical setup', match: /chart|technic|rsi|macd|sma|price action/i, skin: '#c58c5c', hair: '#0b0b0b', suit: '#1d4ed8', hairStyle: 'short' },
  { id: 'editor', name: 'Ananya Krishnan', role: 'Editor', title: 'Investment memo', match: /editor|memo|synthes|complet|recommend|final|council/i, skin: '#e0ac86', hair: '#5c3317', suit: '#4c1d95', hairStyle: 'long' },
];

export function speakerFromLogs(logs) {
  if (!logs?.length) return 'historian';
  const last = logs[logs.length - 1];
  for (const agent of COUNCIL) {
    if (agent.match.test(last)) return agent.id;
  }
  return COUNCIL[logs.length % COUNCIL.length].id;
}

function Portrait({ agent, speaking }) {
  const { skin, hair, suit, hairStyle } = agent;
  return (
    <svg viewBox="0 0 88 108" className={`portrait ${speaking ? 'is-talking' : ''}`} aria-hidden="true">
      <ellipse cx="44" cy="98" rx="34" ry="16" fill={suit} />
      <path d="M18 98 C22 78 30 70 44 70 C58 70 66 78 70 98" fill={suit} />
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

export default function CouncilChamber({ logs = [], isRunning = false, headline = 'Investment Committee' }) {
  const [tick, setTick] = useState(0);
  const inferred = useMemo(() => speakerFromLogs(logs), [logs]);
  const speakerId = isRunning ? inferred : null;
  const spokenIds = useMemo(() => {
    const ids = new Set();
    logs.forEach((line) => {
      COUNCIL.forEach((a) => { if (a.match.test(line)) ids.add(a.id); });
    });
    return ids;
  }, [logs]);

  useEffect(() => {
    if (!isRunning) return undefined;
    const id = setInterval(() => setTick((n) => n + 1), 400);
    return () => clearInterval(id);
  }, [isRunning]);

  const latest = logs.length ? logs[logs.length - 1] : '';
  const speaker = COUNCIL.find((a) => a.id === speakerId);

  return (
    <section className={`chamber ${isRunning ? 'is-live' : ''}`}>
      <div className="chamber-head">
        <div>
          <p className="chamber-kicker">{headline}</p>
          <h3>{isRunning ? 'Committee in session' : 'Analysts on standby'}</h3>
        </div>
        <div className={`session-pill ${isRunning ? 'live' : ''}`}>
          <span className="session-dot" />
          {isRunning ? 'LIVE BRIEFING' : 'READY'}
        </div>
      </div>

      <div className="chamber-grid">
        {COUNCIL.map((agent, i) => {
          const speaking = speakerId === agent.id;
          const done = !isRunning && spokenIds.has(agent.id);
          const waiting = isRunning && !speaking && !spokenIds.has(agent.id);
          return (
            <article
              key={agent.id}
              className={[
                'agent-seat',
                speaking ? 'speaking' : '',
                done ? 'done' : '',
                waiting ? 'waiting' : '',
                spokenIds.has(agent.id) && isRunning && !speaking ? 'listened' : '',
              ].join(' ')}
              style={{ animationDelay: `${i * 60}ms` }}
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
              <span className="agent-title">{speaking ? 'Speaking…' : done ? 'Brief filed' : agent.title}</span>
            </article>
          );
        })}
      </div>

      {speaker && isRunning && (
        <p className="now-speaking">
          <em>{speaker.name}</em> · {speaker.role} is addressing the desk
        </p>
      )}
    </section>
  );
}
