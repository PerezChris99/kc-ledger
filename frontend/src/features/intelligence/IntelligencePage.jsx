import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
    Chart as ChartJS, CategoryScale, LinearScale, RadialLinearScale,
    BarElement, PointElement, LineElement, ArcElement, Filler, Tooltip, Legend
} from "chart.js";
import { Bar, Doughnut, Line, Scatter, Radar, PolarArea } from "react-chartjs-2";
import { api } from "../../api";
import BusinessCommandPage from "../business/BusinessCommandPage";

ChartJS.register(
    CategoryScale, LinearScale, RadialLinearScale, BarElement, PointElement,
    LineElement, ArcElement, Filler, Tooltip, Legend
);
const chartColors = {
    navy: "#0B1B3D", sky: "#38BDF8", yellow: "#E2AD48",
    amber: "#C78538", danger: "#CE645A", green: "#4E997C",
    gray: "#8190A6", pale: "rgba(56,189,248,.14)"
};
const common = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { boxWidth: 9, color: chartColors.navy, font: { size: 11 } } } }
};
const axis = {
    x: { ticks: { color: chartColors.gray }, grid: { color: "rgba(130,144,166,.1)" } },
    y: { ticks: { color: chartColors.gray }, grid: { color: "rgba(130,144,166,.1)" }, beginAtZero: true }
};
const barOptions = { ...common, plugins: { ...common.plugins, legend: { display: false } }, scales: axis };
const horizontalOptions = { ...barOptions, indexAxis: "y" };
const display = (value) => Number(value ?? 0).toLocaleString("en-US");
function ChartPanel({ heading, meta, children, empty = false }) {
    return <section className="panel intel-panel">
        <div className="panel-heading"><span>{heading}</span><span className="panel-period">{meta}</span></div>
        {empty ? <p className="empty-message">Record client activity to populate this visualization.</p>
            : <div className="intel-chart">{children}</div>}
    </section>;
}

