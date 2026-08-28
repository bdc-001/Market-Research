// api.js
export const getApiUrl = (path) => {
  const base = import.meta.env.VITE_API_URL || '';
  return `${base}${path}`;
};

export async function fetchJson(path, { tries = 3, signal } = {}) {
  let last;
  for (let i = 0; i < tries; i++) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    try {
      const res = await fetch(getApiUrl(path), { signal });
      if (res.ok) return res.json();
      last = new Error(`Could not load ${path} (${res.status})`);
    } catch (err) {
      if (err.name === 'AbortError') throw err;
      last = err;
    }
    await new Promise((resolve) => setTimeout(resolve, 450 * (i + 1)));
  }
  throw last || new Error(`Could not load ${path}`);
}
