"""Smoke tests for the FastAPI API layer using FastAPI's TestClient (no network).

Run with uv:
    uv run pytest tests/test_api.py -v
or the inline smoke:
    uv run python -m src.api --smoke
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure repo root is importable when run via pytest from anywhere.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.db import DEMO_KEY, init_db


@pytest.fixture(scope="module", autouse=True)
def _ready_db():
    """Make sure the schema + demo key exist and the DB has seed data."""
    init_db()
    # Seed offline sample data so /deals/top has content to rank.
    # kimovil.seed_static loads the curated static_specs.json (specs table);
    # reddit.load_sample_data loads the 3 sample listings.
    from src import kimovil, reddit
    kimovil.seed_static()
    reddit.load_sample_data()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def test_health_no_auth_not_counted(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "db" in body
    assert body["version"]


def test_deals_top_requires_auth(client):
    r = client.get("/deals/top?n=3")
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "missing_api_key"


def test_deals_top_invalid_key(client):
    r = client.get("/deals/top?n=3", headers={"X-API-Key": "no-such-key"})
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "invalid_api_key"


def test_deals_top_demo_key(client):
    r = client.get("/deals/top?n=3", headers={"X-API-Key": DEMO_KEY})
    assert r.status_code == 200, r.text
    j = r.json()
    assert "weights" in j
    assert "count" in j
    assert "deals" in j
    assert isinstance(j["deals"], list)
    assert j["count"] == len(j["deals"])
    # Weight normalization should sum to ~1.0.
    assert abs(sum(j["weights"].values()) - 1.0) < 1e-6


def test_deals_top_custom_weights(client):
    r = client.get(
        "/deals/top?n=5&cpu=0.5&battery=0.2&camera=0.3&display=0&form_factor=0",
        headers={"X-API-Key": DEMO_KEY},
    )
    assert r.status_code == 200
    j = r.json()
    assert abs(j["weights"]["cpu"] - 0.5) < 1e-6


def test_deals_top_include_unknown(client):
    r = client.get("/deals/top?n=10&include_unknown=true", headers={"X-API-Key": DEMO_KEY})
    assert r.status_code == 200


def test_specs_list(client):
    r = client.get("/specs", headers={"X-API-Key": DEMO_KEY})
    assert r.status_code == 200
    j = r.json()
    assert j["count"] == len(j["specs"])
    if j["specs"]:
        first = j["specs"][0]
        assert "slug" in first and "brand" in first and "model" in first


def test_spec_one_found(client):
    r = client.get("/specs/google-pixel-7", headers={"X-API-Key": DEMO_KEY})
    assert r.status_code == 200
    assert r.json()["slug"] == "google-pixel-7"


def test_spec_one_404(client):
    r = client.get("/specs/no-such-phone", headers={"X-API-Key": DEMO_KEY})
    assert r.status_code == 404


def test_refresh_tier_gate(client):
    # Demo key is free tier -> refresh must be 403.
    r = client.get("/deals/refresh", headers={"X-API-Key": DEMO_KEY})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "tier_required"


def test_rapidapi_secret_header_accepted(client):
    # X-RapidAPI-Proxy-Secret should also resolve the demo key.
    r = client.get("/deals/top?n=1", headers={"X-RapidAPI-Proxy-Secret": DEMO_KEY})
    assert r.status_code == 200


if __name__ == "__main__":
    # Allow `python tests/test_api.py` as a no-pytest smoke runner.
    pytest.main([__file__, "-v"])
