import { useState, useEffect, useCallback } from "react";
import Header from "./components/Header";
import MetricsRow from "./components/MetricsRow";
import InstanceList from "./components/InstanceList";
import DetailPanel from "./components/DetailPanel";
import CreateModal from "./components/CreateModal";
import Toast from "./components/Toast";
import { api } from "./api";

export default function App() {
  const [instances, setInstances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [selectedId, setSelectedId] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = useCallback((msg, type = "info") => {
    setToast({ msg, type, key: Date.now() });
  }, []);

  const fetchInstances = useCallback(async () => {
    try {
      const data = await api.listInstances(filter === "all" ? null : filter);
      setInstances(data);
    } catch (e) {
      showToast("Помилка з'єднання з API", "error");
    } finally {
      setLoading(false);
    }
  }, [filter, showToast]);

  useEffect(() => {
    fetchInstances();
    const interval = setInterval(fetchInstances, 10000);
    return () => clearInterval(interval);
  }, [fetchInstances]);

  const handleAction = async (id, action) => {
    const inst = instances.find((i) => i.id === id);
    try {
      if (action === "retry") {
        await api.retry(id);
        showToast(`⟳ retry запущено: ${inst?.subdomain}`, "info");
      } else if (action === "delete") {
        await api.deleteInstance(id);
        showToast(`✓ ${inst?.subdomain} видалено`, "success");
        if (selectedId === id) setSelectedId(null);
      } else {
        await api.action(id, action);
        showToast(`${action} → ${inst?.subdomain}`, "success");
      }
      await fetchInstances();
    } catch (e) {
      showToast(e.message || "Помилка", "error");
    }
  };

  const handleCreate = async (subdomain, tgBotToken) => {
    try {
      const result = await api.create(subdomain, tgBotToken);
      setCreateOpen(false);
      showToast(`⟳ деплой запущено: ${subdomain}.printbot.app`, "info");
      await fetchInstances();
      return result;
    } catch (e) {
      throw e;
    }
  };

  const selected = instances.find((i) => i.id === selectedId) || null;

  return (
    <div className="app-root">
      <Header
        onRefresh={() => { setLoading(true); fetchInstances(); }}
        onNewInstance={() => setCreateOpen(true)}
      />

      <MetricsRow instances={instances} />

      <InstanceList
        instances={instances}
        loading={loading}
        filter={filter}
        onFilterChange={(f) => { setFilter(f); setSelectedId(null); }}
        selectedId={selectedId}
        onSelect={(id) => setSelectedId(id === selectedId ? null : id)}
        onAction={handleAction}
      />

      {selected && (
        <DetailPanel
          instance={selected}
          onClose={() => setSelectedId(null)}
          onAction={handleAction}
        />
      )}

      {createOpen && (
        <CreateModal
          onClose={() => setCreateOpen(false)}
          onCreate={handleCreate}
          showToast={showToast}
        />
      )}

      {toast && <Toast key={toast.key} msg={toast.msg} type={toast.type} />}

      <style>{globalStyles}</style>
    </div>
  );
}

const globalStyles = `
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --ink: #0f0f0e;
    --muted: #6b6b67;
    --hint: #a0a09b;
    --surface: #f5f4f0;
    --card: #ffffff;
    --border: rgba(0,0,0,0.10);
    --border-em: rgba(0,0,0,0.20);
    --amber: #854f0b;
    --amber-bg: #faeeda;
    --green: #3b6d11;
    --green-bg: #eaf3de;
    --red: #a32d2d;
    --red-bg: #fcebeb;
    --blue: #185fa5;
    --blue-bg: #e6f1fb;
    --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
  }

  @media (prefers-color-scheme: dark) {
    :root {
      --ink: #e8e7e2;
      --muted: #8a8a84;
      --hint: #5a5a56;
      --surface: #1a1a18;
      --card: #222220;
      --border: rgba(255,255,255,0.10);
      --border-em: rgba(255,255,255,0.20);
      --amber: #ef9f27;
      --amber-bg: #2a1e08;
      --green: #97c459;
      --green-bg: #172106;
      --red: #f09595;
      --red-bg: #200d0d;
      --blue: #85b7eb;
      --blue-bg: #051529;
    }
  }

  body {
    font-family: var(--font-mono);
    background: var(--surface);
    color: var(--ink);
    font-size: 13px;
    line-height: 1.5;
    min-height: 100vh;
  }

  .app-root {
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 20px 60px;
  }

  button {
    font-family: var(--font-mono);
    cursor: pointer;
  }

  input {
    font-family: var(--font-mono);
  }
`;
