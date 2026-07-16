"""Regression checks for the private-staging safety boundary."""
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_public_site_refresh_fails_closed():
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "update_site.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "disabled pending source-rights review" in result.stderr


def test_static_page_has_no_third_party_listing_links():
    page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert "Private staging only." in page
    for host in ("kijiji.ca", "reddit.com", "ebay.ca"):
        assert host not in page


def test_private_deploy_uses_loopback_and_fixture_seed():
    deploy = (ROOT / "deploy" / "vps40-deploy.sh").read_text(encoding="utf-8")
    assert 'BIND_HOST="127.0.0.1"' in deploy
    assert "StrictHostKeyChecking=yes" in deploy
    assert "src.fetch" not in deploy
