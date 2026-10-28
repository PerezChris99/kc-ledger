import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api, money } from "../../api";

type InvoiceRow = { id: number; number: string; title: string; client_id: number; client_name: string; amount: string; collected: string; outstanding: string; currency: string; issue_date: string; due_date: string; status: string };
export default function InvoicesPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [paying, setPaying] = useState<InvoiceRow | null>(null);
  const [createOpen,setCreateOpen]=useState(false);
  const [createBusy,setCreateBusy]=useState(false);
  const [createError,setCreateError]=useState("");
  const today=new Date().toISOString().slice(0,10);
  const [draft,setDraft]=useState({client_id:"",number:"",title:"",issue_date:today,due_date:today,amount:"",currency:"USD",status:"sent"});
  const [amount, setAmount] = useState("");
  const [paidOn, setPaidOn] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState("");
  const queryClient = useQueryClient();
  const clientList=useQuery({queryKey:["clients","invoice-create"],queryFn:()=>api<{items:{id:number;name:string;company:string}[]}>("/api/clients?limit=100"),enabled:createOpen});
  const invoices = useQuery({ queryKey: ["invoices", q, status], queryFn: () => api<{items: InvoiceRow[]; total: number}>(`/api/invoices?q=${encodeURIComponent(q)}&status=${encodeURIComponent(status)}&limit=100`) });
  async function createInvoice(event:FormEvent) {
    event.preventDefault();setCreateBusy(true);setCreateError("");
    try {
      await api("/api/invoices",{method:"POST",body:JSON.stringify({...draft,client_id:Number(draft.client_id),engagement_id:null})});
      await Promise.all([queryClient.invalidateQueries({queryKey:["invoices"]}),queryClient.invalidateQueries({queryKey:["dashboard"]}),queryClient.invalidateQueries({queryKey:["clients"]})]);
      setCreateOpen(false);setDraft({client_id:"",number:"",title:"",issue_date:today,due_date:today,amount:"",currency:"USD",status:"sent"});
    } catch(e) {setCreateError(e instanceof Error?e.message:"Could not create invoice.");}
    finally {setCreateBusy(false);}
  }
  async function recordPayment(event: FormEvent) {
    event.preventDefault();
    if (!paying) return;
    setError("");
    try {
      await api("/api/payments", { method: "POST", body: JSON.stringify({ invoice_id: paying.id, amount, paid_on: paidOn, method: "manual" }) });
      await Promise.all([queryClient.invalidateQueries({queryKey:["invoices"]}), queryClient.invalidateQueries({queryKey:["dashboard"]}), queryClient.invalidateQueries({queryKey:["clients"]})]);
      setPaying(null); setAmount("");
    } catch (e) { setError(e instanceof Error ? e.message : "Payment failed."); }
  }
  return <div className="listing-page"><div className="list-toolbar"><div className="filter-search"><Search size={15}/><input value={q} onChange={e => setQ(e.target.value)} placeholder="Search invoices or clients…" aria-label="Search invoices"/></div><select value={status} onChange={e => setStatus(e.target.value)} aria-label="Filter by invoice status"><option value="">All statuses</option>{["draft","sent","partial","paid","written_off","disputed"].map(s => <option key={s} value={s}>{s}</option>)}</select><span className="result-count">{invoices.data?.total ?? "—"} INVOICES</span><button className="primary-button" onClick={()=>setCreateOpen(true)}>Create invoice</button></div><section className="panel table-panel"><div className="table-scroll"><table><thead><tr><th>INVOICE</th><th>CLIENT</th><th>ISSUED</th><th>DUE</th><th>STATUS</th><th>AMOUNT</th><th>OUTSTANDING</th><th></th></tr></thead><tbody>{invoices.data?.items.map(i => <tr key={i.id}><td><strong className="mono">{i.number}</strong><small className="table-subtitle">{i.title}</small><button className="text-button" onClick={()=>window.open(`/api/invoices/${i.id}/pdf`,"_blank","noopener")}>PDF statement</button></td><td>{i.client_name}</td><td className="mono">{i.issue_date}</td><td className="mono">{i.due_date}</td><td><span className={`status-pill ${i.status}`}>{i.status}</span></td><td className="mono">{money(i.amount,i.currency)}</td><td className="mono">{money(i.outstanding,i.currency)}</td><td>{Number(i.outstanding)>0 && !["written_off"].includes(i.status) && <button className="small-button" onClick={() => {setPaying(i);setAmount(i.outstanding);setPaidOn(new Date().toISOString().slice(0,10));}}>Record payment</button>}</td></tr>)}</tbody></table>{invoices.isLoading && <p className="empty-message">Loading invoices…</p>}{invoices.error && <p className="empty-message">Could not load invoices.</p>}{!invoices.isLoading && !invoices.data?.items.length && <p className="empty-message">No invoice records yet.</p>}</div></section>{createOpen&&<div className="modal-backdrop"><section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="invoice-create-title"><div className="panel-heading"><span id="invoice-create-title">CREATE INVOICE</span><button className="text-button" onClick={()=>setCreateOpen(false)}>Close</button></div><form className="form-stack" onSubmit={createInvoice}><label>CLIENT<select value={draft.client_id} onChange={e=>setDraft({...draft,client_id:e.target.value})} required><option value="">Choose client…</option>{clientList.data?.items.map(client=><option key={client.id} value={client.id}>{client.name}{client.company? " · "+client.company:""}</option>)}</select></label><div className="form-row"><label>INVOICE NUMBER<input value={draft.number} onChange={e=>setDraft({...draft,number:e.target.value})} required maxLength={40}/></label><label>CURRENCY<input value={draft.currency} onChange={e=>setDraft({...draft,currency:e.target.value.toUpperCase().slice(0,3)})} required minLength={3} maxLength={3}/></label></div><label>TITLE<input value={draft.title} onChange={e=>setDraft({...draft,title:e.target.value})} required maxLength={200}/></label><label>AMOUNT<input type="number" min="0.01" step="0.01" value={draft.amount} onChange={e=>setDraft({...draft,amount:e.target.value})} required/></label><div className="form-row"><label>ISSUE DATE<input type="date" value={draft.issue_date} onChange={e=>setDraft({...draft,issue_date:e.target.value})} required/></label><label>DUE DATE<input type="date" min={draft.issue_date} value={draft.due_date} onChange={e=>setDraft({...draft,due_date:e.target.value})} required/></label></div><label>INITIAL STATUS<select value={draft.status} onChange={e=>setDraft({...draft,status:e.target.value})}><option value="draft">Draft</option><option value="sent">Sent</option></select></label>{createError&&<p className="form-error">{createError}</p>}{clientList.error&&<p className="form-error">Client list could not be loaded.</p>}<button className="primary-button" disabled={createBusy||!clientList.data?.items.length}>{createBusy?"SAVING…":"Create invoice"}</button></form></section></div>}{paying && <div className="modal-backdrop" role="presentation"><section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="payment-title"><div className="panel-heading"><span id="payment-title">RECORD PAYMENT · {paying.number}</span><button className="text-button" onClick={() => setPaying(null)}>Close</button></div><p className="muted">{paying.client_name} · Outstanding {money(paying.outstanding,paying.currency)}</p><form onSubmit={recordPayment} className="form-stack"><label>PAYMENT AMOUNT ({paying.currency})<input type="number" min="0.01" max={paying.outstanding} step="0.01" value={amount} onChange={e => setAmount(e.target.value)} required/></label><label>PAYMENT DATE<input type="date" value={paidOn} onChange={e => setPaidOn(e.target.value)} required/></label>{error && <p className="form-error">{error}</p>}<button className="primary-button">Save payment</button></form></section></div>}</div>;
}
