import { renderReviewQueue, initReviewExport } from "./reviews.js";
import {
  escapeHTML as e,
  title,
  percentage as pct,
  valueOf,
  filterRows,
  isError,
  paginate,
} from "./utils.mjs";
const $ = (id) => document.getElementById(id);
const kind = document.body.dataset.project;
let run = null,
  scenarios = [],
  selectedRun = "demo",
  page = 0,
  activePage = "overview",
  visibleRows = [];
const labels = {
  agent: [
    "Unauthorized actions",
    "Legitimate completion",
    "False-positive blocking",
    "Mean execution latency",
  ],
  monitor: [
    "Mean F1 score",
    "Violation recall",
    "Missed violations",
    "Review workload",
  ],
  oversight: [
    "Automatic accuracy",
    "Missed or unresolved violations",
    "Human review workload",
    "Brier score",
  ],
};
const notify = (message, error = false) => {
  $("notice").textContent = message;
  $("notice").classList.toggle("error", error);
};
async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok)
    throw new Error(
      `Request failed (${response.status}). Check the configuration and server availability.`,
    );
  return response.json();
}
function switchPage(name) {
  activePage = name;
  document
    .querySelectorAll(".page")
    .forEach((el) => el.classList.toggle("hidden", el.id !== name));
  document
    .querySelectorAll(".nav")
    .forEach((el) => el.classList.toggle("active", el.dataset.page === name));
  $("page-label").textContent = title(name);
  for (const id of ["strategy", "category"])
    $(id)
      .closest("label")
      .classList.toggle("hidden", name === "reviews");
}
function options(id, values) {
  const old = $(id).value;
  $(id).replaceChildren(
    new Option(
      "All " + (id === "strategy" ? "strategies" : "categories"),
      "all",
    ),
    ...values.map((v) => new Option(title(v), v)),
  );
  if (values.includes(old)) $(id).value = old;
}
function mean(values) {
  const good = values.filter(
    (v) => typeof v === "number" && Number.isFinite(v),
  );
  return good.length ? good.reduce((a, b) => a + b, 0) / good.length : null;
}
function bar(label, primary, secondary = null) {
  const n = Math.max(0, Math.min(1, primary ?? 0));
  return `<div class="chart-row" role="img" aria-label="${e(title(label))}: ${pct(primary)}${secondary == null ? "" : "; comparison " + pct(secondary)}"><span>${e(title(label))}</span><svg viewBox="0 0 200 20" preserveAspectRatio="none" aria-hidden="true"><rect class="track" x="0" y="2" width="200" height="16" rx="3"/><rect class="bar" x="0" y="2" width="${n * 200}" height="${secondary == null ? 16 : 7}" rx="2"/>${secondary == null ? "" : `<rect class="bar secondary-bar" x="0" y="11" width="${Math.max(0, Math.min(1, secondary)) * 200}" height="7" rx="2"/>`}</svg><strong>${pct(primary)}</strong></div>`;
}
function filtered() {
  return filterRows(run?.rows ?? [], $("strategy").value, $("category").value);
}
function render() {
  if (!run) return;
  const rows = filtered();
  const strategies = run.summary.filter(
    (s) => $("strategy").value === "all" || s.strategy === $("strategy").value,
  );
  const agent = kind === "agent";
  const vals = agent
    ? [
        mean(strategies.map((s) => valueOf(s.unauthorized_rate))),
        mean(strategies.map((s) => valueOf(s.completion_rate))),
        mean(strategies.map((s) => valueOf(s.false_positive_rate))),
        mean(strategies.map((s) => s.latency_ms)),
      ]
    : kind === "monitor"
      ? [
          mean(strategies.map((s) => s.f1)),
          mean(strategies.map((s) => s.recall)),
          mean(
            strategies.map((s) =>
              valueOf(
                s.unresolved_or_missed_violation_rate ??
                  s.missed_violation_rate,
              ),
            ),
          ),
          mean(strategies.map((s) => s.review_workload)),
        ]
      : [
          mean(strategies.map((s) => valueOf(s.accuracy))),
          mean(
            strategies.map((s) =>
              valueOf(
                s.unresolved_or_missed_violation_rate ??
                  s.missed_violation_rate,
              ),
            ),
          ),
          mean(strategies.map((s) => s.review_workload)),
          mean(strategies.map((s) => s.brier)),
        ];
  $("kpis").innerHTML = vals
    .map(
      (v, i) =>
        `<article class="kpi"><p class="kpi-label">${labels[kind][i]}</p><div class="kpi-value">${agent && i === 3 ? (v ?? 0).toFixed(2) + "<small> ms</small>" : kind === "oversight" && i === 3 ? (v ?? 0).toFixed(3) : pct(v)}</div><span class="kpi-note">${i === 0 ? "Macro mean across selected strategies" : "Selected strategy summaries · full categories"}</span></article>`,
    )
    .join("");
  $("chart-title").textContent = agent
    ? "Unauthorized action rate ↓"
    : kind === "monitor"
      ? "Precision & recall ↑"
      : "Accuracy & automatic coverage ↑";
  $("comparison").innerHTML =
    strategies
      .map((s) =>
        bar(
          s.strategy,
          agent
            ? valueOf(s.unauthorized_rate)
            : kind === "monitor"
              ? s.precision
              : valueOf(s.accuracy),
          agent ? null : kind === "monitor" ? s.recall : 1 - s.review_workload,
        ),
      )
      .join("") +
    (!agent
      ? `<div class="chart-legend"><span>${kind === "monitor" ? "Precision" : "Accuracy"}</span><span>${kind === "monitor" ? "Recall" : "Automatic coverage"}</span></div>`
      : "");
  const unique = new Set(rows.map((r) => r.id)).size;
  $("protocol").innerHTML = [
    ["Dataset split", run.config.split],
    ["Unique selected cases", unique],
    ["Repeated trials", run.config.trials],
    ["Random seed", run.config.seed],
    ["Execution mode", run.mode],
    [
      "Input / output tokens",
      `${run.rows.reduce((a, r) => a + (r.input_tokens ?? 0), 0)} / ${run.rows.reduce((a, r) => a + (r.output_tokens ?? 0), 0)}`,
    ],
    [
      "Estimated inference cost",
      `$${run.rows.reduce((a, r) => a + (r.cost_usd ?? 0), 0).toFixed(4)}`,
    ],
    [
      "Evidence / context",
      `${run.config.evidence_mode} / ${run.config.context_limit}`,
    ],
  ]
    .map(([a, b]) => `<dt>${e(a)}</dt><dd>${e(b)}</dd>`)
    .join("");
  $("insight").textContent = agent
    ? "This run tests a deliberately susceptible behavioral fixture. The enforced tool boundary is the measured intervention; this is not a frontier-model result."
    : kind === "monitor"
      ? "Context limits can hide early evidence. Compare full observations with structured extraction to inspect this tradeoff on the synthetic benchmark."
      : "Capability is measured on a separate calibration split. Deferred decisions are not counted as correct; human workload and automatic accuracy are reported separately.";
  const families = [...new Set(rows.map((r) => r.family))];
  $("categories").innerHTML =
    families
      .map((f) => {
        const g = rows.filter((r) => r.family === f);
        return `<div class="category-card">${e(title(f))}<span>${new Set(g.map((r) => r.id)).size} cases · ${g.length} observations · ${g.filter(isError).length} errors / violations</span></div>`;
      })
      .join("") || "<p>No observations match these filters.</p>";
  $("row-count").textContent = `${rows.length.toLocaleString()} observations`;
  renderScenarios();
  renderTraces();
  renderAnalysis(strategies);
  renderReviewQueue({ run, runId: selectedRun, api, inspect, notify }).catch(
    (err) => notify(err.message, true),
  );
}
function renderScenarios() {
  const query = $("scenario-search").value.toLowerCase().trim();
  const category = $("category").value;
  const list = scenarios.filter(
    (s) =>
      (category === "all" || s.family === category) &&
      (!query ||
        [s.id, s.family, s.task, s.description, s.rationale]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(query)),
  );
  $("scenario-list").innerHTML =
    list
      .map(
        (s) => `
    <article class="scenario-card"><h3>${e(s.id)}</h3>
    <span class="pill">${e(s.split)} · ${e(title(s.family))}</span>
    <p>${e(s.task ?? s.description ?? s.rationale)}</p>
    <details data-scenario="${e(s.id)}"><summary>Show synthetic data and ground truth</summary><pre></pre></details></article>
  `,
      )
      .join("") || "<p>No scenarios match this search.</p>";
  $("scenario-list")
    .querySelectorAll("details")
    .forEach((details) => {
      details.addEventListener("toggle", () => {
        if (!details.open || details.dataset.loaded) return;
        const scenario = scenarios.find(
          (s) => s.id === details.dataset.scenario,
        );
        details.querySelector("pre").textContent = JSON.stringify(
          scenario,
          null,
          2,
        );
        details.dataset.loaded = "true";
      });
    });
}

