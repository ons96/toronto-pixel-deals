from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "deals.db"
STATIC_SPECS_PATH = DATA_DIR / "static_specs.json"

ONTARIO_HST = 0.13
DEFAULT_TORONTO_POSTAL = "M5V"
DEFAULT_SHIP_RADIUS_KM = 100
DEFAULT_SHIP_CAD = 20.0
DEFAULT_CURRENCY = "CAD"

KIMOVIL_PREFETCH = "https://www.kimovil.com/uploads/last_prefetch.json"
KIMOVIL_HEADERS = {
    "Accept": "application/json,text/html;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.kimovil.com/",
}

REDDIT_SUBREDDITS = ["CanadianHardwareSwap", "kijiji", "canadabay"]
REDDIT_USER_AGENT = "deal-aggregator/1.0 (Toronto GTA pixel deal hunter)"

FRANKFURTER_LATEST = "https://api.frankfurter.dev/v1/latest"
FRANKFURTER_CURRENCIES = "https://api.frankfurter.dev/v1/currencies"
FX_CACHE_HOURS = 12

EBAY_BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
EBAY_OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"

TARGET_MODELS = [
    "google-pixel-4a",
    "google-pixel-4a-5g",
    "google-pixel-5",
    "google-pixel-5a-5g",
    "google-pixel-6",
    "google-pixel-6a",
    "google-pixel-6-pro",
    "google-pixel-7",
    "google-pixel-7a",
    "google-pixel-7-pro",
    "google-pixel-8",
    "google-pixel-8a",
    "google-pixel-8-pro",
    "google-pixel-9",
    "google-pixel-9-pro",
    "google-pixel-9-pro-xl",
    "oneplus-nord-ce-3-lite",
    "oneplus-nord-2t",
    "oneplus-8t",
    "samsung-galaxy-a54",
    "samsung-galaxy-s21-fe",
    "samsung-galaxy-a34",
]


@dataclass(frozen=True)
class QualityBaselines:
    antutu_min: int = 200_000
    antutu_max: int = 2_500_000
    geekbench5_single_min: int = 300
    geekbench5_single_max: int = 2_000
    geekbench6_single_min: int = 400
    geekbench6_single_max: int = 3_000
    battery_min: int = 2_500
    battery_max: int = 6_000
    camera_main_min: int = 8
    camera_main_max: int = 200
    weight_g_min: int = 130
    weight_g_max: int = 250
    ram_min_gb: int = 4
    ram_max_gb: int = 16
    storage_min_gb: int = 64
    storage_max_gb: int = 1024
    refresh_min: int = 60
    refresh_max: int = 144


BASELINES = QualityBaselines()


@dataclass
class Weights:
    cpu: float = 0.40
    battery: float = 0.25
    camera: float = 0.25
    display: float = 0.05
    form_factor: float = 0.05

    def normalized(self) -> "Weights":
        s = self.cpu + self.battery + self.camera + self.display + self.form_factor
        if s <= 0:
            return Weights()
        return Weights(
            cpu=self.cpu / s,
            battery=self.battery / s,
            camera=self.camera / s,
            display=self.display / s,
            form_factor=self.form_factor / s,
        )


def eba_creds() -> tuple[str | None, str | None]:
    return os.environ.get("EBAY_CLIENT_ID"), os.environ.get("EBAY_CLIENT_SECRET")
