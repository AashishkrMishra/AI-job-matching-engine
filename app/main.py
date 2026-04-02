from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.security import hash_password
from app.security import verify_password
from app.auth import create_access_token
from app.dependencies import get_current_user
from fastapi.security import OAuth2PasswordRequestForm
from app.database import SessionLocal, engine, Base, get_db
from app import models
import app.schemas as schemas
from app.schemas import JobCreate
from app.models import Job
from fastapi import Depends
from app.dependencies import get_current_user
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.ai.job_analyzer import analyze_job_description
from app.ai.resume_analyzer import analyze_resume
from fastapi import UploadFile, File
from app.ai.file_parser import read_pdf, read_docx, read_txt
from app.ai.resume_analyzer import analyze_resume
from app.ai.llm_recommender import generate_recommendation

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
def analyze_job(data: dict):
    result = analyze_job_description(data["description"])
    return result

@app.post("/analyze-resume")
def analyze_resume_api(data: dict):

    result = analyze_resume(data["resume"], data["job"])

    recommendation = generate_recommendation(
        result["resume_skills"],
        result["job_skills"],
        result["missing_skills"],
        result["match_percentage"]
    )

    result["ai_recommendation"] = recommendation

    return result

@app.post("/analyze-resume-file")
async def analyze_resume_file(
    resume: UploadFile = File(...),
    job_description: str = ""
):
    filename = resume.filename.lower()

    if filename.endswith(".pdf"):
        text = read_pdf(resume.file)
    elif filename.endswith(".docx"):
        text = read_docx(resume.file)
    elif filename.endswith(".txt"):
        text = read_txt(resume.file)
    else:
        return {"error": "Unsupported file type"}

    result = analyze_resume(text, job_description)

    recommendation = generate_recommendation(
        result["resume_skills"],
        result["job_skills"],
        result["missing_skills"],
        result["match_percentage"]
    )

    result["ai_recommendation"] = recommendation

    return result
