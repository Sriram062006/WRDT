/**
 * Shared presentational components.
 *
 * Extracted from the prototype's single 1,700-line file so screens stay
 * readable and so states the prototype simply did not have -- loading,
 * empty, error, pagination, toasts -- exist in one place instead of
 * being reinvented (or omitted) per screen.
 */
import { useEffect, useRef, useState } from "react";

/* ---------------- icons ---------------- */
const PATHS = {
  LayoutDashboard: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  MapPin: "M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z M12 10m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
  Users: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2 M23 21v-2a4 4 0 0 1-3-3.87 M16 3.13a4 4 0 0 1 0 7.75",
  UserCheck: "M9 11c2.21 0 4-1.79 4-4S11.21 3 9 3 5 4.79 5 7s1.79 4 4 4z M1 21v-2c0-2.21 3.58-4 8-4 M16 11l2 2 4-4",
  CalendarDays: "M19 4H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2z M16 2v4 M8 2v4 M3 10h18",
  CreditCard: "M1 4h22v16H1z M1 10h22",
  FileBarChart: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8",
  Receipt: "M4 2h16v20l-4-2-4 2-4-2-4 2V2z",
  Bell: "M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9 M13.73 21a2 2 0 0 1-3.46 0",
  Settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4",
  Menu: "M3 12h18 M3 6h18 M3 18h18",
  ChevronRight: "M9 18l6-6-6-6",
  ChevronLeft: "M15 18l-6-6 6-6",
  TrendingUp: "M23 6l-9.5 9.5-5-5L1 18 M17 6h6v6",
  LogOut: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9",
  Plus: "M12 5v14 M5 12h14",
  Eye: "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
  EyeOff: "M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94 M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19 M1 1l22 22",
  Lock: "M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2z M7 11V7a5 5 0 0 1 10 0v4",
  CheckCircle: "M22 11.08V12a10 10 0 1 1-5.93-9.14 M22 4L12 14.01l-3-3",
  Printer: "M6 9V2h12v7 M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2 M6 14h12v8H6z",
  FileDown: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M12 18v-6 M9 15l3 3 3-3",
  X: "M18 6L6 18 M6 6l12 12",
  AlertCircle: "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z M12 8v4 M12 16h.01",
  ArrowLeft: "M19 12H5 M12 5l-7 7 7 7",
  Upload: "M12 3v12 M7 8l5-5 5 5 M5 21h14",
  Edit: "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7 M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4z",
  Trash2: "M3 6h18 M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2 M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6 M10 11v6 M14 11v6",
  Search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z M21 21l-4.35-4.35",
  RefreshCw: "M23 4v6h-6 M1 20v-6h6 M3.51 9a9 9 0 0 1 14.85-3.36L23 10 M1 14l4.64 4.36A9 9 0 0 0 20.49 15",
  Activity: "M22 12h-4l-3 9L9 3l-3 9H2",
};

export const Icon = ({ n, s = 16, c = "currentColor", sw = 2, style }) => (
  <svg
    width={s}
    height={s}
    viewBox="0 0 24 24"
    fill="none"
    stroke={c}
    strokeWidth={sw}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    style={{ flexShrink: 0, ...style }}
  >
    <path d={PATHS[n] || ""} />
  </svg>
);

/* ---------------- primitives ---------------- */
export function Badge({ s }) {
  const map = {
    Active: ["var(--ok-bg)", "#166534"],
    Completed: ["var(--ok-bg)", "#166534"],
    completed: ["var(--ok-bg)", "#166534"],
    "In Progress": ["var(--info-bg)", "#1e40af"],
    in_progress: ["var(--info-bg)", "#1e40af"],
    Pending: ["var(--warn-bg)", "#9a3412"],
    Inactive: ["#f3f4f6", "#6b7280"],
    Imported: ["var(--ok-bg)", "#166534"],
    Skipped: ["#f3f4f6", "#6b7280"],
    Invalid: ["var(--err-bg)", "#991b1b"],
    owner: ["#ede9fe", "#5b21b6"],
    supervisor: ["var(--info-bg)", "#1e40af"],
  };
  const label = { in_progress: "In Progress", completed: "Completed" }[s] || s;
  const [bg, color] = map[s] || ["#f3f4f6", "#6b7280"];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 9px",
        borderRadius: 12,
        fontSize: 11,
        fontWeight: 600,
        background: bg,
        color,
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}

