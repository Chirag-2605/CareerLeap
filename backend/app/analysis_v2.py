from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from .parser_v2 import SKILL_GROUPS

QUALITY_VERSION = "quality-v2"
MATCH_VERSION = "match-v2"

WEIGHTS = {
    "contact": 5,
    "structure": 15,
    "experience": 20,
    "impact": 20,
    "skills": 15,
    "education": 10,
    "readability": 10,
    "completeness": 5,
}

ACTION_VERBS = {
    "built", "developed", "designed", "implemented", "created", "led",
    "improved", "optimized", "automated", "delivered", "launched",
    "reduced", "increased", "integrated", "managed", "analyzed",
    "migrated", "deployed", "engineered", "maintained", "configured",
}
METRIC_RE = re.compile(
    r"(?<!\w)(?:\d+(?:\.\d+)?\s?%|\d+(?:\.\d+)?\s?(?:x|×)|"
    r"[$₹€]\s?\d[\d,.]*|\d+\+?\s?(?:users|customers|requests|ms|"
    r"seconds|hours|days|teams|projects|records|employees|clients|services|"
    r"transactions|queries|datasets|students|members))(?!\w)",
    re.I,
)
REQUIRED_CUES = ("required", "must have", "must", "minimum", "you need", "requirement")
PREFERRED_CUES = ("preferred", "nice to have", "bonus", "ideally", "plus", "desired")
ROLE_WORDS = {
    "engineer", "developer", "analyst", "designer", "manager", "architect",
    "scientist", "consultant", "administrator", "specialist", "researcher",
}


