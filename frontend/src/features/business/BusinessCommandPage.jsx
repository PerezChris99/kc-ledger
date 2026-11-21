import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
    Chart as ChartJS, CategoryScale, LinearScale, BarElement, PointElement,
    LineElement, ArcElement, Tooltip, Legend
} from "chart.js";
import { Bar, Line, Doughnut } from "react-chartjs-2";
import { api, money } from "../../api";

ChartJS.register(
    CategoryScale, LinearScale, BarElement, PointElement, LineElement, ArcElement,
    Tooltip, Legend
);
const colors = {
    receipts: "#38BDF8", expenses: "#D89461", net: "#58A88B",
    concern: "#D66C65", muted: "#8393A8", navy: "#0B1B3D"
};
const chartBase = {
    responsive: true, maintainAspectRatio: false,
    plugins: {
        legend: {
            labels: { boxWidth: 10, usePointStyle: true, color: colors.navy }
        }
    },
    scales: {
        x: { grid: { display: false }, ticks: { color: colors.muted } },
        y: { beginAtZero: true, ticks: { color: colors.muted } }
    }
};
const moneyLike = (value, currency) => money(value ?? "0", currency);
const moneyInputs = [
    { value: "monthly_receipts", label: "Monthly receipts · minimum" },
    { value: "monthly_cash_result", label: "Monthly recorded cash result · minimum" },
    { value: "monthly_expenses", label: "Monthly recorded costs · maximum" },
    { value: "overdue_balance", label: "Overdue unpaid balance · maximum" },
    { value: "active_clients", label: "Number of active clients · minimum" },
    { value: "cash_per_hour", label: "Collected cash per logged hour · minimum" }
];
const kinds = [
    ["pricing", "Pricing / packaging"], ["outreach", "Outreach / pitching"],
    ["delivery", "Delivery / scope"], ["collections", "Payment terms / collections"],
    ["costs", "Cost management"], ["capacity", "Capacity / time"],
    ["other", "Other"]
];
const dateIn = (days) => {
    const value = new Date();
    value.setDate(value.getDate() + days);
    value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
    return value.toISOString().slice(0, 10);
};

function DataPanel({ title, sub, children, empty }) {
    return <section className="panel command-chart-panel">
      <div className="panel-heading"><span>{title}</span><span className="panel-period">{sub}</span></div>
      {empty ? <p className="empty-message">No recorded data for this view.</p>
          : <div className="command-chart">{children}</div>}
    </section>;
}

