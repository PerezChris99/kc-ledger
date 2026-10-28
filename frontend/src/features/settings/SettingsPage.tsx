import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, money } from "../../api";
type Target = { id: number; name: string; type: string; amount: string; currency: string; deadline: string };
export default function SettingsPage() {
  const [name,setName]=useState("");
  const [type,setType]=useState("revenue");
  const [amount,setAmount]=useState("");
  const [currency,setCurrency]=useState("USD");
  const [deadline,setDeadline]=useState("");
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  const client=useQueryClient();
  const targets=useQuery({queryKey:["targets"],queryFn:()=>api<{items:Target[]}>("/api/targets")});
  async function create(event:FormEvent) {
    event.preventDefault(); setError(""); setMessage("");
    try {
      await api("/api/targets",{method:"POST",body:JSON.stringify({name,type,amount,currency,deadline})});
      setMessage("Target saved."); setName(""); setAmount("");
      await client.invalidateQueries({queryKey:["targets"]});
    } catch(e) { setError(e instanceof Error?e.message:"Could not save target."); }
  }
  return <div className="settings-grid"><section className="panel"><div className="panel-heading"><span>BUSINESS TARGETS</span><span className="panel-period">PERSISTENT</span></div><form className="form-stack" onSubmit={create}><label>TARGET NAME<input value={name} onChange={e=>setName(e.target.value)} required maxLength={120}/></label><div className="form-row"><label>TYPE<select value={type} onChange={e=>setType(e.target.value)}><option value="revenue">Revenue</option><option value="clients">Clients</option><option value="hours">Hours</option></select></label><label>CURRENCY<input value={currency} onChange={e=>setCurrency(e.target.value.toUpperCase().slice(0,3))} required minLength={3} maxLength={3}/></label></div><label>AMOUNT<input type="number" min="0.01" step="0.01" value={amount} onChange={e=>setAmount(e.target.value)} required/></label><label>DEADLINE<input type="date" value={deadline} onChange={e=>setDeadline(e.target.value)} required/></label>{error&&<p className="form-error">{error}</p>}{message&&<p className="form-success">{message}</p>}<button className="primary-button">Create target</button></form></section><section className="panel"><div className="panel-heading"><span>SAVED TARGETS</span><span className="panel-period">{targets.data?.items.length ?? 0} RECORDS</span></div>{targets.data?.items.map(t=><div className="target-row" key={t.id}><div><strong>{t.name}</strong><small>{t.type} · deadline {t.deadline}</small></div><strong className="mono">{money(t.amount,t.currency)}</strong></div>)}{targets.isLoading&&<p className="empty-message">Loading targets…</p>}{!targets.isLoading&&!targets.data?.items.length&&<p className="empty-message">No targets set yet.</p>}<p className="settings-note">Targets are stored in the server database. Progress projections will use recorded financial data in a later widget pass.</p></section><section className="panel security-panel"><div className="panel-heading"><span>SECURITY BASELINE</span><span className="panel-period">PRIVATE INSTANCE</span></div><div className="security-line"><strong>Session authentication</strong><span className="status-pill">Enabled</span></div><div className="security-line"><strong>CSRF protection</strong><span className="status-pill">Enabled</span></div><div className="security-line"><strong>Database</strong><span className="mono">SQLite / WAL</span></div><div className="security-line"><strong>Offline storage</strong><span className="mono">App shell only</span></div></section></div>;
}
