import re
from rapidfuzz import fuzz

SKILL_KEYWORDS = [
    "python","java","sql","fastapi","django","flask",
    "react","node","mongodb","postgresql","docker",
    "kubernetes","aws","machine learning","deep learning",
    "nlp","pandas","numpy","git","linux"
]

def extract_skills(text: str):
    text = text.lower()
    found = []

    for skill in SKILL_KEYWORDS:
        if re.search(r'\b' + re.escape(skill) + r'\b', text):
            found.append(skill)

    return list(set(found))


def calculate_match(resume_skills, job_skills):
    if not job_skills:
        return 0

    match_count = 0
    for skill in job_skills:
        for rskill in resume_skills:
            if fuzz.partial_ratio(skill, rskill) > 85:
                match_count += 1
                break

    return int((match_count / len(job_skills)) * 100)


def analyze_resume(resume_text: str, job_text: str):

    resume_skills = extract_skills(resume_text)
    job_skills = extract_skills(job_text)

    match = calculate_match(resume_skills, job_skills)
    missing = list(set(job_skills) - set(resume_skills))

    return {
        "resume_skills": resume_skills,
        "job_skills": job_skills,
        "missing_skills": missing,
        "match_percentage": match
    }
