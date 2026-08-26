"""Coverage for the resume file parsers.

`read_pdf` and `read_docx` had no tests at all, so the PyPDF2 -> pypdf migration
would otherwise have been unverified. The PDF here is hand-built rather than
generated so the suite needs no PDF-writing dependency.
"""

import io

import docx
import pytest
from fastapi.testclient import TestClient

from app.ai.file_parser import read_docx, read_pdf, read_txt
from app.main import app

client = TestClient(app)


def _minimal_pdf(text: str) -> bytes:
    """Build a valid one-page PDF whose content stream draws `text`.

    The xref offsets are computed from the real object positions, so this is a
    structurally sound file — not something that only parses because pypdf
    silently repairs broken input.
    """
    escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode()

    return bytes(out)


def _docx_bytes(*paragraphs: str) -> bytes:
    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# --- PDF ---

def test_read_pdf_extracts_the_page_text():
    pdf = io.BytesIO(_minimal_pdf("Python Docker Kubernetes"))
    assert "Python" in read_pdf(pdf)


def test_read_pdf_feeds_the_skill_extractor():
    """The end the parser actually serves: text that the matcher can read."""
    from app.ai.skills import extract_skills

    text = read_pdf(io.BytesIO(_minimal_pdf("Python Docker and PostgreSQL")))
    assert {"python", "docker", "postgresql"} <= set(extract_skills(text))


def test_read_pdf_rejects_a_file_that_is_not_a_pdf():
    with pytest.raises(Exception):
        read_pdf(io.BytesIO(b"this is definitely not a pdf"))


# --- DOCX ---

def test_read_docx_joins_paragraphs_with_newlines():
    text = read_docx(io.BytesIO(_docx_bytes("Python developer", "Docker and AWS")))
    assert text == "Python developer\nDocker and AWS"


def test_read_docx_rejects_a_file_that_is_not_a_docx():
    with pytest.raises(Exception):
        read_docx(io.BytesIO(b"not a zip archive at all"))


# --- TXT encodings ---

def test_read_txt_handles_plain_utf8():
    assert read_txt(io.BytesIO("Python café".encode("utf-8"))) == "Python café"


def test_read_txt_strips_the_windows_bom():
    """Notepad writes UTF-8 with a BOM by default; it must not leak into the text."""
    assert read_txt(io.BytesIO("Python".encode("utf-8-sig"))) == "Python"
    assert not read_txt(io.BytesIO("Python".encode("utf-8-sig"))).startswith("﻿")


def test_read_txt_falls_back_to_cp1252():
    """A resume exported from Word as .txt is cp1252 and is not valid UTF-8. It
    used to raise UnicodeDecodeError and surface as a misleading 400.
    """
    raw = "Python — senior “role”".encode("cp1252")
    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")

    assert read_txt(io.BytesIO(raw)) == "Python — senior “role”"


def test_read_txt_never_raises_on_undecodable_bytes():
    text = read_txt(io.BytesIO(b"Python \xc3\x28\x80\xff Docker"))
    assert "Python" in text and "Docker" in text


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-16-be"])
def test_read_txt_handles_utf16(encoding):
    """Notepad's "Unicode" save option writes UTF-16, and cp1252 *cannot* fail on
    it — every byte maps to some character, NUL included. So without an explicit
    branch this decoded to NUL-interleaved mojibake, matched no skills, and was
    reported as a confident 0% match instead of an error.
    """
    assert read_txt(io.BytesIO("Python Docker".encode(encoding))) == "Python Docker"


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-16-be"])
def test_utf16_resumes_reach_the_skill_matcher(encoding):
    from app.ai.skills import extract_skills

    text = read_txt(io.BytesIO("Python and Docker".encode(encoding)))
    assert "\x00" not in text
    assert {"python", "docker"} <= set(extract_skills(text))


# --- Through the endpoint ---

@pytest.fixture(scope="module")
def auth_headers():
    email = "parser@example.com"
    password = "correct-horse-battery"
    client.post("/register", json={"email": email, "password": password})

    token = client.post(
        "/login", data={"username": email, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("filename, content_type, payload_factory", [
    ("cv.pdf", "application/pdf", lambda: _minimal_pdf("Python and Docker")),
    (
        "cv.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        lambda: _docx_bytes("Python and Docker"),
    ),
    ("cv.txt", "text/plain", lambda: "Python and Docker".encode("utf-8-sig")),
])
def test_every_supported_format_reaches_the_matcher(
    auth_headers, monkeypatch, filename, content_type, payload_factory
):
    monkeypatch.setattr("app.main.generate_recommendation", lambda *a, **k: "stubbed")

    response = client.post(
        "/analyze-resume-file",
        files={"resume": (filename, payload_factory(), content_type)},
        data={"job_description": "We need Python and Docker"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["match_percentage"] == 100
    assert set(body["job_skills"]) == {"python", "docker"}


def test_a_corrupt_pdf_is_a_400_not_a_500(auth_headers):
    response = client.post(
        "/analyze-resume-file",
        files={"resume": ("cv.pdf", b"%PDF-1.4 truncated garbage", "application/pdf")},
        data={"job_description": "python"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "corrupt" in response.json()["detail"]
