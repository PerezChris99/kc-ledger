import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api, money } from "../../api";
type EventRow = { id: number; title: string; detail: string; kind: string; category: string; polarity: number; amount: string|null; client: string|null; occurred_at: string };
export default function HistoryPage() {
  const [q,setQ] = useState("");
  const [category,setCategory] = useState("");
  const query = useQuery({ queryKey: ["events",q,category], queryFn: () => api<{items:EventRow[];total:number}>(`/api/events?q=${encodeURIComponent(q)}&category=${encodeURIComponent(category)}&limit=200`) });
  return <div className="listing-page"><div className="list-toolbar"><div className="filter-search"><Search size={15}/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search event history…" aria-label="Search event history"/></div><select value={category} onChange={e=>setCategory(e.target.value)} aria-label="Filter event category"><option value="">All categories</option>{["money","behaviour","comms","delivery","relationship"].map(v=><option key={v} value={v}>{v}</option>)}</select><span className="result-count">{query.data?.total ?? "—"} EVENTS</span></div><section className="panel table-panel"><div className="event-list">{query.data?.items.map(e=><div className="event-row" key={e.id}><span className={`event-polarity ${e.polarity<0?"negative":e.polarity>0?"positive":""}`}>{e.polarity<0?"−":e.polarity>0?"+":"·"}</span><div className="event-main"><div><strong>{e.title}</strong><span className="status-pill">{e.category}</span></div><p>{e.detail || "No detail supplied."}</p><small>{e.client ?? "System"} · {e.kind}</small></div><div className="event-meta">{e.amount && <strong className="mono">{money(e.amount)}</strong>}<time>{new Date(e.occurred_at).toLocaleString()}</time></div></div>)}{query.isLoading && <p className="empty-message">Loading audit history…</p>}{query.error && <p className="empty-message">Could not load history.</p>}{!query.isLoading&&!query.error&&!query.data?.items.length&&<p className="empty-message">No events recorded yet.</p>}</div></section></div>;
}