export function Btn({ children, onClick, variant = "primary", size = "md", icon, disabled, type = "button", title }) {
  const styles = {
    primary: {
      background: "linear-gradient(135deg,var(--brand),var(--brand-dk))",
      color: "#fff",
      border: "none",
      boxShadow: "0 2px 8px rgba(22,163,74,0.25)",
    },
    secondary: { background: "#fff", color: "var(--tx2)", border: "1px solid var(--bdr)" },
    ghost: { background: "transparent", color: "var(--tx2)", border: "none" },
    danger: { background: "#dc2626", color: "#fff", border: "none" },
  };
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        padding: size === "sm" ? "6px 12px" : "9px 16px",
        borderRadius: 8,
        fontSize: 13,
        fontWeight: 600,
        minHeight: size === "sm" ? 32 : 40, /* comfortable touch target */
        ...styles[variant],
      }}
    >
      {icon && <Icon n={icon} s={14} />}
      {children}
    </button>
  );
}

export function IconBtn({ n, onClick, title, color = "var(--tx2)", disabled }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      disabled={disabled}
      style={{
        background: "none",
        border: "none",
        color,
        padding: 8,
        borderRadius: 6,
        display: "inline-flex",
      }}
    >
      <Icon n={n} s={16} c={color} />
    </button>
  );
}

export const fieldStyle = {
  width: "100%",
  border: "1px solid var(--bdr)",
  borderRadius: 8,
  padding: "10px 12px",
  color: "var(--tx1)",
  outline: "none",
  background: "#fff",
  minHeight: 40,
};

export function Field({ label, children, hint, error }) {
  return (
    <label style={{ display: "block", marginBottom: 14 }}>
      <span style={{ fontSize: 12, fontWeight: 600, color: "var(--tx1)", display: "block", marginBottom: 5 }}>
        {label}
      </span>
      {children}
      {hint && <span className="tiny muted" style={{ display: "block", marginTop: 4 }}>{hint}</span>}
      {error && <span className="tiny" style={{ display: "block", marginTop: 4, color: "var(--err)" }}>{error}</span>}
    </label>
  );
}

export function SearchInput({ value, onChange, placeholder }) {
  return (
    <div style={{ position: "relative", maxWidth: 320, width: "100%" }}>
      <span style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)" }}>
        <Icon n="Search" s={15} c="var(--txm)" />
      </span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{ ...fieldStyle, paddingLeft: 32 }}
      />
    </div>
  );
}

export function Modal({ title, onClose, children, width = 460 }) {
  // Escape-to-close and a focus trap entry point: the prototype's modals
  // were mouse-only, which is unworkable during fast data entry.
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 60,
        padding: 16,
        paddingTop: `calc(16px + var(--safe-top))`,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#fff",
          borderRadius: 14,
          padding: 22,
          width,
          maxWidth: "100%",
          maxHeight: "90vh",
          overflowY: "auto",
          boxShadow: "0 20px 40px rgba(0,0,0,0.18)",
        }}
      >
        <div className="row" style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 16, fontWeight: 700 }}>{title}</div>
          <div className="spacer" />
          <IconBtn n="X" onClick={onClose} title="Close" color="var(--txm)" />
        </div>
        {children}
      </div>
    </div>
  );
}

export function ConfirmModal({ title, message, confirmLabel = "Delete", onConfirm, onClose, busy, danger = true }) {
  return (
    <Modal title={title} onClose={onClose} width={420}>
      <div style={{ fontSize: 13, color: "var(--tx2)", lineHeight: 1.65, marginBottom: 18 }}>{message}</div>
      <div className="row" style={{ gap: 10 }}>
        <div className="spacer" />
        <Btn variant="secondary" onClick={onClose} disabled={busy}>Cancel</Btn>
        <Btn variant={danger ? "danger" : "primary"} onClick={onConfirm} disabled={busy}>
          {busy ? "Working..." : confirmLabel}
        </Btn>
      </div>
    </Modal>
  );
}

export function PageHead({ title, sub, actions, back }) {
  return (
    <div className="page-head">
      <div style={{ minWidth: 0 }}>
        {back && (
          <button
            onClick={back.onClick}
            style={{ background: "none", border: "none", color: "var(--tx2)", padding: 0, marginBottom: 4, display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12 }}
          >
            <Icon n="ArrowLeft" s={13} /> {back.label}
          </button>
        )}
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0, letterSpacing: "-0.3px", overflowWrap: "anywhere" }}>
          {title}
        </h1>
        {sub && <div className="muted" style={{ fontSize: 13, marginTop: 3 }}>{sub}</div>}
      </div>
      {actions && <div className="toolbar">{actions}</div>}
    </div>
  );
}

