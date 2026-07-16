"""Smoke tests for the FastAPI API layer using FastAPI's TestClient (no network).

Run with uv:
    uv run pytest tests/test_api.py -v
or the inline smoke:
    uv run python -m src.api --smoke
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is importable when run via pytest from anywhere.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from src import db
from src.api import app
from src.db import DEMO_KEY


@pytest.fixture()
def empty_db(monkeypatch, tmp_path):
    """Route all DB helpers to a fresh database for each test."""
    path = tmp_path / "deals.db"
    db.init_db(path)
    real_conn_ctx = db.conn_ctx
    monkeypatch.setattr(db, "conn_ctx", lambda: real_conn_ctx(path))
    return path


@pytest.fixture()
def seeded_db(empty_db):
    """Seed deterministic offline rows for endpoint tests that need deals."""
    from src.kimovil import load_static_specs
    from src.reddit import SAMPLE_LISTINGS

    db.upsert_specs(load_static_specs())
    for listing in SAMPLE_LISTINGS:
        db.upsert_listing(listing)
    return empty_db


@pytest.fixture()
def client(seeded_db):
    return TestClient(app)


@pytest.fixture()
def empty_client(empty_db):
    return TestClient(app)


def test_health_no_auth_not_counted(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "db" in body
    assert "freshness" in body
    assert body["version"]


def test_freshness_is_null_for_empty_db(empty_client):
    expected = {
        "listings_fetched_at": None,
        "specs_fetched_at": None,
        "fx_rates_as_of": None,
    }

    health = empty_client.get("/health")
    assert health.status_code == 200
    assert health.json()["freshness"] == expected

    deals = empty_client.get("/deals/top", headers={"X-API-Key": DEMO_KEY})
    assert deals.status_code == 200, deals.text
    assert deals.json()["count"] == 0
    assert deals.json()["freshness"] == expected


def test_freshness_reports_exact_database_maxima(client):
    expected = {
        "listings_fetched_at": "2026-03-04T05:06:07Z",
        "specs_fetched_at": "2026-02-03T04:05:06Z",
        "fx_rates_as_of": "2026-01-02",
    }
    with db.conn_ctx() as conn:
        conn.execute("UPDATE listings SET fetched_at=?", ("2026-03-01T00:00:00Z",))
        conn.execute("UPDATE specs SET fetched_at=?", ("2026-02-01T00:00:00Z",))
        conn.execute(
            "INSERT INTO listings(source, external_id, fetched_at) VALUES (?,?,?)",
            ("test", "latest-listing", expected["listings_fetched_at"]),
        )
        conn.execute(
            "INSERT INTO specs(slug, brand, model, fetched_at) VALUES (?,?,?,?)",
            ("test-phone", "Test", "Phone", expected["specs_fetched_at"]),
        )
        conn.execute(
            "INSERT INTO fx_rates(base, quote, rate, as_of) VALUES (?,?,?,?)",
            ("USD", "CAD", 1.35, "2026-01-01"),
        )
        conn.execute(
            "INSERT INTO fx_rates(base, quote, rate, as_of) VALUES (?,?,?,?)",
            ("EUR", "CAD", 1.50, expected["fx_rates_as_of"]),
        )

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["freshness"] == expected

    deals = client.get("/deals/top", headers={"X-API-Key": DEMO_KEY})
    assert deals.status_code == 200, deals.text
    assert deals.json()["freshness"] == expected


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
