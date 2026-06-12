import { useState, useRef } from "react";

const SUBDOMAIN_RE = /^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$/;

const DEFAULT_PRICE_LIST = JSON.stringify({
  print_prices: [
    { paper_size: "A4", color_mode: "bw",    duplex: false, price_per_page: 2.50 },
    { paper_size: "A4", color_mode: "bw",    duplex: true,  price_per_page: 2.00 },
    { paper_size: "A4", color_mode: "color", duplex: false, price_per_page: 8.00 },
    { paper_size: "A4", color_mode: "color", duplex: true,  price_per_page: 7.00 },
  ],
  currency: "UAH",
}, null, 2);

export default function CreateModal({ onClose, onCreate, showToast }) {
  const [subdomain, setSubdomain]       = useState("");
  const [token, setToken]               = useState("");
  const [priceMode, setPriceMode]       = useState("none"); // none | json | file
  const [priceJson, setPriceJson]       = useState(DEFAULT_PRICE_LIST);
  const [priceJsonErr, setPriceJsonErr] = useState(null);
  const [loading, setLoading]           = useState(false);
  const [errors, setErrors]             = useState({});
  const fileRef                         = useRef(null);

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

  const parsePriceList = () => {
    if (priceMode === "none") return null;
    try {
      const parsed = JSON.parse(priceJson);
      setPriceJsonErr(null);
      return parsed;
    } catch {
      setPriceJsonErr("Невалідний JSON");
      return undefined; // undefined = помилка
    }
  };

  const handleFileLoad = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      setPriceJson(ev.target.result);
      setPriceJsonErr(null);
    };
    reader.readAsText(file);
  };

  const handleSubmit = async () => {
    const e = validate();
    if (Object.keys(e).length) { setErrors(e); return; }

    const priceList = parsePriceList();
    if (priceList === undefined) return; // JSON помилка

    setLoading(true);
    try {
      await onCreate(subdomain.trim().toLowerCase(), token.trim(), priceList);
    } catch (err) {
      showToast(err.message || "Помилка деплою", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e) => { if (e.key === "Enter" && priceMode !== "json") handleSubmit(); };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.title}>новий інстанс</div>

        {/* subdomain */}
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

        {/* bot token */}
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

        {/* price list */}
        <div style={styles.fieldGroup}>
          <label style={styles.label}>прайс-лист (необов'язково)</label>
          <div style={styles.modeRow}>
            {["none", "json", "file"].map((m) => (
              <button
                key={m}
                style={{ ...styles.modeBtn, ...(priceMode === m ? styles.modeBtnActive : {}) }}
                onClick={() => setPriceMode(m)}
              >
                {m === "none" ? "без прайсу" : m === "json" ? "JSON" : "файл"}
              </button>
            ))}
          </div>

          {priceMode === "json" && (
            <>
              <textarea
                style={{ ...styles.textarea, ...(priceJsonErr ? styles.inputErr : {}) }}
                value={priceJson}
                onChange={(e) => { setPriceJson(e.target.value); setPriceJsonErr(null); }}
                rows={8}
                spellCheck={false}
              />
              {priceJsonErr && <div style={styles.errMsg}>{priceJsonErr}</div>}
            </>
          )}

          {priceMode === "file" && (
            <>
              <input
                ref={fileRef}
                type="file"
                accept=".json"
                style={{ display: "none" }}
                onChange={handleFileLoad}
              />
              <button style={styles.fileBtn} onClick={() => fileRef.current.click()}>
                обрати JSON файл
              </button>
              {priceJson !== DEFAULT_PRICE_LIST && priceMode === "file" && (
                <div style={{ ...styles.hint, color: "var(--green, #4caf50)", marginTop: 4 }}>
                  ✓ файл завантажено
                </div>
              )}
            </>
          )}
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
    padding: 20, width: 420, maxWidth: "95%",
    maxHeight: "90vh", overflowY: "auto",
  },
  title: { fontSize: 14, fontWeight: 500, color: "var(--ink)", marginBottom: 16 },
  fieldGroup: { marginBottom: 14 },
  label: { fontSize: 11, color: "var(--muted)", display: "block", marginBottom: 4, letterSpacing: "0.05em" },
  input: {
    width: "100%", padding: "7px 10px", fontSize: 12,
    border: "0.5px solid var(--border-em)", borderRadius: 6,
    background: "var(--surface)", color: "var(--ink)",
    fontFamily: "var(--font-mono)", outline: "none",
    boxSizing: "border-box",
  },
  inputErr: { borderColor: "var(--red)" },
  errMsg: { fontSize: 11, color: "var(--red)", marginTop: 4 },
  hint: { fontSize: 10, color: "var(--hint)", marginTop: 4 },
  modeRow: { display: "flex", gap: 6, marginBottom: 8 },
  modeBtn: {
    fontSize: 11, padding: "4px 10px", borderRadius: 5,
    border: "0.5px solid var(--border-em)", background: "transparent",
    color: "var(--muted)", cursor: "pointer",
  },
  modeBtnActive: {
    background: "var(--ink)", color: "var(--card)",
    borderColor: "var(--ink)",
  },
  textarea: {
    width: "100%", padding: "7px 10px", fontSize: 11,
    border: "0.5px solid var(--border-em)", borderRadius: 6,
    background: "var(--surface)", color: "var(--ink)",
    fontFamily: "var(--font-mono)", outline: "none",
    resize: "vertical", boxSizing: "border-box",
  },
  fileBtn: {
    fontSize: 11, padding: "5px 12px", borderRadius: 5,
    border: "0.5px solid var(--border-em)", background: "transparent",
    color: "var(--ink)", cursor: "pointer", marginTop: 4,
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
