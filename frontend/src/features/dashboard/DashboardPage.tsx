import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, ArcElement, Tooltip, Legend } from "chart.js";
import { Doughnut, Line } from "react-chartjs-2";
import { AlertTriangle, ArrowUpRight, CircleDollarSign, FileClock, Users } from "lucide-react";
import { api, money } from "../../api";
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, ArcElement, Tooltip, Legend);

type Item = {kind:string;title:string;client:string;due_date:string};
type Dashboard = {
  currency:string;collected:string;outstanding:string;overdue:string;expenses:string;net_profit:string;
  client_count:number;invoice_count:number;payment_count:number;total_hours:string;
  attention:Item[];today:Item[];unconverted_currencies:string[];
  revenue_trend:{month:string;revenue:number;expenses:number}[];
  invoice_status:{status:string;count:number}[];
  aging:{bucket:string;amount:string}[];
  client_health:{id:number;name:string;company:string;status:string;score:number}[];
  concentration:{name:string;collected:string;share:number}[];
};
const bucketLabels:Record<string,string>={not_due:"Not yet due","1_30":"1–30 days","31_60":"31–60 days","61_plus":"61+ days"};
const statusLabels:Record<string,string>={draft:"Draft",sent:"Sent",partial:"Partial",paid:"Paid",written_off:"Written off",disputed:"Disputed"};

