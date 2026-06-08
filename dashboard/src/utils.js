/**
 * utils.js — спільні утиліти для компонентів дашборду.
 */

export function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return (
    d.toLocaleDateString("uk", { day: "2-digit", month: "2-digit", year: "2-digit" }) +
    " " +
    d.toLocaleTimeString("uk", { hour: "2-digit", minute: "2-digit" })
  );
}

const STATUS_STYLES = {
  active: {
    fontSize: 10, padding: "2px 7px", borderRadius: 3, fontWeight: 500,
    letterSpacing: "0.04em", textAlign: "center",
    background: "var(--green-bg)", color: "var(--green)",
  },
  provisioning: {
    fontSize: 10, padding: "2px 7px", borderRadius: 3, fontWeight: 500,
    letterSpacing: "0.04em", textAlign: "center",
    background: "var(--amber-bg)", color: "var(--amber)",
  },
  failed: {
    fontSize: 10, padding: "2px 7px", borderRadius: 3, fontWeight: 500,
    letterSpacing: "0.04em", textAlign: "center",
    background: "var(--red-bg)", color: "var(--red)",
  },
  stopped: {
    fontSize: 10, padding: "2px 7px", borderRadius: 3, fontWeight: 500,
    letterSpacing: "0.04em", textAlign: "center",
    background: "var(--surface)", color: "var(--muted)",
    border: "0.5px solid var(--border)",
  },
};

export function statusBadgeStyle(status) {
  return STATUS_STYLES[status] || STATUS_STYLES.stopped;
}

const INDICATOR_COLORS = {
  active:       { background: "#639922" },
  provisioning: { background: "#BA7517", animation: "pulse 1.4s infinite" },
  failed:       { background: "#E24B4A" },
  stopped:      { background: "#888780" },
};

export function indicatorStyle(status) {
  return INDICATOR_COLORS[status] || INDICATOR_COLORS.stopped;
}