export default function BusinessCommandPage() {
    const [section, setSection] = useState("performance");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [scenario, setScenario] = useState(null);
    const [pricing, setPricing] = useState(0);
    const [collection, setCollection] = useState(0);
    const [cost, setCost] = useState(0);
    const [goalName, setGoalName] = useState("");
    const [goalMetric, setGoalMetric] = useState("monthly_receipts");
    const [goalTarget, setGoalTarget] = useState("");
    const [goalDate, setGoalDate] = useState(dateIn(90));
    const [goalDescription, setGoalDescription] = useState("");
    const [strategyTitle, setStrategyTitle] = useState("");
    const [strategyKind, setStrategyKind] = useState("pricing");
    const [strategyMetric, setStrategyMetric] = useState("monthly_cash_result");
    const [strategyObjective, setStrategyObjective] = useState("");
    const [strategyRationale, setStrategyRationale] = useState("");
    const [strategyExpected, setStrategyExpected] = useState("");
    const [strategyReview, setStrategyReview] = useState(dateIn(30));
    const [decisionToReview, setDecisionToReview] = useState(null);
    const [outcomeNote, setOutcomeNote] = useState("");
    const [provider, setProvider] = useState("local");
    const [consent, setConsent] = useState(false);
    const [advice, setAdvice] = useState(null);
    const [clientId, setClientId] = useState("");
    const cache = useQueryClient();
    const query = useQuery({
        queryKey: ["business-intelligence"],
        queryFn: () => api("/api/intelligence/business/overview"),
        refetchInterval: 60000
    });
    const data = query.data;
    const pitchClients = (data?.client_contribution ?? []).filter(x => !x.is_archived);
    const selectedClient = clientId || String(pitchClients[0]?.id ?? "");
    const pitch = useQuery({
        queryKey: ["business-pitch", selectedClient],
        queryFn: () => api("/api/intelligence/business/pitch/" + selectedClient),
        enabled: section === "pitches" && Boolean(selectedClient)
    });
    async function perform(action, successMessage) {
        setBusy(true);
        setError("");
        setNotice("");
        try {
            const result = await action();
            if (successMessage) {
                await cache.invalidateQueries({ queryKey: ["business-intelligence"] });
                setNotice(successMessage);
            }
            return result;
        } catch (e) {
            setError(e instanceof Error ? e.message : "Could not complete the request.");
            return null;
        } finally {
            setBusy(false);
        }
    }
    async function createGoal(e) {
        e.preventDefault();
        const result = await perform(
            () => api("/api/intelligence/business/objectives", {
                method: "POST",
                body: JSON.stringify({
                    name: goalName, metric: goalMetric, target: goalTarget,
                    due_date: goalDate, description: goalDescription
                })
            }),
            "Objective recorded. Future advice will compare results against it."
        );
        if (result) {
            setGoalName(""); setGoalTarget(""); setGoalDescription("");
        }
    }
    async function setGoalStatus(id, status) {
        await perform(
            () => api("/api/intelligence/business/objectives/" + id, {
                method: "PATCH", body: JSON.stringify({ status })
            }), "Objective status updated."
        );
    }
    async function createDecision(e) {
        e.preventDefault();
        const result = await perform(
            () => api("/api/intelligence/business/decisions", {
                method: "POST",
                body: JSON.stringify({
                    title: strategyTitle, kind: strategyKind,
                    metric: strategyMetric, objective_id: strategyObjective
                        ? Number(strategyObjective) : null,
                    rationale: strategyRationale, expected_effect: strategyExpected,
                    review_on: strategyReview
                })
            }), "Strategy logged with a baseline and review deadline."
        );
        if (result) {
            setStrategyTitle(""); setStrategyRationale(""); setStrategyExpected("");
        }
    }
    async function reviewDecision(status) {
        if (!decisionToReview) return;
        const result = await perform(
            () => api("/api/intelligence/business/decisions/" + decisionToReview.id, {
                method: "PATCH",
                body: JSON.stringify({ status, outcome_note: outcomeNote })
            }), "Your strategy review is saved; the original baseline remains intact."
        );
        if (result) { setDecisionToReview(null); setOutcomeNote(""); }
    }
    async function runScenario() {
        const params = new URLSearchParams({
            pricing_pct: String(pricing),
            collection_pct: String(collection),
            expenses_pct: String(cost)
        });
        const result = await perform(
            () => api("/api/intelligence/business/scenario?" + params.toString())
        );
        if (result) setScenario(result);
    }
    async function askAdvisor() {
        setAdvice(null);
        const result = await perform(
            () => api("/api/intelligence/business/advice", {
                method: "POST",
                body: JSON.stringify({
                    provider, share_anonymized: provider !== "local" && consent
                })
            })
        );
        if (result) setAdvice(result);
    }
    if (query.isLoading) {
        return <div className="loading-panel">Reconciling recorded business activity and strategy history…</div>;
    }
    if (query.error || !data) {
        return <div className="error-panel">Business intelligence cannot be loaded. Verify database migrations and API access.</div>;
    }
    const monthLabels = data.monthly.map(x => x.month.slice(2));
    const categoryCosts = data.expense_categories.slice(0, 8);
    const clients = data.client_contribution.slice(0, 8);
    const chartMoney = value => moneyLike(value, data.currency);
    const activeGoals = data.objectives.filter(x => x.status === "active");
    return <div className="command-page">
      <header className="command-heading">
        <div>
          <strong className="command-heading-title">Business intelligence</strong>
          <p className="page-subtitle">Your ledger, objectives and decisions—analyzed together. Rule-based first; model advice optional.</p>
        </div>
        <button type="button" className="small-button" disabled={busy}
          onClick={() => void perform(() => cache.invalidateQueries({
              queryKey: ["business-intelligence"]
          }), "Business evidence recalculated.")}>Refresh analysis</button>
      </header>
      <div className="kpi-grid command-kpis">
        {[
            ["CASH COLLECTED", chartMoney(data.metrics.collected), "Recorded receipts", "neutral"],
            ["RECORDED EXPENSES", chartMoney(data.metrics.expenses), "Costs captured in ledger", "neutral"],
            ["NET CASH RESULT", chartMoney(data.metrics.recorded_net_cash),
                "Recorded inflows minus outflows", Number(data.metrics.recorded_net_cash) < 0 ? "negative" : "positive"],
            ["OVERDUE RECEIVABLES", chartMoney(data.metrics.overdue), "Unpaid and past due", Number(data.metrics.overdue) > 0 ? "negative" : "neutral"],
            ["OUTSTANDING", chartMoney(data.metrics.outstanding), "Open non-draft invoices", "neutral"],
            ["ACTIVE CLIENTS", data.metrics.active_clients, "Current active records", "neutral"],
        ].map(([label, value, caption, tone]) =>
            <section className="panel kpi-card" key={label}>
              <div className="panel-heading"><span>{label}</span></div>
              <strong className={"kpi-value " + tone}>{value}</strong>
              <p className="panel-foot">{caption}</p>
            </section>)}
      </div>
      <p className="command-accounting-warning" role="note">
        <strong>Accounting distinction:</strong> This is recorded cash movement, <strong>not audited profit or loss</strong>. Unrecorded costs, taxes, owner pay, accruals and bank balances may change the conclusion. FX uses currently stored rates.
        {data.data_quality.missing_fx.length > 0 && <span> Missing conversions: {data.data_quality.missing_fx.join(", ")}.</span>}
      </p>
      <div className="intel-tabs" role="tablist" aria-label="Business intelligence sections">
        {[
            ["performance", "Performance & anomalies"],
            ["strategy", "Strategy & goals"],
            ["pitches", "Client approach"],
            ["advisor", "Advisor & challenge"]
        ].map(([id, label]) => <button type="button" role="tab"
            aria-selected={section === id} className={section === id ? "active" : ""}
            key={id} onClick={() => setSection(id)}>{label}</button>)}
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="form-success" role="status">{notice}</p>}
      {section === "performance" && <>
        <div className="command-graphs">
          <DataPanel title="RECEIPTS VS COSTS" sub="13 MONTHS · RECORDED CASH"
            empty={!data.monthly.some(x => x.receipt_count || x.expense_count)}>
            <Line data={{ labels: monthLabels, datasets: [
                { label: "Receipts", data: data.monthly.map(x => Number(x.receipts)),
                    borderColor: colors.receipts, tension: .2, pointRadius: 2 },
                { label: "Expenses", data: data.monthly.map(x => Number(x.expenses)),
                    borderColor: colors.expenses, tension: .2, pointRadius: 2 }
            ] }} options={chartBase}/>
          </DataPanel>
          <DataPanel title="MONTHLY NET CASH" sub="POSITIVE / NEGATIVE"
            empty={!data.monthly.some(x => x.receipt_count || x.expense_count)}>
            <Bar data={{ labels: monthLabels, datasets: [
                { label: "Net recorded cash",
                    data: data.monthly.map(x => Number(x.cash_result)),
                    backgroundColor: data.monthly.map(x =>
                        Number(x.cash_result) < 0 ? colors.concern : colors.net) }
            ] }} options={chartBase}/>
          </DataPanel>
          <DataPanel title="WHERE THE COSTS GO" sub="BY RECORDED CATEGORY" empty={!categoryCosts.length}>
            <Doughnut data={{
                labels: categoryCosts.map(x => x.category),
                datasets: [{ label: "Expenses", data: categoryCosts.map(x => Number(x.amount)),
                    backgroundColor: [colors.receipts, colors.expenses, colors.net,
                        colors.concern, "#A59BC1", "#D6BB69", "#6B9EB4", colors.muted],
                    borderWidth: 0 }]
            }} options={{ ...chartBase, cutout: "62%", scales: undefined }}/>
          </DataPanel>
          <DataPanel title="CLIENT CASH CONTRIBUTION" sub="DIRECT COSTS ONLY" empty={!clients.length}>
            <Bar data={{
                labels: clients.map(x => x.client),
                datasets: [
                    { label: "Receipts", data: clients.map(x => Number(x.receipts)),
                        backgroundColor: colors.receipts },
                    { label: "Assigned costs", data: clients.map(x => Number(x.direct_expenses)),
                        backgroundColor: colors.expenses }
                ]
            }} options={{
                ...chartBase, indexAxis: "y",
                scales: { x: { beginAtZero: true }, y: { grid: { display: false } } }
            }}/>
          </DataPanel>
          <DataPanel title="UNPAID INVOICE AGING" sub="AMOUNTS NOT CLIENT COUNTS"
            empty={!data.aging.some(x => Number(x.amount) > 0)}>
            <Bar data={{
                labels: data.aging.map(x => x.bucket.replace("_", "–")),
                datasets: [{
                    data: data.aging.map(x => Number(x.amount)),
                    backgroundColor: [colors.net, "#D8B465", colors.expenses, colors.concern]
                }]
            }} options={{ ...chartBase,
                plugins: { legend: { display: false } }, indexAxis: "y",
                scales: { x: { beginAtZero: true }, y: { grid: { display: false } } }
            }}/>
          </DataPanel>
          <DataPanel title="PROJECT ECONOMICS" sub="PROJECT CASH RECEIPTS LESS DIRECT COSTS"
            empty={!data.projects.length}>
            <Bar data={{
                labels: data.projects.slice(0, 8).map(x => x.engagement),
                datasets: [
                    { label: "Received", data: data.projects.slice(0, 8).map(x => Number(x.received)),
                        backgroundColor: colors.receipts },
                    { label: "Direct costs", data: data.projects.slice(0, 8).map(x => Number(x.direct_costs)),
                        backgroundColor: colors.expenses }
                ]
            }} options={{ ...chartBase, indexAxis: "y",
                scales: { x: { beginAtZero: true }, y: { grid: { display: false } } } }}/>
          </DataPanel>
        </div>
        <div className="command-two">
          <section className="panel">
            <div className="panel-heading"><span>DETECTED ANOMALIES</span><span className="panel-period">COMPLETED MONTHS ONLY</span></div>
            {data.anomalies.length ? data.anomalies.map(item =>
                <article key={item.id} className="command-finding">
                  <strong>{item.description}</strong><p>
                    {item.month} · {item.change_pct > 0 ? "+" : ""}{item.change_pct}% vs prior 3-month median
                  </p><small>{item.caution}</small>
                </article>) : <p className="empty-message">No statistically notable three-month deviations detected with available history.</p>}
          </section>
          <section className="panel">
            <div className="panel-heading"><span>HISTORICAL CASH SCENARIO</span><span className="panel-period">LOW CONFIDENCE</span></div>
            {data.forecast.available ? <>
              <div className="command-forecast">
                <div><small>Illustrative low</small><strong>{chartMoney(data.forecast.illustrative_low)}</strong></div>
                <div><small>Historical midpoint</small><strong>{chartMoney(data.forecast.cash_result_baseline)}</strong></div>
                <div><small>Illustrative high</small><strong>{chartMoney(data.forecast.illustrative_high)}</strong></div>
              </div>
              <p className="settings-note">{data.forecast.method} {data.forecast.warning}</p>
            </> : <p className="empty-message">{data.forecast.reason}</p>}
          </section>
        </div>
        <section className="panel">
          <div className="panel-heading"><span>CLIENT AND PROJECT ECONOMICS</span><span className="panel-period">NO LABOR / OVERHEAD ALLOCATION</span></div>
          <div className="table-scroll">
            <table><thead><tr><th>CLIENT</th><th>COLLECTED</th><th>DIRECT EXPENSES</th><th>DIRECT CONTRIBUTION</th><th>HOURS</th><th>OVERDUE</th></tr></thead>
              <tbody>{data.client_contribution.slice(0, 25).map(x =>
                <tr key={x.id}><td><strong>{x.client}</strong></td>
                  <td>{chartMoney(x.receipts)}</td><td>{chartMoney(x.direct_expenses)}</td>
                  <td className={Number(x.direct_cash_contribution) < 0 ? "negative" : ""}>
                    {chartMoney(x.direct_cash_contribution)}</td><td>{x.logged_hours}</td>
                  <td>{chartMoney(x.outstanding_overdue)}</td></tr>)}</tbody>
            </table>
          </div>
        </section>
      </>}
      {section === "strategy" && <>
        <div className="command-two">
          <section className="panel">
            <div className="panel-heading"><span>YOUR MEASURABLE GOALS</span><span className="panel-period">{activeGoals.length} ACTIVE</span></div>
            <div className="command-goals">
              {data.objectives.map(goal => <article className="command-goal" key={goal.id}>
                <div><strong>{goal.name}</strong><small>{moneyInputs.find(x => x.value === goal.metric)?.label} · due {goal.due_date}</small></div>
                <p className="mono">{goal.current ?? "FX unavailable"} / {goal.target} <small>{goal.favorable === true ? "Met now" : goal.favorable === false ? "Below target" : "Cannot evaluate"}</small></p>
                <p className="settings-note">{goal.metric_context}. Current position is not a causal evaluation.</p>
                <div className="intel-actions">{goal.status === "active" ?
                    <button type="button" className="small-button" disabled={busy}
                      onClick={() => void setGoalStatus(goal.id, "paused")}>Pause</button> :
                    <button type="button" className="small-button" disabled={busy}
                      onClick={() => void setGoalStatus(goal.id, "active")}>Reactivate</button>}
                  {goal.status !== "completed" && <button type="button" className="text-button" disabled={busy}
                    onClick={() => void setGoalStatus(goal.id, "completed")}>Mark completed</button>}
                </div>
              </article>)}
              {!data.objectives.length && <p className="empty-message">Set a measurable target so advice can challenge actions against your own priorities.</p>}
            </div>
          </section>
          <section className="panel">
            <div className="panel-heading"><span>NEW BUSINESS GOAL</span><span className="panel-period">OWNER-DEFINED</span></div>
            <form className="form-stack" onSubmit={createGoal}>
              <label>OBJECTIVE NAME<input required maxLength={140} value={goalName}
                onChange={e => setGoalName(e.target.value)} placeholder="Reduce unpaid invoices by next quarter"/></label>
              <label>MEASURABLE OUTCOME<select value={goalMetric}
                onChange={e => setGoalMetric(e.target.value)}>
                {moneyInputs.map(x => <option key={x.value} value={x.value}>{x.label}</option>)}
              </select></label>
              <div className="form-row">
                <label>TARGET VALUE<input type="number" required step=".01" value={goalTarget}
                  onChange={e => setGoalTarget(e.target.value)}/></label>
                <label>DEADLINE<input type="date" required min={dateIn(0)}
                  value={goalDate} onChange={e => setGoalDate(e.target.value)}/></label>
              </div>
              <label>OPTIONAL CONTEXT<textarea rows={2} maxLength={800}
                value={goalDescription} onChange={e => setGoalDescription(e.target.value)}
                placeholder="How will you measure success?"/></label>
              <button className="primary-button" disabled={busy}>Save business goal</button>
            </form>
          </section>
        </div>
        <div className="command-two">
          <section className="panel">
            <div className="panel-heading"><span>SCENARIO / SENSITIVITY LAB</span><span className="panel-period">NO CLAIMS OF CAUSATION</span></div>
            <div className="command-levers">
              {[
                  ["Pricing effect on receipts", pricing, setPricing, -40, 100],
                  ["Collections effect on receipts", collection, setCollection, -40, 100],
                  ["Cost adjustment", cost, setCost, -80, 100]
              ].map(([label, val, setter, low, high]) =>
                <label key={label}>{label} <strong className="mono">{val > 0 ? "+" : ""}{val}%</strong>
                  <input type="range" min={low} max={high} value={val}
                    onChange={e => { setter(Number(e.target.value)); setScenario(null); }}/>
                </label>)}
            </div>
            <button type="button" className="small-button" onClick={() => void runScenario()}
              disabled={busy}>Run scenario</button>
            {scenario && (scenario.available ? <div className="command-result">
                <p>Estimated illustrative cash result <strong className="mono">{chartMoney(scenario.scenario_cash)}</strong></p>
                <p>Difference from historical midpoint <strong className="mono">{chartMoney(scenario.difference)}</strong></p>
                <small>{scenario.warning}</small>
            </div> : <p className="inline-warning">{scenario.reason}</p>)}
          </section>
          <section className="panel">
            <div className="panel-heading"><span>LOG A STRATEGY EXPERIMENT</span><span className="panel-period">REVIEWABLE OUTCOME</span></div>
            <form className="form-stack" onSubmit={createDecision}>
              <label>STRATEGY / ACTION<input maxLength={160} required value={strategyTitle}
                placeholder="Introduce milestone deposits" onChange={e => setStrategyTitle(e.target.value)}/></label>
              <div className="form-row">
                <label>TYPE<select value={strategyKind} onChange={e => setStrategyKind(e.target.value)}>
                    {kinds.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
                </select></label>
                <label>REVIEW DATE<input type="date" required min={dateIn(0)}
                  value={strategyReview} onChange={e => setStrategyReview(e.target.value)}/></label>
              </div>
              <label>LINK TO GOAL<select value={strategyObjective}
                onChange={e => {
                    setStrategyObjective(e.target.value);
                    const goal = data.objectives.find(x => String(x.id) === e.target.value);
                    if (goal) setStrategyMetric(goal.metric);
                }}>
                <option value="">Independent experiment</option>
                {data.objectives.filter(x => x.status !== "completed").map(x =>
                    <option key={x.id} value={x.id}>{x.name}</option>)}
              </select></label>
              <label>METRIC TO TRACK<select value={strategyMetric} disabled={Boolean(strategyObjective)}
                onChange={e => setStrategyMetric(e.target.value)}>
                {moneyInputs.map(x => <option key={x.value} value={x.value}>{x.label}</option>)}
              </select></label>
              <label>WHY THIS APPROACH<textarea rows={2} value={strategyRationale}
                maxLength={900} onChange={e => setStrategyRationale(e.target.value)}/></label>
              <label>EXPECTED CHANGE<input value={strategyExpected} maxLength={280}
                onChange={e => setStrategyExpected(e.target.value)}
                placeholder="Reduce late payments, not just generate more invoices"/></label>
              <button className="primary-button" disabled={busy}>Log strategy and baseline</button>
            </form>
          </section>
        </div>
        <section className="panel">
          <div className="panel-heading"><span>WHAT YOU TRIED · WHAT CHANGED</span><span className="panel-period">NOT A CAUSAL PROOF</span></div>
          {data.decisions.length ? <div className="command-decision-grid">
            {data.decisions.slice(0, 30).map(row => <article className="command-decision" key={row.id}>
                <div className="command-decision-head"><strong>{row.title}</strong><span>{row.status}</span></div>
                <p className="settings-note">{kinds.find(x => x[0] === row.kind)?.[1]} · review {row.review_on}</p>
                <div className="command-decision-numbers"><span>Baseline <strong>{row.baseline ?? "Unknown"}</strong></span>
                  <span>Current <strong>{row.current ?? "Unavailable"}</strong></span>
                  <span>Difference <strong>{row.observed_change ?? "—"}</strong></span></div>
                {row.direction_favorable === false && <p className="inline-warning">The tracked metric moved in an unfavorable direction. Reevaluate assumptions.</p>}
                {row.review_due && <p className="inline-warning">Review due. Document evidence and next steps.</p>}
                {row.outcome_note && <p className="settings-note">Outcome: {row.outcome_note}</p>}
                <p className="settings-note">{row.caution}</p>
                {row.status !== "reviewed" && row.status !== "cancelled" &&
                    <button type="button" className="small-button" onClick={() => {
                        setDecisionToReview(row); setOutcomeNote(row.outcome_note ?? "");
                    }}>Review / close experiment</button>}
              </article>)}
          </div> : <p className="empty-message">Log a decision to begin tracking your strategy history and results.</p>}
          {decisionToReview && <div className="command-review">
            <strong>Review: {decisionToReview.title}</strong>
            <label>OUTCOME AND WHAT YOU LEARNED<textarea rows={3} maxLength={1200}
              value={outcomeNote} onChange={e => setOutcomeNote(e.target.value)}/></label>
            <div className="intel-actions">
              <button type="button" className="small-button" disabled={busy} onClick={() => void reviewDecision("reviewed")}>Save review</button>
              <button type="button" className="text-button" disabled={busy} onClick={() => void reviewDecision("cancelled")}>Cancel strategy</button>
              <button type="button" className="text-button" onClick={() => setDecisionToReview(null)}>Close</button>
            </div>
          </div>}
        </section>
      </>}
      {section === "pitches" && <div className="command-two">
        <section className="panel">
          <div className="panel-heading"><span>CLIENT PITCH STRATEGY</span><span className="panel-period">OBJECTIVE BUSINESS CONTEXT</span></div>
          <p className="settings-note">Uses your recorded delivery, outstanding balance and contracting history. Does not infer clients’ personalities or invent market research.</p>
          <label className="command-select-label">SELECT CLIENT<select value={selectedClient}
            onChange={e => setClientId(e.target.value)}>
              {pitchClients.map(x => <option key={x.id} value={x.id}>{x.client}</option>)}
            </select></label>
          {pitch.isLoading ? <div className="loading-panel">Checking recorded engagements…</div>
            : pitch.error ? <p className="error-panel">Could not load this pitch guide.</p>
            : pitch.data ? <div className="command-pitch">
              <p><strong>{pitch.data.client}</strong> · {pitch.data.recorded_engagements} engagements · {pitch.data.recorded_invoices} invoices</p>
              <strong>Recommended approach</strong>
              <ol className="intel-guidance">{pitch.data.approach.map((step, index) =>
                  <li key={index}>{step}</li>)}</ol>
              <strong>Proposal outline</strong>
              <ol className="intel-guidance">{pitch.data.pitch_outline.map((step, index) =>
                  <li key={index}>{step}</li>)}</ol>
              <p className="inline-warning">{pitch.data.avoid}</p>
            </div> : <p className="empty-message">Add a client first to prepare an evidence-aware pitch.</p>}
        </section>
        <section className="panel">
          <div className="panel-heading"><span>SELL THROUGH RESULTS</span><span className="panel-period">STRATEGY PLAYBOOK</span></div>
          <p>Without external market data, the safest initial pitch is a measurable solution, transparent scope, agreed acceptance criteria and documented payment terms.</p>
          <div className="command-finding"><strong>Discovery</strong><p>Clarify the client's actual problem, cost of delay, intended outcome and who decides.</p></div>
          <div className="command-finding"><strong>Proposal</strong><p>Show the deliverable, milestones, price options, exclusions and payment dates.</p></div>
          <div className="command-finding"><strong>Negotiation</strong><p>Trade scope or timing transparently rather than promising unrealistic outcomes.</p></div>
          <div className="command-finding"><strong>Follow-through</strong><p>Record actual conversion, payment performance and delivered value before repeating the tactic.</p></div>
        </section>
      </div>}
      {section === "advisor" && <div className="command-two">
        <section className="panel">
          <div className="panel-heading"><span>DECISION CHALLENGES AND WARNINGS</span><span className="panel-period">EVIDENCE FIRST</span></div>
          <div className="command-ranked-strategies">
            <strong>Ranked strategy experiments</strong>
            <p className="settings-note">Ranked by recorded risks, active goals and past observed changes—not invented market predictions.</p>
            {(data.strategy_paths ?? []).map(path =>
              <article className="command-finding" key={path.id}>
                <div className="command-decision-head">
                  <strong>{path.rank}. {path.strategy}</strong>
                  <span>Rule priority {path.rank_score}</span>
                </div>
                <p><strong>Why:</strong> {path.why}</p>
                <ol className="intel-guidance">{path.steps.map((step, index) =>
                  <li key={index}>{step}</li>)}</ol>
                <p className="settings-note">Reviewed prior attempts: {path.experiments_reviewed};
                  favorable observations {path.past_favorable_observations},
                  unfavorable {path.past_unfavorable_observations}.
                </p>
                <p className="inline-warning">{path.caution}</p>
              </article>)}
          </div>
          <div className="panel-heading"><span>LIVE WARNING RULES</span><span className="panel-period">{data.recommendations.length} FINDINGS</span></div>
          {data.recommendations.length ? data.recommendations.map(item =>
            <article className="command-finding" key={item.id}>
              <div className="command-decision-head"><strong>{item.title}</strong><span>{item.priority} priority</span></div>
              <p className="settings-note"><strong>Evidence:</strong> {item.evidence}</p>
              <p><strong>Do this:</strong> {item.action}</p>
              <p><strong>Avoid:</strong> {item.avoid}</p>
              <small>{item.confidence} evidence · {item.source}</small>
            </article>) :
            <p className="empty-message">No high-priority rule was triggered by the current records. This is not proof of profitability or risk-free operations.</p>}
        </section>
        <section className="panel">
          <div className="panel-heading"><span>GET A SECOND OPINION</span><span className="panel-period">RULES REMAIN PRIMARY</span></div>
          <p className="settings-note">Ask the internal advisor to challenge assumptions, or explicitly opt into a configured external model. External prompts contain aggregated ratios and coded facts only—not client names, descriptions or ledger rows.</p>
          <label>ADVISORY SOURCE<select value={provider} onChange={e => {
              setProvider(e.target.value); setConsent(false); setAdvice(null);
          }}>
            <option value="local">Internal deterministic advisor · offline</option>
            <option value="gemini" disabled={!data.provider_status.gemini}>Gemini · configured API key</option>
            <option value="grok" disabled={!data.provider_status.grok}>Grok · metered API authorization</option>
          </select></label>
          {provider !== "local" && <label className="intel-consent">
            <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)}/>
            I approve sharing anonymized business ratios and coded goal/strategy indicators for this request only.
          </label>}
          <button type="button" className="primary-button" disabled={busy || provider !== "local" && !consent}
            onClick={() => void askAdvisor()}>{busy ? "Analyzing…" : "Challenge my strategy"}</button>
          <p className="settings-note">Gemini and Grok credentials live only on the server. Grok API requests may incur charges. Google ADK is unnecessary for this read-only advisory stage.</p>
          {advice && <div className="command-advice" aria-live="polite">
            <strong>{advice.provider === "local" ? "Local business advisor" :
                advice.provider + " second opinion · " + advice.model}</strong>
            <p>{advice.summary ?? advice.advice?.summary}</p>
            <h4>Recommended actions</h4>
            <ol className="intel-guidance">{(advice.actions ?? advice.advice?.actions ?? []).map((item, idx) =>
                <li key={idx}>{item}</li>)}</ol>
            <h4>What to avoid</h4>
            <ol className="intel-guidance">{(advice.avoid ?? advice.advice?.avoid ?? []).map((item, idx) =>
                <li key={idx}>{item}</li>)}</ol>
            <p className="settings-note">{advice.disclaimer ?? advice.advice?.uncertainty ??
                "Evidence is limited and results should be checked."}</p>
          </div>}
        </section>
      </div>}
      <p className="intel-methodology">{data.methodology}</p>
    </div>;
}
