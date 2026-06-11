/**
 * api.js — HTTP клієнт для Manager API.
 *
 * БЕЗПЕКА: API ключ НЕ зберігається у фронтенд-коді і НЕ вбудовується
 * у зібраний JS (де він був би видимий у DevTools будь-кому).
 *
 * Схема:
 *   Browser → /api/* → Nginx (додає X-API-Key з серверної змінної) → FastAPI
 *
 * В dev-режимі (vite dev server) запити проксіюються через vite.config.js,
 * а X-API-Key додається Nginx або встановлюється вручну через
 * dashboard/.env.local (тільки для локальної розробки, не для prod).
 *
 * Для prod: VITE_API_KEY не використовується. Ключ інжектується Nginx:
 *   proxy_set_header X-API-Key $MANAGER_API_KEY;  # зі змінної середовища Nginx
 */

// В dev режимі можна виставити VITE_API_KEY у .env.local для зручності.
// В prod це значення має бути порожнім — ключ додає Nginx.
const DEV_KEY = import.meta.env.VITE_API_KEY || "";

// Базовий URL: у prod запити йдуть через /api/ (відносний шлях → Nginx проксі).
// У dev — через vite proxy (налаштовано у vite.config.js).
const BASE = "";

async function request(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  // Dev-режим: додаємо ключ якщо виставлений у .env.local
  // Prod-режим: Nginx вже додав заголовок до запиту, DEV_KEY порожній
  if (DEV_KEY) {
    headers["X-API-Key"] = DEV_KEY;
  }

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  /** GET /api/instances?status_filter=... */
  listInstances(statusFilter = null) {
    const qs = statusFilter ? `?status_filter=${statusFilter}` : "";
    return request(`/api/instances${qs}`);
  },

  /** POST /api/instances/create */
  create(subdomain, tgBotToken) {
    return request("/api/instances/create", {
      method: "POST",
      body: JSON.stringify({ subdomain, tg_bot_token: tgBotToken }),
    });
  },

  /** GET /api/instances/{id}/logs?tail=N */
  getLogs(id, tail = 100, signal = undefined) {
    return request(`/api/instances/${id}/logs?tail=${tail}`, { signal });
  },

  /** POST /api/instances/{id}/retry */
  retry(id) {
    return request(`/api/instances/${id}/retry`, { method: "POST" });
  },

  /** POST /api/instances/{id}/action  body: { action: "stop"|"start"|"restart" } */
  action(id, action) {
    return request(`/api/instances/${id}/action`, {
      method: "POST",
      body: JSON.stringify({ action }),
    });
  },


  /** POST /api/instances/{id}/backup */
  backup(id) {
    return request(`/api/instances/${id}/backup`, { method: "POST" });
  },

  /** DELETE /api/instances/{id}?confirm=true */
  deleteInstance(id) {
    return request(`/api/instances/${id}?confirm=true`, { method: "DELETE" });
  },
  /** GET /api/instances/{id}/operator */
  getOperatorInfo(id) {
    return request(`/api/instances/${id}/operator`);
  },
  /** POST /api/instances/{id}/maintenance  body: { action: "enable"|"disable" } */
  maintenance(id, action) {
    return request(`/api/instances/${id}/maintenance`, {
      method: "POST",
      body: JSON.stringify({ action }),
    });
  },
  /** WebSocket підключення до /api/ws */
  wsConnect(onMessage) {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${location.host}/api/ws`;
    const ws = new WebSocket(url);
    ws.onmessage = (e) => {
      try { onMessage(JSON.parse(e.data)); } catch (_) {}
    };
    ws.onerror = () => {};
    return ws;
  },
};
