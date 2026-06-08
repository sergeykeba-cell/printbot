import { useState, useEffect } from "react";

export default function Toast({ msg, type = "info" }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(true);
    const t = setTimeout(() => setVisible(false), 2500);
    return () => clearTimeout(t);
  }, []);

  const colorMap = {
    info:    "var(--ink)",
    success: "var(--green-bg)",
    error:   "var(--red-bg)",
  };
  const textMap = {
    info:    "var(--card)",
    success: "var(--green)",
    error:   "var(--red)",
  };

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: "fixed", bottom: 20, right: 20, zIndex: 200,
        background: colorMap[type],
        color: textMap[type],
        border: `0.5px solid ${type === "info" ? "transparent" : "currentColor"}`,
        fontSize: 12, padding: "8px 14px", borderRadius: 6,
        fontFamily: "var(--font-mono)",
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(6px)",
        transition: "opacity 0.2s, transform 0.2s",
        pointerEvents: "none",
        maxWidth: 320,
      }}
    >
      {msg}
    </div>
  );
}
