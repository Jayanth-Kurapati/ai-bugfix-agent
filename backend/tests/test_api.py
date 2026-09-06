from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import app


def test_health_reports_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_creates_queued_snippet_job() -> None:
    payload = {
        "mode": "snippet",
        "code": "def add(left, right):\n    return left + right\n",
        "test_type": "pytest",
        "test_content": "from snippet import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
    }

    with TestClient(app) as client:
        create_response = client.post("/api/analyze", json=payload)
        job_id = create_response.json()["job_id"]
        job_response = client.get(f"/api/jobs/{job_id}")

    assert create_response.status_code == 201
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["job_id"] == job_id
    assert job["status"] in {"queued", "running", "failed"}
    assert job["mode"] == "snippet"
    assert job["llm_call_count"] == 0
    assert job["iteration_count"] >= 0
    assert job["created_at"].endswith("Z")


def test_analyze_rejects_incomplete_snippet_request() -> None:
    with TestClient(app) as client:
        response = client.post("/api/analyze", json={"mode": "snippet", "code": "print('x')"})

    assert response.status_code == 422


def test_analyze_rejects_non_github_repo_url() -> None:
    payload = {"mode": "repo", "repo_url": "https://example.com/project", "test_command": "pytest"}

    with TestClient(app) as client:
        response = client.post("/api/analyze", json=payload)

    assert response.status_code == 422


def test_get_job_returns_not_found_for_unknown_id() -> None:
    with TestClient(app) as client:
        response = client.get(f"/api/jobs/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}
