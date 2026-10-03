import { useCallback, useEffect, useState } from "react";

import { AuthProvider, useAuth } from "./lib/auth.jsx";
import { makeT } from "./lib/i18n.js";
import { initials } from "./lib/format.js";
import { Icon, Loading, useToasts } from "./components/ui.jsx";

import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Regions from "./pages/Regions.jsx";
import Groups from "./pages/Groups.jsx";
import Members from "./pages/Members.jsx";
import MemberProfile from "./pages/MemberProfile.jsx";
import MeetingsList from "./pages/MeetingsList.jsx";
import MeetingRegister from "./pages/MeetingRegister.jsx";
import Loans from "./pages/Loans.jsx";
import Expenses from "./pages/Expenses.jsx";
import Reports from "./pages/Reports.jsx";
import Activity from "./pages/Activity.jsx";
import Settings from "./pages/Settings.jsx";
import ExcelImport from "./pages/ExcelImport.jsx";

/**
 * Application shell: sidebar navigation, top bar and a tiny state-based
 * router. The hierarchy screens pass context (region, group, meeting)
 * forward through `go(page, ctx)`.
 *
 * Navigation items are filtered by role. That is a convenience only: the
 * API independently rejects anything a Supervisor is not allowed to do.
 */
const NAV = [
  { id: "dashboard", icon: "LayoutDashboard", key: "dashboard" },
  { id: "regions", icon: "MapPin", key: "regions", owner: true },
  { id: "groups", icon: "Users", key: "groups" },
  { id: "members", icon: "UserCheck", key: "members" },
  { id: "loans", icon: "CreditCard", key: "loans" },
  { id: "expenses", icon: "Receipt", key: "expenses" },
  { id: "reports", icon: "FileBarChart", key: "reports" },
  { id: "import", icon: "Upload", key: "excelImport", owner: true },
  { id: "activity", icon: "Activity", key: "activity", owner: true },
  { id: "settings", icon: "Settings", key: "settings" },
];

// Which sidebar item should light up for deeper screens.
const PARENT = {
  memberProfile: "members",
  meetings: "groups",
  register: "groups",
};