export function StatCard({ icon, iconBg, label, value, sub, subColor, onClick }) {
  return (
    <div
      className="card"
      onClick={onClick}
      style={{ padding: "16px 18px", cursor: onClick ? "pointer" : "default" }}
    >
      <div className="row" style={{ alignItems: "flex-start" }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 12, color: "var(--tx2)", fontWeight: 500, marginBottom: 4 }}>{label}</div>
          <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.4px", overflowWrap: "anywhere" }}>
            {value}
          </div>
          {sub && <div style={{ fontSize: 11, marginTop: 4, fontWeight: 500, color: subColor || "var(--ok)" }}>{sub}</div>}
        </div>
        <div className="spacer" />
        <div
          style={{
            width: 40, height: 40, borderRadius: 10, background: iconBg,
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
          }}
        >
          <Icon n={icon} s={18} c="#fff" />
        </div>
      </div>
    </div>
  );
}

/* ---------------- states ---------------- */
export function Spinner({ size = 18 }) {
  return (
    <span
      style={{
        width: size, height: size, display: "inline-block",
        border: "2px solid var(--bdr)", borderTopColor: "var(--brand)",
        borderRadius: "50%", animation: "wrdt-spin 0.7s linear infinite",
      }}
    />
  );
}

export function Loading({ label = "Loading..." }) {
  return (
    <div style={{ padding: 40, textAlign: "center", color: "var(--tx2)" }}>
      <Spinner />
      <div style={{ marginTop: 10, fontSize: 13 }}>{label}</div>
    </div>
  );
}

export function EmptyState({ icon = "AlertCircle", title, message, action }) {
  return (
    <div style={{ padding: 44, textAlign: "center" }}>
      <div
        style={{
          width: 52, height: 52, borderRadius: 14, background: "var(--brand-bg)",
          display: "inline-flex", alignItems: "center", justifyContent: "center", marginBottom: 12,
        }}
      >
        <Icon n={icon} s={24} c="var(--brand)" />
      </div>
      <div style={{ fontSize: 15, fontWeight: 600 }}>{title}</div>
      {message && <div className="muted" style={{ fontSize: 13, marginTop: 6 }}>{message}</div>}
      {action && <div style={{ marginTop: 16 }}>{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div style={{ padding: 36, textAlign: "center" }}>
      <Icon n="AlertCircle" s={26} c="var(--err)" />
      <div style={{ fontSize: 14, fontWeight: 600, marginTop: 10 }}>Could not load this</div>
      <div className="muted" style={{ fontSize: 13, marginTop: 6 }}>
        {error?.message || "Unexpected error."}
      </div>
      {onRetry && (
        <div style={{ marginTop: 14 }}>
          <Btn variant="secondary" icon="RefreshCw" onClick={onRetry}>Retry</Btn>
        </div>
      )}
    </div>
  );
}

export function InlineError({ error }) {
  if (!error) return null;
  return (
    <div
      role="alert"
      style={{
        fontSize: 12.5, color: "#991b1b", background: "var(--err-bg)",
        border: "1px solid #fecaca", borderRadius: 8, padding: "9px 12px", marginBottom: 14,
      }}
    >
      {typeof error === "string" ? error : error.message}
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPage }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="row wrap" style={{ padding: "10px 14px", borderTop: "1px solid var(--bdr)", gap: 10 }}>
      <span className="tiny muted">
        Showing {from}&ndash;{to} of {total}
      </span>
      <div className="spacer" />
      <IconBtn n="ChevronLeft" title="Previous page" onClick={() => onPage(page - 1)} disabled={page <= 1} />
      <span className="tiny muted">
        {page} / {pages}
      </span>
      <IconBtn n="ChevronRight" title="Next page" onClick={() => onPage(page + 1)} disabled={page >= pages} />
    </div>
  );
}

/* ---------------- toasts ---------------- */
export function useToasts() {
  const [items, setItems] = useState([]);
  const idRef = useRef(0);
  const push = (message, tone = "ok") => {
    const id = ++idRef.current;
    setItems((x) => [...x, { id, message, tone }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 4200);
  };
  const node = (
    <div
      style={{
        position: "fixed", right: 14, bottom: `calc(14px + var(--safe-bottom))`,
        display: "flex", flexDirection: "column", gap: 8, zIndex: 80, maxWidth: "calc(100vw - 28px)",
      }}
    >
      {items.map((t) => (
        <div
          key={t.id}
          role="status"
          style={{
            background: t.tone === "err" ? "#991b1b" : "var(--tx1)",
            color: "#fff", borderRadius: 9, padding: "10px 14px",
            fontSize: 13, boxShadow: "0 8px 24px rgba(0,0,0,0.22)",
          }}
        >
          {t.message}
        </div>
      ))}
    </div>
  );
  return { push, node };
}
