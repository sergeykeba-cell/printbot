import { useState } from "react";

const SUBDOMAIN_RE = /^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$/;

export default function CreateModal({ onClose, onCreate, showToast }) {
  const [subdomain, setSubdomain] = useState("");
  const [token, setToken]         = useState("");
  const [loading, setLoading]     = useState(false);
  const [errors, setErrors]       = useState({});

  const validate = () => {
    const e = {};
    const sub = subdomain.trim().toLowerCase();
    if (!sub) e.subdomain = "обов'язкове поле";
    else if (!SUBDOMAIN_RE.test(sub))
      e.subdomain = "лише [a-z0-9-], не починається/закінчується на дефіс, 3–63 символи";
    if (!token.trim()) e.token = "обов'язкове поле";
    else if (token.trim().length < 20) e.token = "токен занадто короткий";
    return e;
  };

  const handleSubmit = async () => {
    const e = validate();
    if (Object.keys(e).length) { setErrors(e); return; }
    setLoading(true);
    try {
      await onCreate(subdomain.trim().toLowerCase(), token.trim());
    } catch (err) {
      showToast(err.message || "Помилка деплою", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e) => { if (e.key === "Enter") handleSubmit(); };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.title}>новий інстанс</div>

        <div style={styles.fieldGroup}>
          <label style={styles.label}>subdomain</label>
          <input
            style={{ ...styles.input, ...(errors.subdomain ? styles.inputErr : {}) }}
            type="text"
            value={subdomain}
            onChange={(e) => { setSubdomain(e.target.value); setErrors((p) => ({ ...p, subdomain: null })); }}
            onKeyDown={handleKey}
            placeholder="odessa-center"
            autoFocus
          />
          {errors.subdomain && <div style={styles.errMsg}>{errors.subdomain}</div>}
          <div style={styles.hint}>→ https://printbot-manager.duckdns.org/instance/{(subdomain || "subdomain").toLowerCase().trim()}</div>
        </div>

        <div style={styles.fieldGroup}>
          <label style={styles.label}>telegram bot token</label>
          <input
            style={{ ...styles.input, ...(errors.token ? styles.inputErr : {}) }}
            type="text"
            value={token}
            onChange={(e) => { setToken(e.target.value); setErrors((p) => ({ ...p, token: null })); }}
            onKeyDown={handleKey}
            placeholder="1234567890:AAH..."
          />
          {errors.token && <div style={styles.errMsg}>{errors.token}</div>}
        </div>

        <div style={styles.footer}>
          <button style={styles.btnCancel} onClick={onClose} disabled={loading}>
            скасувати
          </button>
          <button
            style={{ ...styles.btnSubmit, ...(loading ? styles.btnDisabled : {}) }}
            onClick={handleSubmit}
            disabled={loading}
          >
            {loading ? "деплой..." : "deploy ↗"}
          </button>
        </div>
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    position: "fixed", inset: 0, zIndex: 100,
    background: "rgba(0,0,0,0.45)",
    display: "flex", alignItems: "center", justifyContent: "center",
  },
  modal: {
    background: "var(--card)", borderRadius: 10,
    border: "0.5px solid var(--border-em)",
    padding: 20, width: 380, maxWidth: "95%",
  },
  title: { fontSize: 14, fontWeight: 500, color: "var(--ink)", marginBottom: 16 },
  fieldGroup: { marginBottom: 14 },
  label: { fontSize: 11, color: "var(--muted)", display: "block", marginBottom: 4, letterSpacing: "0.05em" },
  input: {
    width: "100%", padding: "7px 10px", fontSize: 12,
    border: "0.5px solid var(--border-em)", borderRadius: 6,
    background: "var(--surface)", color: "var(--ink)",
    fontFamily: "var(--font-mono)",
    outline: "none",
  },
  inputErr: { borderColor: "var(--red)" },
  errMsg: { fontSize: 11, color: "var(--red)", marginTop: 4 },
  hint: { fontSize: 10, color: "var(--hint)", marginTop: 4 },
  footer: { display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 18 },
  btnCancel: {
    fontSize: 12, padding: "6px 12px", borderRadius: 6,
    border: "0.5px solid var(--border-em)", background: "transparent",
    color: "var(--muted)", cursor: "pointer",
  },
  btnSubmit: {
    fontSize: 12, padding: "6px 14px", borderRadius: 6,
    border: "0.5px solid var(--ink)", background: "var(--ink)",
    color: "var(--card)", cursor: "pointer", fontWeight: 500,
  },
  btnDisabled: { opacity: 0.5, cursor: "not-allowed" },
};
