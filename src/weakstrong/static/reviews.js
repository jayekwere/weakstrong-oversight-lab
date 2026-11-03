import { escapeHTML as e, percentage as pct } from "./utils.mjs";

export async function renderReviewQueue({ run, runId, api, inspect, notify }) {
  const state = await api(`/api/runs/${encodeURIComponent(runId)}/reviews`);
  const reviews = new Map(
    state.reviews.map((review) => [review.scenario_id, review]),
  );
  const target = document.getElementById("review-queue");
  const status = state.assessment;
  target.innerHTML =
    `<div class="insight">${status.manual_reviews} supplied reviews · ${status.remaining_unresolved} decisions remain unresolved. Known-label accuracy among decided/reviewed cases: ${pct(status.metrics.accuracy.value)}. No human-study claim is made.</div>` +
      state.queue
        .map(
          (item) => `<article class="scenario-card">
    <h3>${e(item.id)}</h3><p>Dependency depth ${item.difficulty} · risk ${pct(item.risk)} · ${e(item.reason)}</p>
    <button class="secondary review-inspect" data-case="${e(item.id)}">Inspect evidence ↗</button>
    <form class="manual-review" data-case="${e(item.id)}">
      <label>Decision<select name="decision"><option value="insufficient">Evidence still insufficient</option><option value="allow">Allow proposed action</option><option value="block">Block proposed action</option></select></label>
      <label>Synthetic review note<input name="note" maxlength="500" value="${e(reviews.get(item.id)?.note ?? "")}"></label>
      <button class="primary" type="submit">Save review</button>
      <span class="review-status">${reviews.has(item.id) ? "Saved: " + e(reviews.get(item.id).decision) : "Unreviewed"}</span>
    </form></article>`,
        )
        .join("") ||
    "<p>No first-trial selective deferrals in this experiment.</p>";
  target.querySelectorAll(".review-inspect").forEach((button) =>
    button.addEventListener("click", () => {
      inspect(
        run.rows.find(
          (row) =>
            row.id === button.dataset.case &&
            row.strategy === "selective" &&
            row.trial === 0,
        ),
      );
    }),
  );
  target.querySelectorAll(".manual-review").forEach((form) => {
    const existing = reviews.get(form.dataset.case);
    if (existing) form.elements.decision.value = existing.decision;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      const token = document.querySelector("[name=token]").value;
      const button = form.querySelector("button[type=submit]");
      button.disabled = true;
      try {
        await api(`/api/runs/${encodeURIComponent(runId)}/reviews`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            scenario_id: form.dataset.case,
            decision: data.get("decision"),
            note: data.get("note"),
          }),
        });
        await renderReviewQueue({ run, runId, api, inspect, notify });
        notify(
          "Review saved. Unresolved decisions remain unresolved; export supplied reviews to retain them.",
        );
      } catch (error) {
        notify(error.message, true);
        button.disabled = false;
      }
    });
  });
}

export function initReviewExport(getRunId, api, notify) {
  document
    .getElementById("review-export")
    .addEventListener("click", async () => {
      try {
        const content = await api(
          `/api/runs/${encodeURIComponent(getRunId())}/reviews`,
        );
        const url = URL.createObjectURL(
          new Blob([JSON.stringify(content, null, 2)], {
            type: "application/json",
          }),
        );
        const link = document.createElement("a");
        link.href = url;
        link.download = "manual-reviews.json";
        link.click();
        URL.revokeObjectURL(url);
      } catch (error) {
        notify(error.message, true);
      }
    });
}