export default function DashboardPage() {
  const {data,isLoading,error}=useQuery({queryKey:["dashboard"],queryFn:()=>api<Dashboard>("/api/dashboard"),refetchInterval:30000});
  if(isLoading)return <div className="loading-panel">Loading financial records…</div>;
  if(error||!data)return <div className="error-panel">Dashboard data could not be loaded. {error instanceof Error?error.message:""}</div>;
  const token=(name:string)=>getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const palette=useMemo(()=>({
    revenue:token("--chart-revenue"),loss:token("--chart-loss"),grid:token("--chart-grid"),text:token("--text-muted"),
    secondary:token("--text-secondary"),primarySurface:token("--primary-surface"),neutral:token("--neutral-badge"),
    warning:token("--warning"),success:token("--success"),danger:token("--danger")
  }),[]);

  const kpis=[
    {label:"COLLECTED",value:money(data.collected,data.currency),note:`${data.payment_count} recorded payments`,icon:CircleDollarSign,tone:"positive"},
    {label:"OUTSTANDING",value:money(data.outstanding,data.currency),note:"Open invoice balance",icon:FileClock,tone:"neutral"},
    {label:"OVERDUE",value:money(data.overdue,data.currency),note:"Past due, unpaid",icon:AlertTriangle,tone:"negative"},
    {label:"EXPENSES",value:money(data.expenses,data.currency),note:"Recorded business costs",icon:ArrowUpRight,tone:"neutral"},
    {label:"NET CASH RESULT",value:money(data.net_profit,data.currency),note:"Collected less expenses",icon:CircleDollarSign,tone:Number(data.net_profit)>=0?"positive":"negative"},
    {label:"CLIENTS",value:String(data.client_count),note:`${data.invoice_count} invoices recorded`,icon:Users,tone:"neutral"}
  ];
  const trend=useMemo(()=>data.revenue_trend??[],[data.revenue_trend]);
  const chartData=useMemo(()=>({labels:trend.map(row=>row.month),datasets:[
    {label:"Revenue",data:trend.map(row=>row.revenue),borderColor:palette.revenue,backgroundColor:palette.primarySurface,tension:.25,pointRadius:2},
    {label:"Expenses",data:trend.map(row=>row.expenses),borderColor:palette.loss,backgroundColor:"transparent",tension:.25,pointRadius:2}
  ]}),[trend,palette]);
  const statuses=useMemo(()=>(data.invoice_status??[]).filter(row=>row.count>0),[data.invoice_status]);
  const doughnutData=useMemo(()=>({labels:statuses.map(row=>statusLabels[row.status]??row.status),datasets:[{data:statuses.map(row=>row.count),backgroundColor:[palette.neutral,palette.revenue,palette.warning,palette.success,palette.loss,palette.danger],borderWidth:0,hoverOffset:3}]}),[statuses,palette]);
  const maxAging=Math.max(1,...(data.aging??[]).map(row=>Number(row.amount)));
  const maxConcentration=Math.max(1,...(data.concentration??[]).map(row=>Number(row.collected)));
  return <div className="dashboard-page">
    <div className="kpi-grid">{kpis.map(item=>{const Icon=item.icon;return <section className="panel kpi-card" key={item.label}><div className="panel-heading"><span>{item.label}</span><Icon size={15}/></div><strong className={`kpi-value ${item.tone}`}>{item.value}</strong><p className="panel-foot">{item.note}</p></section>;})}</div>
    <div className="dashboard-grid">
      <section className="panel chart-panel span-8"><div className="panel-heading"><span>REVENUE VS EXPENSES</span><span className="panel-period">LAST 6 MONTHS · {data.currency}</span></div>{trend.some(row=>row.revenue!==0||row.expenses!==0)?<div className="chart-wrap"><Line data={chartData} options={{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:palette.secondary,boxWidth:10,usePointStyle:true,font:{size:11}}}},scales:{x:{grid:{color:palette.grid},ticks:{color:palette.text}},y:{grid:{color:gridColor},ticks:{color:textColor}}}}}/></div>:<div className="chart-empty"><span>No transaction history yet</span><small>Revenue and expense trends appear when dated records exist.</small></div>}</section>
      <section className="panel chart-panel span-4"><div className="panel-heading"><span>INVOICE STATUS</span><span className="panel-period">{data.invoice_count} INVOICES</span></div>{statuses.length?<div className="doughnut-wrap"><Doughnut data={doughnutData} options={{responsive:true,maintainAspectRatio:false,cutout:"72%",plugins:{legend:{position:"bottom",labels:{color:token("--text-secondary"),boxWidth:8,usePointStyle:true,padding:12,font:{size:11}}}}}}/><div className="doughnut-center"><strong>{data.invoice_count}</strong><small>INVOICES</small></div></div>:<div className="chart-empty"><span>No invoices recorded</span></div>}</section>
      <section className="panel span-4"><div className="panel-heading"><span>RECEIVABLES AGING</span><span className="panel-period">{data.currency}</span></div>{(data.aging??[]).map(row=><div className="insight-bar-row" key={row.bucket}><div><span>{bucketLabels[row.bucket]??row.bucket}</span><strong className="mono">{money(row.amount,data.currency)}</strong></div><div className="insight-track"><span style={{width:`${Number(row.amount)/maxAging*100}%`}}/></div></div>)}</section>
      <section className="panel span-4"><div className="panel-heading"><span>CLIENT HEALTH LEADERS</span><span className="panel-period">TOP SCORES</span></div>{data.client_health.map((client,index)=><div className="leader-row" key={client.id}><span className="rank mono">{String(index+1).padStart(2,"0")}</span><div className="leader-name"><strong>{client.name}</strong><small>{client.company||client.status}</small></div><strong className={`score-number ${client.score>=70?"success":client.score<40?"danger":""}`}>{client.score}</strong></div>)}{!data.client_health.length&&<p className="empty-message">Client scores will appear here.</p>}</section>
      <section className="panel span-4"><div className="panel-heading"><span>REVENUE CONCENTRATION</span><span className="panel-period">TOP 5 CLIENTS</span></div>{data.concentration.map((row,index)=><div className="concentration-row" key={row.name}><span className="rank mono">{String(index+1).padStart(2,"0")}</span><div className="concentration-main"><div><strong>{row.name}</strong><span className="mono">{money(row.collected,data.currency)}</span></div><div className="insight-track"><span style={{width:`${Number(row.collected)/maxConcentration*100}%`}}/></div></div><span className="share mono">{(row.share*100).toFixed(1)}%</span></div>)}{!data.concentration.length&&<p className="empty-message">Collected revenue is required to calculate concentration.</p>}</section>
      <section className="panel span-6"><div className="panel-heading"><span>TODAY / DUE SOON</span><span className="panel-period">NEXT 3 DAYS</span></div>{data.today.length?data.today.map((item,index)=><div className="attention-row" key={`${item.kind}-${index}`}><span className="attention-warning"><FileClock size={15}/></span><div><strong>{item.title}</strong><small>{item.client} · due {item.due_date}</small></div></div>):<div className="chart-empty compact"><span>No instalments due in the next three days</span></div>}</section>
      <section className="panel span-6"><div className="panel-heading"><span>NEEDS ATTENTION</span><span className="panel-period">OVERDUE</span></div>{data.attention.length?data.attention.map((item,index)=><div className="attention-row" key={`${item.kind}-${index}`}><span className="attention-warning"><AlertTriangle size={15}/></span><div><strong>{item.title}</strong><small>{item.client} · due {item.due_date}</small></div></div>):<div className="chart-empty compact"><span>No overdue invoices</span></div>}</section>
      <section className="panel span-12"><div className="panel-heading"><span>CLIENT HEALTH REGISTER</span><span className="panel-period">TOP 8 CLIENTS · LIVE SCORES</span></div><div className="table-scroll"><table><thead><tr><th>CLIENT</th><th>STATUS</th><th>HEALTH SCORE</th><th>TIER</th></tr></thead><tbody>{data.client_health.map(client=><tr key={client.id}><td><strong>{client.name}</strong><small className="table-subtitle">{client.company}</small></td><td><span className={`status-pill ${client.status}`}>{client.status}</span></td><td><span className={`score-number ${client.score>=70?"success":client.score<40?"danger":""}`}>{client.score}</span></td><td>{client.score>=85?"Champion":client.score>=70?"Reliable":client.score>=55?"Neutral":client.score>=40?"Caution":"Avoid"}</td></tr>)}</tbody></table></div></section>
    </div>
    {data.unconverted_currencies.length>0&&<p className="inline-warning">Totals exclude currencies without an available exchange rate: {data.unconverted_currencies.join(", ")}.</p>}
  </div>;
}
