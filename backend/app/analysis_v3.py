from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .analysis_v2 import analyze_quality_v2, _sections, _text, _evidence, _finding
from .parser_v2 import SKILL_GROUPS

QUALITY_VERSION = "quality-v3"
MATCH_VERSION = "match-v3"

# Only explicit, defensible equivalences belong here. These are not broad
# technology-family substitutions (e.g. SQL is not PostgreSQL).
SKILL_EQUIVALENTS = {
    "rest api": ("rest api", "restful api", "rest apis", "restful services"),
    "javascript": ("javascript", "js", "ecmascript"),
    "typescript": ("typescript", "ts"),
    "node.js": ("node.js", "node js", "nodejs"),
    "postgresql": ("postgresql", "postgres"),
    "mongodb": ("mongodb", "mongo db"),
    "machine learning": ("machine learning", "ml"),
    "scikit-learn": ("scikit-learn", "sklearn"),
}

REQUIRED_PATTERNS = (
    r"\bmust\s+have\b", r"\brequired\b", r"\bminimum\b",
    r"\bmandatory\b", r"\bneed\s+to\b", r"\bneed\b",
    r"\bshould\s+have\b", r"\brequirement\b",
)
PREFERRED_PATTERNS = (
    r"\bpreferred\b", r"\bnice\s+to\s+have\b", r"\bbonus\b",
    r"\bideally\b", r"\bplus\b", r"\bdesired\b",
    r"\bgood\s+to\s+have\b",
)
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "into", "is", "it", "of", "on", "or", "our", "that", "the",
    "their", "this", "to", "with", "will", "you", "your", "we", "work",
    "working", "experience", "ability", "strong", "knowledge", "familiarity",
}
ROLE_FAMILIES = {
    "software_engineering": {"software", "backend", "frontend", "fullstack", "developer", "engineering", "engineer"},
    "data": {"data", "analytics", "analyst", "bi", "business intelligence"},
    "machine_learning": {"machine learning", "ml", "ai", "artificial intelligence", "research scientist"},
    "design": {"design", "designer", "ux", "ui", "product design"},
    "management": {"manager", "management", "lead", "director"},
    "operations": {"operations", "administrator", "support", "reliability", "sre"},
}
SENIORITY_TERMS = {
    "intern": ("intern", "internship"),
    "entry": ("entry level", "junior", "graduate", "new grad"),
    "mid": ("mid level", "mid-level"),
    "senior": ("senior", "sr."),
    "lead": ("staff", "principal", "lead", "architect", "director"),
}


