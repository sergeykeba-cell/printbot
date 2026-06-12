import { useState, useEffect } from "react";
import { fmtDate } from "../utils";
import { api } from "../api";

export default function DetailPanel({ instance, onClose, onAction }) {
  const [logs, setLogs]       = useState(null);
  const [logsLoading, setLL]  = useState(false);
  const [tailLines, setTail]  = useState(100);
  const [opInfo, setOpInfo]   = useState(null);
  const [opLoading, setOpL]   = useState(false);
  const [copied, setCopied]   = useState(false);

  const fetchOperator = async () => {
    if (instance.status !== "active") return;
    setOpL(true);
    try {
      const data = await api.getOperatorInfo(instance.id);
      setOpInfo(data);
    } catch (_) {
      setOpInfo(null);
    } finally {
      setOpL(false);
    }
  };

  const copyCmd = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };

  const fetchLogs = async (tail = tailLines) => {
    setLL(true);
    try {
      const data = await api.getLogs(instance.id, tail);
      setLogs(data);
    } catch (e) {
      setLogs({ source: "error", logs: e.message });
    } finally {
      setLL(false);
    }
  };

  useEffect(() => {
    setLogs(null);
    setOpInfo(null);
    fetchLogs();
    fetchOperator();
  }, [instance.id]);

  const handleAction = async (action) => {
    await onAction(instance.id, action);
  };

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <div style={styles.title}>{instance.subdomain}</div>
        <button style={styles.closeBtn} onClick={onClose} aria-label="Закрити">✕</button>
      </div>

      <div style={styles.grid}>
        <Field label="instance id"  value={instance.id} mono />
        <Field label="status"       value={instance.status} status={instance.status} />
        <Field label="created"      value={fmtDate(instance.created_at)} mono />
        <Field label="updated"      value={fmtDate(instance.updated_at)} mono />
        {instance.billing_status && (
          <Field label="billing" value={instance.billing_status} status={instance.billing_status} />
        )}
        {instance.subscription_expires_at && (
          <Field label="expires" value={fmtDate(instance.subscription_expires_at)} mono />
        )}
      </div>

      <OperatorBlock
        info={opInfo}
        loading={opLoading}
        status={instance.status}
        instanceApiUrl={`https://printbot-manager.duckdns.org/instance/${instance.subdomain}`}
        instance={instance}
        copied={copied}
        onCopy={copyCmd}
        onRefresh={fetchOperator}
      />

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
            <ActionBtn onClick={() => handleAction("maintenance_enable")}>⏸ maintenance</ActionBtn>
          </>
        )}
        {instance.status === "maintenance" && (
          <ActionBtn onClick={() => handleAction("maintenance_disable")}>▶ leave maintenance</ActionBtn>
        )}
        {instance.status === "stopped" && (
          <ActionBtn onClick={() => handleAction("start")}>▶ start</ActionBtn>
        )}
        <ActionBtn onClick={() => fetchLogs(tailLines)}>≡ refresh logs</ActionBtn>
        {/* backup запускається вручну на сервері: ./infrastructure/backup_instance.sh {subdomain} */}
        <ActionBtn disabled title="запустіть вручну: backup_instance.sh">↓ backup</ActionBtn>
      </div>
    </div>
  );
}

