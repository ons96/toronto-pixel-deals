from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import DB_PATH, Weights
from src.db import all_listings, all_specs, counts, init_db
from src.score import build_index, rank_listings


REPO_URL = "https://github.com/ons96/toronto-pixel-deals"
PAGES_URL = "https://ons96.github.io/toronto-pixel-deals/"

DEFAULT_WEIGHTS = {"cpu": 0.4, "battery": 0.25, "camera": 0.25, "display": 0.05, "form_factor": 0.05}


def condition_badge(cond: str) -> str:
    colors = {
        "Like New": "#10b981",
        "Excellent": "#22c55e",
        "Good": "#84cc16",
        "Used": "#f59e0b",
        "Refurbished": "#3b82f6",
        "Fair": "#ef4444",
    }
    color = colors.get(cond, "#6b7280")
    return f'<span class="pill" style="background:{color}22;color:{color};border-color:{color}55">{html.escape(cond or "?")}</span>'


def source_badge(src: str) -> str:
    return f'<span class="src">{html.escape(src)}</span>'


def deal_bar(score: float, max_score: float) -> str:
    pct = max(0, min(100, (score / max_score * 100) if max_score else 0))
    color = "#10b981" if pct > 70 else "#3b82f6" if pct > 40 else "#6b7280"
    return f'<div class="bar"><div class="bar-fill" style="width:{pct:.0f}%;background:{color}"></div><span class="bar-text">{score:.1f}</span></div>'


