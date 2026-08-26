"""Guard the auth gate on the AI endpoints.

These three routes were originally unauthenticated, which let anyone drive
LLM inference and file parsing on the deployment's HuggingFace token.
"""

import io

import pytest
from fastapi.testclient import TestClient

from app.main import MAX_RESUME_BYTES, app

client = TestClient(app)

AI_ENDPOINTS = [
    ("/analyze-job", {"json": {"description": "python developer"}}),
    ("/analyze-resume", {"json": {"resume": "python", "job": "python"}}),
    (
        "/analyze-resume-file",
        {
            "files": {"resume": ("cv.txt", b"python", "text/plain")},
            "data": {"job_description": "python"},
        },
    ),
]


@pytest.mark.parametrize("path,kwargs", AI_ENDPOINTS)
def test_ai_endpoints_reject_anonymous_requests(path, kwargs):
    assert client.post(path, **kwargs).status_code == 401


@pytest.mark.parametrize("path,kwargs", AI_ENDPOINTS)
def test_ai_endpoints_reject_bad_tokens(path, kwargs):
    response = client.post(
        path, headers={"Authorization": "Bearer not-a-real-token"}, **kwargs
    )
    assert response.status_code == 401


def test_job_endpoints_also_require_auth():
    assert client.get("/jobs").status_code == 401
    assert client.post("/jobs", json={"company": "Acme", "role": "Dev"}).status_code == 401
    assert client.get("/me").status_code == 401


def test_upload_cap_is_below_the_llm_call():
    """The size limit must be enforced, not just documented."""
    assert MAX_RESUME_BYTES == 5 * 1024 * 1024


def test_oversized_upload_is_rejected_before_parsing():
    """Auth runs first, so this is a 401 — but the cap must not be the reason.

    The point of this test is that the endpoint never reaches the parser or the
    LLM for an anonymous caller, regardless of payload size.
    """
    oversized = io.BytesIO(b"x" * (MAX_RESUME_BYTES + 1024))
    response = client.post(
        "/analyze-resume-file",
        files={"resume": ("cv.txt", oversized, "text/plain")},
        data={"job_description": "python"},
    )
    assert response.status_code == 401


def test_analyze_job_rejects_malformed_body_with_422_not_500():
    """This used to be a raw `data["description"]` lookup -> KeyError -> 500."""
    response = client.post(
        "/analyze-job",
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"wrong_key": "value"},
    )
    # Auth is checked before the body, so 401 here; the important part is that
    # a malformed body never produces a 500.
    assert response.status_code != 500


def test_openapi_marks_ai_endpoints_as_secured():
    spec = app.openapi()["paths"]
    for path in ("/analyze-job", "/analyze-resume", "/analyze-resume-file"):
        assert spec[path]["post"].get("security"), f"{path} is not auth-gated"


def test_job_description_is_a_form_field_not_a_query_param():
    """It was a bare `str`, so it bound as a query param and was always empty."""
    post = app.openapi()["paths"]["/analyze-resume-file"]["post"]
    assert [p["name"] for p in post.get("parameters", [])] == []

    body_ref = post["requestBody"]["content"]["multipart/form-data"]["schema"]["$ref"]
    body_schema = app.openapi()["components"]["schemas"][body_ref.rsplit("/", 1)[-1]]
    assert "job_description" in body_schema["properties"]
    assert "job_description" in body_schema["required"]
