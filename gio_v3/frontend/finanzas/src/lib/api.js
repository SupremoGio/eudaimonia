// Cliente de la API de Estados de cuenta. Mismos endpoints que el bundle
// anterior: todo cuelga de window.__EU_API_BASE__ (/finanzas/estados/api),
// que define templates/finanzas/estados.html. El fetch global del layout ya
// añade el header CSRF a las peticiones same-origin.
export const BASE = (typeof window !== 'undefined' && window.__EU_API_BASE__) || '/finanzas/estados/api';
export const ADMIN = BASE.replace(/\/api\/?$/, '/admin');

export function qs(params) {
  if (!params) return '';
  const u = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') u.append(k, v);
  });
  const s = u.toString();
  return s ? `?${s}` : '';
}

async function request(method, url, body) {
  const init = { method, credentials: 'same-origin', headers: {} };
  if (body instanceof FormData) init.body = body;
  else if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  const res = await fetch(url, init);
  let data = null;
  try { data = await res.json(); } catch { data = null; }
  if (!res.ok) {
    const err = new Error((data && data.error) || `Error ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  get: (path, params) => request('GET', BASE + path + qs(params)),
  post: (path, body) => request('POST', BASE + path, body === undefined ? {} : body),
  patch: (path, body) => request('PATCH', BASE + path, body),
  del: (path) => request('DELETE', BASE + path),
  admin: (path, params) => request('GET', ADMIN + path + qs(params)),
  upload: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return request('POST', BASE + '/upload', fd);
  },
  csvUrl: (params) => BASE + '/transactions/export/csv' + qs(params),
};