def render_html(rows: list[dict], weights: dict, stats: dict) -> str:
    max_deal = max((r["deal_score"] for r in rows), default=1.0) or 1.0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    weights_str = ", ".join(f"{k}: {v:.0%}" for k, v in weights.items() if v > 0)

    rows_html = []
    for i, r in enumerate(rows, 1):
        model = r.get("model") or "Unknown"
        components = r.get("components") or {}
        cpu_str = ""
        if r.get("slug"):
            for spec in all_specs():
                if spec["slug"] == r["slug"]:
                    cpu_str = (spec["cpu"] or "").replace("Google ", "").replace("Snapdragon ", "SD ")
                    battery = spec["battery_mah"] or 0
                    camera = spec["camera_main_mp"] or 0
                    break
            else:
                battery = 0
                camera = 0
        else:
            battery = 0
            camera = 0
        url = html.escape(r.get("url") or "#")
        rows_html.append(f"""
        <tr>
          <td class="rank">#{i}</td>
          <td>
            <div class="phone-name">{html.escape(model)}</div>
            <div class="phone-sub">{html.escape(cpu_str)} · {battery} mAh · {camera} MP</div>
          </td>
          <td>{source_badge(r.get('source',''))}</td>
          <td>{condition_badge(r.get('condition',''))}</td>
          <td class="num">${r.get('price_cad',0):.0f}</td>
          <td class="num">${r.get('net_cost_cad',0):.0f}</td>
          <td class="num">{r.get('quality',0):.1f}</td>
          <td>{deal_bar(r.get('deal_score',0), max_deal)}</td>
          <td class="loc">{html.escape(r.get('seller_location',''))}</td>
          <td><a href="{url}" target="_blank" rel="noopener" class="link">View</a></td>
        </tr>""")
    rows_block = "\n".join(rows_html) if rows_html else '<tr><td colspan="10" class="empty">No listings yet. Run <code>uv run python -m src.fetch</code> to populate.</td></tr>'

    css = """
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:#0a0e1a;color:#e2e8f0;line-height:1.5;padding:2rem 1rem}
    .container{max-width:1400px;margin:0 auto}
    header{text-align:center;margin-bottom:2rem;padding:2rem;background:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);border-radius:12px;border:1px solid #334155}
    h1{font-size:2.5rem;background:linear-gradient(90deg,#60a5fa,#a78bfa);-webkit-background-clip:text;background-clip:text;color:transparent;margin-bottom:0.5rem}
    .subtitle{color:#94a3b8;font-size:1.1rem;margin-bottom:1rem}
    .stats{display:flex;gap:1.5rem;justify-content:center;flex-wrap:wrap;margin-top:1rem}
    .stat{background:#1e293b;padding:0.75rem 1.25rem;border-radius:8px;border:1px solid #334155}
    .stat-value{font-size:1.5rem;font-weight:700;color:#60a5fa}
    .stat-label{font-size:0.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em}
    table{width:100%;border-collapse:collapse;background:#0f172a;border-radius:8px;overflow:hidden;border:1px solid #1e293b}
    th{background:#1e293b;padding:0.75rem;text-align:left;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;color:#94a3b8;font-weight:600;border-bottom:1px solid #334155}
    td{padding:0.75rem;border-bottom:1px solid #1e293b;font-size:0.9rem}
    tr:hover td{background:#1e293b40}
    .rank{font-weight:700;color:#60a5fa;font-family:'SF Mono',Monaco,monospace;width:50px}
    .phone-name{font-weight:600;color:#f1f5f9}
    .phone-sub{font-size:0.75rem;color:#64748b;margin-top:0.15rem}
    .pill{display:inline-block;padding:0.2rem 0.6rem;border-radius:12px;font-size:0.7rem;font-weight:600;border:1px solid}
    .src{color:#94a3b8;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em}
    .num{font-family:'SF Mono',Monaco,monospace;text-align:right;white-space:nowrap}
    .bar{position:relative;background:#1e293b;border-radius:4px;height:22px;width:140px;overflow:hidden}
    .bar-fill{height:100%;border-radius:4px;transition:width 0.3s}
    .bar-text{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:0.75rem;font-weight:700;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,0.5)}
    .loc{font-size:0.8rem;color:#94a3b8}
    .link{color:#60a5fa;text-decoration:none;font-size:0.8rem}
    .link:hover{text-decoration:underline}
    .empty{text-align:center;padding:3rem;color:#64748b}
    .meta{background:#0f172a;padding:1.5rem;border-radius:8px;border:1px solid #1e293b;margin-top:2rem;display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1.5rem}
    .meta h3{font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;color:#60a5fa;margin-bottom:0.5rem}
    .meta p,.meta code{font-size:0.85rem;color:#cbd5e1}
    .meta code{background:#1e293b;padding:0.15rem 0.4rem;border-radius:3px;font-size:0.8rem}
    footer{text-align:center;margin-top:2rem;padding:1.5rem;color:#64748b;font-size:0.85rem}
    footer a{color:#60a5fa;text-decoration:none}
    footer a:hover{text-decoration:underline}
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Toronto/GTA Pixel Deal Hunter</title>
<style>{css}</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Toronto/GTA Pixel Deal Hunter</h1>
    <p class="subtitle">Used & refurbished Google Pixel (4a→9) + mid-range alternatives, ranked by quality-per-dollar in CAD</p>
    <div class="stats">
      <div class="stat"><div class="stat-value">{stats['listings']}</div><div class="stat-label">Listings</div></div>
      <div class="stat"><div class="stat-value">{stats['specs']}</div><div class="stat-label">Phone Models</div></div>
      <div class="stat"><div class="stat-value">{len(rows)}</div><div class="stat-label">Top Deals</div></div>
      <div class="stat"><div class="stat-value">{now}</div><div class="stat-label">Last Updated</div></div>
    </div>
  </header>

  <table>
    <thead>
      <tr>
        <th>#</th><th>Phone</th><th>Source</th><th>Condition</th>
        <th>Price</th><th>Net Cost</th><th>Quality</th><th>Deal Score</th>
        <th>Location</th><th></th>
      </tr>
    </thead>
    <tbody>
      {rows_block}
    </tbody>
  </table>

  <div class="meta">
    <div>
      <h3>Scoring Weights</h3>
      <p>{weights_str}</p>
      <p style="margin-top:0.5rem;color:#94a3b8;font-size:0.75rem">Adjustable via the local Flask app (<code>uv run python -m src.app</code>)</p>
    </div>
    <div>
      <h3>Deal Score Formula</h3>
      <p><code>NetCost = (Price + Ship) × 1.13</code> (Ontario HST)</p>
      <p><code>Quality = 100 × Σ(weight × normalized_spec)</code></p>
      <p><code>Deal = (Quality / NetCost) × 1000</code></p>
    </div>
    <div>
      <h3>Data Sources</h3>
      <p>eBay Browse API · Reddit JSON · Kijiji · Frankfurter FX</p>
      <p style="margin-top:0.5rem;color:#94a3b8;font-size:0.75rem">Specs baseline: curated (Paxsenix + Wikidata + GSMArena)</p>
    </div>
  </div>

  <footer>
    <p><a href="{REPO_URL}">Source code</a> · <a href="{PAGES_URL}">View this site</a> · MIT licensed</p>
    <p style="margin-top:0.5rem">Generated by <code>src/generate_report.py</code> · Refresh via <code>bash scripts/update_site.sh</code></p>
  </footer>
</div>
</body>
</html>
"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--output", type=Path, default=ROOT / "docs" / "index.html")
    p.add_argument("--weights-json", default=None)
    args = p.parse_args()

    weights = DEFAULT_WEIGHTS
    if args.weights_json:
        weights = json.loads(args.weights_json)

    rows = rank_listings(all_listings(), build_index(all_specs()), Weights(**weights), top=args.top)
    stats = counts()
    stats["updated"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(rows, weights, stats), encoding="utf-8")
    print(f"wrote {args.output} ({len(rows)} rows, {args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
