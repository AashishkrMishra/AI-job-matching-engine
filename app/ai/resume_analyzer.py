from app.ai.skills import compare_skills, extract_skills


def analyze_resume(resume_text: str, job_text: str) -> dict:
    resume_skills = extract_skills(resume_text)
    job_skills = extract_skills(job_text)

    comparison = compare_skills(resume_skills, job_skills)

    return {
        "resume_skills": resume_skills,
        "job_skills": job_skills,
        **comparison,
    }
