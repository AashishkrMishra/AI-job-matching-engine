import io
import os

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import models
import app.schemas as schemas
from app.ai.file_parser import read_docx, read_pdf, read_txt
from app.ai.job_analyzer import analyze_job_description
from app.ai.llm_recommender import generate_recommendation
from app.ai.resume_analyzer import analyze_resume
from app.auth import create_access_token
from app.config import FRONTEND_URL
from app.database import get_db
from app.dependencies import get_current_user
from app.security import hash_password, verify_password

app = FastAPI()

# Build CORS origins: always allow localhost + production frontend URL
cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if FRONTEND_URL and FRONTEND_URL not in cors_origins:
    cors_origins.append(FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Schema is owned by Alembic (`alembic upgrade head`), not by
# `Base.metadata.create_all` — create_all only ever creates missing tables and
# silently ignores changes to existing ones, so the two cannot coexist.

@app.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):

    # check if user already exists
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # create new user
    new_user = models.User(
    email=user.email,
    hashed_password=hash_password(user.password)
)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User created successfully"}

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(),
          db: Session = Depends(get_db)):

    db_user = db.query(models.User).filter(models.User.email == form_data.username).first()

    if not db_user or not verify_password(form_data.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token({"sub": db_user.email})

    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me")
def read_current_user(current_user = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email
    }

@app.post("/jobs", response_model=schemas.JobOut)
def create_job(
    job: schemas.JobCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    new_job = models.Job(
        company=job.company,
        role=job.role,
        owner_id=current_user.id
    )

    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    return new_job

@app.get("/jobs", response_model=list[schemas.JobOut])
def get_jobs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    jobs = db.query(models.Job).filter(models.Job.owner_id == current_user.id).all()
    return jobs

@app.patch("/jobs/{job_id}", response_model=schemas.JobOut)
def update_job(
    job_id: int,
    job: schemas.JobUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_job = db.query(models.Job).filter(models.Job.id == job_id).first()

    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")

    # SECURITY CHECK (very important)
    if db_job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    db_job.status = job.status
    db.commit()
    db.refresh(db_job)

    return db_job

@app.delete("/jobs/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    db.delete(job)
    db.commit()

    return {"message": "Job deleted successfully"}

@app.post("/analyze-job")
def analyze_job(
    data: schemas.JobAnalyzeIn,
    current_user: models.User = Depends(get_current_user)
):
    return analyze_job_description(data.description)

@app.post("/analyze-resume")
def analyze_resume_api(
    data: schemas.ResumeAnalyzeIn,
    current_user: models.User = Depends(get_current_user)
):
    result = analyze_resume(data.resume, data.job)

    result["ai_recommendation"] = generate_recommendation(
        result["resume_skills"],
        result["job_skills"],
        result["missing_skills"],
        result["match_percentage"]
    )

    return result


# Resume upload limits. The cap is enforced while draining the stream so we
# never hand an oversized file to pypdf or pay for an LLM call on it.
MAX_RESUME_BYTES = 5 * 1024 * 1024  # 5 MB
_UPLOAD_CHUNK = 64 * 1024

RESUME_PARSERS = {
    ".pdf": read_pdf,
    ".docx": read_docx,
    ".txt": read_txt,
}


async def _read_capped(upload: UploadFile) -> io.BytesIO:
    buffer = io.BytesIO()
    total = 0

    while chunk := await upload.read(_UPLOAD_CHUNK):
        total += len(chunk)
        if total > MAX_RESUME_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Resume file too large (limit {MAX_RESUME_BYTES // (1024 * 1024)} MB)."
            )
        buffer.write(chunk)

    if total == 0:
        raise HTTPException(status_code=400, detail="Uploaded resume file is empty.")

    buffer.seek(0)
    return buffer


@app.post("/analyze-resume-file")
async def analyze_resume_file(
    resume: UploadFile = File(...),
    # Must be Form(...), not a bare str — the frontend sends this in the
    # multipart body, and a bare str binds as a *query* parameter, so every
    # upload silently analysed against an empty job description.
    job_description: str = Form(..., min_length=1),
    current_user: models.User = Depends(get_current_user)
):
    suffix = os.path.splitext((resume.filename or "").lower())[1]
    parser = RESUME_PARSERS.get(suffix)

    if parser is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix or 'unknown'}'. Use PDF, DOCX or TXT."
        )

    buffer = await _read_capped(resume)

    try:
        text = parser(buffer)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not read that resume file — it may be corrupt or password-protected."
        )

    result = analyze_resume(text, job_description)

    result["ai_recommendation"] = generate_recommendation(
        result["resume_skills"],
        result["job_skills"],
        result["missing_skills"],
        result["match_percentage"]
    )

    return result
