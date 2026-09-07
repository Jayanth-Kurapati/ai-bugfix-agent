"""Tests verifying sliding-window rate limiting and concurrency cap on POST /api/analyze."""

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api import routes
from backend.api.routes import InMemoryRateLimiter
from backend.main import app


def _valid_payload() -> dict:
    return {
        "mode": "snippet",
        "code": "def add(a, b):\n    return a + b\n",
        "test_type": "pytest",
        "test_content": "def test_add():\n    from snippet import add\n    assert add(1, 2) == 3\n",
    }


def test_rate_limiter_prunes_stale_records_preventing_memory_leak():
    limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=60.0)
    base_time = 1000.0

    # Add requests for 3 different IPs
    assert limiter.check_and_record("1.1.1.1", current_time=base_time)
    assert limiter.check_and_record("2.2.2.2", current_time=base_time + 10)
    assert limiter.check_and_record("3.3.3.3", current_time=base_time + 70)

    # After base_time + 70:
    # 1.1.1.1 (recorded at 1000, cutoff is 1010) must be pruned out.
    # 2.2.2.2 (recorded at 1010, cutoff is 1010) must be pruned out.
    # 3.3.3.3 (recorded at 1070) must remain.
    assert "1.1.1.1" not in limiter._records
    assert "2.2.2.2" not in limiter._records
    assert "3.3.3.3" in limiter._records
    assert len(limiter._records) == 1


def test_rate_limiter_blocks_on_sixth_request():
    limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=60.0)
    now = 1000.0
    for i in range(5):
        assert limiter.check_and_record("10.0.0.1", current_time=now + i) is True

    # 6th request within window must be rejected
    assert limiter.check_and_record("10.0.0.1", current_time=now + 5) is False

    # Different IP is not blocked
    assert limiter.check_and_record("10.0.0.2", current_time=now + 5) is True

    # After window passes, original IP is allowed again
    assert limiter.check_and_record("10.0.0.1", current_time=now + 65) is True


def test_api_rate_limit_returns_429(monkeypatch):
    from backend.agent.orchestrator import OrchestrationResult
    monkeypatch.setattr(
        routes,
        "run_analysis",
        lambda *args, **kwargs: OrchestrationResult("failed", [], None, None, None, None, 0, "fast test mock"),
    )

    with TestClient(app) as client:
        # Send 5 requests from same IP (headers can specify IP)
        headers = {"X-Forwarded-For": "192.168.1.50"}
        for i in range(5):
            resp = client.post("/api/analyze", json=_valid_payload(), headers=headers)
            assert resp.status_code == 201, f"Request {i+1} failed: {resp.text}"
            # Small yield to let background thread finish and release semaphore
            time.sleep(0.05)

        # 6th request must receive 429
        resp6 = client.post("/api/analyze", json=_valid_payload(), headers=headers)
        assert resp6.status_code == 429
        assert "Rate limit exceeded" in resp6.json()["detail"]

        # Different client IP is unaffected
        resp_other = client.post(
            "/api/analyze",
            json=_valid_payload(),
            headers={"X-Forwarded-For": "192.168.1.51"},
        )
        assert resp_other.status_code == 201



def test_api_concurrency_cap_returns_503(monkeypatch):
    # Simulate 2 in-flight analysis jobs holding the semaphore
    routes._reset_limits()

    # Acquire all 2 semaphore slots
    acquired_1 = routes._job_semaphore.acquire(blocking=False)
    acquired_2 = routes._job_semaphore.acquire(blocking=False)
    assert acquired_1 is True
    assert acquired_2 is True

    try:
        with TestClient(app) as client:
            resp = client.post("/api/analyze", json=_valid_payload())
            assert resp.status_code == 503
            assert "Server busy" in resp.json()["detail"]
    finally:
        routes._job_semaphore.release()
        routes._job_semaphore.release()

    # Once released, new requests succeed
    with TestClient(app) as client:
        resp = client.post("/api/analyze", json=_valid_payload())
        assert resp.status_code == 201
