import { useState } from "react";

import { useAuth } from "../lib/auth.jsx";
import { Btn, Icon, InlineError, fieldStyle } from "../components/ui.jsx";

/**
 * Real sign-in.
 *
 * The prototype accepted anything: it ran a 900ms timer and flipped a
 * boolean, with the demo credentials pre-filled in the inputs. This
 * calls the API, surfaces the server's message (including the
 * rate-limit response), and keeps no credentials in the source.
 */
export default function Login({ t, lang, setLang }) {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [showHelp, setShowHelp] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email.trim(), password);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100%",
        background: "linear-gradient(135deg,#f0fdf4,#f8fafc,#eff6ff)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        paddingTop: "calc(16px + var(--safe-top))",
      }}
    >
      <div style={{ width: "100%", maxWidth: 400 }}>
        <form
          onSubmit={submit}
          style={{ background: "#fff", borderRadius: 16, boxShadow: "0 20px 40px rgba(0,0,0,0.10)", padding: "34px 28px" }}
        >
          <div style={{ textAlign: "center", marginBottom: 22 }}>
            <div
              style={{
                width: 86, height: 86,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: 10,
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
            <div style={{ fontSize: 23, fontWeight: 800, letterSpacing: "-0.5px" }}>{t.appName}</div>
            <div className="tiny muted">{t.tagline}</div>
            <div className="tiny" style={{ color: "var(--txm)" }}>{t.taTagline}</div>
          </div>

          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 3 }}>{t.loginTitle}</div>
          <div className="muted" style={{ fontSize: 12, marginBottom: 16 }}>{t.loginSub}</div>

          <InlineError error={error} />

          <label style={{ display: "block", marginBottom: 13 }}>
            <span style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 5 }}>{t.email}</span>
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={fieldStyle}
            />
          </label>

          <label style={{ display: "block", marginBottom: 14 }}>
            <span style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 5 }}>{t.password}</span>
            <div style={{ position: "relative" }}>
              <input
                type={showPwd ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{ ...fieldStyle, paddingRight: 40 }}
              />
              <button
                type="button"
                onClick={() => setShowPwd((v) => !v)}
                aria-label={showPwd ? "Hide password" : "Show password"}
                style={{
                  position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
                  background: "none", border: "none", padding: 6,
                }}
              >
                <Icon n={showPwd ? "EyeOff" : "Eye"} s={16} c="var(--txm)" />
              </button>
            </div>
          </label>

          <div className="row" style={{ marginBottom: 16 }}>
            <button
              type="button"
              onClick={() => setShowHelp((v) => !v)}
              style={{ fontSize: 12, color: "var(--brand)", background: "none", border: "none", padding: 0, fontWeight: 500 }}
            >
              {t.forgotPwd}
            </button>
          </div>
          {showHelp && (
            <div
              className="tiny"
              style={{ background: "var(--brand-bg)", border: "1px solid var(--brand-lt)", borderRadius: 8, padding: "9px 12px", marginBottom: 14, lineHeight: 1.6 }}
            >
              {t.forgotHelp}
            </div>
          )}

          <Btn type="submit" disabled={busy}>
            <span style={{ width: "100%", textAlign: "center" }}>{busy ? t.signingIn : t.loginBtn}</span>
          </Btn>

          <div style={{ marginTop: 18 }}>
            <div className="tiny muted" style={{ marginBottom: 6, fontWeight: 500 }}>{t.langLabel}</div>
            <div style={{ display: "flex", gap: 8 }}>
              {["en", "ta"].map((l) => (
                <button
                  key={l}
                  type="button"
                  onClick={() => setLang(l)}
                  style={{
                    flex: 1, padding: "8px 0", borderRadius: 7, fontSize: 12, fontWeight: 500,
                    border: `1.5px solid ${lang === l ? "var(--brand)" : "var(--bdr)"}`,
                    background: lang === l ? "var(--brand-lt)" : "#fff",
                    color: lang === l ? "var(--brand)" : "var(--tx2)",
                  }}
                >
                  {l === "en" ? "English" : "\u0ba4\u0bae\u0bbf\u0bb4\u0bcd"}
                </button>
              ))}
            </div>
          </div>
        </form>
        <div className="tiny" style={{ textAlign: "center", marginTop: 14, color: "var(--txm)" }}>
          &copy; {new Date().getFullYear()} Women And Rural Development Trust
        </div>
      </div>
    </div>
  );
}

