export default function Header({ onRefresh, onNewInstance }) {
  return (
    <header style={styles.header}>
      <div style={styles.left}>
        <div style={styles.logoMark}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <rect x="1" y="3" width="12" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
            <path d="M4 3V2a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1" stroke="currentColor" strokeWidth="1.2"/>
            <rect x="3.5" y="6" width="7" height="1" rx="0.5" fill="currentColor"/>
            <rect x="3.5" y="8.5" width="5" height="1" rx="0.5" fill="currentColor"/>
          </svg>
        </div>
        <div>
          <div style={styles.appName}>PRINTBOT</div>
          <div style={styles.appSub}>instance manager</div>
        </div>
      </div>

      <div style={styles.right}>
        <div style={styles.apiPill}>
          <span style={{ color: "var(--green)", marginRight: 5 }}>●</span>
          api: {import.meta.env.VITE_API_URL || "localhost:8080"}
        </div>
        <button style={styles.btnSm} onClick={onRefresh}>
          <RefreshIcon /> refresh
        </button>
        <button style={{ ...styles.btnSm, ...styles.btnPrimary }} onClick={onNewInstance}>
          + new instance
        </button>
      </div>
    </header>
  );
}

function RefreshIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ marginRight: 4 }}>
      <path d="M10 6A4 4 0 1 1 6 2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      <path d="M6 0l2 2-2 2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

const styles = {
  header: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    paddingBottom: 16, borderBottom: "0.5px solid var(--border)", marginBottom: 20,
  },
  left: { display: "flex", alignItems: "center", gap: 10 },
  logoMark: {
    width: 28, height: 28, borderRadius: 6,
    background: "var(--ink)", color: "var(--card)",
    display: "flex", alignItems: "center", justifyContent: "center",
  },
  appName: { fontSize: 12, fontWeight: 600, letterSpacing: "0.1em", color: "var(--ink)" },
  appSub: { fontSize: 10, color: "var(--muted)", letterSpacing: "0.05em" },
  right: { display: "flex", alignItems: "center", gap: 8 },
  apiPill: {
    fontSize: 11, padding: "3px 8px", borderRadius: 4,
    border: "0.5px solid var(--border-em)", color: "var(--muted)",
    background: "var(--surface)",
  },
  btnSm: {
    display: "flex", alignItems: "center", fontSize: 12,
    padding: "5px 10px", borderRadius: 6,
    border: "0.5px solid var(--border-em)", background: "var(--card)",
    color: "var(--ink)",
  },
  btnPrimary: { background: "var(--ink)", color: "var(--card)", borderColor: "var(--ink)" },
};