function Field({ label, value, mono, status }) {
  const statusColor = {
    active: "var(--green)", maintenance: "var(--amber)",
    suspended: "var(--red)", terminated: "var(--red)",
    failed: "var(--red)", stopped: "var(--muted)",
  }[status] || undefined;
  return (
    <div>
      <div style={fieldStyles.label}>{label}</div>
      <div style={{ ...fieldStyles.value, ...(mono ? fieldStyles.mono : {}), ...(statusColor ? { color: statusColor, fontWeight: 600 } : {}) }}>{value}</div>
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


function OperatorBlock({ info, loading, status, instanceApiUrl, instance, copied, onCopy, onRefresh }) {
  if (status !== "active") return null;

  return (
    <div style={opStyles.wrap}>
      <div style={opStyles.header}>
        <div style={opStyles.label}>operator access</div>
        <button style={opStyles.refreshBtn} onClick={onRefresh} disabled={loading}>
          {loading ? "..." : "↺"}
        </button>
      </div>

      {!info && !loading && (
        <div style={opStyles.empty}>секрет не задано — натисніть ↺</div>
      )}

      {info && (
        <div style={opStyles.cmdRow}>
          <span style={opStyles.dnsLabel}>bot:</span>
          <code style={opStyles.cmd}>{info.bot_url}</code>
          <button style={opStyles.copyBtn} onClick={() => onCopy(info.bot_url)}>copy</button>
        </div>
      )}
      {info && info.operator_secret && (
        <div style={opStyles.cmdRow}>
          <span style={opStyles.dnsLabel}>pass:</span>
          <code style={opStyles.cmd}>{info.operator_secret}</code>
          <button style={opStyles.copyBtn} onClick={() => onCopy(info.operator_secret)}>copy</button>
        </div>
      )}
      {info && info.instance_api_key && (
        <div style={opStyles.cmdRow}>
          <span style={opStyles.dnsLabel}>api:</span>
          <code style={opStyles.cmd}>{info.instance_api_key}</code>
          <button style={opStyles.copyBtn} onClick={() => onCopy(info.instance_api_key)}>copy</button>
        </div>
      )}
      {info && info.operator_command && (
        <div style={opStyles.cmdRow}>
          <span style={opStyles.dnsLabel}>cmd:</span>
          <code style={opStyles.cmd}>{info.operator_command}</code>
          <button style={opStyles.copyBtn} onClick={() => onCopy(info.operator_command)}>
            {copied ? "✓" : "copy"}
          </button>
        </div>
      )}

      {info && !info.operator_command && (
        <div style={opStyles.empty}>operator_secret не встановлено в .env інстансу</div>
      )}

      {info && (
        <div style={opStyles.meta}>
          <a href={info.bot_url} target="_blank" rel="noreferrer" style={opStyles.link}>
            {info.bot_url}
          </a>
          <span style={opStyles.sep}>·</span>
          <a href={info.web_url} target="_blank" rel="noreferrer" style={opStyles.link}>
            web form
          </a>
          <a
            href={`https://printbot-operator.duckdns.org/login?instance=${encodeURIComponent(instanceApiUrl)}`}
            target="_blank" rel="noreferrer" style={opStyles.link}
          >
            operator panel ↗
          </a>
        </div>
      )}
    </div>
  );
}

const opStyles = {
  wrap: {
    background: "var(--surface)", border: "0.5px solid var(--border)",
    borderRadius: 6, padding: "10px 12px", marginBottom: 12,
  },
  header: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 },
  label: { fontSize: 10, letterSpacing: "0.08em", color: "var(--muted)", textTransform: "uppercase" },
  refreshBtn: {
    fontSize: 12, padding: "1px 7px", borderRadius: 4,
    border: "0.5px solid var(--border)", background: "transparent",
    color: "var(--muted)", cursor: "pointer",
  },
  dnsLabel: { color: "var(--text-muted)", fontSize: "11px", minWidth: "36px", marginRight: "6px" },
  cmdRow: { display: "flex", alignItems: "center", gap: 8, marginBottom: 6 },
  cmd: {
    flex: 1, fontSize: 12, fontFamily: "var(--font-mono)",
    color: "var(--green)", background: "var(--card)",
    border: "0.5px solid var(--border)", borderRadius: 4,
    padding: "4px 8px", letterSpacing: "0.03em",
  },
  copyBtn: {
    fontSize: 11, padding: "3px 9px", borderRadius: 4,
    border: "0.5px solid var(--border-em)", background: "var(--card)",
    color: "var(--ink)", cursor: "pointer", whiteSpace: "nowrap",
  },
  meta: { display: "flex", alignItems: "center", gap: 6, marginTop: 2 },
  link: { fontSize: 11, color: "var(--muted)", textDecoration: "none" },
  sep:  { fontSize: 11, color: "var(--border)" },
  empty: { fontSize: 11, color: "var(--muted)", fontStyle: "italic" },
};
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