function Shell() {
  const { user, role, isOwner, booting, logout } = useAuth();
  const [lang, setLang] = useState(() => localStorage.getItem("wrdt.lang") || "en");
  const [route, setRoute] = useState({ page: "dashboard", ctx: {} });
  const [navOpen, setNavOpen] = useState(false);
  const toasts = useToasts();
  const t = makeT(lang);

  useEffect(() => {
    localStorage.setItem("wrdt.lang", lang);
  }, [lang]);

  const go = useCallback((page, ctx = {}) => {
    setRoute({ page, ctx });
    setNavOpen(false);
  }, []);

  // Back to the dashboard whenever the session ends, so the next person
  // to sign in on a shared device never lands on the previous user's screen.
  useEffect(() => {
    if (!user) setRoute({ page: "dashboard", ctx: {} });
  }, [user]);

  if (booting) return <Loading label={t.loading} />;
  if (!user) return <Login t={t} lang={lang} setLang={setLang} />;

  const toast = toasts.push;
  const { page, ctx } = route;
  const active = PARENT[page] || (page === "import" ? "import" : page);

  const screens = {
    dashboard: <Dashboard t={t} go={go} />,
    regions: <Regions t={t} go={go} />,
    groups: <Groups t={t} ctx={ctx} go={go} />,
    members: <Members t={t} ctx={ctx} go={go} />,
    memberProfile: <MemberProfile t={t} ctx={ctx} go={go} />,
    meetings: <MeetingsList t={t} ctx={ctx} go={go} />,
    register: <MeetingRegister key={ctx.meetingId} t={t} ctx={ctx} go={go} toast={toast} />,
    loans: <Loans t={t} go={go} />,
    expenses: <Expenses t={t} />,
    reports: <Reports t={t} />,
    activity: <Activity t={t} />,
    settings: <Settings t={t} toast={toast} />,
    import: <ExcelImport t={t} toast={toast} />,
  };

  return (
    <div className="app-shell">
      {navOpen && <div className="scrim" onClick={() => setNavOpen(false)} />}

      <aside className={`sidebar${navOpen ? " open" : ""}`}>
        <div style={{ padding: "18px 18px 14px", display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 42,
              height: 42,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <img
              src="/wrdt-logo.png"
              alt="Women And Rural Development Trust"
              style={{
                width: "100%",
                height: "100%",
                objectFit: "contain",
                display: "block",
              }}
            />
          </div>
          <div>
            <div style={{ color: "#fff", fontWeight: 700, fontSize: 15 }}>{t.appName}</div>
            <div style={{ color: "var(--side-txt)", fontSize: 10 }}>{t.tagline}</div>
          </div>
        </div>

        <nav style={{ flex: 1, overflowY: "auto", padding: "6px 10px" }}>
          {NAV.filter((n) => !n.owner || isOwner).map((n) => {
            const on = active === n.id;
            return (
              <button
                key={n.id}
                onClick={() => go(n.id)}
                aria-current={on ? "page" : undefined}
                style={{
                  width: "100%", display: "flex", alignItems: "center", gap: 10,
                  padding: "10px 12px", marginBottom: 2, borderRadius: 8, border: "none",
                  background: on ? "var(--side-act)" : "transparent",
                  color: on ? "var(--side-txt-act)" : "var(--side-txt)",
                  fontSize: 13, fontWeight: on ? 600 : 500, textAlign: "left", minHeight: 40,
                }}
              >
                <Icon n={n.icon} s={17} />
                {t[n.key]}
              </button>
            );
          })}
        </nav>

        <div style={{ padding: 12, borderTop: "1px solid var(--side-hov)" }}>
          <div className="row" style={{ gap: 10, marginBottom: 10 }}>
            <div
              style={{
                width: 34, height: 34, borderRadius: "50%", background: "var(--side-hov)",
                color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 12, fontWeight: 700,
              }}
            >
              {initials(user.full_name)}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ color: "#fff", fontSize: 12.5, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {user.full_name}
              </div>
              <div style={{ color: "var(--side-txt)", fontSize: 11 }}>{role === "owner" ? t.owner : t.supervisor}</div>
            </div>
          </div>
          <button
            onClick={logout}
            style={{
              width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              padding: "9px 0", borderRadius: 8, border: "1px solid var(--side-hov)",
              background: "transparent", color: "var(--side-txt)", fontSize: 12.5, minHeight: 38,
            }}
          >
            <Icon n="LogOut" s={14} /> {t.logout}
          </button>
        </div>
      </aside>

      <div className="main-col">
        <header
          className="topbar"
          style={{
            height: "var(--topbar-h)", background: "#fff", borderBottom: "1px solid var(--bdr)",
            display: "flex", alignItems: "center", gap: 10, padding: "0 16px", flexShrink: 0,
            paddingTop: "var(--safe-top)", boxSizing: "content-box",
          }}
        >
          <button
            className="menu-btn"
            onClick={() => setNavOpen(true)}
            aria-label="Open menu"
            style={{ background: "none", border: "none", padding: 8, display: "none" }}
          >
            <Icon n="Menu" s={20} />
          </button>
          <div className="spacer" />
          <div style={{ display: "flex", gap: 6 }}>
            {["en", "ta"].map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                style={{
                  padding: "6px 12px", borderRadius: 7, fontSize: 12, fontWeight: 500, minHeight: 32,
                  border: `1.5px solid ${lang === l ? "var(--brand)" : "var(--bdr)"}`,
                  background: lang === l ? "var(--brand-lt)" : "#fff",
                  color: lang === l ? "var(--brand)" : "var(--tx2)",
                }}
              >
                {l === "en" ? "EN" : "\u0ba4\u0bae\u0bbf\u0bb4\u0bcd"}
              </button>
            ))}
          </div>
        </header>

        <main className="content">{screens[page] || screens.dashboard}</main>
      </div>

      {toasts.node}
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}