function renderTraces() {
  const outcome = $("outcome").value;
  visibleRows = filtered().filter(
    (r) =>
      outcome === "all" ||
      (outcome === "errors" && isError(r)) ||
      (outcome === "review" && r.prediction === null),
  );
  const max = Math.max(0, Math.ceil(visibleRows.length / 12) - 1);
  page = Math.min(page, max);
  $("trace-rows").innerHTML =
    paginate(visibleRows, page)
      .map(
        (r, i) =>
          `<tr><td>${e(r.id)}</td><td>${e(title(r.strategy))}</td><td>${r.trial + 1}</td><td><span class="pill ${isError(r) ? "bad" : ""}">${r.error ? "Run error" : kind === "agent" ? (r.unauthorized ? "Unauthorized action" : r.legitimate ? "Authorized task complete" : "Incomplete") : r.prediction === null ? "Human review" : isError(r) ? "Misclassified" : "Correct classification"}</span></td><td>${(r.latency_ms ?? 0).toFixed(2)} ms</td><td><button class="secondary inspect" data-index="${page * 12 + i}">Inspect ↗</button></td></tr>`,
      )
      .join("") ||
    '<tr><td colspan="6">No observations match the selected filters.</td></tr>';
  $("pagination-label").textContent =
    `Page ${page + 1} of ${max + 1} · ${visibleRows.length} observations`;
  $("previous").disabled = page === 0;
  $("next").disabled = page === max;
  document
    .querySelectorAll(".inspect")
    .forEach((b) =>
      b.addEventListener("click", () =>
        inspect(visibleRows[Number(b.dataset.index)]),
      ),
    );
}
function inspect(row) {
  $("trace-title").textContent = row.id;
  const scenario = scenarios.find((s) => s.id === row.id);
  const events =
    row.trace ??
    row.events ??
    (scenario?.observation?.facts ?? []).filter((f) =>
      (row.observed_fact_ids ?? []).includes(f.id),
    );
  const evidence = row.evidence ?? [];
  $("trace-detail").innerHTML =
    `<p>${e(title(row.strategy))} · trial ${row.trial + 1} · ${e(row.family)} · ${row.latency_ms.toFixed(2)} ms</p><div class="timeline">${events.map((ev, i) => `<div class="timeline-event ${evidence.includes(ev.id) || ev.result?.allowed === false ? "flagged" : ""}"><strong>EVENT ${i + 1}</strong><pre>${e(JSON.stringify(ev, null, 2))}</pre></div>`).join("") || "<p>No tool events recorded.</p>"}</div><details><summary>Full observation record</summary><pre>${e(JSON.stringify(row, null, 2))}</pre></details>`;
  $("trace-dialog").showModal();
}
function renderAnalysis(strategies) {
  $("analysis-content").innerHTML =
    (run.analysis.capability_calibration
      ? `<article class="panel"><p class="eyebrow">OPERATIONAL CAPABILITY</p><h2>Separate calibration split</h2>${run.analysis.capability_calibration.map((c) => bar(c.profile, c.accuracy.value)).join("")}<p>Measured binary judgment accuracy. Names and prices do not establish capability; inspect uncertainty in the recorded output.</p></article>`
      : "") +
    (run.analysis.by_difficulty
      ? `<article class="panel"><p class="eyebrow">TASK COMPLEXITY</p><h2>Accuracy by dependency depth</h2>${run.analysis.by_difficulty
          .filter(
            (d) =>
              $("strategy").value === "all" ||
              d.strategy === $("strategy").value,
          )
          .map((d) =>
            bar(`Depth ${d.difficulty} · ${d.strategy}`, d.accuracy.value),
          )
          .join("")}</article>`
      : "") +
    strategies
      .map((s) => {
        if (kind === "agent")
          return `<article class="panel"><p class="eyebrow">${e(title(s.strategy))}</p><h2>Authorization outcomes</h2>${["unauthorized_rate", "completion_rate", "bypass_rate", "false_positive_rate"].map((k) => `<p>${e(title(k))}: <strong>${pct(s[k]?.value)}</strong> · 95% CI ${pct(s[k]?.low)}–${pct(s[k]?.high)} · n=${s[k]?.n ?? 0}</p>`).join("")}<p>Provider/validation errors: ${s.errors}</p></article>`;
        return `<article class="panel"><p class="eyebrow">${e(title(s.strategy))}</p><h2>Automatic decisions</h2><div class="matrix"><div><strong>${s.tp}</strong>True positives</div><div class="negative"><strong>${s.fp}</strong>False positives</div><div class="negative"><strong>${s.fn}</strong>False negatives</div><div><strong>${s.tn}</strong>True negatives</div></div><p>Accuracy ${pct(s.accuracy.value)} · Wilson 95% CI ${pct(s.accuracy.low)}–${pct(s.accuracy.high)} · n=${s.accuracy.n}</p><p>Deferred: ${pct(s.review_workload)} · Brier: ${s.brier?.toFixed(3) ?? "N/A"}</p><h3>Confidence reliability (including raw deferred judgments)</h3>${(
          s.confidence_calibration ?? []
        )
          .filter((b) => b.n)
          .map((b) => bar(`${b.n} cases`, b.confidence, b.accuracy))
          .join(
            "",
          )}<p>ECE ${s.confidence_ece?.toFixed(3) ?? "N/A"} · missed or unresolved violations ${pct(s.unresolved_or_missed_violation_rate?.value)}</p><h3>Risk calibration</h3>${s.calibration
          .filter((b) => b.n)
          .map((b) => bar(`${b.n} cases`, b.predicted, b.observed))
          .join(
            "",
          )}<div class="chart-legend"><span>Predicted risk</span><span>Observed violation fraction</span></div></article>`;
      })
      .join("") +
    `<article class="panel"><p class="eyebrow">EXPERIMENT ANALYSIS</p><h2>Recorded research outputs</h2><pre>${e(JSON.stringify(run.analysis, null, 2))}</pre></article>`;
}
async function loadRun(id) {
  selectedRun = id;
  run = await api(`/api/runs/${encodeURIComponent(id)}`);
  options(
    "strategy",
    run.summary.map((s) => s.strategy),
  );
  options("category", [...new Set(run.rows.map((r) => r.family))]);
  $("provenance").textContent =
    `${run.mode} · ${run.analysis.unique_cases ?? new Set(run.rows.map((r) => r.id)).size} unique cases · ${run.config.trials} trials · seed ${run.config.seed}`;
  $("digest").textContent = `SHA256 ${run.dataset_sha256.slice(0, 12)}`;
  $("json-export").href =
    `/api/runs/${encodeURIComponent(id)}/export?format=json`;
  $("csv-export").href =
    `/api/runs/${encodeURIComponent(id)}/export?format=csv`;
  page = 0;
  render();
}
document
  .querySelectorAll(".nav")
  .forEach((b) =>
    b.addEventListener("click", () => switchPage(b.dataset.page)),
  );
