import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api, money } from "../../api";

type InvoiceRow = { id: number; number: string; title: string; client_id: number; client_name: string; amount: string; collected: string; outstanding: string; currency: string; issue_date: string; due_date: string; status: string };
export default function InvoicesPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [paying, setPaying] = useState<InvoiceRow | null>(null);
  const [amount, setAmount] = useState("");
  const [paidOn, setPaidOn] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState("");
  const queryClient = useQueryClient();
  const invoices = useQuery({ queryKey: ["invoices", q, status], queryFn: () => api<{items: InvoiceRow[]; total: number}>(`/api/invoices?q=${encodeURIComponent(q)}&status=${encodeURIComponent(status)}&limit=100`) });
  async function recordPayment(event: React.FormEvent) {
    event.preventDefault();
    if (!paying) return;
    setError("");
    try {
      await api("/api/payments", { method: "POST", body: JSON.stringify({ invoice_id: paying.id, amount, paid_on: paidOn, method: "manual" }) });
      await Promise.all([queryClient.invalidateQueries({queryKey:["invoices"]}), queryClient.invalidateQueries({queryKey:["dashboard"]}), queryClient.invalidateQueries({queryKey:["clients"]})]);
      setPaying(null); setAmount("");
    } catch (e) { setError(e instanceof Error ? e.message : "Payment failed."); }
  }
  return <div className="listing-page"><div className="list-toolbar"><div className="filter-search"><Search size={15}/><input value={q} onChange={e => setQ(e.target.value)} placeholder="Search invoices or clients…" aria-label="Search invoices"/></div><select value={status} onChange={e => setStatus(e.target.value)} aria-label="Filter by invoice status"><option value="">All statuses</option>{["draft","sent","partial","paid","written_off","disputed"].map(s => <option key={s} value={s}>{s}</option>)}</select><span className="result-count">{invoices.data?.total ?? "—"} INVOICES</span></div><section className="panel table-panel"><div className="table-scroll"><table><thead><tr><th>INVOICE</th><th>CLIENT</th><th>ISSUED</th><th>DUE</th><th>STATUS</th><th>AMOUNT</th><th>OUTSTANDING</th><th></th></tr></thead><tbody>{invoices.data?.items.map(i => <tr key={i.id}><td><strong className="mono">{i.number}</strong><small className="table-subtitle">{i.title}</small></td><td>{i.client_name}</td><td className="mono">{i.issue_date}</td><td className="mono">{i.due_date}</td><td><span className={`status-pill ${i.status}`}>{i.status}</span></td><td className="mono">{money(i.amount,i.currency)}</td><td className="mono">{money(i.outstanding,i.currency)}</td><td>{Number(i.outstanding)>0 && !["written_off"].includes(i.status) && <button className="small-button" onClick={() => {setPaying(i);setAmount(i.outstanding);setPaidOn(new Date().toISOString().slice(0,10));}}>Record payment</button>}</td></tr>)}</tbody></table>{invoices.isLoading && <p className="empty-message">Loading invoices…</p>}{invoices.error && <p className="empty-message">Could not load invoices.</p>}{!invoices.isLoading && !invoices.data?.items.length && <p className="empty-message">No invoice records yet.</p>}</div></section>{paying && <div className="modal-backdrop" role="presentation"><section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="payment-title"><div className="panel-heading"><span id="payment-title">RECORD PAYMENT · {paying.number}</span><button className="text-button" onClick={() => setPaying(null)}>Close</button></div><p className="muted">{paying.client_name} · Outstanding {money(paying.outstanding,paying.currency)}</p><form onSubmit={recordPayment} className="form-stack"><label>PAYMENT AMOUNT ({paying.currency})<input type="number" min="0.01" max={paying.outstanding} step="0.01" value={amount} onChange={e => setAmount(e.target.value)} required/></label><label>PAYMENT DATE<input type="date" value={paidOn} onChange={e => setPaidOn(e.target.value)} required/></label>{error && <p className="form-error">{error}</p>}<button className="primary-button">Save payment</button></form></section></div>}</div>;
}
