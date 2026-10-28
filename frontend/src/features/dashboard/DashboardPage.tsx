import { useQuery } from "@tanstack/react-query";
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend } from "chart.js";
import { Line } from "react-chartjs-2";
import { AlertTriangle, ArrowUpRight, CircleDollarSign, FileClock, Users } from "lucide-react";
import { api, money } from "../../api";
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

type Dashboard = { currency: string; collected: string; outstanding: string; overdue: string; expenses: string; net_profit: string; client_count: number; invoice_count: number; payment_count: number; attention: {kind: string; title: string; client: string; due_date: string}[]; unconverted_currencies: string[]; revenue_trend?: {month: string; revenue: number; expenses: number}[]; invoice_status?: {status: string; count: number}[] };

export default function DashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/api/dashboard"), refetchInterval: 30000 });
  if (isLoading) return <div className="loading-panel">Loading financial records…</div>;
  if (error || !data) return <div className="error-panel">Dashboard data could not be loaded. {error instanceof Error ? error.message : ""}</div>;
  const kpis = [
    { label: "COLLECTED", value: money(data.collected, data.currency), note: `${data.payment_count} recorded payments`, icon: CircleDollarSign, tone: "positive" },
    { label: "OUTSTANDING", value: money(data.outstanding, data.currency), note: "Open invoice balance", icon: FileClock, tone: "neutral" },
    { label: "OVERDUE", value: money(data.overdue, data.currency), note: "Past due, unpaid", icon: AlertTriangle, tone: "negative" },
    { label: "EXPENSES", value: money(data.expenses, data.currency), note: "Recorded business costs", icon: ArrowUpRight, tone: "neutral" },
    { label: "NET CASH RESULT", value: money(data.net_profit, data.currency), note: "Collected less expenses", icon: CircleDollarSign, tone: Number(data.net_profit) >= 0 ? "positive" : "negative" },
    { label: "CLIENTS", value: String(data.client_count), note: `${data.invoice_count} invoices recorded`, icon: Users, tone: "neutral" }
  ];
  const trend = data.revenue_trend ?? [];
  const token = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const chartRevenue = token("--chart-revenue");
  const chartLoss = token("--chart-loss");
  const chartGrid = token("--chart-grid");
  const chartText = token("--text-muted");
  const chartData = { labels: trend.map(row => row.month), datasets: [
    { label: "Revenue", data: trend.map(row => row.revenue), borderColor: chartRevenue, backgroundColor: "rgba(88,166,255,.08)", tension: .25, pointRadius: 2 },
    { label: "Expenses", data: trend.map(row => row.expenses), borderColor: chartLoss, backgroundColor: "transparent", tension: .25, pointRadius: 2 }
  ]};
  return <div className="dashboard-page">
    <div className="kpi-grid">{kpis.map(item => { const Icon = item.icon; return <section className="panel kpi-card" key={item.label}><div className="panel-heading"><span>{item.label}</span><Icon size={15}/></div><strong className={`kpi-value ${item.tone}`}>{item.value}</strong><p className="panel-foot">{item.note}</p></section>; })}</div>
    <div className="dashboard-main-grid">
      <section className="panel chart-panel"><div className="panel-heading"><span>REVENUE VS EXPENSES</span><span className="panel-period">RECENT MONTHS</span></div>{trend.length ? <div className="chart-wrap"><Line data={chartData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: token("--text-secondary"), boxWidth: 10, usePointStyle: true, font: { size: 11 } } } }, scales: { x: { grid: { color: chartGrid }, ticks: { color: chartText } }, y: { grid: { color: chartGrid }, ticks: { color: chartText } } } }} /></div> : <div className="chart-empty"><span>No transaction history yet</span><small>Revenue and expense trends appear when dated records exist.</small></div>}</section>
      <section className="panel attention-panel"><div className="panel-heading"><span>NEEDS ATTENTION</span><span className="panel-period">TODAY</span></div>{data.attention.length ? <div className="attention-list">{data.attention.map((item, index) => <div className="attention-row" key={`${item.kind}-${index}`}><span className="attention-warning"><AlertTriangle size={15}/></span><div><strong>{item.title}</strong><small>{item.client} · due {item.due_date}</small></div></div>)}</div> : <div className="chart-empty"><span>Nothing requiring attention</span><small>Overdue invoices and instalments will be listed here.</small></div>}</section>
    </div>
    {data.unconverted_currencies.length > 0 && <p className="inline-warning">Totals exclude currencies without an available exchange rate: {data.unconverted_currencies.join(", ")}.</p>}
  </div>;
}
