import { useState, type FormEvent } from "react";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { api } from "../../api";

export default function LoginPage({ onSuccess, unavailable = false }: { onSuccess: () => void; unavailable?: boolean }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }
  return <main className="login-layout">
    <section className="login-visual">
      <div className="login-brand"><span className="wordmark-symbol">KC</span><span>KC LEDGER</span></div>
      <div className="login-message"><p className="eyebrow">PRIVATE FINANCIAL OPERATIONS</p><h1>Your business,<br/>guarded.</h1><p>Track the money. Understand the client. Make the next decision with evidence.</p><div className="login-rule"><span/> PERSONAL FINANCE CONSOLE / SENTINEL</div></div>
      <div className="login-foot"><span>PRIVATE INSTANCE</span><span>ACCESS RESTRICTED</span></div>
    </section>
    <section className="login-panel">
      <div className="login-form-wrap">
        <div className="login-lock"><LockKeyhole size={18}/></div>
        <p className="eyebrow">AUTHENTICATED ACCESS</p>
        <h2>Sign in to your ledger</h2>
        <p className="login-help">This workspace is private. Sign in with the owner account configured by the administrator.</p>
        {unavailable && <p className="form-error" role="alert">The API is unavailable. Start the backend and try again.</p>}
        <form onSubmit={submit}>
          <label htmlFor="username">USERNAME</label>
          <input id="username" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required />
          <label htmlFor="password">PASSWORD</label>
          <input id="password" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required />
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" disabled={busy}>{busy ? "AUTHENTICATING…" : "Open console"} <ArrowRight size={15}/></button>
        </form>
        <p className="login-security">SESSION PROTECTED <span/> CSRF ENABLED</p>
      </div>
    </section>
  </main>;
}