$("theme").addEventListener("click", () => {
  const theme =
    document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem("research-theme", theme);
  } catch {}
});
try {
  const theme = localStorage.getItem("research-theme");
  if (theme === "light") document.documentElement.dataset.theme = theme;
} catch {}
$("configure").addEventListener("click", () => $("config-dialog").showModal());
$("close-config").addEventListener("click", () => $("config-dialog").close());
$("close-trace").addEventListener("click", () => $("trace-dialog").close());
$("config-help").textContent =
  kind === "agent"
    ? "This benchmark uses seed, trials and split. Context, evidence and deferral controls apply to the other research systems."
    : kind === "monitor"
      ? "Context and evidence mode change what the monitor observes. The risk threshold controls when a trace is flagged."
      : "Confidence below the selected threshold enters the manual review queue. The context control bounds observable evidence.";
if (kind === "agent")
  for (const key of ["context_limit", "evidence_mode", "threshold"])
    document
      .querySelector(`[name=${key}]`)
      .closest("label")
      .classList.add("hidden");
if (kind === "monitor")
  document
    .querySelector("[name=threshold]")
    .closest("label")
    .classList.add("hidden");
$("config-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(event.target);
  const cfg = {
    seed: Number(data.get("seed")),
    trials: Number(data.get("trials")),
    split: data.get("split"),
    context_limit: Number(data.get("context_limit")),
    evidence_mode: data.get("evidence_mode"),
    threshold: Number(data.get("threshold")),
  };
  $("run-button").disabled = true;
  $("run-button").textContent = "Running experiment…";
  try {
    const token = data.get("token");
    const result = await api("/api/runs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(cfg),
    });
    await refreshRuns(result.id);
    $("config-dialog").close();
    notify("Simulation completed. Export results to preserve this experiment.");
  } catch (err) {
    notify(err.message, true);
  } finally {
    $("run-button").disabled = false;
    $("run-button").textContent = "Execute simulation →";
  }
});
for (const id of ["strategy", "category"])
  $(id).addEventListener("change", () => {
    page = 0;
    render();
  });
$("outcome").addEventListener("change", () => {
  page = 0;
  renderTraces();
});
$("scenario-search").addEventListener("input", renderScenarios);
$("previous").addEventListener("click", () => {
  page--;
  renderTraces();
});
$("next").addEventListener("click", () => {
  page++;
  renderTraces();
});
$("run-select").addEventListener("change", () =>
  loadRun($("run-select").value).catch((err) => notify(err.message, true)),
);
async function refreshRuns(select) {
  const ids = await api("/api/runs");
  $("run-select").replaceChildren(
    ...ids.map(
      (id) => new Option(id === "demo" ? "Saved demonstration" : id, id),
    ),
  );
  if (!ids.length) {
    notify("No saved experiments. Run a simulation to populate the dashboard.");
    return;
  }
  $("run-select").value = ids.includes(select) ? select : ids[0];
  await loadRun($("run-select").value);
}
initReviewExport(() => selectedRun, api, notify);
try {
  scenarios = await api("/api/scenarios");
  await refreshRuns(selectedRun);
} catch (err) {
  notify(err.message, true);
}
