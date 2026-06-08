import { useState, useEffect, useRef } from "react";
import { fmtDate } from "../utils";
import { api } from "../api";

export default function DetailPanel({ instance, onClose, onAction }) {
  const [logs, setLogs]       = useState(null);
  const [logsLoading, setLL]  = useState(false);
  const [tailLines, setTail]  = useState(100);
  const abortRef              = useRef(null);

  const fetchLogs = async (tail = tailLines) => {
    // Скасовуємо попередній запит якщо ще не завершився
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLL(true);
    try {
      const data = await api.getLogs(instance.id, tail, controller.signal);
      if (!controller.signal.aborted) setLogs(data);
    } catch (e) {
      if (!controller.signal.aborted)
        setLogs({ source: "error", logs: e.message });
    } finally {
      if (!controller.signal.aborted) setLL(false);
    }
  };

  useEffect(() => {
    setLogs(null);
    fetchLogs();
    // Cleanup: скасовуємо запит при розмонтуванні або зміні instance
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, [instance.id]);

  const handleAction = async (action) => {
    await onAction(instance.id, action);
  };

  const handleBackup = async () => {
    try {
      await api.backup(instance.id);
      // showToast недоступний тут — повідомлення через батьківський компонент
      alert(`Бекап запущено: /opt/printbot/backups/${instance.subdomain}`);
    } catch (e) {
      alert(`Помилка бекапу: ${e.message}`);
    }
  };

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <div style={styles.title}>{instance.subdomain}.printbot.app</div>
        <button style={styles.closeBtn} onClick={onClose} aria-label="Закрити">✕</button>
      </div>

      <div style={styles.grid}>
        <Field label="instance id"  value={instance.id} mono />
        <Field label="status"       value={instance.status} />
        <Field label="created"      value={fmtDate(instance.created_at)} mono />
        <Field label="updated"      value={fmtDate(instance.updated_at)} mono />
      </div>

      <div style={styles.logsHeader}>
        <div style={styles.sectionLabel}>logs</div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <select
            value={tailLines}
            onChange={(e) => { setTail(Number(e.target.value)); fetchLogs(Number(e.target.value)); }}
            style={styles.select}
          >
            {[50, 100, 200, 500].map((n) => (
              <option key={n} value={n}>tail {n}</option>
            ))}
          </select>
          <button style={styles.smallBtn} onClick={() => fetchLogs(tailLines)} disabled={logsLoading}>
            {logsLoading ? "..." : "↺"}
          </button>
        </div>
      </div>

      <LogBox logs={logs} loading={logsLoading} instance={instance} />

      <div style={styles.actionBar}>
        {instance.status === "failed" && (
          <ActionBtn onClick={() => handleAction("retry")}>↺ retry deploy</ActionBtn>
        )}
        {instance.status === "active" && (
          <>
            <ActionBtn onClick={() => handleAction("stop")}>■ stop</ActionBtn>
            <ActionBtn onClick={() => handleAction("restart")}>↺ restart</ActionBtn>
          </>
        )}
        {instance.status === "stopped" && (
          <ActionBtn onClick={() => handleAction("start")}>▶ start</ActionBtn>
        )}
        <ActionBtn onClick={() => fetchLogs(tailLines)}>≡ refresh logs</ActionBtn>
        <ActionBtn onClick={() => handleBackup()}>↓ backup</ActionBtn>
      </div>
    </div>
  );
}

function Field({ label, value, mono }) {
  return (
    <div>
      <div style={fieldStyles.label}>{label}</div>
      <div style={{ ...fieldStyles.value, ...(mono ? fieldStyles.mono : {}) }}>{value}</div>
    </div>
  );
}

function LogBox({ logs, loading, instance }) {
  if (loading) return <div style={logStyles.box}><span style={logStyles.muted}>завантаження...</span></div>;
  if (!logs)   return <div style={logStyles.box}><span style={logStyles.muted}>—</span></div>;

  if (logs.source === "error_log" || logs.source === "error") {
    return (
      <div style={logStyles.box}>
        <span style={logStyles.err}>{logs.logs}</span>
      </div>
    );
  }

  if (instance.status === "provisioning") {
    return (
      <div style={logStyles.box}>
        <span style={logStyles.warn}>⟳ деплой в процесі...</span>
      </div>
    );
  }

  const lines = (logs.logs || "").split("\n");
  return (
    <div style={logStyles.box}>
      {lines.map((line, i) => (
        <div key={i} style={logLineStyle(line)}>{line || "\u00a0"}</div>
      ))}
    </div>
  );
}

function logLineStyle(line) {
  if (line.includes("ERROR") || line.includes("error") || line.includes("CRITICAL"))
    return logStyles.err;
  if (line.includes("WARNING") || line.includes("WARN"))
    return logStyles.warn;
  if (line.includes("INFO") || line.includes("✅"))
    return logStyles.ok;
  return logStyles.muted;
}

function ActionBtn({ children, onClick, disabled, title }) {
  return (
    <button
      style={{ ...styles.actionBtn, ...(disabled ? styles.actionBtnDisabled : {}) }}
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      title={title}
    >
      {children}
    </button>
  );
}

const styles = {
  panel: {
    background: "var(--card)", border: "0.5px solid var(--border)",
    borderRadius: 8, padding: 16, marginBottom: 20,
  },
  header: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 },
  title:  { fontSize: 14, fontWeight: 500, color: "var(--ink)" },
  closeBtn: {
    width: 24, height: 24, borderRadius: 5, fontSize: 12,
    border: "0.5px solid var(--border)", background: "transparent",
    color: "var(--muted)", cursor: "pointer", display: "flex",
    alignItems: "center", justifyContent: "center",
  },
  grid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 14 },
  logsHeader: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 },
  sectionLabel: { fontSize: 10, letterSpacing: "0.08em", color: "var(--muted)", textTransform: "uppercase" },
  select: {
    fontSize: 11, padding: "2px 6px", borderRadius: 4,
    border: "0.5px solid var(--border)", background: "var(--surface)", color: "var(--muted)",
    fontFamily: "var(--font-mono)",
  },
  smallBtn: {
    fontSize: 12, padding: "2px 8px", borderRadius: 4,
    border: "0.5px solid var(--border)", background: "transparent", color: "var(--muted)",
    cursor: "pointer",
  },
  actionBar: { display: "flex", gap: 6, flexWrap: "wrap", marginTop: 12 },
  actionBtn: {
    fontSize: 11, padding: "4px 10px", borderRadius: 5,
    border: "0.5px solid var(--border-em)", background: "var(--card)",
    color: "var(--ink)", cursor: "pointer",
  },
  actionBtnDisabled: {
    opacity: 0.4, cursor: "not-allowed",
    color: "var(--muted)", borderColor: "var(--border)",
  },
};

const fieldStyles = {
  label: { fontSize: 10, color: "var(--muted)", letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: 3 },
  value: { fontSize: 12, color: "var(--ink)" },
  mono:  { fontFamily: "var(--font-mono)" },
};

const logStyles = {
  box: {
    background: "var(--surface)", borderRadius: 6, border: "0.5px solid var(--border)",
    padding: "10px 12px", fontSize: 11, fontFamily: "var(--font-mono)",
    color: "var(--muted)", lineHeight: 1.7, maxHeight: 180,
    overflowY: "auto", whiteSpace: "pre-wrap", wordBreak: "break-all",
    marginBottom: 0,
  },
  muted: { color: "var(--muted)" },
  ok:    { color: "var(--green)" },
  err:   { color: "var(--red)" },
  warn:  { color: "var(--amber)" },
};
