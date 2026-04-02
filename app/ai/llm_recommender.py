import requests
import os
from dotenv import load_dotenv

load_dotenv(override=True)

HF_API_TOKEN = os.getenv("HF_API_TOKEN")

API_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL = "Qwen/Qwen2.5-72B-Instruct"

headers = {
    "Authorization": f"Bearer {HF_API_TOKEN}",
    "Content-Type": "application/json"
}

def generate_recommendation(resume_skills, job_skills, missing_skills, match_score):

    system_prompt = """You are a professional resume advisor AI. 
Your job is to analyze a candidate's resume against job requirements and give specific, actionable suggestions to improve their CV score. 
Be direct and helpful. Use bullet points."""

    user_prompt = f"""Here is the analysis of a candidate's resume vs a job posting:

- Candidate's current skills: {', '.join(resume_skills) if resume_skills else 'None detected'}
- Job required skills: {', '.join(job_skills) if job_skills else 'None detected'}
- Skills MISSING from resume: {', '.join(missing_skills) if missing_skills else 'None — great match!'}
- Current match score: {match_score}%

Based on this, tell the candidate:
1. Exactly which skills they need to ADD to their resume to increase their CV score.
2. For each missing skill, suggest a project or certification they can pursue.
3. Give a brief overall verdict on how strong their resume is for this role."""

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 600,
        "temperature": 0.7
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=120)

        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            print("STATUS:", response.status_code)
            print("RESPONSE:", response.text)
            return f"AI suggestion unavailable (API returned {response.status_code}). Please try again later."
    except requests.exceptions.Timeout:
        return "AI suggestion timed out. Please try again later."
    except Exception as e:
        print("LLM Error:", str(e))
        return "AI suggestion unavailable due to an error."