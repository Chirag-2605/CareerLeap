from app.services.experience_evaluator_service import evaluate_experience_depth
from app.services.project_evaluator_service import evaluate_projects
from app.services.responsibility_matching_service import match_responsibilities
from app.services.scoring_orchestrator import aggregate_dimensions
from app.services.skill_matching_service import match_requirement


def test_skill_matcher_distinguishes_direct_from_supporting_evidence():
    evidence = [{
        "text": "Developed REST APIs using Express.js and MongoDB.",
        "evidence_ids": ["exp-1"],
    }]
    skills = {"rest api": {"listed": [], "demonstrated": ["exp-1"]}}
    aliases = {
        "api development": ("api development", "api design", "api implementation"),
        "http": ("http", "http protocols"),
        "relational databases": ("relational databases", "relational database"),
    }

    api = match_requirement({
        "name": "api development", "classification": "required",
        "source_sentence": "Experience in API development",
    }, skills, evidence, aliases)
    http = match_requirement({
        "name": "http", "classification": "required",
        "source_sentence": "Knowledge of HTTP",
    }, skills, evidence, aliases)

    assert api["status"] == "supporting"
    assert http["status"] == "supporting"
    assert api["resume_evidence_ids"] == ["exp-1"]


def test_database_design_is_not_proven_by_a_database_keyword_alone():
    evidence = [{"text": "Used SQL queries to retrieve records.", "evidence_ids": ["p-1"]}]
    result = match_requirement({
        "name": "database design", "classification": "required",
        "source_sentence": "Experience with database design",
    }, {}, evidence, {"database design": ("database design",)})
    assert result["status"] == "supporting"


def test_responsibility_matcher_recognizes_api_and_backend_paraphrases():
    job_lines = ["Design and maintain REST API endpoints for backend services."]
    bullets = [{
        "text": "Developed REST APIs using Express.js for internal services.",
        "evidence_ids": ["exp-2"],
    }]
    matches, score = match_responsibilities(job_lines, bullets)
    assert matches
    assert matches[0]["evidence_ids"] == ["exp-2"]
    assert score is not None and score > 0


def test_experience_depth_rewards_substance_not_bullet_count():
    vague = evaluate_experience_depth(
        [{"text": "Worked on projects."}] * 4,
        [{"text": "Software Intern"}], [], [0, 0, 0, 0],
    )
    detailed = evaluate_experience_depth(
        [{"text": "Built REST APIs using Python and PostgreSQL."}] * 2,
        [{"text": "Backend Engineer"}],
        [{"text": "Designed a Docker service with API integrations."}],
        [6, 7],
    )
    assert vague["score"] < detailed["score"]
    assert vague["score"] < 10


def test_project_evaluator_reports_source_linked_technical_substance():
    result = evaluate_projects([
        {"text": "NovaChat", "evidence_ids": ["p-title"]},
        {"text": "Built a real-time chat API using React, Node.js and MongoDB.",
         "evidence_ids": ["p-detail"]},
    ])
    assert result["substantive_bullets"] == 1
    assert result["needs_detail"][0]["evidence_ids"] == ["p-title"]
    assert result["evidence_ids"] == ["p-detail"]


def test_scoring_orchestrator_normalizes_only_assessed_dimensions():
    result = aggregate_dimensions([
        ("required_skills", 20, 40),
        ("preferred_skills", None, 15),
        ("responsibility_alignment", 10, 25),
    ])
    assert result["score"] == 46
    assert result["active_weight"] == 65
    assert result["breakdown"][1]["assessed"] is False
