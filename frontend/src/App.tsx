import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, CalendarDays, ChevronDown, CircleDollarSign, Clock3, Command, LayoutDashboard, LogOut, Menu, Search, Settings2, ShieldAlert, Users, WalletCards, X, ArrowLeftRight } from "lucide-react";
import { api, money } from "./api";
import LoginPage from "./features/auth/LoginPage";
import DashboardPage from "./features/dashboard/DashboardPage";
import ClientsPage from "./features/clients/ClientsPage";
import InvoicesPage from "./features/invoices/InvoicesPage";
import PlansPage from "./features/plans/PlansPage";
import InsightsPage from "./features/insights/InsightsPage";
import AvoidPage from "./features/avoid/AvoidPage";
import HistoryPage from "./features/history/HistoryPage";
import SettingsPage from "./features/settings/SettingsPage";
import NotificationWatcher from "./features/notifications/NotificationWatcher";

type Session = { authenticated: boolean; username: string | null };
type CalendarResult = { month: string; items: {date:string;kind:string;title:string;client:string;status:string}[] };
type Target = {id:number;name:string;type:string;amount:string;currency:string;deadline:string};

const nav = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "clients", label: "Clients", icon: Users },
  { id: "invoices", label: "Invoices", icon: WalletCards },
  { id: "plans", label: "Instalment plans", icon: CalendarDays },
  { id: "insights", label: "Insights", icon: Activity },
  { id: "avoid", label: "Avoid", icon: ShieldAlert },
  { id: "history", label: "History", icon: Activity },
  { id: "settings", label: "Settings", icon: Settings2 },
];

function CalendarPopover() {
  const [open,setOpen] = useState(false);
  const month = new Date().toISOString().slice(0,7);
  const query = useQuery({queryKey:["calendar",month],queryFn:()=>api<CalendarResult>(`/api/calendar?month=${month}`),enabled:open});
  return <div className="widget-anchor"><button className="icon-button" aria-label="Calendar and due dates" aria-expanded={open} onClick={()=>setOpen(!open)}><CalendarDays size={17}/></button>{open&&<section className="widget-popover"><div className="panel-heading"><span>THIS MONTH</span><button className="text-button" onClick={()=>setOpen(false)}>Close</button></div>{query.isLoading&&<p className="empty-message">Loading dates…</p>}{query.data?.items.map((item,i)=><div className="widget-list-row" key={`${item.kind}-${i}`}><span className={item.status==="overdue"?"calendar-dot danger":"calendar-dot"}/><div><strong>{item.title}</strong><small>{item.client} · {item.date}</small></div></div>)}{!query.isLoading&&!query.error&&!query.data?.items.length&&<p className="empty-message">No invoice or instalment due dates this month.</p>}{query.error&&<p className="empty-message">Calendar unavailable.</p>}</section>}</div>;
}

function FxPopover() {
  const [open,setOpen]=useState(false);
  const [amount,setAmount]=useState("1");
  const [base,setBase]=useState("USD");
  const [quote,setQuote]=useState("UGX");
  const query=useQuery({queryKey:["fx-convert",amount,base,quote],queryFn:()=>api<{converted:string;rate:string;source:string}>(`/api/fx/convert?amount=${encodeURIComponent(amount)}&base=${base}&quote=${quote}`),enabled:open&&amount!==""&&Number(amount)>=0});
  return <div className="widget-anchor"><button className="icon-button" aria-label="Currency converter" aria-expanded={open} onClick={()=>setOpen(!open)}><ArrowLeftRight size={17}/></button>{open&&<section className="widget-popover fx-popover"><div className="panel-heading"><span>CURRENCY CONVERTER</span><button className="text-button" onClick={()=>setOpen(false)}>Close</button></div><label>AMOUNT<input type="number" min="0" step="any" value={amount} onChange={e=>setAmount(e.target.value)}/></label><div className="form-row"><label>FROM<input value={base} maxLength={3} onChange={e=>setBase(e.target.value.toUpperCase())}/></label><label>TO<input value={quote} maxLength={3} onChange={e=>setQuote(e.target.value.toUpperCase())}/></label></div>{query.data&&<div className="fx-result"><strong>{query.data.converted} {quote}</strong><small>Rate {query.data.rate} · {query.data.source}</small></div>}{query.error&&<p className="inline-warning">No stored exchange rate for this pair. Add a rate in the FX service before converting.</p>}</section>}</div>;
}

function TargetTracker() {
  const targets=useQuery({queryKey:["targets"],queryFn:()=>api<{items:Target[]}>("/api/targets")});
  const dashboard=useQuery({queryKey:["dashboard"],queryFn:()=>api<{currency:string;collected:string;client_count:number;total_hours:string}>("/api/dashboard")});
  const target=targets.data?.items[0];
  if(!target) return <div className="target-empty"><span className="target-icon"><CircleDollarSign size={17}/></span><div><strong>No target set</strong><small>Set one in Settings</small></div></div>;
  const current=target.type==="revenue"?Number(dashboard.data?.collected??0):target.type==="clients"?Number(dashboard.data?.client_count??0):Number(dashboard.data?.total_hours??0);
  const progress=Math.max(0,Math.min(100,current/Math.max(1,Number(target.amount))*100));
  return <button className="target-widget" onClick={()=>window.dispatchEvent(new CustomEvent("kc-ledger:navigate",{detail:"settings"}))}><div className="target-widget-top"><span>{target.name}</span><strong>{progress.toFixed(0)}%</strong></div><div className="target-track"><span style={{width:`${progress}%`}}/></div><small>{target.type==="revenue"?money(current,target.currency):current} / {target.type==="revenue"?money(target.amount,target.currency):target.amount} · {target.deadline}</small></button>;
}

