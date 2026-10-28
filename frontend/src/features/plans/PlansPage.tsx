import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, money } from "../../api";

type InstalmentRow = {id:number;seq:number;label:string;amount:string;due_date:string;grace_days:number;status:string;paid_on:string|null};
type Plan = {invoice_id:number;invoice_number:string;client_id:number;client_name:string;verdict:string;instalments:InstalmentRow[]};
type InvoiceRow = {id:number;number:string;client_name:string;amount:string;outstanding:string;currency:string;status:string};

export default function PlansPage() {
  const [createOpen,setCreateOpen]=useState(false);
  const [editingPlanId,setEditingPlanId]=useState<number|null>(null);
  const [invoiceId,setInvoiceId]=useState("");
  const [count,setCount]=useState("3");
  const [firstDue,setFirstDue]=useState(new Date(Date.now()+7*86400000).toISOString().slice(0,10));
  const [interval,setIntervalDays]=useState("30");
  const [grace,setGrace]=useState("3");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const client=useQueryClient();
  const plans=useQuery({queryKey:["plans"],queryFn:()=>api<{items:Plan[]}>("/api/plans")});
  const invoices=useQuery({queryKey:["invoices","plan-create"],queryFn:()=>api<{items:InvoiceRow[]}>("/api/invoices?limit=100"),enabled:createOpen});
  const eligible=(invoices.data?.items??[]).filter(inv=>Number(inv.outstanding)>0&&!["written_off","paid"].includes(inv.status)&&!(plans.data?.items??[]).some(p=>p.invoice_id===inv.id));
  const invoiceChoices=editingPlanId!==null?(invoices.data?.items??[]).filter(inv=>inv.id===editingPlanId):eligible;
  function openPlanEditor(plan:Plan) {
    setEditingPlanId(plan.invoice_id);setInvoiceId(String(plan.invoice_id));setCount(String(plan.instalments.length));
    setFirstDue(plan.instalments[0]?.due_date??new Date().toISOString().slice(0,10));
    const first=plan.instalments[0]?.due_date;
    const second=plan.instalments[1]?.due_date;
    setIntervalDays(String(first&&second?Math.max(1,Math.round((new Date(second+"T00:00:00").getTime()-new Date(first+"T00:00:00").getTime())/86400000)):30));
    setGrace(String(plan.instalments[0]?.grace_days??3));setError("");setCreateOpen(true);
  }
  async function createPlan(event:FormEvent) {
    event.preventDefault();setError("");setBusy(true);
    try {
      const invoice=invoiceChoices.find(item=>String(item.id)===invoiceId)??invoiceChoices[0];
      if(!invoice) throw new Error("Choose an invoice with an outstanding balance and no existing plan.");
      const totalCents=Math.round(Number(invoice.outstanding)*100);
      const parts=Math.max(1,Math.min(24,Number(count)||1));
      const base=Math.floor(totalCents/parts);
      const start=new Date(firstDue+"T00:00:00");
      const rows=Array.from({length:parts},(_,index)=>{
        const due=new Date(start);due.setDate(due.getDate()+index*Math.max(1,Number(interval)||1));
        const cents=index===parts-1?totalCents-base*(parts-1):base;
        return {seq:index+1,label:parts===1?"Full payment":`Instalment ${index+1}`,amount:(cents/100).toFixed(2),due_date:`${due.getFullYear()}-${String(due.getMonth()+1).padStart(2,"0")}-${String(due.getDate()).padStart(2,"0")}`,grace_days:Math.max(0,Math.min(60,Number(grace)||0))};
      });
      await api(editingPlanId!==null?`/api/plans/${invoice.id}`:"/api/plans",{method:editingPlanId!==null?"PATCH":"POST",body:JSON.stringify({invoice_id:invoice.id,instalments:rows})});
      await Promise.all([client.invalidateQueries({queryKey:["plans"]}),client.invalidateQueries({queryKey:["invoices"]}),client.invalidateQueries({queryKey:["dashboard"]}),client.invalidateQueries({queryKey:["clients"]})]);
      setCreateOpen(false);setInvoiceId("");setEditingPlanId(null);
    } catch(e) {setError(e instanceof Error?e.message:"Could not create plan.");}
    finally {setBusy(false);}
  }
  return <div className="plans-list"><div className="list-toolbar"><p className="page-subtitle">Five-verdict tracking for scheduled invoice payments.</p><button className="primary-button" onClick={()=>{setEditingPlanId(null);setInvoiceId("");setCreateOpen(true);}}>Create instalment plan</button></div>{plans.isLoading&&<div className="loading-panel">Loading instalment plans…</div>}{plans.error&&<div className="error-panel">Could not load instalment plans.</div>}{plans.data?.items.map(plan=><section className="panel plan-card" key={plan.invoice_id}><div className="plan-heading"><div><p className="eyebrow">{plan.invoice_number} · {plan.client_name}</p><h3>Payment schedule</h3></div><div className="plan-actions"><button className="small-button" onClick={()=>openPlanEditor(plan)}>Edit plan</button><span className={`verdict-pill ${plan.verdict}`}>{plan.verdict.replace("_"," ")}</span></div></div><div className="plan-rows">{plan.instalments.map(row=><div className="plan-row" key={row.id}><span className={`plan-state ${row.status}`}/><div className="plan-row-name"><strong>{row.label}</strong><small>Instalment {row.seq}</small></div><span className="mono">{money(row.amount)}</span><span className="mono">{row.due_date}</span><span className={`status-pill ${row.status}`}>{row.status}</span></div>)}</div></section>)}{!plans.isLoading&&!plans.error&&!plans.data?.items.length&&<div className="empty-panel"><h3>No instalment plans</h3><p>Create a schedule from an invoice with an outstanding balance.</p></div>}
    {createOpen&&<div className="modal-backdrop"><section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="plan-create-title"><div className="panel-heading"><span id="plan-create-title">{editingPlanId!==null?"EDIT PAYMENT SCHEDULE":"CREATE PAYMENT SCHEDULE"}</span><button className="text-button" onClick={()=>setCreateOpen(false)}>Close</button></div><p className="muted">The generated instalments will exactly equal the selected invoice's outstanding balance.</p><form className="form-stack" onSubmit={createPlan}><label>INVOICE<select value={invoiceId} onChange={e=>setInvoiceId(e.target.value)} required disabled={editingPlanId!==null}><option value="">Choose invoice…</option>{invoiceChoices.map(i=><option key={i.id} value={i.id}>{i.number} · {i.client_name} · {money(i.outstanding,i.currency)} outstanding</option>)}</select></label><div className="form-row"><label>NUMBER OF INSTALMENTS<input type="number" min="1" max="24" value={count} onChange={e=>setCount(e.target.value)} required/></label><label>GRACE DAYS<input type="number" min="0" max="60" value={grace} onChange={e=>setGrace(e.target.value)} required/></label></div><div className="form-row"><label>FIRST DUE DATE<input type="date" value={firstDue} onChange={e=>setFirstDue(e.target.value)} required/></label><label>INTERVAL (DAYS)<input type="number" min="1" max="365" value={interval} onChange={e=>setIntervalDays(e.target.value)} required/></label></div>{error&&<p className="form-error">{error}</p>}{invoiceChoices.length===0&&<p className="inline-warning">No eligible invoices found. Create or send an invoice first.</p>}<button className="primary-button" disabled={busy||invoiceChoices.length===0}>{busy?"SAVING PLAN…":editingPlanId!==null?"Update plan":"Create plan"}</button></form></section></div>}
  </div>;
}
