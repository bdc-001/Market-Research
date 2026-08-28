import { useRef, useState } from 'react';
import { getApiUrl } from './api';

export function editorConvenes(subject) {
  const label = subject ? ` on ${subject}` : '';
  return `Itachi (Editor): Sir, I will convene the committee${label}. Agents brief in order. I will place the memo on your desk.`;
}

export function useCouncilRun() {
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState([]);
  const [report, setReport] = useState(null);
  const [payload, setPayload] = useState(null);
  const esRef = useRef(null);
  const timerRef = useRef(null);

  const stop = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
  };

  const start = ({ url, subject, onComplete }) => {
    stop();
    setIsRunning(true);
    setLogs([editorConvenes(subject)]);
    setReport(null);
    setPayload(null);

    timerRef.current = setTimeout(() => {
      const es = new EventSource(getApiUrl(url));
      esRef.current = es;
      es.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'progress') {
          setLogs((prev) => {
            if (prev[prev.length - 1] === data.message) return prev;
            return [...prev, data.message];
          });
        } else if (data.type === 'complete') {
          setLogs((prev) => [...prev, 'Itachi (Editor): Memo is on your desk.']);
          setReport(data.report || null);
          setPayload(data);
          setIsRunning(false);
          es.close();
          esRef.current = null;
          onComplete?.(data);
        } else if (data.type === 'error') {
          setLogs((prev) => [...prev, `Error: ${data.message}`]);
          setIsRunning(false);
          es.close();
          esRef.current = null;
        }
      };
      es.onerror = () => {
        setLogs((prev) => [...prev, 'Connection error. Terminating pipeline.']);
        setIsRunning(false);
        es.close();
        esRef.current = null;
      };
    }, 700);
  };

  return { isRunning, logs, report, payload, start, stop };
}
