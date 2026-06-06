from __future__ import annotations

import math
from dataclasses import dataclass

from .config import BASELINES, Weights


def _norm(value: float | None, lo: float, hi: float) -> float:
    if value is None or value <= 0 or math.isnan(value):
        return 0.0
    if hi <= lo:
        return 0.0
    x = (float(value) - lo) / (hi - lo)
    return max(0.0, min(1.0, x))


def norm_antutu(v: float | None) -> float:
    return _norm(v, BASELINES.antutu_min, BASELINES.antutu_max)


def norm_geekbench_single(v: float | None, version: int = 6) -> float:
    if version >= 6:
        return _norm(v, BASELINES.geekbench6_single_min, BASELINES.geekbench6_single_max)
    return _norm(v, BASELINES.geekbench5_single_min, BASELINES.geekbench5_single_max)


def norm_battery(v: float | None) -> float:
    return _norm(v, BASELINES.battery_min, BASELINES.battery_max)


def norm_camera(v: float | None) -> float:
    return _norm(v, BASELINES.camera_main_min, BASELINES.camera_main_max)


def norm_ram(v: float | None) -> float:
    return _norm(v, BASELINES.ram_min_gb, BASELINES.ram_max_gb)


def norm_storage(v: float | None) -> float:
    return _norm(v, BASELINES.storage_min_gb, BASELINES.storage_max_gb)


def norm_refresh(v: float | None) -> float:
    return _norm(v, BASELINES.refresh_min, BASELINES.refresh_max)


def norm_weight_inverse(v: float | None) -> float:
    if v is None or v <= 0:
        return 0.0
    x = (BASELINES.weight_g_max - float(v)) / (BASELINES.weight_g_max - BASELINES.weight_g_min)
    return max(0.0, min(1.0, x))


def norm_display(v: float | None) -> float:
    if v is None or v <= 0:
        return 0.0
    return max(0.0, min(1.0, (float(v) - 5.0) / 2.5))


@dataclass
class ComponentScores:
    cpu: float
    battery: float
    camera: float
    display: float
    form_factor: float

    @classmethod
    def from_spec(cls, spec: dict) -> "ComponentScores":
        gb = None
        if spec.get("geekbench6_single"):
            gb = ("v6", spec["geekbench6_single"])
        elif spec.get("geekbench5_single"):
            gb = ("v5", spec["geekbench5_single"])
        gb_norm = norm_geekbench_single(gb[1], 6 if gb[0] == "v6" else 5) if gb else 0.0
        antutu_norm = norm_antutu(spec.get("antutu"))
        cpu = max(gb_norm, antutu_norm * 0.85) if (gb_norm or antutu_norm) else 0.0
        refresh_part = norm_refresh(spec.get("refresh_hz"))
        display = (norm_display(spec.get("display_in")) * 0.5) + (refresh_part * 0.5)
        return cls(
            cpu=round(cpu, 4),
            battery=norm_battery(spec.get("battery_mah")),
            camera=norm_camera(spec.get("camera_main_mp")),
            display=round(display, 4),
            form_factor=norm_weight_inverse(spec.get("weight_g")),
        )


def quality_score(components: ComponentScores, weights: Weights) -> float:
    w = weights.normalized()
    s = (
        w.cpu * components.cpu
        + w.battery * components.battery
        + w.camera * components.camera
        + w.display * components.display
        + w.form_factor * components.form_factor
    )
    return round(s * 100.0, 2)
