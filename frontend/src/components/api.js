// api.js
export const getApiUrl = (path) => {
  // If VITE_API_URL env variable is provided (e.g. "https://quantum-backend.onrender.com"), use it.
  // Otherwise, default to relative paths (for monorepo single-server setups).
  const base = import.meta.env.VITE_API_URL || '';
  return `${base}${path}`;
};
