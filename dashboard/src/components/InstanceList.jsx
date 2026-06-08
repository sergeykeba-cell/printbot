import { useState } from "react";
import { fmtDate, statusBadgeStyle, indicatorStyle } from "../utils";

const FILTERS = ["all", "active", "failed", "provisioning", "stopped"];

export default function InstanceList({
  instances, loading, filter, onFilterChange,
  selectedId, onSelect, onAction,
}) {
  const filtered = filter === "all"
    ? instances
    : instances.filter((i) => i.status === filter);

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={styles.sectionHeader}>
        <div style={styles.sectionTitle}>інстанси</div>
        <div style={styles.filterRow}>
          {FILTERS.map((f) => (
            <button
              key={f}
              style={{ ...styles.filterBtn, ...(filter === f ? styles.filterActive : {}) }}
              onClick={() => onFilterChange(f)}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div style={styles.emptyState}>завантаження...</div>
      ) : filtered.length === 0 ? (
        <div style={styles.emptyState}>інстанси не знайдено</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {filtered.map((inst) => (
            <InstanceRow
              key={inst.id}
              inst={inst}
              selected={selectedId === inst.id}
              onSelect={() => onSelect(inst.id)}
              onAction={onAction}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function InstanceRow({ inst, selected, onSelect, onAction }) {
  const confirmDelete = (e) => {
    e.stopPropagation();
    if (window.confirm(`Видалити ${inst.subdomain}?\nVolumes збережуться.`)) {
      onAction(inst.id, "delete");
    }
  };

  return (
    <div
      style={{ ...styles.row, ...(selected ? styles.rowSelected : {}) }}
      onClick={onSelect}
    >
      <div style={{ ...styles.indicator, ...indicatorStyle(inst.status) }} />

      <div>
        <div style={styles.instName}>{inst.subdomain}</div>
        <div style={styles.instUrl}>{inst.subdomain}.printbot.app</div>
      </div>

      <Badge status={inst.status} />

      <div style={styles.meta}>{fmtDate(inst.created_at)}</div>
      <div style={styles.meta}>{fmtDate(inst.updated_at)}</div>

      <div style={styles.actions} onClick={(e) => e.stopPropagation()}>
        {inst.status === "failed" && (
          <IconBtn title="retry" onClick={() => onAction(inst.id, "retry")}>↺</IconBtn>
        )}
        {inst.status === "active" && (
          <IconBtn title="stop" onClick={() => onAction(inst.id, "stop")}>■</IconBtn>
        )}
        {inst.status === "stopped" && (
          <IconBtn title="start" onClick={() => onAction(inst.id, "start")}>▶</IconBtn>
        )}
        <IconBtn title="logs" onClick={onSelect}>≡</IconBtn>
        <IconBtn title="delete" danger onClick={confirmDelete}>✕</IconBtn>
      </div>
    </div>
  );
}

function Badge({ status }) {
  const s = statusBadgeStyle(status);
  return (
    <span style={s}>{status}</span>
  );
}

function IconBtn({ children, title, onClick, danger }) {
  const [hov, setHov] = useState(false);
  return (
    <button
      title={title}
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        ...styles.iconBtn,
        ...(hov && !danger ? styles.iconBtnHov : {}),
        ...(hov && danger ? styles.iconBtnDanger : {}),
      }}
    >
      {children}
    </button>
  );
}



const styles = {
  sectionHeader: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  sectionTitle: { fontSize: 10, letterSpacing: "0.1em", color: "var(--muted)", textTransform: "uppercase" },
  filterRow: { display: "flex", gap: 4 },
  filterBtn: {
    fontSize: 11, padding: "3px 8px", borderRadius: 4, cursor: "pointer",
    border: "0.5px solid var(--border)", background: "transparent", color: "var(--muted)",
  },
  filterActive: { background: "var(--ink)", color: "var(--card)", borderColor: "var(--ink)" },

  row: {
    display: "grid",
    gridTemplateColumns: "12px 1fr 110px 110px 110px 110px",
    alignItems: "center", gap: 10,
    background: "var(--card)", border: "0.5px solid var(--border)",
    borderRadius: 8, padding: "10px 14px", cursor: "pointer",
    transition: "border-color 0.15s",
  },
  rowSelected: { borderColor: "var(--ink)" },

  indicator: { width: 8, height: 8, borderRadius: "50%", flexShrink: 0 },
  instName: { fontSize: 13, fontWeight: 500, color: "var(--ink)" },
  instUrl:  { fontSize: 11, color: "var(--muted)" },
  meta:     { fontSize: 11, color: "var(--muted)" },

  actions: { display: "flex", gap: 4, justifyContent: "flex-end" },
  iconBtn: {
    width: 26, height: 26, borderRadius: 5, fontSize: 12,
    border: "0.5px solid var(--border)", background: "transparent",
    display: "flex", alignItems: "center", justifyContent: "center",
    cursor: "pointer", color: "var(--muted)",
  },
  iconBtnHov:    { background: "var(--surface)", color: "var(--ink)", borderColor: "var(--border-em)" },
  iconBtnDanger: { background: "var(--red-bg)", color: "var(--red)", borderColor: "var(--red)" },

  emptyState: {
    textAlign: "center", padding: 32, color: "var(--muted)", fontSize: 12,
    border: "0.5px dashed var(--border)", borderRadius: 8,
  },
};
