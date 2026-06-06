from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import Weights
from src.db import all_specs, counts, init_db
from src.kimovil import load_static_specs, seed_static
from src.normalize import ComponentScores, quality_score


def main() -> int:
    init_db()
    n = seed_static()
    print(f"seeded {n} spec rows from static baseline")
    db_counts = counts()
    print("db counts:", json.dumps(db_counts, indent=2))
    print()
    weights = Weights()
    print(f"default weights (normalized): {weights.normalized()}")
    print()
    print(f"{'slug':<28} {'cpu':>6} {'bat':>6} {'cam':>6} {'dsp':>6} {'ff':>6} {'QUAL':>7}")
    print("-" * 75)
    for spec in sorted(all_specs(), key=lambda r: r["slug"]):
        d = dict(spec)
        d["geekbench5_single"] = d.get("geekbench5_single")
        d["geekbench6_single"] = d.get("geekbench6_single")
        comp = ComponentScores.from_spec(d)
        q = quality_score(comp, weights)
        print(f"{spec['slug']:<28} {comp.cpu:>6.2f} {comp.battery:>6.2f} {comp.camera:>6.2f} {comp.display:>6.2f} {comp.form_factor:>6.2f} {q:>7.2f}")
    print()
    print("Weight sensitivity test (camera-heavy):")
    cam_heavy = Weights(cpu=0.2, battery=0.2, camera=0.5, display=0.05, form_factor=0.05).normalized()
    for spec in list(all_specs())[:5]:
        comp = ComponentScores.from_spec(dict(spec))
        q = quality_score(comp, cam_heavy)
        print(f"  {spec['slug']:<28} cam-heavy QUAL={q:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
