import { useEffect, useState } from "react";
import { Activity, Bell, CalendarDays, ChevronDown, CircleDollarSign, Clock3, Command, LayoutDashboard, Search, Settings2, ShieldAlert, Users, WalletCards } from "lucide-react";

const nav = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "clients", label: "Clients", icon: Users },
  { id: "invoices", label: "Invoices", icon: WalletCards },
  { id: "plans", label: "Instalment plans", icon: CalendarDays },
  { id: "insights", label: "Insights", icon: Activity },
  { id: "avoid", label: "Avoid", icon: ShieldAlert },
];

export default function App() {
  const [active, setActive] = useState("dashboard");
  const [now, setNow] = useState(new Date());
  const [search, setSearch] = useState("");
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return <div className="app-frame">
    <aside className="sidebar">
      <a className="wordmark" href="/" aria-label="KC Ledger home"><span className="wordmark-symbol">KC</span><span className="wordmark-copy">KC LEDGER<small>FINANCIAL OPERATIONS</small></span></a>
      <div className="sidebar-label">WORKSPACE</div>
      <nav aria-label="Main navigation">{nav.map(item => {
        const Icon = item.icon;
        return <button key={item.id} className={active === item.id ? "nav-item active" : "nav-item"} onClick={() => setActive(item.id)} aria-current={active === item.id ? "page" : undefined}><Icon size={17} strokeWidth={1.8}/><span>{item.label}</span>{item.id === "avoid" && <span className="nav-count">0</span>}</button>;
      })}</nav>
      <div className="sidebar-bottom">
        <div className="sidebar-label">TARGET TRACKER</div>
        <div className="target-empty"><span className="target-icon"><CircleDollarSign size={17}/></span><div><strong>No target set</strong><small>Set a target in settings</small></div></div>
        <button className="nav-item" onClick={() => setActive("settings")}><Settings2 size={17}/><span>Settings</span></button>
        <div className="privacy-note"><span className="status-dot"/><span>PRIVATE WORKSPACE</span></div>
      </div>
    </aside>
    <main className="main-area">
      <header className="topbar">
        <div className="global-search"><Search size={16}/><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search clients, invoices, payments…" aria-label="Global search"/><kbd><Command size={11}/> K</kbd></div>
        <div className="topbar-actions"><div className="clock"><Clock3 size={15}/><span>{now.toLocaleTimeString("en-GB", { hour12: false })}</span></div><button className="icon-button" aria-label="Calendar"><CalendarDays size={17}/></button><button className="icon-button" aria-label="Notifications"><Bell size={17}/><span className="notification-dot"/></button><button className="user-menu"><span className="avatar">KC</span><span className="user-copy"><strong>KC</strong><small>Owner</small></span><ChevronDown size={14}/></button></div>
      </header>
      <section className="page-content">
        <div className="page-heading"><div><p className="eyebrow">FINANCIAL OPERATIONS / OVERVIEW</p><h1>{nav.find(item => item.id === active)?.label ?? "Settings"}</h1><p className="page-subtitle">A precise view of your client relationships and cash position.</p></div><div className="date-stamp">{now.toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", month: "short", year: "numeric" }).toUpperCase()}</div></div>
        <div className="notice-panel"><div className="notice-icon"><Activity size={18}/></div><div><strong>Workspace initialized</strong><p>The interface is ready. Financial data will appear here once the data layer is installed.</p></div><span className="notice-state">BOOTSTRAP</span></div>
        <div className="empty-grid"><section className="panel"><div className="panel-heading"><span>COLLECTED REVENUE</span><span className="panel-period">LIFETIME</span></div><strong className="empty-value">—</strong><p className="panel-foot">Awaiting ledger records</p></section><section className="panel"><div className="panel-heading"><span>OUTSTANDING</span><span className="panel-period">OPEN BALANCE</span></div><strong className="empty-value">—</strong><p className="panel-foot">Awaiting invoice records</p></section><section className="panel"><div className="panel-heading"><span>OVERDUE</span><span className="panel-period">PAST DUE</span></div><strong className="empty-value">—</strong><p className="panel-foot">Awaiting due-date calculations</p></section><section className="panel"><div className="panel-heading"><span>CLIENTS TO REVIEW</span><span className="panel-period">RISK SIGNALS</span></div><strong className="empty-value">—</strong><p className="panel-foot">No fabricated sample figures</p></section></div>
        <div className="lower-grid"><section className="panel chart-placeholder"><div className="panel-heading"><span>REVENUE VS EXPENSES</span><span className="panel-period">LAST 90 DAYS</span></div><div className="chart-empty"><Activity size={22}/><span>Chart populates from recorded transactions</span></div></section><section className="panel"><div className="panel-heading"><span>NEEDS ATTENTION</span><span className="panel-period">TODAY</span></div><div className="attention-empty"><span className="attention-mark">—</span><div><strong>No records yet</strong><p>Overdue invoices and instalments will be prioritised here.</p></div></div></section></div>
        <footer className="page-footer"><span>KC LEDGER / PRIVATE INSTANCE</span><span>DATA SOURCE: SERVER · SQLITE WAL</span></footer>
      </section>
    </main>
  </div>;
}
