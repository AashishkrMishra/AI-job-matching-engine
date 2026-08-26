"""Single source of truth for skill extraction and resume/job comparison.

Both the job analyzer and the resume analyzer used to carry their own copy of
`SKILL_KEYWORDS` *and* their own matching rule — one substring-based, one
word-boundary-based — so the two endpoints disagreed about the same text.
Everything skill-related now lives here.
"""

import re

# The canonical vocabulary. Extraction only ever reports these strings, so
# both sides of a comparison are always drawn from the same alphabet.
CANONICAL_SKILLS = (
    "python", "java", "sql", "fastapi", "django", "flask",
    "react", "node", "mongodb", "postgresql", "docker",
    "kubernetes", "aws", "machine learning", "deep learning",
    "nlp", "pandas", "numpy", "git", "linux",
)

# Surface forms that should normalise onto a canonical skill.
SKILL_ALIASES = {
    "postgres": "postgresql",
    "psql": "postgresql",
    "mongo": "mongodb",
    "node.js": "node",
    "nodejs": "node",
    "react.js": "react",
    "reactjs": "react",
    "k8s": "kubernetes",
    "amazon web services": "aws",
    "natural language processing": "nlp",
    "ml": "machine learning",
    "deep-learning": "deep learning",
}

# Skills that genuinely entail another skill. Kept deliberately small and
# near-tautological: a Django resume is a Python resume, and Postgres is SQL.
# Note that mongodb does *not* imply sql.
SKILL_IMPLIES = {
    "postgresql": frozenset({"sql"}),
    "django": frozenset({"python"}),
    "flask": frozenset({"python"}),
    "fastapi": frozenset({"python"}),
    "pandas": frozenset({"python"}),
    "numpy": frozenset({"python"}),
    "deep learning": frozenset({"machine learning"}),
}


def _compile(term: str) -> "re.Pattern[str]":
    # Split on whitespace and rejoin with a flexible separator so that
    # "machine learning", "machine-learning" and "machine_learning" all match.
    parts = [re.escape(part) for part in term.split()]
    return re.compile(r"\b" + r"[\s_/-]+".join(parts) + r"\b", re.IGNORECASE)


# term -> (compiled pattern, canonical skill)
_PATTERNS = [(_compile(s), s) for s in CANONICAL_SKILLS]
_PATTERNS += [(_compile(alias), canonical) for alias, canonical in SKILL_ALIASES.items()]


def extract_skills(text: str) -> list[str]:
    """Return the canonical skills mentioned in `text`, sorted.

    Matching is word-boundary anchored, so "JavaScript" does not count as
    "java" and "500ml" does not count as "ml".
    """
    if not text:
        return []

    found = {canonical for pattern, canonical in _PATTERNS if pattern.search(text)}
    return sorted(found)


def expand_with_implied(skills) -> set[str]:
    """Widen a skill set with everything those skills entail."""
    expanded = set(skills)
    for skill in skills:
        expanded |= SKILL_IMPLIES.get(skill, frozenset())
    return expanded


def compare_skills(resume_skills, job_skills) -> dict:
    """Compare a resume against a job using one predicate for every output.

    `matched_skills` and `missing_skills` are a strict partition of
    `job_skills`, and `match_percentage` is computed from that same partition —
    so a 100% score always means an empty `missing_skills`, and vice versa.

    `match_percentage` is None when no skills could be read out of the job
    description at all: "we could not tell" is not the same answer as "0%".
    """
    job_skills = list(job_skills)

    if not job_skills:
        return {
            "matched_skills": [],
            "missing_skills": [],
            "match_percentage": None,
        }

    capabilities = expand_with_implied(resume_skills)

    matched = sorted(s for s in job_skills if s in capabilities)
    missing = sorted(s for s in job_skills if s not in capabilities)

    return {
        "matched_skills": matched,
        "missing_skills": missing,
        "match_percentage": round(len(matched) / len(job_skills) * 100),
    }
