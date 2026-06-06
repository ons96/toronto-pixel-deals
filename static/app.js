const SLIDER_IDS = ["cpu", "battery", "camera", "display", "form_factor"];

let debounceTimer = null;

function getWeights() {
  const w = {};
  for (const id of SLIDER_IDS) {
    const el = document.getElementById("w-" + id);
    w[id] = el ? parseFloat(el.value) : 0;
  }
  return w;
}

function bindSliders() {
  for (const id of SLIDER_IDS) {
    const el = document.getElementById("w-" + id);
    const v = document.getElementById("v-" + id);
    if (!el || !v) continue;
    el.addEventListener("input", () => {
      v.textContent = parseFloat(el.value).toFixed(2);
      scheduleRerank();
    });
  }
}

function scheduleRerank() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(refresh, 120);
}

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
}

function fmt(n, d = 0) {
  if (n == null || isNaN(n)) return "-";
  return Number(n).toLocaleString("en-CA", { minimumFractionDigits: d, maximumFractionDigits: d });
}

function maxDeal(deals) {
  return deals.reduce((m, d) => Math.max(m, d.deal_score || 0), 0) || 1;
}

function renderDeals(payload) {
  const wrap = document.getElementById("table-wrap");
  wrap.classList.remove("loading");
  const deals = payload.deals || [];
  document.getElementById("rank-count").textContent = deals.length ? "(" + deals.length + ")" : "";
  document.getElementById("s-specs").textContent = payload.db.specs;
  document.getElementById("s-listings").textContent = payload.db.listings;
  document.getElementById("s-fx").textContent = payload.db.fx;
  document.getElementById("db-meta").textContent = deals.length + " deals, " + payload.db.specs + " specs, " + payload.db.listings + " listings";
  document.getElementById("last-update").textContent = new Date().toLocaleTimeString();
  if (!deals.length) {
    wrap.innerHTML = "<p style='color:var(--muted)'>No deals match current weights. Run <code>uv run python -m src.fetch --sample-reddit</code> to load sample data.</p>";
    return;
  }
  const max = maxDeal(deals);
  const rows = deals.map((d, i) => {
    const cond = (d.condition || "used").toLowerCase();
    const bar = d.deal_score > 0 ? Math.round((d.deal_score / max) * 100) : 0;
    return "<tr>" +
      "<td>" + (i + 1) + "</td>" +
      "<td>" + escapeHtml((d.brand || "") + " " + (d.model || d.slug || "")) + "</td>" +
      "<td><span class='pill " + escapeHtml(cond) + "'>" + escapeHtml(cond) + "</span></td>" +
      "<td>" + escapeHtml(d.source) + "</td>" +
      "<td class='num'>" + fmt(d.price_cad) + "</td>" +
      "<td class='num'>" + fmt(d.shipping_cad) + "</td>" +
      "<td class='num'>" + fmt(d.net_cost_cad) + "</td>" +
      "<td class='num'>" + fmt(d.quality, 1) + "</td>" +
      "<td class='num'><span class='deal-bar'><span style='width:" + bar + "%'></span></span>" + fmt(d.deal_score, 1) + "</td>" +
      "<td><a href='" + escapeHtml(d.url) + "' target='_blank' rel='noopener noreferrer'>view</a></td>" +
    "</tr>";
  }).join("");
  wrap.innerHTML = "<table><thead><tr><th>#</th><th>Model</th><th>Cond</th><th>Source</th><th class='num'>Price CAD</th><th class='num'>Ship</th><th class='num'>Net CAD</th><th class='num'>Quality</th><th class='num'>Deal</th><th>Link</th></tr></thead><tbody>" + rows + "</tbody></table>";
}

async function refresh() {
  const wrap = document.getElementById("table-wrap");
  wrap.classList.add("loading");
  wrap.textContent = "Ranking...";
  const w = getWeights();
  try {
    const resp = await fetch("/api/deals?top=20&include_unknown=1", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(w),
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    renderDeals(await resp.json());
  } catch (e) {
    wrap.classList.remove("loading");
    wrap.textContent = "Error: " + e.message;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  bindSliders();
  refresh();
});
