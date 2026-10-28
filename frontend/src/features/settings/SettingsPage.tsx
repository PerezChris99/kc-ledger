import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, money } from "../../api";

type Target = {id:number;name:string;type:string;amount:string;currency:string;deadline:string;current:string;progress_pct:number;pace_status:string;days_remaining:number};
type AppSettings = {base_currency:string;time_zone:string;notifications_enabled:boolean;sounds:Record<string,boolean>};
const defaultSounds={success:true,info:true,warning:true,alarm:true};

export default function SettingsPage() {
  const [name,setName]=useState("");
  const [type,setType]=useState("revenue");
  const [amount,setAmount]=useState("");
  const [currency,setCurrency]=useState("USD");
  const [deadline,setDeadline]=useState("");
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  const [baseCurrency,setBaseCurrency]=useState("USD");
  const [timeZone,setTimeZone]=useState("Africa/Kampala");
  const [notificationsEnabled,setNotificationsEnabled]=useState(false);
  const [sounds,setSounds]=useState<Record<string,boolean>>(defaultSounds);
  const [prefsMessage,setPrefsMessage]=useState("");
  const [prefsError,setPrefsError]=useState("");
  const [prefsBusy,setPrefsBusy]=useState(false);
  const [permission,setPermission]=useState(typeof Notification!=="undefined"?Notification.permission:"unsupported");
  const client=useQueryClient();
  const targets=useQuery({queryKey:["targets"],queryFn:()=>api<{items:Target[]}>("/api/targets")});
  const preferences=useQuery({queryKey:["settings"],queryFn:()=>api<AppSettings>("/api/settings")});
  useEffect(()=>{
    if(!preferences.data)return;
    setBaseCurrency(preferences.data.base_currency);
    setTimeZone(preferences.data.time_zone);
    setNotificationsEnabled(preferences.data.notifications_enabled);
    setSounds({...defaultSounds,...preferences.data.sounds});
  },[preferences.data]);
  async function createTarget(event:FormEvent) {
    event.preventDefault();setError("");setMessage("");
    try {
      await api("/api/targets",{method:"POST",body:JSON.stringify({name,type,amount,currency,deadline})});
      setMessage("Target saved.");setName("");setAmount("");
      await client.invalidateQueries({queryKey:["targets"]});
    } catch(e) {setError(e instanceof Error?e.message:"Could not save target.");}
  }
  async function requestNotificationPermission() {
    if(!("Notification" in window)){setPrefsError("This browser does not support desktop notifications.");return;}
    const result=await Notification.requestPermission();
    setPermission(result);
    if(result!=="granted")setPrefsError("Browser notification permission was not granted.");
    else setPrefsMessage("Browser notification permission granted. Save preferences to enable notifications.");
  }
  async function savePreferences(event?: Pick<FormEvent, "preventDefault">) {
    event?.preventDefault();setPrefsBusy(true);setPrefsError("");setPrefsMessage("");
    if(notificationsEnabled&&permission!=="granted"){
      setPrefsBusy(false);setPrefsError("Grant browser notification permission first.");
      return;
    }
    try {
      const saved=await api<AppSettings>("/api/settings",{method:"PATCH",body:JSON.stringify({
        base_currency:baseCurrency.toUpperCase(),time_zone:timeZone,notifications_enabled:notificationsEnabled,sounds
      })});
      await Promise.all([client.invalidateQueries({queryKey:["settings"]}),client.invalidateQueries({queryKey:["dashboard"]}),client.invalidateQueries({queryKey:["insights"]})]);
      setBaseCurrency(saved.base_currency);setTimeZone(saved.time_zone);setNotificationsEnabled(saved.notifications_enabled);setSounds({...defaultSounds,...saved.sounds});
      setPrefsMessage("Preferences saved.");
    } catch(e) {setPrefsError(e instanceof Error?e.message:"Could not save preferences.");}
    finally {setPrefsBusy(false);}
  }
  return <div className="settings-grid">
    <section className="panel"><div className="panel-heading"><span>BUSINESS TARGETS</span><span className="panel-period">PERSISTENT</span></div><form className="form-stack" onSubmit={createTarget}><label>TARGET NAME<input value={name} onChange={e=>setName(e.target.value)} required maxLength={120}/></label><div className="form-row"><label>TYPE<select value={type} onChange={e=>setType(e.target.value)}><option value="revenue">Revenue</option><option value="clients">Clients</option><option value="hours">Hours</option></select></label><label>CURRENCY<input value={currency} onChange={e=>setCurrency(e.target.value.toUpperCase().slice(0,3))} required minLength={3} maxLength={3}/></label></div><label>AMOUNT<input type="number" min="0.01" step="0.01" value={amount} onChange={e=>setAmount(e.target.value)} required/></label><label>DEADLINE<input type="date" value={deadline} onChange={e=>setDeadline(e.target.value)} required/></label>{error&&<p className="form-error">{error}</p>}{message&&<p className="form-success">{message}</p>}<button className="primary-button">Create target</button></form></section>
    <section className="panel"><div className="panel-heading"><span>SAVED TARGETS</span><span className="panel-period">{targets.data?.items.length??0} RECORDS</span></div>{targets.data?.items.map(t=><div className="target-row" key={t.id}><div className="target-row-main"><strong>{t.name}</strong><small>{t.type} · deadline {t.deadline} · {t.days_remaining} days remaining</small><div className="target-track"><span style={{width:`${Math.max(0,Math.min(100,t.progress_pct))}%`}}/></div><small>{t.type==="revenue"?money(t.current,t.currency):t.current} / {t.type==="revenue"?money(t.amount,t.currency):t.amount} · {t.pace_status.replace("_"," ")}</small></div><strong className="mono">{t.progress_pct.toFixed(0)}%</strong></div>)}{targets.isLoading&&<p className="empty-message">Loading targets…</p>}{!targets.isLoading&&!targets.data?.items.length&&<p className="empty-message">No targets set yet.</p>}<p className="settings-note">Revenue and client targets use live server totals. Hour targets use recorded time entries.</p></section>
    <section className="panel"><div className="panel-heading"><span>REGIONAL AND CURRENCY SETTINGS</span><span className="panel-period">PERSISTENT</span></div><form className="form-stack" onSubmit={savePreferences}><div className="form-row"><label>BASE CURRENCY<input value={baseCurrency} onChange={e=>setBaseCurrency(e.target.value.toUpperCase().slice(0,3))} required minLength={3} maxLength={3}/></label><label>TIMEZONE<input value={timeZone} onChange={e=>setTimeZone(e.target.value)} required placeholder="Africa/Kampala"/></label></div><p className="settings-note">Financial totals convert only when a matching stored FX rate exists. Timezone changes affect the preferred display timezone; backend scheduling currently follows the server timezone.</p><button className="primary-button" disabled={prefsBusy}>{prefsBusy?"SAVING…":"Save preferences"}</button>{prefsError&&<p className="form-error">{prefsError}</p>}{prefsMessage&&<p className="form-success">{prefsMessage}</p>}</form></section>
    <section className="panel"><div className="panel-heading"><span>SOUNDS AND NOTIFICATIONS</span><span className="panel-period">EVENT-DRIVEN</span></div><div className="settings-toggle"><div><strong>Browser notifications</strong><small>Show desktop notifications when the app is in the background.</small></div><input type="checkbox" checked={notificationsEnabled} onChange={e=>setNotificationsEnabled(e.target.checked)} aria-label="Enable browser notifications"/></div><div className="notification-permission"><span>Permission: {permission}</span><button className="small-button" type="button" onClick={requestNotificationPermission}>Request permission</button></div>{Object.entries(sounds).map(([key,value])=><div className="settings-toggle" key={key}><div><strong>{key.charAt(0).toUpperCase()+key.slice(1)} tones</strong><small>{key==="success"?"Payment recorded or a plan becomes perfect":key==="info"?"General ledger event":key==="warning"?"Instalment due soon or plan at risk":"Overdue invoice or broken plan"}</small></div><input type="checkbox" checked={Boolean(value)} onChange={e=>setSounds(current=>({...current,[key]:e.target.checked}))} aria-label={`Enable ${key} sounds`}/></div>)}<button className="primary-button" onClick={()=>void savePreferences()} disabled={prefsBusy}>Save sound preferences</button><p className="settings-note">Tones are synthesized locally with Web Audio. No audio files or network requests are required.</p></section>
    <section className="panel security-panel"><div className="panel-heading"><span>SECURITY BASELINE</span><span className="panel-period">PRIVATE INSTANCE</span></div><div className="security-line"><strong>Session authentication</strong><span className="status-pill">Enabled</span></div><div className="security-line"><strong>CSRF protection</strong><span className="status-pill">Enabled</span></div><div className="security-line"><strong>Database</strong><span className="mono">SQLite / WAL</span></div><div className="security-line"><strong>Offline storage</strong><span className="mono">App shell only</span></div></section>
  </div>;
}