def _sections(resume: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {}
    for section in resume.get("sections", []):
        result.setdefault(section.get("type", "other"), []).extend(section.get("items", []))
    return result


def _all_items(resume: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [item for items in _sections(resume).values() for item in items]


def _text(item: Dict[str, Any]) -> str:
    return str(item.get("text", "")).strip()


def _evidence(item: Dict[str, Any]) -> List[str]:
    ids = item.get("evidence_ids") or ([item["evidence_id"]] if item.get("evidence_id") else [])
    return [str(value) for value in ids]


def _finding(code: str, title: str, severity: str, recommendation: str,
             evidence_ids: Optional[List[str]] = None, detail: Optional[str] = None) -> Dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "severity": severity,
        "recommendation": recommendation,
        "evidence_ids": list(dict.fromkeys(evidence_ids or [])),
        "detail": detail,
    }


def _score_component(key: str, earned: int, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    possible = WEIGHTS[key]
    return {
        "key": key,
        "label": key.replace("_", " ").title(),
        "earned": max(0, min(possible, int(earned))),
        "possible": possible,
        "deducted": possible - max(0, min(possible, int(earned))),
    }


def analyze_quality_v2(resume: Dict[str, Any]) -> Dict[str, Any]:
    """Explainable baseline quality analysis over parser-v2 output.

    This is a deterministic heuristic, not a prediction of any particular ATS.
    Missing or unassessable information is reported cautiously.
    """
    sections = _sections(resume)
    candidate = resume.get("candidate", {})
    all_items = _all_items(resume)
    all_text = " ".join(_text(item) for item in all_items)
    findings: List[Dict[str, Any]] = []
    components: List[Dict[str, Any]] = []

    contact_score = 0
    if candidate.get("email"):
        contact_score += 2
    else:
        findings.append(_finding("contact_email_unseen", "Email address not detected", "medium",
                                 "Add a professional email address to the resume header."))
    if candidate.get("phone"):
        contact_score += 2
    else:
        findings.append(_finding("contact_phone_unseen", "Phone number not detected", "low",
                                 "Consider adding a reachable phone number."))
    if candidate.get("profile_urls"):
        contact_score += 1
    else:
        findings.append(_finding("profile_link_unseen", "Professional profile link not detected", "low",
                                 "Add a relevant LinkedIn, portfolio, or GitHub link if you have one."))
    components.append(_score_component("contact", contact_score, findings))

    required_sections = ("experience", "education", "skills")
    present = [key for key in required_sections if sections.get(key)]
    structure_score = 5 * len(present)
    if sections.get("summary"):
        structure_score += 2
    if sections.get("projects") or sections.get("certifications"):
        structure_score += 3
    for key in required_sections:
        if not sections.get(key):
            findings.append(_finding("section_" + key + "_unseen", key.title() + " section not detected",
                                     "high" if key in ("experience", "education") else "medium",
                                     "Add a clearly labelled " + key + " section when relevant to your background."))
    components.append(_score_component("structure", structure_score, findings))

    experience_items = sections.get("experience", [])
    experience_bullets = [item for item in experience_items if item.get("kind") == "bullet" and _text(item)]
    experience_score = min(8, len(experience_bullets) * 2)
    if experience_items:
        experience_score += 4
    dated_evidence = [item for item in experience_items if re.search(
        r"\b(?:19|20)\d{2}\b|\b(?:present|current)\b", _text(item), re.I)]
    if dated_evidence:
        experience_score += 3
    if sections.get("projects"):
        experience_score += 3
    experience_score = min(WEIGHTS["experience"], experience_score)
    if experience_items and len(experience_bullets) < 2:
        findings.append(_finding("experience_detail_limited", "Limited achievement bullets detected",
                                 "medium", "Describe your contribution in concise bullets for each relevant role.",
                                 [eid for item in experience_items for eid in _evidence(item)]))
    components.append(_score_component("experience", experience_score, findings))

    achievement_items = [item for item in all_items if item.get("kind") == "bullet" and _text(item)]
    action_items = [item for item in achievement_items if any(
        re.search(r"\b" + re.escape(verb) + r"\b", _text(item), re.I) for verb in ACTION_VERBS)]
    metric_items = [item for item in achievement_items if METRIC_RE.search(_text(item))]
    impact_score = min(10, len(action_items) * 2) + min(10, len(metric_items) * 3)
    impact_score = min(20, impact_score)
    if len(metric_items) < 2:
        findings.append(_finding("impact_metrics_limited", "Few quantified outcomes detected", "medium",
                                 "Where truthful, quantify scale or outcomes such as time saved, latency, adoption, accuracy, or volume.",
                                 [eid for item in achievement_items for eid in _evidence(item)][:12]))
    if not action_items:
        findings.append(_finding("achievement_evidence_limited", "Few action-led bullets detected", "low",
                                 "Start achievement bullets with clear descriptions of what you personally built, changed, or delivered."))
    components.append(_score_component("impact", impact_score, findings))

    skills = resume.get("skills", [])
    skill_evidence = {skill.get("canonical_name"): skill.get("evidence_ids", []) for skill in skills}
    demonstrated_names: Set[str] = set()
    for name, evidence_ids in skill_evidence.items():
        if any(eid in {eid for item in achievement_items for eid in _evidence(item)} for eid in evidence_ids):
            demonstrated_names.add(str(name))
    skill_score = min(15, min(8, len(skills) * 2) + min(7, len(demonstrated_names)))
    if skills and not demonstrated_names:
        findings.append(_finding("skills_not_demonstrated", "Listed skills lack detected achievement evidence",
                                 "medium", "Reinforce important skills with specific examples in experience or project bullets.",
                                 [eid for skill in skills for eid in skill.get("evidence_ids", [])][:12]))
    if not skills:
        findings.append(_finding("skills_unseen", "No recognized skills detected", "medium",
                                 "Add a focused skills section using technologies or competencies you can demonstrate."))
    components.append(_score_component("skills", skill_score, findings))

    education_items = sections.get("education", [])
    education_score = 0
    if education_items:
        education_score += 5
        edu_text = " ".join(_text(item) for item in education_items)
        if re.search(r"\b(bachelor|b\.?tech|b\.?e\.?|master|m\.?tech|ph\.?d|degree|university|college)\b", edu_text, re.I):
            education_score += 3
        if re.search(r"\b(?:19|20)\d{2}\b", edu_text):
            education_score += 2
    else:
        findings.append(_finding("education_unseen", "Education details not detected", "low",
                                 "Add your qualification and institution if applicable."))
    components.append(_score_component("education", education_score, findings))

    document = resume.get("document", {})
    warnings = resume.get("warnings", [])
    readability_score = 10
    if document.get("word_count", 0) < 100:
        readability_score -= 3
        findings.append(_finding("short_extraction", "Limited resume text was extracted", "medium",
                                 "Check that the uploaded document includes all relevant content."))
    if document.get("pages") and document["pages"] > 3:
        readability_score -= 2
        findings.append(_finding("length_review", "Resume is longer than three pages", "low",
                                 "Review whether older or less relevant content can be shortened; length depends on career stage."))
    if warnings:
        readability_score -= min(3, len(warnings))
    components.append(_score_component("readability", readability_score, findings))

    completeness_score = 5
    if not candidate.get("name"):
        completeness_score -= 2
    if not sections.get("experience") and not sections.get("projects"):
        completeness_score -= 3
    components.append(_score_component("completeness", completeness_score, findings))

    score = sum(component["earned"] for component in components)
    findings.sort(key=lambda item: ({"high": 0, "medium": 1, "low": 2}.get(item["severity"], 3),
                                    -len(item["evidence_ids"])))
    return {
        "score": score,
        "version": QUALITY_VERSION,
        "breakdown": components,
        "findings": findings,
        "strengths": [
            {"title": "Detected " + str(len(skills)) + " recognized skills",
             "evidence_ids": [eid for skill in skills for eid in skill.get("evidence_ids", [])][:12]}
        ] if skills else [],
        "summary": (
            "Strong resume structure; focus on tailoring and strengthening evidence."
            if score >= 80 else
            "There is a useful foundation, but several areas could be supported more clearly."
            if score >= 60 else
            "The resume needs more complete, clearly structured evidence before applying."
        ),
        "disclaimer": "A transparent heuristic assessment, not an employer-specific ATS prediction.",
    }


def _skill_aliases(resume: Dict[str, Any]) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    for skill in resume.get("skills", []):
        canonical = str(skill.get("canonical_name", "")).lower()
        if canonical:
            aliases[canonical] = canonical
    return aliases


def analyze_job_match_v2(resume: Dict[str, Any], job_description: str) -> Dict[str, Any]:
    """Conservative catalog-based job alignment; semantic equivalence is not inferred."""
    if not job_description or len(job_description.strip()) < 40:
        raise ValueError("Please provide a job description with at least 40 characters.")

    resume_skills = _skill_aliases(resume)
    required: Set[str] = set()
    preferred: Set[str] = set()
    sentences = re.split(r"[\n.!?;]+", job_description.lower())
    for canonical, aliases in SKILL_GROUPS.items():
        pattern = re.compile(
            r"(?<![a-z0-9])(?:" + "|".join(re.escape(alias.lower()) for alias in aliases) + r")(?![a-z0-9])",
            re.I,
        )
        matching_sentences = [sentence for sentence in sentences if pattern.search(sentence)]
        if not matching_sentences:
            continue
        for sentence in matching_sentences:
            if any(cue in sentence for cue in PREFERRED_CUES):
                preferred.add(canonical)
            else:
                # Neutral mentions are treated as requirements only when explicitly
                # framed as required; otherwise keep them in the assessed set as
                # neutral requirements for this initial baseline.
                required.add(canonical)

    detected = set(resume_skills)
    matched_required = sorted(required & detected)
    missing_required = sorted(required - detected)
    matched_preferred = sorted(preferred & detected)
    missing_preferred = sorted(preferred - detected)
    required_score = round(70 * len(matched_required) / len(required)) if required else 70
    preferred_score = round(10 * len(matched_preferred) / len(preferred)) if preferred else 10

    sections = _sections(resume)
    experience_text = " ".join(
        _text(item) for item in sections.get("experience", []) + sections.get("projects", [])
    ).lower()
    matched_in_context = sorted(
        skill for skill in matched_required
        if re.search(r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])", experience_text)
    )
    context_score = round(20 * len(matched_in_context) / len(matched_required)) if matched_required else 20
    score = min(100, required_score + preferred_score + context_score)

    findings = []
    if missing_required:
        findings.append(_finding(
            "required_skills_missing", "Job-description skills not detected in resume", "high",
            "If you genuinely have these skills, add specific examples in relevant experience or projects.",
            detail=", ".join(missing_required),
        ))
    if missing_preferred:
        findings.append(_finding(
            "preferred_skills_missing", "Preferred skills not detected", "low",
            "Treat preferred requirements as differentiators, not automatic disqualifiers.",
            detail=", ".join(missing_preferred),
        ))
    if not required and not preferred:
        findings.append(_finding(
            "no_catalog_skills", "No supported catalog skills could be assessed", "medium",
            "Review the job description manually; this baseline only recognizes its explicit supported skill vocabulary.",
        ))

    return {
        "score": score,
        "version": MATCH_VERSION,
        "breakdown": [
            {"key": "required_skills", "label": "Required skill coverage", "earned": required_score, "possible": 70, "deducted": 70-required_score},
            {"key": "preferred_skills", "label": "Preferred skill coverage", "earned": preferred_score, "possible": 10, "deducted": 10-preferred_score},
            {"key": "experience_evidence", "label": "Skills evidenced in experience/projects", "earned": context_score, "possible": 20, "deducted": 20-context_score},
        ],
        "matched_required_skills": matched_required,
        "missing_required_skills": missing_required,
        "matched_preferred_skills": matched_preferred,
        "missing_preferred_skills": missing_preferred,
        "not_assessed": [],
        "findings": findings,
        "summary": "Detected {0} of {1} required catalog skills.".format(len(matched_required), len(required)),
        "disclaimer": "This baseline checks explicit catalog terms; it does not infer semantic equivalence or predict an employer's ATS ranking.",
    }