export default function IntelligencePage() {
    const [tab, setTab] = useState("business");
    const [selectedId, setSelectedId] = useState(null);
    const [search, setSearch] = useState("");
    const [filter, setFilter] = useState("all");
    const [signal, setSignal] = useState("scope_creep");
    const [evidence, setEvidence] = useState("");
    const [provider, setProvider] = useState("local");
    const [approved, setApproved] = useState(false);
    const [busy, setBusy] = useState(false);
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");
    const [advice, setAdvice] = useState(null);
    const queryClient = useQueryClient();
    const overview = useQuery({
        queryKey: ["intelligence-overview"],
        queryFn: () => api("/api/intelligence/overview"), refetchInterval: 60000,
        enabled: tab !== "business"
    });
    const types = useQuery({
        queryKey: ["intelligence-signals"],
        queryFn: () => api("/api/intelligence/signal-types")
    });
    const all = overview.data?.clients ?? [];
    const actualId = selectedId ?? all[0]?.id;
    const detail = useQuery({
        queryKey: ["intelligence-client", actualId],
        queryFn: () => api(`/api/intelligence/clients/${actualId}`),
        enabled: Boolean(actualId) && tab === "client"
    });
    const data = overview.data;
    const current = detail.data;
    const filtered = all.filter(row => (
        (filter === "all" || filter === "alert" && row.open_alerts > 0 ||
         filter === "review" && row.risk_index >= 35 ||
         filter === "limited" && row.confidence === "insufficient") &&
        row.name.toLowerCase().includes(search.toLowerCase())
    ));
    async function refresh(note = "Analysis refreshed from current ledger records.") {
        setError("");
        setBusy(true);
        try {
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: ["intelligence-overview"] }),
                queryClient.invalidateQueries({ queryKey: ["intelligence-client"] }),
                queryClient.invalidateQueries({ queryKey: ["clients"] }),
                queryClient.invalidateQueries({ queryKey: ["avoid"] })
            ]);
            setMessage(note);
        } catch {
            setError("Unable to refresh the intelligence workspace.");
        } finally { setBusy(false); }
    }
    function select(id) {
        setSelectedId(id);
        setAdvice(null);
        setMessage("");
        setError("");
        setTab("client");
    }
    async function record(event) {
        event.preventDefault();
        if (!actualId) return;
        setBusy(true); setError(""); setMessage("");
        try {
            await api(`/api/intelligence/clients/${actualId}/signals`, {
                method: "POST", body: JSON.stringify({ code: signal, detail: evidence })
            });
            setEvidence("");
            await refresh("Documented signal added. Scores and historical matches recalculated.");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unable to record evidence.");
        } finally { setBusy(false); }
    }
    async function review(id, status) {
        setError(""); setBusy(true);
        try {
            await api(`/api/intelligence/alerts/${id}/review`, {
                method: "POST", body: JSON.stringify({ status })
            });
            await refresh("Alert review saved.");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unable to review the alert.");
        } finally { setBusy(false); }
    }
    async function ask() {
        if (!actualId) return;
        setError(""); setMessage(""); setBusy(true); setAdvice(null);
        try {
            const answer = await api("/api/intelligence/advice", {
                method: "POST",
                body: JSON.stringify({
                    client_id: actualId, provider, share_anonymized: approved
                })
            });
            setAdvice(answer);
            await queryClient.invalidateQueries({
                queryKey: ["intelligence-client", actualId]
            });
        } catch (err) {
            setError(err instanceof Error ? err.message : "Advisory provider unavailable.");
        } finally { setBusy(false); }
    }
    if (tab === "business") {
        return <div className="intelligence-page">
          <div className="intel-tabs" role="tablist" aria-label="Intelligence workspace">
            {[
                ["business", "Business command"], ["overview", "Client portfolio"],
                ["patterns", "Pattern watch"], ["client", "Client analysis"]
            ].map(([id, label]) => <button type="button" role="tab"
                aria-selected={tab === id} className={tab === id ? "active" : ""}
                key={id} onClick={() => setTab(id)}>{label}</button>)}
          </div>
          <BusinessCommandPage/>
        </div>;
    }
    if (overview.isLoading) return <div className="loading-panel">Analyzing the complete recorded client history…</div>;
    if (overview.error || !data) return <div className="error-panel">Client intelligence is unavailable. Check the database migration and API.</div>;
    const scores = data.score_distribution ?? [];
    const risk = data.risk_distribution ?? [];
    const behaviors = data.behavior_frequency ?? [];
    const trend = data.trend ?? [];
    const matrix = data.behavior_matrix ?? { columns: [], rows: [] };
    const activeAlerts = data.alerts?.filter(row => row.status === "open") ?? [];
    const currentlyUnassessed = all.filter(c => c.confidence === "insufficient").length;
    const matrixColor = n => n > 3 ? "intel-cell-strong" : n > 1 ? "intel-cell-medium" : n > 0 ? "intel-cell-light" : "";
    return <div className="intelligence-page">
      <div className="intel-toolbar">
        <div><p className="page-subtitle">Recorded behaviour, explainable scores and historical patterns. No model is required for the core analysis.</p></div>
        <button className="small-button" type="button" onClick={() => void refresh()} disabled={busy}>Refresh evidence</button>
      </div>
      <div className="kpi-grid intel-kpis">
        <section className="panel kpi-card"><div className="panel-heading">CLIENTS ANALYZED</div><strong className="kpi-value">{display(data.client_count)}</strong><p className="panel-foot">Live client records</p></section>
        <section className="panel kpi-card"><div className="panel-heading">OPEN PATTERN ALERTS</div><strong className="kpi-value">{display(data.open_alert_count)}</strong><p className="panel-foot">Evidence-backed comparisons</p></section>
        <section className="panel kpi-card"><div className="panel-heading">REVIEW INDEX 35+</div><strong className="kpi-value">{display(all.filter(row => row.risk_index >= 35).length)}</strong><p className="panel-foot">Needs owner review</p></section>
        <section className="panel kpi-card"><div className="panel-heading">INSUFFICIENT EVIDENCE</div><strong className="kpi-value">{currentlyUnassessed}</strong><p className="panel-foot">Not enough history to conclude</p></section>
      </div>
      <div className="intel-tabs" role="tablist" aria-label="Intelligence workspace">
        {[
            ["business", "Business command"], ["overview", "Client portfolio"],
            ["patterns", "Pattern watch"], ["client", "Client analysis"]
        ].map(([id, label]) => <button
            type="button" role="tab" aria-selected={tab === id} key={id}
            className={tab === id ? "active" : ""} onClick={() => setTab(id)}
        >{label}</button>)}
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {message && <p className="form-success" role="status">{message}</p>}
      {tab === "overview" && <>
        <div className="intel-charts">
          <ChartPanel heading="CLIENT HEALTH DISTRIBUTION" meta="0–100 INDEX" empty={!all.length}>
            <Bar data={{
                labels: scores.map(row => row.bucket),
                datasets: [{ label: "Clients", data: scores.map(row => row.count),
                    backgroundColor: [chartColors.danger, chartColors.amber,
                        chartColors.yellow, chartColors.sky, chartColors.green] }]
            }} options={barOptions}/>
          </ChartPanel>
          <ChartPanel heading="RISK REVIEW BANDS" meta="DETERMINISTIC SIGNALS" empty={!all.length}>
            <Doughnut data={{
                labels: risk.map(row => row.name),
                datasets: [{ data: risk.map(row => row.count),
                    backgroundColor: [chartColors.green, chartColors.yellow, chartColors.danger],
                    borderWidth: 0 }]
            }} options={{ ...common, cutout: "65%" }}/>
          </ChartPanel>
          <ChartPanel heading="RECORDED WARNING SIGNALS" meta="FREQUENCY" empty={!behaviors.length}>
            <Bar data={{
                labels: behaviors.map(row => row.label),
                datasets: [{ data: behaviors.map(row => row.count),
                    backgroundColor: chartColors.amber }]
            }} options={horizontalOptions}/>
          </ChartPanel>
          <ChartPanel heading="HEALTH SCORE VS RISK INDEX" meta="EVIDENCE SCATTER" empty={!all.length}>
            <Scatter data={{
                datasets: [{ label: "Clients", data: data.score_risk.map(row => ({
                    x: row.score, y: row.risk, name: row.name, evidence: row.evidence
                })), backgroundColor: chartColors.sky, pointRadius: 5, pointHoverRadius: 7 }]
            }} options={{
                ...common,
                plugins: { ...common.plugins, tooltip: {
                    callbacks: { label: context => {
                        const p = context.raw;
                        return `${p.name}: health ${p.x}, risk ${p.y}, evidence ${p.evidence}`;
                    } }
                } },
                scales: { x: { ...axis.x, min: 0, max: 100,
                    title: { display: true, text: "Health score" } },
                    y: { ...axis.y, min: 0, max: 100,
                        title: { display: true, text: "Risk review index" } } }
            }}/>
          </ChartPanel>
        </div>
        <section className="panel intel-register">
          <div className="panel-heading"><span>CLIENT INTELLIGENCE REGISTER</span><span className="panel-period">FILTERABLE · LIVE</span></div>
          <div className="intel-filterbar">
            <input aria-label="Search analyzed clients" placeholder="Search clients…" value={search}
                onChange={e => setSearch(e.target.value)}/>
            <select aria-label="Filter intelligence by priority" value={filter}
                onChange={e => setFilter(e.target.value)}>
              <option value="all">All clients</option><option value="alert">Open alerts</option>
              <option value="review">Risk index 35+</option><option value="limited">Insufficient evidence</option>
            </select>
          </div>
          <div className="table-scroll"><table>
            <thead><tr><th>CLIENT</th><th>HEALTH</th><th>REVIEW INDEX</th><th>EVIDENCE</th><th>ALERTS</th><th></th></tr></thead>
            <tbody>{filtered.map(row => <tr key={row.id}>
              <td><strong>{row.name}</strong><small className="table-subtitle">{row.status}</small></td>
              <td><strong className="mono">{row.score}/100</strong></td>
              <td><strong className="mono">{row.risk_index}/100</strong></td>
              <td>{row.confidence}<small className="table-subtitle">{row.evidence_count} observations</small></td>
              <td>{row.open_alerts || "—"}</td>
              <td><button type="button" className="small-button" onClick={() => select(row.id)}>Analyze</button></td>
            </tr>)}</tbody>
          </table>{!filtered.length && <p className="empty-message">No clients match the selected filter.</p>}</div>
        </section>
      </>}
      {tab === "patterns" && <>
        <div className="intel-charts">
          <ChartPanel heading="PORTFOLIO HEALTH OVER TIME" meta="LAST 90 DAYS" empty={trend.length < 2}>
            <Line data={{
                labels: trend.map(row => row.day),
                datasets: [
                    { label: "Avg health", data: trend.map(row => row.avg_score),
                        borderColor: chartColors.sky, pointRadius: 2, tension: .2 },
                    { label: "Avg review index", data: trend.map(row => row.avg_risk),
                        borderColor: chartColors.danger, pointRadius: 2, tension: .2 }
                ]
            }} options={{ ...common, scales: { x: axis.x, y: { ...axis.y, max: 100 } } }}/>
          </ChartPanel>
          <ChartPanel heading="CLIENT STATUSES" meta="RECORDED STATUS" empty={!all.length}>
            <PolarArea data={{
                labels: data.status_distribution.map(row => row.name),
                datasets: [{ data: data.status_distribution.map(row => row.count),
                    backgroundColor: [chartColors.sky, chartColors.gray,
                        chartColors.yellow, chartColors.danger] }]
            }} options={common}/>
          </ChartPanel>
        </div>
        <section className="panel intel-register">
          <div className="panel-heading"><span>BEHAVIOUR HEATMAP</span><span className="panel-period">HIGHEST REVIEW INDEX · UP TO 20 CLIENTS</span></div>
          <p className="settings-note">Counts of documented warning events. Empty cells mean no matching evidence recorded, not proof of perfect conduct.</p>
          {matrix.columns.length ? <div className="table-scroll">
            <table className="intel-heatmap"><thead><tr><th>CLIENT</th>{matrix.columns.map(col =>
                <th key={col.code} title={col.label}>{col.label}</th>)}</tr></thead>
              <tbody>{matrix.rows.map(row => <tr key={row.id}>
                <td><button className="text-button" onClick={() => select(row.id)}>{row.name}</button></td>
                {row.counts.map((count, idx) => <td key={matrix.columns[idx].code}
                    className={matrixColor(count)} title={`${matrix.columns[idx].label}: ${count} records`}>
                    {count || "·"}</td>)}
              </tr>)}</tbody>
            </table>
          </div> : <p className="empty-message">No coded adverse events exist yet.</p>}
        </section>
        <section className="panel">
          <div className="panel-heading"><span>HISTORICAL PATTERN MATCHES</span><span className="panel-period">{activeAlerts.length} OPEN</span></div>
          {activeAlerts.length ? <div className="intel-alert-grid">
            {activeAlerts.map(row => <article className="intel-alert" key={row.id}>
              <div className="intel-alert-head"><strong>{all.find(c => c.id === row.client_id)?.name ?? "Client"} / {row.reference_client}</strong>
                <span className="mono">{row.similarity}% overlap</span></div>
              <p>{row.explanation}</p>
              <p className="settings-note">Shared: {row.shared_signals.map(s => s.label).join(" · ")}</p>
              <div className="intel-actions">
                <button type="button" className="small-button" disabled={busy} onClick={() => select(row.client_id)}>View evidence</button>
                <button type="button" className="small-button" disabled={busy} onClick={() => void review(row.id, "reviewed")}>Mark reviewed</button>
                <button type="button" className="text-button" disabled={busy} onClick={() => void review(row.id, "dismissed")}>Dismiss</button>
              </div>
            </article>)}
          </div> : <p className="empty-message">No unreviewed cross-client matches. New matches require two shared adverse behaviour types and sufficient recorded overlap.</p>}
        </section>
      </>}
      {tab === "client" && <>
        <section className="panel intel-selector">
          <div className="panel-heading"><span>CLIENT DOSSIER</span><span className="panel-period">EXPLAINABLE EVIDENCE</span></div>
          <select aria-label="Select a client for intelligence analysis" value={actualId ?? ""}
            onChange={e => select(Number(e.target.value))}>
            {all.map(row => <option key={row.id} value={row.id}>{row.name} · {row.score}/100</option>)}
          </select>
        </section>
        {!actualId ? <p className="empty-message">Create a client record to begin the intelligence history.</p>
            : detail.isLoading ? <div className="loading-panel">Assembling this client’s evidence…</div>
            : detail.error || !current ? <p className="error-panel">Could not load this client’s intelligence profile.</p>
            : <>
              <div className="intel-client-summary">
                <section className="panel"><div className="panel-heading">HEALTH SCORE</div><strong className="kpi-value">{current.score}<small>/100</small></strong><p className="panel-foot">Deterministic eight-factor score</p></section>
                <section className="panel"><div className="panel-heading">REVIEW INDEX</div><strong className="kpi-value">{current.analysis.risk_index}<small>/100</small></strong><p className="panel-foot">Not a probability</p></section>
                <section className="panel"><div className="panel-heading">EVIDENCE</div><strong className="kpi-value">{current.analysis.observations}</strong><p className="panel-foot">{current.analysis.evidence_confidence} confidence</p></section>
                <section className="panel"><div className="panel-heading">MATCHED HISTORIES</div><strong className="kpi-value">{current.alerts.filter(row => row.status === "open").length}</strong><p className="panel-foot">Awaiting owner assessment</p></section>
              </div>
              <div className="intel-charts">
                <ChartPanel heading="CLIENT SCORE AND RISK HISTORY" meta="DAILY OBSERVATIONS"
                    empty={current.history.length < 2}>
                  <Line data={{ labels: current.history.map(row => row.date),
                    datasets: [
                        { label: "Health", data: current.history.map(row => row.score),
                            borderColor: chartColors.sky, tension: .2 },
                        { label: "Review index", data: current.history.map(row => row.risk_index),
                            borderColor: chartColors.danger, tension: .2 }
                    ] }} options={{ ...common, scales: { x: axis.x, y: { ...axis.y, max: 100 } } }}/>
                </ChartPanel>
                <ChartPanel heading="WARNING EVIDENCE WEIGHTS" meta="DOCUMENTED INSTANCES"
                    empty={!current.analysis.adverse_signals.length}>
                  <Radar data={{ labels: current.analysis.adverse_signals.map(row => row.label),
                    datasets: [{ label: "Recorded incidents",
                        data: current.analysis.adverse_signals.map(row => row.count),
                        borderColor: chartColors.danger, backgroundColor: "rgba(206,100,90,.15)" }]
                  }} options={{ ...common, scales: { r: { beginAtZero: true, ticks: { stepSize: 1 } } } }}/>
                </ChartPanel>
              </div>
              <div className="intel-charts">
                <section className="panel"><div className="panel-heading"><span>CODE-BASED NEXT STEPS</span><span className="panel-period">PRIMARY ADVISOR</span></div>
                  <p>{current.recommendation.summary}</p>
                  <ol className="intel-guidance">{current.recommendation.actions.map((step, idx) =>
                    <li key={idx}>{step}</li>)}</ol>
                  <p className="settings-note">{current.recommendation.limitations}</p>
                </section>
                <section className="panel"><div className="panel-heading"><span>OBSERVED CLIENT SIGNALS</span><span className="panel-period">{current.analysis.adverse_signals.length} WARNING TYPES</span></div>
                  {current.analysis.adverse_signals.map(row =>
                    <div key={row.kind} className="intel-signal-row">
                      <span>{row.label}</span><strong className="mono">{row.count} ×</strong>
                    </div>)}
                  {current.analysis.positive_signals.map(row =>
                    <div key={row.kind} className="intel-signal-row positive"><span>{row.label}</span>
                      <strong className="mono">{row.count} ×</strong></div>)}
                  {!current.analysis.adverse_signals.length && !current.analysis.positive_signals.length &&
                      <p className="empty-message">No structured behaviour observations recorded.</p>}
                </section>
              </div>
              <div className="intel-charts">
                <section className="panel"><div className="panel-heading"><span>RECORD A FACTUAL SIGNAL</span><span className="panel-period">ADDS AN IMMUTABLE EVENT</span></div>
                  <form className="form-stack" onSubmit={record}>
                    <label>OBSERVED BEHAVIOUR
                      <select value={signal} onChange={e => setSignal(e.target.value)}>
                        {types.data?.items.map(item => <option key={item.code} value={item.code}>
                            {item.category === "positive" ? "+ " : "− "}{item.label}
                        </option>)}
                      </select>
                    </label>
                    <label>OPTIONAL EVIDENCE NOTE<textarea value={evidence}
                      onChange={e => setEvidence(e.target.value)} rows={3} maxLength={800}
                      placeholder="Describe an actual event and when it happened, not assumptions about personality."/></label>
                    <p className="settings-note">Notes remain in the local/private ledger. Only coded, anonymized counts can be sent to an external AI when you opt in.</p>
                    <button className="primary-button" disabled={busy}>{busy ? "Recording…" : "Record and recalculate"}</button>
                  </form>
                </section>
                <section className="panel"><div className="panel-heading"><span>SECOND OPINION FROM AI</span><span className="panel-period">OPTIONAL · NEVER AUTO-CHANGES RECORDS</span></div>
                  <div className="form-stack">
                    <label>ADVICE SOURCE<select value={provider}
                      onChange={e => { setProvider(e.target.value); setAdvice(null); setApproved(false); }}>
                      <option value="local">Local deterministic rules (offline)</option>
                      <option value="gemini" disabled={!current.ai.gemini}>Gemini (configured API free tier)</option>
                      <option value="grok" disabled={!current.ai.grok}>Grok (metered API only)</option>
                    </select></label>
                    {provider !== "local" && <label className="intel-consent">
                      <input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)}/>
                      Send only anonymous signal codes, counts and summary scores to {provider} for this request.
                    </label>}
                    <button className="primary-button" type="button" disabled={busy || provider !== "local" && !approved}
                      onClick={() => void ask()}>{busy ? "Analyzing…" : "Generate advisory report"}</button>
                    {!current.ai.gemini && <p className="settings-note">Gemini requires an enabled server-side API key. Core analysis works without one.</p>}
                    <p className="settings-note">Grok API calls are not guaranteed free and must be explicitly enabled by the owner.</p>
                    {advice && <div className="intel-advice-result" aria-live="polite">
                      <strong>{advice.provider === "local" ? "Local advisory" : `${advice.provider} · ${advice.model}`}</strong>
                      <p>{advice.summary ?? advice.advice?.summary}</p>
                      <ol className="intel-guidance">{(advice.actions ?? advice.advice?.actions ?? []).map((item, idx) =>
                        <li key={idx}>{item}</li>)}</ol>
                      {(advice.advice?.avoid ?? []).length > 0 && <><strong>What to avoid</strong><ul>
                        {advice.advice.avoid.map((item, idx) => <li key={idx}>{item}</li>)}
                      </ul></>}
                      <p className="settings-note">{advice.disclaimer ?? advice.advice?.uncertainty}</p>
                    </div>}
                  </div>
                </section>
              </div>
              <section className="panel"><div className="panel-heading"><span>SIMILAR HISTORICAL CLIENT PATTERNS</span><span className="panel-period">REVIEW REQUIRED</span></div>
                {current.alerts.length ? current.alerts.map(row =>
                  <div className="intel-alert" key={row.id}>
                    <div className="intel-alert-head"><strong>{row.reference_client}</strong>
                      <span className="mono">{row.similarity}% overlap · {row.status}</span></div>
                    <p>Common observed behaviours: {row.shared_signals.map(s => s.label).join(", ")}.</p>
                    <p className="settings-note">{row.explanation}</p>
                    {row.status === "open" && <div className="intel-actions">
                      <button className="small-button" disabled={busy} onClick={() => void review(row.id, "reviewed")}>Mark reviewed</button>
                      <button className="text-button" disabled={busy} onClick={() => void review(row.id, "dismissed")}>Dismiss</button>
                    </div>}
                  </div>) : <p className="empty-message">No qualifying history overlaps. Two distinct adverse behaviour types are required.</p>}
              </section>
              {current.advisories.length > 0 && <section className="panel">
                <div className="panel-heading"><span>PREVIOUS AI ADVISORIES</span><span className="panel-period">OWNER-REQUESTED ONLY</span></div>
                {current.advisories.map(item => <div className="intel-signal-row" key={item.id}>
                  <span><strong>{item.provider} · {item.model}</strong><small className="table-subtitle">{item.advice.summary}</small></span>
                  <time>{new Date(item.created_at).toLocaleDateString()}</time>
                </div>)}
              </section>}
            </>}
      </>}
      <p className="intel-methodology">{data.methodology}</p>
    </div>;
}
