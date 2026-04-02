import re
import spacy

nlp = spacy.load("en_core_web_sm")

SKILL_KEYWORDS = [
    "python","java","sql","fastapi","django","flask",
    "react","node","mongodb","postgresql","docker",
    "kubernetes","aws","machine learning","deep learning",
    "nlp","pandas","numpy","git","linux"
]

def extract_experience(text: str):
    text = text.lower()

    # detect numeric experience
    match = re.search(r'(\d+)\+?\s*(years|yrs)', text)
    if match:
        years = int(match.group(1))
        if years <= 1:
            return "fresher"
        elif years <= 3:
            return "junior"
        elif years <= 6:
            return "mid-level"
        else:
            return "senior"

    # fallback keywords
    if "senior" in text:
        return "senior"
    if "junior" in text:
        return "junior"
    if "fresher" in text:
        return "fresher"

    return "unknown"


def analyze_job_description(text: str):
    doc = nlp(text.lower())

    found_skills = []
    for skill in SKILL_KEYWORDS:
        if skill in text.lower():
            found_skills.append(skill)

    experience = extract_experience(text)

    return {
        "skills": list(set(found_skills)),
        "experience_level": experience
    }