def _normal(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _contains_alias(text: str, alias: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(alias.lower()).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
    return bool(re.search(pattern, text, re.I))


def _catalog_aliases() -> Dict[str, Tuple[str, ...]]:
    aliases = {}
    for canonical, values in SKILL_GROUPS.items():
        aliases[canonical] = tuple(values)
    aliases.update(SKILL_EQUIVALENTS)
    return aliases


def _extract_requirements(job_description: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Extract catalog skills sentence-by-sentence; neutral mentions stay unscored."""
    requirements = []
    sentences = [s.strip() for s in re.split(r"[\n.!?;]+", job_description) if s.strip()]
    aliases = _catalog_aliases()
    seen = {}
    for sentence_index, sentence in enumerate(sentences):
        lowered = _normal(sentence)
        is_required = any(re.search(p, lowered) for p in REQUIRED_PATTERNS)
        is_preferred = any(re.search(p, lowered) for p in PREFERRED_PATTERNS)
        classification = "required" if is_required else "preferred" if is_preferred else "not_assessed"
        for canonical, values in aliases.items():
            if any(_contains_alias(lowered, alias) for alias in values):
                previous = seen.get(canonical)
                # A required mention takes precedence over preferred/neutral.
                priority = {"not_assessed": 0, "preferred": 1, "required": 2}
                if previous and priority[previous["classification"]] >= priority[classification]:
                    continue
                seen[canonical] = {
                    "name": canonical,
                    "classification": classification,
                    "confidence": "high" if classification != "not_assessed" else "medium",
                    "source_sentence": sentence,
                    "sentence_index": sentence_index,
                }
    requirements = sorted(seen.values(), key=lambda item: item["name"])
    notes = []
    if not requirements:
        notes.append("No supported catalog skills were identified in the job description.")
    if any(item["classification"] == "not_assessed" for item in requirements):
        notes.append("Skills mentioned without explicit priority language are informational and excluded from the score.")
    return requirements, notes


def _resume_skill_evidence(resume: Dict[str, Any]) -> Dict[str, Dict[str, List[str]]]:
    result = {}
    for item in resume.get("skills", []):
        name = str(item.get("canonical_name", "")).lower()
        if not name:
            continue
        result[name] = {
            "all": list(dict.fromkeys(item.get("evidence_ids", []))),
            "listed": list(dict.fromkeys(item.get("listed_evidence_ids", []))),
            "demonstrated": list(dict.fromkeys(item.get("demonstrated_evidence_ids", []))),
        }
    return result


def _evidence_items(resume: Dict[str, Any]) -> List[Dict[str, Any]]:
    sections = _sections(resume)
    output = []
    for section_type in ("experience", "projects", "leadership", "volunteer"):
        for item in sections.get(section_type, []):
            if item.get("kind") == "bullet" and _text(item):
                output.append({
                    "section": section_type,
                    "text": _text(item),
                    "evidence_ids": _evidence(item),
                })
    return output


def _token_set(value: str) -> Set[str]:
    tokens = re.findall(r"[a-z][a-z0-9+#.]{1,}", value.lower())
    return {token for token in tokens if token not in STOP_WORDS and len(token) > 2}


def _overlap_score(left: str, right: str) -> float:
    a, b = _token_set(left), _token_set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a))


def _skill_in_bullet(skill: str, bullet: str) -> bool:
    aliases = _catalog_aliases().get(skill, (skill,))
    return any(_contains_alias(bullet, alias) for alias in aliases)


def _role_family(text: str) -> Optional[str]:
    lowered = _normal(text)
    matches = []
    for family, terms in ROLE_FAMILIES.items():
        if any(_contains_alias(lowered, term) for term in terms):
            matches.append(family)
    return matches[0] if len(matches) == 1 else None


def _seniority(text: str) -> Optional[str]:
    lowered = _normal(text)
    for level in ("lead", "senior", "mid", "entry", "intern"):
        if any(_contains_alias(lowered, term) for term in SENIORITY_TERMS[level]):
            return level
    return None


def _seniority_rank(level: Optional[str]) -> Optional[int]:
    return {"intern": 0, "entry": 1, "mid": 2, "senior": 3, "lead": 4}.get(level)


def analyze_quality_v3(resume: Dict[str, Any]) -> Dict[str, Any]:
    """Quality assessment V3 adds evidence coverage and extraction-aware findings.

    Existing quality dimensions/weights remain stable for score comparability.
    """
    result = analyze_quality_v2(resume)
    result["version"] = QUALITY_VERSION
    sections = _sections(resume)
    evidence_ids = {item.get("id") for item in resume.get("evidence", [])}
    findings = result.get("findings", [])

    # Detect empty or near-empty section headings: a heading alone is not evidence
    # that the section is complete.
    for section_type in ("experience", "education", "skills", "projects"):
        section_records = [s for s in resume.get("sections", []) if s.get("type") == section_type]
        empty = [s for s in section_records if not s.get("items")]
        for section in empty:
            heading_ids = [eid for eid in section.get("evidence_ids", []) if eid in evidence_ids]
            findings.append(_finding(
                "empty_section_" + section_type,
                section_type.title() + " section has no extracted content",
                "medium",
                "Check whether this section's content was extracted correctly or add relevant details.",
                heading_ids,
            ))

    # Count skills with explicit demonstration rather than treating all listed
    # skills as equally evidenced. Expose the counts without inventing a score.
    skills = resume.get("skills", [])
    demonstrated = [s for s in skills if s.get("demonstrated_evidence_ids")]
    listed_only = [s for s in skills if s.get("listed_evidence_ids") and not s.get("demonstrated_evidence_ids")]
    result["evidence_summary"] = {
        "recognized_skills": len(skills),
        "demonstrated_skills": len(demonstrated),
        "listed_only_skills": len(listed_only),
        "achievement_bullets": len(_evidence_items(resume)),
        "extraction_warnings": list(resume.get("warnings", [])),
    }
    result["findings"] = findings
    result["disclaimer"] = (
        "A deterministic, evidence-linked resume quality heuristic. It is not an employer-specific ATS score."
    )
    return result


def analyze_job_match_v3(resume: Dict[str, Any], job_description: str) -> Dict[str, Any]:
    """Requirement-, evidence- and responsibility-aware job alignment."""
    if not job_description or len(job_description.strip()) < 40:
        raise ValueError("Please provide a job description with at least 40 characters.")

    requirements, extraction_notes = _extract_requirements(job_description)
    resume_skills = _resume_skill_evidence(resume)
    bullets = _evidence_items(resume)
    classified = {"required": [], "preferred": [], "not_assessed": []}
    matched_details = []
    missing_details = []

    for requirement in requirements:
        name = requirement["name"]
        classification = requirement["classification"]
        classified[classification].append(name)
        if classification == "not_assessed":
            continue
        resume_evidence = resume_skills.get(name, {})
        direct_bullets = [
            bullet for bullet in bullets if _skill_in_bullet(name, bullet["text"])
        ]
        demonstrated_ids = list(dict.fromkeys(
            eid for bullet in direct_bullets for eid in bullet["evidence_ids"]
        ))
        listed_ids = resume_evidence.get("listed", [])
        all_ids = list(dict.fromkeys(resume_evidence.get("all", []) + demonstrated_ids))
        is_present = bool(all_ids)
        detail = {
            "skill": name,
            "classification": classification,
            "status": "demonstrated" if demonstrated_ids else "listed" if listed_ids else "not_found",
            "confidence": requirement["confidence"],
            "resume_evidence_ids": demonstrated_ids or listed_ids or all_ids,
            "job_description_excerpt": requirement["source_sentence"],
        }
        if is_present:
            matched_details.append(detail)
        else:
            missing_details.append(detail)

    required_total = len(classified["required"])
    preferred_total = len(classified["preferred"])
    required_present = sum(1 for item in matched_details if item["classification"] == "required")
    preferred_present = sum(1 for item in matched_details if item["classification"] == "preferred")
    # A listed-only skill earns partial credit; direct experience/project evidence
    # earns full credit. The score never claims a missing skill if it is unassessable.
    required_points = round(45 * sum(
        1.0 if item["status"] == "demonstrated" else 0.55
        for item in matched_details if item["classification"] == "required"
    ) / required_total) if required_total else 45
    preferred_points = round(10 * sum(
        1.0 if item["status"] == "demonstrated" else 0.55
        for item in matched_details if item["classification"] == "preferred"
    ) / preferred_total) if preferred_total else 10

    # Requirement-specific evidence context: compare each JD skill with the
    # candidate's actual bullets, awarding points only for exact/alias evidence.
    required_names = classified["required"]
    demonstrated_required = [
        item for item in matched_details
        if item["classification"] == "required" and item["status"] == "demonstrated"
    ]
    context_points = round(15 * len(demonstrated_required) / required_total) if required_total else 15

    # Responsibilities are matched using transparent token overlap. A low score
    # is never interpreted as proof the candidate lacks the responsibility.
    responsibility_sentences = []
    for sentence in [s.strip() for s in re.split(r"[\n.!?;]+", job_description) if s.strip()]:
        tokens = _token_set(sentence)
        if len(tokens) >= 4 and any(term in sentence.lower() for term in (
            "responsibil", "you will", "you'll", "build", "develop", "design",
            "manage", "lead", "maintain", "analyze", "deliver", "own",
            "implement", "collaborate", "support", "architect",
        )):
            if not any(_contains_alias(sentence.lower(), alias) for values in _catalog_aliases().values() for alias in values):
                responsibility_sentences.append(sentence)
    responsibility_matches = []
    for sentence in responsibility_sentences:
        ranked = sorted(
            ((_overlap_score(sentence, bullet["text"]), bullet) for bullet in bullets),
            key=lambda pair: pair[0], reverse=True
        )
        if ranked and ranked[0][0] >= 0.20:
            score, bullet = ranked[0]
            responsibility_matches.append({
                "job_responsibility": sentence,
                "resume_excerpt": bullet["text"],
                "overlap": round(score, 3),
                "confidence": "medium" if score >= 0.35 else "low",
                "evidence_ids": bullet["evidence_ids"],
            })
    responsibility_total = len(responsibility_sentences)
    responsibility_points = round(
        20 * sum(min(1.0, item["overlap"] / 0.5) for item in responsibility_matches) / responsibility_total
    ) if responsibility_total else 20

    # Role/seniority are signals, not hard gates. Unknown levels are not penalized.
    candidate_text = " ".join(
        [_text(item) for item in _sections(resume).get("experience", [])]
    )
    candidate_role = _role_family(candidate_text)
    target_role = _role_family(job_description)
    role_assessment = "not_assessed"
    role_points = 0
    if candidate_role and target_role:
        role_assessment = "aligned" if candidate_role == target_role else "different_signal"
        role_points = 5 if candidate_role == target_role else 0

    candidate_level = _seniority(candidate_text)
    target_level = _seniority(job_description)
    seniority_assessment = "not_assessed"
    seniority_points = 0
    if candidate_level and target_level:
        c_rank, t_rank = _seniority_rank(candidate_level), _seniority_rank(target_level)
        seniority_assessment = (
            "aligned" if c_rank >= t_rank else "below_target_signal"
        )
        seniority_points = 5 if c_rank >= t_rank else 0

    # Unknown role/seniority signals are neutral, not deductions. Keep the
    # category weights fixed so the displayed breakdown always totals 100.
    role_seniority_assessed = int(bool(candidate_role and target_role)) + int(bool(candidate_level and target_level))
    role_seniority_points = role_points + seniority_points
    if role_seniority_assessed == 0:
        role_seniority_points = 10
    elif role_seniority_assessed == 1:
        role_seniority_points += 5

    score = min(100, required_points + preferred_points + context_points +
                responsibility_points + role_seniority_points)
    matched_required = sorted(
        item["skill"] for item in matched_details if item["classification"] == "required"
    )
    missing_required = sorted(
        item["skill"] for item in missing_details if item["classification"] == "required"
    )
    matched_preferred = sorted(
        item["skill"] for item in matched_details if item["classification"] == "preferred"
    )
    missing_preferred = sorted(
        item["skill"] for item in missing_details if item["classification"] == "preferred"
    )
    findings = []
    if missing_required:
        findings.append(_finding(
            "required_skills_not_detected",
            "Some explicitly required catalog skills were not detected",
            "high",
            "Only add a skill if you genuinely have it; otherwise use the gap to guide learning and project work.",
            detail=", ".join(missing_required),
        ))
    if any(item["status"] == "listed" for item in matched_details):
        findings.append(_finding(
            "skills_listed_without_demonstration",
            "Some matched skills appear only in the skills list",
            "medium",
            "Add a truthful experience or project example showing how you used these skills.",
            [eid for item in matched_details if item["status"] == "listed" for eid in item["resume_evidence_ids"]],
            detail=", ".join(item["skill"] for item in matched_details if item["status"] == "listed"),
        ))
    if not responsibility_sentences:
        findings.append(_finding(
            "responsibilities_not_extracted",
            "Job responsibilities could not be isolated confidently",
            "low",
            "Review the responsibilities manually; this score does not assume they are absent.",
        ))
    if extraction_notes:
        findings.append(_finding(
            "job_description_extraction_limits",
            "Some job-description content was not classified as a scored requirement",
            "low",
            "Review informational or uncategorized skills manually; they were not treated as missing.",
            detail=" ".join(extraction_notes),
        ))

    breakdown = [
        {"key": "required_skills", "label": "Required skill coverage", "earned": required_points, "possible": 45, "deducted": 45-required_points},
        {"key": "preferred_skills", "label": "Preferred skill coverage", "earned": preferred_points, "possible": 10, "deducted": 10-preferred_points},
        {"key": "skill_demonstration", "label": "Skills demonstrated in experience/projects", "earned": context_points, "possible": 15, "deducted": 15-context_points},
        {"key": "responsibility_alignment", "label": "Responsibility alignment", "earned": responsibility_points, "possible": 20, "deducted": 20-responsibility_points},
        {"key": "role_seniority", "label": "Role and seniority signals", "earned": role_seniority_points, "possible": 10, "deducted": 10-role_seniority_points},
    ]
    return {
        "score": score,
        "version": MATCH_VERSION,
        "breakdown": breakdown,
        "requirements": requirements,
        "matched_required_skills": matched_required,
        "missing_required_skills": missing_required,
        "matched_preferred_skills": matched_preferred,
        "missing_preferred_skills": missing_preferred,
        "not_assessed": sorted(classified["not_assessed"]),
        "skill_matches": matched_details,
        "skill_gaps": missing_details,
        "responsibility_matches": responsibility_matches,
        "role_alignment": {"candidate_family": candidate_role, "target_family": target_role, "assessment": role_assessment},
        "seniority_alignment": {"candidate_level": candidate_level, "target_level": target_level, "assessment": seniority_assessment},
        "findings": findings,
        "summary": "Detected {0} of {1} explicit required catalog skills; {2} responsibility matches found.".format(
            len(matched_required), required_total, len(responsibility_matches)
        ),
        "disclaimer": "A deterministic evidence-based estimate. Semantic similarity is limited to explicit aliases and transparent lexical overlap; this is not an employer ATS ranking.",
    }
