"""Tests for FastAPI endpoints: response shape and status."""

from pathlib import Path
from unittest.mock import patch

import pytest

try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None

# Import app: need project root (for dashboard) and src (for mm)
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

if TestClient is not None:
    from dashboard.api.main import app
    client = TestClient(app)
else:
    app = client = None


@pytest.mark.skipif(client is None, reason="httpx not installed")
def test_health_returns_200():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


@pytest.mark.skipif(client is None, reason="httpx not installed")
def test_bracket_404_when_no_file():
    with patch("dashboard.api.main.BRACKET_PATH") as mock_path:
        mock_path.exists.return_value = False
        r = client.get("/bracket")
    assert r.status_code == 404


@pytest.mark.skipif(client is None, reason="httpx not installed")
def test_bracket_503_when_cache_missing():
    with patch("dashboard.api.main.BRACKET_PATH") as mock_path, patch("dashboard.api.main._load_bracket_cache") as mock_load:
        mock_path.exists.return_value = True
        mock_load.return_value = None
        r = client.get("/bracket")
    assert r.status_code == 503
    assert "refresh" in r.json().get("detail", "").lower()


@pytest.mark.skipif(client is None, reason="httpx not installed")
def test_history_upsets_returns_structure():
    r = client.get("/history/upsets")
    assert r.status_code == 200
    data = r.json()
    assert "matchups" in data


@pytest.mark.skipif(client is None, reason="httpx not installed")
def test_whatif_accepts_post():
    r = client.post("/whatif", json={"fixed_winners": {}})
    # May be 404 if no bracket, or 200 if bracket exists
    assert r.status_code in (200, 404, 503)


@pytest.mark.skipif(client is None, reason="httpx not installed")
def test_value_endpoint():
    r = client.get("/value?threshold=0.05")
    assert r.status_code == 200
    data = r.json()
    assert "recommendations" in data
    assert "threshold" in data
