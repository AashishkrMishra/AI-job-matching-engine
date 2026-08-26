"""End-to-end flow over the Alembic-built schema.

This is the check that the app still works now that `Base.metadata.create_all()`
has been removed from app/main.py: if the migration and the models disagree,
these tests fail.
"""

import ast
import pathlib
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import schemas
from app.main import app

ROOT = pathlib.Path(__file__).resolve().parent.parent

client = TestClient(app)


def _register_and_login(email, password="correct-horse-battery"):
    assert client.post(
        "/register", json={"email": email, "password": password}
    ).status_code == 200

    response = client.post(
        "/login", data={"username": email, "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="module")
def alice():
    return _register_and_login("alice@example.com")


@pytest.fixture(scope="module")
def bob():
    return _register_and_login("bob@example.com")


def test_duplicate_registration_is_rejected():
    payload = {"email": "dupe@example.com", "password": "hunter2hunter2"}
    assert client.post("/register", json=payload).status_code == 200
    assert client.post("/register", json=payload).status_code == 400


def test_login_with_wrong_password_is_rejected():
    _register_and_login("wrongpass@example.com")
    response = client.post(
        "/login", data={"username": "wrongpass@example.com", "password": "nope"}
    )
    assert response.status_code == 401


def test_me_returns_the_authenticated_user(alice):
    response = client.get("/me", headers=alice)
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_job_crud_round_trip(alice):
    created = client.post(
        "/jobs", json={"company": "Acme", "role": "Backend Engineer"}, headers=alice
    )
    assert created.status_code == 200
    job = created.json()
    # server_default from the migration
    assert job["status"] == "applied"

    listed = client.get("/jobs", headers=alice)
    assert listed.status_code == 200
    assert job["id"] in [j["id"] for j in listed.json()]

    updated = client.patch(
        f"/jobs/{job['id']}", json={"status": "interview"}, headers=alice
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "interview"

    assert client.delete(f"/jobs/{job['id']}", headers=alice).status_code == 200
    assert client.delete(f"/jobs/{job['id']}", headers=alice).status_code == 404


def test_jobs_are_scoped_to_their_owner(alice, bob):
    job = client.post(
        "/jobs", json={"company": "Initech", "role": "Dev"}, headers=alice
    ).json()

    assert job["id"] not in [j["id"] for j in client.get("/jobs", headers=bob).json()]

    assert client.patch(
        f"/jobs/{job['id']}", json={"status": "offered"}, headers=bob
    ).status_code == 403
    assert client.delete(f"/jobs/{job['id']}", headers=bob).status_code == 403


def test_analyze_job_with_a_valid_token(alice):
    response = client.post(
        "/analyze-job",
        json={"description": "Senior Python engineer, Django and Postgres, 7 years"},
        headers=alice,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["experience_level"] == "senior"
    assert {"python", "django", "postgresql"} <= set(body["skills"])


def test_analyze_job_rejects_an_empty_description(alice):
    response = client.post("/analyze-job", json={"description": ""}, headers=alice)
    assert response.status_code == 422


def test_analyze_job_rejects_a_missing_field(alice):
    """Previously a raw dict lookup, which raised KeyError -> 500."""
    response = client.post("/analyze-job", json={"nope": "x"}, headers=alice)
    assert response.status_code == 422


def test_analyze_resume_text(alice, monkeypatch):
    monkeypatch.setattr("app.main.generate_recommendation", lambda *a, **k: "stubbed")

    response = client.post(
        "/analyze-resume",
        json={"resume": "I use Django and Docker", "job": "Need SQL and Docker"},
        headers=alice,
    )
    assert response.status_code == 200
    body = response.json()

    assert body["ai_recommendation"] == "stubbed"
    # Django implies Python, Postgres would imply SQL — here SQL is genuinely absent.
    assert body["missing_skills"] == ["sql"]
    assert body["matched_skills"] == ["docker"]
    assert body["match_percentage"] == 50


def test_analyze_resume_file_upload(alice, monkeypatch):
    monkeypatch.setattr("app.main.generate_recommendation", lambda *a, **k: "stubbed")

    response = client.post(
        "/analyze-resume-file",
        files={"resume": ("cv.txt", b"Python, Docker, Postgres", "text/plain")},
        data={"job_description": "We need Python and SQL"},
        headers=alice,
    )
    assert response.status_code == 200
    body = response.json()

    # The job description used to arrive empty because it bound as a query
    # param, so job_skills was always [] and the score always 0.
    assert body["job_skills"] == ["python", "sql"]
    assert body["match_percentage"] == 100


def test_upload_rejects_unsupported_extensions(alice):
    response = client.post(
        "/analyze-resume-file",
        files={"resume": ("cv.exe", b"binary", "application/octet-stream")},
        data={"job_description": "python"},
        headers=alice,
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_rejects_an_empty_file(alice):
    response = client.post(
        "/analyze-resume-file",
        files={"resume": ("cv.txt", b"", "text/plain")},
        data={"job_description": "python"},
        headers=alice,
    )
    assert response.status_code == 400


def test_upload_rejects_oversized_files(alice):
    from app.main import MAX_RESUME_BYTES

    response = client.post(
        "/analyze-resume-file",
        files={"resume": ("cv.txt", b"x" * (MAX_RESUME_BYTES + 1), "text/plain")},
        data={"job_description": "python"},
        headers=alice,
    )
    assert response.status_code == 413


def test_upload_requires_a_job_description(alice):
    response = client.post(
        "/analyze-resume-file",
        files={"resume": ("cv.txt", b"python", "text/plain")},
        headers=alice,
    )
    assert response.status_code == 422


# --- Token expiry ---

def test_access_token_expires_about_an_hour_out():
    """Pins the expiry window, which catches a units slip in the timedelta.

    It deliberately does not claim to catch the naive/aware change in app/auth.py:
    python-jose serialises `exp` as timegm(value.utctimetuple()), and
    utctimetuple() returns a naive datetime's fields unchanged, so utcnow() and
    now(timezone.utc) encode to the same integer. No assertion on the token can
    tell them apart — test_auth_does_not_use_the_deprecated_utcnow covers that.
    """
    from jose import jwt

    from app.auth import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, create_access_token
    from app.config import SECRET_KEY

    token = create_access_token({"sub": "expiry@example.com"})
    exp = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["exp"]

    expected = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    assert abs(exp - expected.timestamp()) < 60


def test_auth_does_not_use_the_deprecated_utcnow():
    """datetime.utcnow() is deprecated in 3.12 and yields a naive value that is
    ambiguous the moment it leaves the process. Because it encodes to the same
    `exp` as the aware form, a reintroduction is invisible to behavioural tests;
    the source is the only place it can be caught.

    Asserted against the parsed tree rather than the text, so the prose in
    app/auth.py explaining the change cannot satisfy or break it.
    """
    tree = ast.parse((ROOT / "app" / "auth.py").read_text(encoding="utf-8"))
    calls = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert "utcnow" not in calls

    clock_reads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "now"
    ]
    assert clock_reads, "expected app/auth.py to read the clock"
    assert all(call.args or call.keywords for call in clock_reads), (
        "datetime.now() without a timezone argument is just as naive as utcnow()"
    )


# --- Registration password policy ---

@pytest.mark.parametrize("password", ["", "short", "1234567"])
def test_registration_rejects_short_passwords(password):
    response = client.post(
        "/register", json={"email": "tooshort@example.com", "password": password}
    )
    assert response.status_code == 422


def test_registration_rejects_passwords_bcrypt_would_truncate():
    """bcrypt hashes only the first 72 bytes; beyond that the tail is ignored.

    ASCII only, so this case says nothing about how the limit is measured — see
    test_registration_measures_the_limit_in_bytes_not_characters for that.
    """
    response = client.post(
        "/register", json={"email": "toolong@example.com", "password": "x" * 73}
    )
    assert response.status_code == 422


@pytest.mark.parametrize("password, expected_bytes", [
    ("é" * 37, 74),              # accented Latin — 2 bytes per character
    ("password-" + "ü" * 32, 73),  # mostly ASCII, tipped over by the tail
    ("密" * 25, 75),             # CJK — 3 bytes per character
])
def test_registration_measures_the_limit_in_bytes_not_characters(password, expected_bytes):
    """The case a character-based cap let straight through: comfortably under 72
    characters, but over 72 bytes, so bcrypt would hash a prefix and discard the
    rest.
    """
    assert len(password) < schemas.BCRYPT_MAX_BYTES < len(password.encode("utf-8"))
    assert len(password.encode("utf-8")) == expected_bytes

    response = client.post(
        "/register", json={"email": "multibyte@example.com", "password": password}
    )
    assert response.status_code == 422


def test_a_truncated_twin_cannot_be_registered_and_then_impersonated():
    """The concrete attack the byte cap closes. Under the old character cap, a
    40-character accented password (80 bytes) registered fine, and a *different*
    password agreeing only on the first 72 bytes then received a valid token.
    """
    password = "é" * 40
    assert len(password.encode("utf-8")) == 80

    assert client.post(
        "/register", json={"email": "twin@example.com", "password": password}
    ).status_code == 422

    twin = password[:36] + "ZZZZ"
    assert twin != password
    assert twin.encode("utf-8")[:72] == password.encode("utf-8")[:72]

    # No account exists, so the twin gets bad-credentials rather than a token.
    assert client.post(
        "/login", data={"username": "twin@example.com", "password": twin}
    ).status_code == 401


@pytest.mark.parametrize("password", ["x" * 72, "é" * 36])
def test_registration_accepts_a_password_at_the_limit(password):
    """Both are exactly 72 bytes — 72 ASCII characters, and 36 two-byte ones."""
    assert len(password.encode("utf-8")) == schemas.BCRYPT_MAX_BYTES

    response = client.post(
        "/register", json={"email": f"atlimit-{len(password)}@example.com", "password": password}
    )
    assert response.status_code == 200


def test_a_password_at_the_limit_round_trips_through_login():
    """72 ASCII characters is exactly 72 bytes, the largest input bcrypt reads in
    full, so it must authenticate rather than land just past the cap.
    """
    response = client.post(
        "/login", data={"username": "atlimit-72@example.com", "password": "x" * 72}
    )
    assert response.status_code == 200


def test_login_has_no_length_policy():
    """A short password must fail as bad credentials (401), not as a validation
    error (422) — otherwise the policy would lock out accounts created before it
    and would leak the rule to anyone probing the endpoint.
    """
    response = client.post(
        "/login", data={"username": "atlimit-72@example.com", "password": "tiny"}
    )
    assert response.status_code == 401


# --- Job field validation ---

@pytest.mark.parametrize("payload", [
    {"company": "", "role": "Dev"},
    {"company": "   ", "role": "Dev"},
    {"company": "Acme", "role": ""},
    {"company": "Acme", "role": "\t\n"},
])
def test_job_creation_rejects_blank_fields(alice, payload):
    assert client.post("/jobs", json=payload, headers=alice).status_code == 422


def test_job_creation_strips_surrounding_whitespace(alice):
    job = client.post(
        "/jobs", json={"company": "  Acme  ", "role": "  Dev  "}, headers=alice
    ).json()
    assert job["company"] == "Acme"
    assert job["role"] == "Dev"


# --- Status validation ---

@pytest.mark.parametrize("status", schemas.JOB_STATUSES)
def test_every_declared_status_is_accepted(alice, status):
    job = client.post(
        "/jobs", json={"company": "Acme", "role": "Dev"}, headers=alice
    ).json()

    response = client.patch(
        f"/jobs/{job['id']}", json={"status": status}, headers=alice
    )
    assert response.status_code == 200
    assert response.json()["status"] == status


@pytest.mark.parametrize("status", ["", "ghosted", "APPLIED", "applied ", None, 3])
def test_unknown_statuses_are_rejected(alice, status):
    """Previously any string at all was written straight to the column."""
    job = client.post(
        "/jobs", json={"company": "Acme", "role": "Dev"}, headers=alice
    ).json()

    response = client.patch(
        f"/jobs/{job['id']}", json={"status": status}, headers=alice
    )
    assert response.status_code == 422


def test_frontend_and_backend_agree_on_the_status_list():
    """STATUS_OPTIONS in the dashboard mirrors JobStatus. Nothing enforces that
    at runtime, so assert it here rather than discover the drift in the UI.
    """
    source = (ROOT / "frontend" / "src" / "pages" / "Dashboard.jsx").read_text(
        encoding="utf-8"
    )
    declared = re.search(r"const STATUS_OPTIONS = \[(.*?)\]", source, re.S)
    assert declared, "could not find STATUS_OPTIONS in Dashboard.jsx"

    assert tuple(re.findall(r"'([^']+)'", declared.group(1))) == schemas.JOB_STATUSES
