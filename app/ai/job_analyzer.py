import re

from app.ai.skills import extract_skills

_YEARS = r'(\d+)\+?\s*(?:years?|yrs?)\b'

# "8+ years of experience", "3 years experience", "5 years' experience". The gap
# may not cross a comma or a sentence end, which is what stops an unrelated
# duration in the same sentence from being read as the requirement.
_YEARS_THEN_EXPERIENCE = re.compile(_YEARS + r"[^.;,\n]{0,20}?experience")

# The same statement written the other way round: "experience: 8 years".
_EXPERIENCE_THEN_YEARS = re.compile(r"experience[^.;,\n]{0,20}?" + _YEARS)

# Any duration at all, for a posting that writes "5+ yrs" and leaves the noun
# implied.
_ANY_YEARS = re.compile(_YEARS)

# Durations that plainly describe something other than experience. Only
# consulted on the last-resort path, where there is no nearby "experience" to
# settle it.
_NOT_EXPERIENCE = re.compile(
    r"\s*(?:degree|program|course|diploma|old|anniversary|visa|contract)\b"
)


def _years_required(text: str):
    """The years-of-experience figure a job description asks for, or None.

    Singular forms count — "1 year of experience" is common phrasing and used to
    fall through to "unknown". But accepting the singular also matches durations
    that are not requirements, and a plain search returns whichever comes
    *first*, so "4 year degree ... 8+ years of experience" has to resolve to 8
    rather than 4. Hence a preference order instead of a single pattern.
    """
    for pattern in (_YEARS_THEN_EXPERIENCE, _EXPERIENCE_THEN_YEARS):
        match = pattern.search(text)
        if match:
            return int(match.group(1))

    for match in _ANY_YEARS.finditer(text):
        if not _NOT_EXPERIENCE.match(text, match.end()):
            return int(match.group(1))

    return None


def extract_experience(text: str):
    text = text.lower()

    years = _years_required(text)
    if years is not None:
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
    return {
        "skills": extract_skills(text),
        "experience_level": extract_experience(text)
    }
