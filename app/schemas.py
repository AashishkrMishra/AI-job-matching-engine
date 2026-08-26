from typing import Annotated, Literal, get_args

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
)

# The set of statuses a job can move through. Declared once here and mirrored by
# STATUS_OPTIONS in the frontend dashboard.
JobStatus = Literal["applied", "interview", "offered", "rejected"]
JOB_STATUSES = get_args(JobStatus)

# Text that must contain something other than whitespace.
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# bcrypt hashes only the first 72 *bytes* of a password and silently discards
# the rest, which would make two different long passwords interchangeable.
BCRYPT_MAX_BYTES = 72


def _within_bcrypt_limit(password: str) -> str:
    encoded = len(password.encode("utf-8"))
    if encoded > BCRYPT_MAX_BYTES:
        raise ValueError(
            f"password must be at most {BCRYPT_MAX_BYTES} bytes once UTF-8 "
            f"encoded ({encoded} given) — bcrypt ignores anything past that"
        )
    return password


# Measured in bytes rather than characters. A character cap looks equivalent but
# is not: it admits a 40-character accented password at 80 bytes, and any other
# password sharing its first 72 bytes then authenticates against it. Non-ASCII
# scripts are hit hardest — 72 CJK characters are 216 bytes, so two thirds of a
# password chosen at that length would contribute nothing.
Password = Annotated[str, Field(min_length=8), AfterValidator(_within_bcrypt_limit)]


class UserCreate(BaseModel):
    email: EmailStr
    password: Password


class UserLogin(BaseModel):
    email: EmailStr
    # Plain str, unlike UserCreate: a length policy belongs on registration.
    # Enforcing it here would lock out any account created before the policy and
    # leak the rule to anyone probing the endpoint.
    password: str


class JobCreate(BaseModel):
    company: NonBlankStr
    role: NonBlankStr


class JobOut(BaseModel):
    id: int
    company: str
    role: str
    # Intentionally a plain str on the way out, unlike JobUpdate: a row written
    # before JobStatus existed would otherwise fail response validation as a 500.
    status: str

    model_config = ConfigDict(from_attributes=True)


class JobUpdate(BaseModel):
    status: JobStatus


# --- AI analysis request bodies ---
# These endpoints previously accepted a bare `dict` and indexed it directly,
# which turned a malformed body into a 500 instead of a 422.

# app.ai.skills runs ~30 regexes over the whole string, so an unbounded body is
# CPU an unauthenticated-by-anything-but-registration caller can spend freely.
# The file upload route caps the *file* at 5 MB (MAX_RESUME_BYTES in app/main.py);
# this caps the *text*, which is the thing that actually gets scanned. A megabyte
# is far more than any real resume or posting.
MAX_ANALYSIS_CHARS = 1024 * 1024

AnalysisText = Annotated[str, Field(min_length=1, max_length=MAX_ANALYSIS_CHARS)]


class JobAnalyzeIn(BaseModel):
    description: AnalysisText


class ResumeAnalyzeIn(BaseModel):
    resume: AnalysisText
    job: AnalysisText
