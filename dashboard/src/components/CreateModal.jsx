import { useState } from "react";

const SUBDOMAIN_RE = /^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$/;

export default function CreateModal({ onClose, onCreate, showToast }) {
  const [subdomain, setSubdomain] = useState("");
  const [token, setToken]         = useState("");
  const [loading, setLoading]     = useState(false);
  const [errors, setErrors]       = useState({});
  const [result, setResult]       = useState(null); // після деплою

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
      // Показуємо credentials після успішного деплою
      setResult({
        subdomain: subdomain.trim().toLowerCase(),
        operatorLogin: "operator",
        operatorPassword: "operator123",
        webUrl: `https://printbot-manager.duckdns.org/${subdomain.trim().toLowerCase()}`,
        operatorCmd: "/operator operator123",
      });
    } catch (err) {
      showToast(err.message || "Помилка деплою", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e) => { if (e.key === "Enter") handleSubmit(); };

  const copy = (text) => {
    navigator.clipboard.writeText(text);
    showToast("скопійовано", "info");
  };

  // ── Екран результату після деплою ──
  if (result) {
    return (
      <div style={styles.overlay} onClick={onClose}>
        <div style={{ ...styles.modal, width: 420 }} onClick={(e) => e.stopPropagation()}>
          <div style={styles.title}>✅ інстанс {result.subdomain} запущено</div>

          <div style={styles.section}>
            <div style={styles.sectionLabel}>веб-форма для клієнтів</div>
            <div style={styles.credRow}>
              <span style={styles.credVal}>{result.webUrl}</span>
              <button style={styles.copyBtn} onClick={() => copy(result.webUrl)}>copy</button>
            </div>
            <div style={styles.hint}>QR-код на цю адресу — клієнти без Telegram</div>
          </div>

          <div style={styles.section}>
            <div style={styles.sectionLabel}>режим оператора в Telegram-боті</div>
            <div style={styles.credRow}>
              <span style={styles.credVal}>/operator оператор123</span>
              <button style={styles.copyBtn} onClick={() => copy("/operator operator123")}>copy</button>
            </div>
            <div style={styles.hint}>надіслати цю команду боту щоб увійти в режим оператора</div>
          </div>

          <div style={styles.section}>
            <div style={styles.sectionLabel}>пароль оператора</div>
            <div style={styles.credRow}>
              <span style={styles.credVal}>operator123</span>
              <button style={styles.copyBtn} onClick={() => copy("operator123")}>copy</button>
            </div>
            <div style={styles.hint}>змінити в .env інстансу: OPERATOR_SECRET=...</div>
          </div>

          <div style={styles.footer}>
            <button style={styles.btnSubmit} onClick={onClose}>закрити</button>
          </div>
        </div>
      </div>
    );
  }

  // ── Форма створення ──
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
          <div style={styles.hint}>
            веб-форма: printbot-manager.duckdns.org/{(subdomain || "subdomain").toLowerCase().trim()}
          </div>
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
          <button style={styles.btnCancel} onClick={onClose} disabled={loading}>скасувати</button>
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
    fontFamily: "var(--font-mono)", outline: "none",
  },
  inputErr: { borderColor: "var(--red)" },
  errMsg: { fontSize: 11, color: "var(--red)", marginTop: 4 },
  hint: { fontSize: 10, color: "var(--hint)", marginTop: 4 },
  section: { marginBottom: 14, padding: "10px 12px", background: "var(--surface)", borderRadius: 8 },
  sectionLabel: { fontSize: 10, color: "var(--muted)", marginBottom: 6, letterSpacing: "0.05em", textTransform: "uppercase" },
  credRow: { display: "flex", alignItems: "center", gap: 8 },
  credVal: { fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--ink)", flex: 1, wordBreak: "break-all" },
  copyBtn: {
    fontSize: 10, padding: "3px 8px", borderRadius: 4,
    border: "0.5px solid var(--border-em)", background: "transparent",
    color: "var(--muted)", cursor: "pointer", flexShrink: 0,
  },
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