export default function App() {
  const [active,setActive]=useState("dashboard");
  const [now,setNow]=useState(new Date());
  const [search,setSearch]=useState("");
  const [moreOpen,setMoreOpen]=useState(false);
  const queryClient=useQueryClient();
  const session=useQuery({queryKey:["session"],queryFn:()=>api<Session>("/api/session"),retry:false});
  const preferences=useQuery({queryKey:["settings"],queryFn:()=>api<{time_zone:string}>("/api/settings"),enabled:Boolean(session.data?.authenticated)});
  useEffect(()=>{const id=window.setInterval(()=>setNow(new Date()),1000);return()=>window.clearInterval(id);},[]);
  useEffect(()=>{const handler=(event:Event)=>{const target=(event as CustomEvent<string>).detail;if(typeof target==="string")setActive(target);};window.addEventListener("kc-ledger:navigate",handler);return()=>window.removeEventListener("kc-ledger:navigate",handler);},[]);
  async function signOut(){try{await api("/api/auth/logout",{method:"POST",body:"{}"});}finally{await queryClient.invalidateQueries({queryKey:["session"]});setActive("dashboard");}}
  if(session.isLoading) return <main className="boot-screen"><span className="wordmark-symbol">KC</span><p className="eyebrow">VERIFYING PRIVATE SESSION</p></main>;
  if(!session.data?.authenticated) return <LoginPage unavailable={Boolean(session.error)} onSuccess={()=>{void queryClient.invalidateQueries({queryKey:["session"]});}}/>;
  const page = active==="clients" ? <ClientsPage initialQuery={search}/> :
    active==="invoices" ? <InvoicesPage/> : active==="plans" ? <PlansPage/> :
    active==="insights" ? <InsightsPage/> : active==="avoid" ? <AvoidPage/> :
    active==="history" ? <HistoryPage/> : active==="settings" ? <SettingsPage/> : <DashboardPage/>;
  const heading=nav.find(item=>item.id===active)?.label??"Dashboard";
  return <div className="app-frame"><NotificationWatcher/>
    <aside className="sidebar">
      <a className="wordmark" href="/" onClick={e=>{e.preventDefault();setActive("dashboard");}} aria-label="KC Ledger home"><span className="wordmark-symbol">KC</span><span className="wordmark-copy">KC LEDGER<small>FINANCIAL OPERATIONS</small></span></a>
      <div className="sidebar-label">WORKSPACE</div>
      <nav aria-label="Main navigation">{nav.map(item=>{const Icon=item.icon;return <button key={item.id} className={active===item.id?"nav-item active":"nav-item"} onClick={()=>setActive(item.id)} aria-current={active===item.id?"page":undefined}><Icon size={17} strokeWidth={1.8}/><span>{item.label}</span>{item.id==="avoid"&&<span className="nav-count">!</span>}</button>;})}</nav>
      <div className="sidebar-bottom"><div className="sidebar-label">TARGET TRACKER</div><TargetTracker/><button className="nav-item" onClick={()=>setActive("settings")}><Settings2 size={17}/><span>Settings</span></button><div className="privacy-note"><span className="status-dot"/><span>PRIVATE WORKSPACE</span></div></div>
    </aside>
    {moreOpen&&<div className="mobile-more-menu">{nav.slice(4).map(item=><button key={item.id} onClick={()=>{setActive(item.id);setMoreOpen(false);}}>{item.label}</button>)}</div>}
    <main className="main-area">
      <header className="topbar"><div className="global-search"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>{if(e.key==="Enter")setActive("clients");}} placeholder="Search clients, invoices, payments…" aria-label="Global search"/><kbd><Command size={11}/> K</kbd></div>
        <div className="topbar-actions"><div className="clock"><Clock3 size={15}/><span>{now.toLocaleTimeString("en-GB",{hour12:false,timeZone:preferences.data?.time_zone})}</span></div><CalendarPopover/><FxPopover/><button className="icon-button" aria-label="Sign out" onClick={signOut}><LogOut size={17}/></button><button className="user-menu" onClick={signOut} aria-label="Sign out"><span className="avatar">KC</span><span className="user-copy"><strong>{session.data.username??"KC"}</strong><small>Owner · Sign out</small></span><ChevronDown size={14}/></button></div>
      </header>
      <section className="page-content"><div className="page-heading"><div><p className="eyebrow">FINANCIAL OPERATIONS / {active.toUpperCase()}</p><h1>{heading}</h1><p className="page-subtitle">A precise view of your client relationships and cash position.</p></div><div className="date-stamp">{now.toLocaleDateString("en-GB",{weekday:"short",day:"2-digit",month:"short",year:"numeric"}).toUpperCase()}</div></div>{page}<footer className="page-footer"><span>KC LEDGER / PRIVATE INSTANCE</span><span>DATA SOURCE: SERVER · SQLITE WAL</span></footer></section>
    </main>
    <button className="mobile-more-button" onClick={()=>setMoreOpen(!moreOpen)} aria-label={moreOpen?"Close more navigation":"More navigation"}>{moreOpen?<X size={18}/>:<Menu size={18}/>}<span>More</span></button>
  </div>;
}
