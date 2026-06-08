export default function MetricsRow({ instances }) {
  const total        = instances.length;
  const active       = instances.filter((i) => i.status === "active").length;
  const failed       = instances.filter((i) => i.status === "failed").length;
  const provisioning = instances.filter((i) => i.status === "provisioning").length;

  return (
    <div style={styles.row}>
      <MetricCard label="total"        value={total}        sub="інстансів" />
      <MetricCard label="active"       value={active}       sub="working"           color="var(--green)" />
      <MetricCard label="failed"       value={failed}       sub="потребують retry"  color="var(--red)" />
      <MetricCard label="provisioning" value={provisioning} sub="деплоїться"        color="var(--amber)" />
    </div>
  );
}

function MetricCard({ label, value, sub, color }) {
  return (
    <div style={styles.card}>
      <div style={styles.label}>{label}</div>
      <div style={{ ...styles.value, ...(color ? { color } : {}) }}>{value}</div>
      <div style={styles.sub}>{sub}</div>
    </div>
  );
}

const styles = {
  row: {
    display: "grid", gridTemplateColumns: "repeat(4, minmax(0,1fr))",
    gap: 10, marginBottom: 20,
  },
  card: {
    background: "var(--surface)", borderRadius: 8,
    padding: "12px 14px", border: "0.5px solid var(--border)",
  },
  label: { fontSize: 10, color: "var(--muted)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 },
  value: { fontSize: 24, fontWeight: 600, color: "var(--ink)", lineHeight: 1 },
  sub:   { fontSize: 11, color: "var(--muted)", marginTop: 4 },
};
