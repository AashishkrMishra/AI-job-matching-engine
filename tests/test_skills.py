"""Unit tests for the shared skill vocabulary, extractor and comparator.

These cover the three bugs that motivated extracting `app/ai/skills.py`:
  1. match_percentage and missing_skills disagreeing with each other,
  2. two divergent extractors (substring vs word-boundary) for the same text,
  3. an unparseable job description reporting a confident 0%.
"""

import pytest

from app.ai.job_analyzer import analyze_job_description, extract_experience
from app.ai.resume_analyzer import analyze_resume
from app.ai.skills import CANONICAL_SKILLS, compare_skills, extract_skills


# --- extraction -----------------------------------------------------------

def test_extraction_is_word_boundary_anchored():
    """"JavaScript" must not be reported as "java"."""
    assert "java" not in extract_skills("Looking for a JavaScript developer")
    assert "java" in extract_skills("Looking for a Java developer")


def test_ml_alias_does_not_match_inside_other_words():
    assert "machine learning" not in extract_skills("rendered the html template")
    assert "machine learning" not in extract_skills("a 500ml bottle")
    assert "machine learning" in extract_skills("hiring an ML engineer")


def test_aliases_normalise_onto_canonical_skills():
    assert extract_skills("Nodejs and Node.js and node") == ["node"]
    assert "postgresql" in extract_skills("we run Postgres in production")
    assert "kubernetes" in extract_skills("deploys to k8s")
    assert "nlp" in extract_skills("experience with Natural Language Processing")


def test_multiword_skills_tolerate_separators():
    for text in ("machine learning", "machine-learning", "machine_learning"):
        assert "machine learning" in extract_skills(text), text


def test_extraction_is_case_insensitive_and_sorted():
    result = extract_skills("DOCKER, python, AWS")
    assert result == sorted(result)
    assert set(result) == {"aws", "docker", "python"}


def test_extraction_handles_empty_input():
    assert extract_skills("") == []
    assert extract_skills(None) == []


def test_extraction_only_ever_returns_canonical_skills():
    found = extract_skills(" ".join(CANONICAL_SKILLS))
    assert set(found) <= set(CANONICAL_SKILLS)


# --- comparison -----------------------------------------------------------

def test_matched_and_missing_partition_the_job_skills():
    result = compare_skills(["python", "docker"], ["python", "aws", "docker", "git"])
    assert result["matched_skills"] == ["docker", "python"]
    assert result["missing_skills"] == ["aws", "git"]
    assert result["match_percentage"] == 50


def test_full_score_implies_nothing_missing():
    """The original bug: 100% match reported alongside a missing skill."""
    result = compare_skills(["postgresql", "docker"], ["sql", "docker"])
    assert result["match_percentage"] == 100
    assert result["missing_skills"] == []


def test_unreadable_job_description_scores_none_not_zero():
    result = compare_skills(["python"], [])
    assert result["match_percentage"] is None
    assert result["matched_skills"] == []
    assert result["missing_skills"] == []


def test_zero_percent_is_still_reachable():
    result = compare_skills(["python"], ["aws"])
    assert result["match_percentage"] == 0
    assert result["missing_skills"] == ["aws"]


@pytest.mark.parametrize(
    "implying,implied",
    [
        ("postgresql", "sql"),
        ("django", "python"),
        ("flask", "python"),
        ("fastapi", "python"),
        ("pandas", "python"),
        ("numpy", "python"),
        ("deep learning", "machine learning"),
    ],
)
def test_implied_skills_count_as_matches(implying, implied):
    assert compare_skills([implying], [implied])["match_percentage"] == 100


def test_mongodb_does_not_imply_sql():
    assert compare_skills(["mongodb"], ["sql"])["missing_skills"] == ["sql"]


def test_implications_do_not_run_backwards():
    """Knowing Python does not mean you know Django."""
    assert compare_skills(["python"], ["django"])["missing_skills"] == ["django"]


# --- invariants -----------------------------------------------------------

_VOCAB = ["python", "java", "sql", "docker", "postgresql",
          "django", "deep learning", "react", "nlp", "aws"]


@pytest.mark.parametrize("seed", range(60))
def test_partition_invariant_holds_for_arbitrary_pairs(seed):
    import random

    rng = random.Random(seed)
    resume = rng.sample(_VOCAB, rng.randint(0, 5))
    job = rng.sample(_VOCAB, rng.randint(0, 5))

    result = compare_skills(resume, job)
    matched, missing = set(result["matched_skills"]), set(result["missing_skills"])

    assert matched | missing == set(job)
    assert not matched & missing

    if result["match_percentage"] is not None:
        assert (result["match_percentage"] == 100) is (missing == set())
        assert 0 <= result["match_percentage"] <= 100


# --- the two analyzers must agree ----------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "We need a JavaScript developer with Nodejs",
        "Senior Python engineer, Django, Postgres, 5 years",
        "ML and deep-learning research role",
        "No recognisable technologies here at all",
    ],
)
def test_job_and_resume_analyzers_extract_identically(text):
    """These used to disagree: one substring-matched, the other did not."""
    assert analyze_job_description(text)["skills"] == extract_skills(text)
    assert analyze_resume("", text)["job_skills"] == extract_skills(text)


def test_analyze_resume_response_shape():
    result = analyze_resume("python and docker", "we need python and aws")
    assert set(result) == {
        "resume_skills", "job_skills",
        "matched_skills", "missing_skills", "match_percentage",
    }


# --- experience -----------------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("1 year of experience", "fresher"),
        ("3 years experience", "junior"),
        ("5+ yrs", "mid-level"),
        ("10 years", "senior"),
        ("Senior Engineer", "senior"),
        ("Junior Developer", "junior"),
        ("Fresher welcome", "fresher"),
        ("Great team, nice office", "unknown"),
    ],
)
def test_experience_buckets(text, expected):
    assert extract_experience(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        # Accepting the singular "year" made these match a duration that is not
        # the requirement. The first match in the string used to win, so each of
        # these reported the degree length instead of the experience figure.
        ("Bachelor's degree (4 year program). Requires 8+ years of experience.", "senior"),
        ("4 year degree, 8+ years experience", "senior"),
        ("2 year diploma and 10 years of experience", "senior"),
        ("3 year rotation, 9+ years of experience", "senior"),
        # A duration with no experience requirement anywhere must not set a level.
        ("Celebrating our 100 year anniversary", "unknown"),
        ("Requires a 4 year degree", "unknown"),
        # The reverse phrasing.
        ("Experience: 8 years", "senior"),
        # Still works when the noun is left implied.
        ("5+ yrs", "mid-level"),
    ],
)
def test_experience_prefers_the_figure_tied_to_experience(text, expected):
    assert extract_experience(text) == expected
