from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .parser_v2 import SKILL_GROUPS

QUALITY_VERSION = "quality-v4"
MATCH_VERSION = "match-v4"

WEIGHTS = {
    "evidence_quality": 25,
    "experience_depth": 20,
    "impact": 20,
    "skills_evidence": 15,
    "education": 8,
    "structure": 7,
    "readability": 5,
}

ACTION_VERBS = {
    "built", "developed", "designed", "implemented", "engineered", "created",
    "automated", "optimized", "improved", "reduced", "increased", "delivered",
    "led", "launched", "integrated", "migrated", "deployed", "architected",
    "analyzed", "managed", "owned", "maintained", "streamlined", "generated",
    "configured", "secured", " mentored".strip(),
}
VAGUE_STARTS = {"worked", "helped", "responsible", "involved", "participated", "assisted"}
# Require a quantity plus a unit or concrete scale noun. The lookahead
# after '%' deliberately avoids the old word-boundary bug (95% ends in a
# non-word character). This also recognizes phrases such as "30+ Athena SQL queries".
METRIC_RE = re.compile(
    r"(?:"
    r"(?<![a-z0-9])\d+(?:\.\d+)?\s*(?:%|percent\b|x\b|ms\b|"
    r"seconds?\b|minutes?\b|hours?\b|days?\b|k\b|m\b|million\b|billion\b)"
    r"(?![a-z0-9])"
    r"|(?<![a-z0-9])\d+(?:\.\d+)?\+?\s+"
    r"(?:[a-z][a-z0-9+#.-]*\s+){0,3}"
    r"(?:users?|customers?|requests?|records?|services?|teams?|members?|"
    r"datasets?|projects?|employees?|participants?|classes?|queries?|"
    r"transactions?|workflows?|systems?|APIs?|students?|events?)(?![a-z0-9])"
    r"|\b(?:reduced|increased|improved|cut|saved|boosted|raised|lowered)\b"
    r".{0,60}\bby\s+\d+(?:\.\d+)?\s*(?:%|percent|x|ms)?(?![a-z0-9])"
    r")",
    re.I,
)
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "of", "on", "or", "our", "that", "the", "their",
    "this", "to", "with", "will", "you", "your", "we", "using", "use",
    "experience", "ability", "work", "working", "responsible",
}
REQUIRED_CUES = (
    r"\brequired\b", r"\bmust\b", r"\bmandatory\b", r"\bminimum\b",
    r"\bneed to\b", r"\bmust have\b", r"\brequirements?\b",
)
PREFERRED_CUES = (
    r"\bpreferred\b", r"\bnice to have\b", r"\bbonus\b", r"\bideally\b",
    r"\bdesired\b", r"\bgood to have\b", r"\bplus\b",
)
ROLE_TERMS = {
    "software_engineering": ("software engineer", "software developer", "backend", "frontend", "full stack", "fullstack", "developer", "engineering"),
    "data": ("data scientist", "data analyst", "analytics", "business intelligence", "data engineer"),
    "machine_learning": ("machine learning", " ml engineer", " ai engineer", "artificial intelligence"),
    "design": ("product designer", "ux designer", "ui designer", "user experience"),
    "product": ("product manager", "product owner"),
    "operations": ("operations", "site reliability", "sre", "technical support"),
}
LEVEL_TERMS = {
    "intern": ("intern", "internship"),
    "entry": ("entry level", "junior", "graduate", "new grad", "associate"),
    "mid": ("mid level", "mid-level"),
    "senior": ("senior", "sr."),
    "lead": ("staff", "principal", "lead", "director", "architect"),
}
LEVEL_RANK = {"intern": 0, "entry": 1, "mid": 2, "senior": 3, "lead": 4}


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _has(text: str, phrase: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(phrase.lower()).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
    return bool(re.search(pattern, text, re.I))


def _sections(resume: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    output: Dict[str, List[Dict[str, Any]]] = {}
    for section in resume.get("sections", []):
        output.setdefault(section.get("type", "other"), []).extend(section.get("items", []))
    return output


def _item_text(item: Dict[str, Any]) -> str:
    return str(item.get("text", "")).strip()


def _item_ids(item: Dict[str, Any]) -> List[str]:
    ids = item.get("evidence_ids") or ([item.get("evidence_id")] if item.get("evidence_id") else [])
    return list(dict.fromkeys([value for value in ids if value]))


def _bullets(sections: Dict[str, List[Dict[str, Any]]], kinds: Tuple[str, ...]) -> List[Dict[str, Any]]:
    output = []
    for kind in kinds:
        for item in sections.get(kind, []):
            text = _item_text(item)
            if text and (item.get("kind") == "bullet" or len(text.split()) >= 7):
                output.append({"section": kind, "text": text, "evidence_ids": _item_ids(item)})
    return output


def _finding(code: str, title: str, severity: str, recommendation: str,
             evidence_ids: Optional[List[str]] = None, detail: Optional[str] = None) -> Dict[str, Any]:
    result = {
        "code": code, "title": title, "severity": severity,
        "recommendation": recommendation,
        "evidence_ids": list(dict.fromkeys(evidence_ids or [])),
    }
    if detail:
        result["detail"] = detail
    return result


def _component(key: str, earned: int, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    possible = WEIGHTS[key]
    earned = max(0, min(possible, int(earned)))
    return {
        "key": key, "label": key.replace("_", " ").title(),
        "earned": earned, "possible": possible, "deducted": possible - earned,
    }


def _first_verb(text: str) -> Optional[str]:
    words = re.findall(r"[a-z]+", _norm(text))
    if not words:
        return None
    return words[0]


def _score_bullet_quality(bullet: Dict[str, Any]) -> int:
    text = bullet["text"]
    words = re.findall(r"\b\w+\b", text)
    if len(words) < 5:
        return 0
    verb = _first_verb(text)
    score = 0
    if verb in ACTION_VERBS:
        score += 2
    elif verb not in VAGUE_STARTS:
        score += 1
    if len(words) >= 10:
        score += 1
    if len(words) >= 16:
        score += 1
    if METRIC_RE.search(text):
        score += 2
    if re.search(r"\b(?:by|through|using|with|across|for)\b", text, re.I):
        score += 1
    return min(7, score)


def analyze_quality_v4(resume: Dict[str, Any]) -> Dict[str, Any]:
    """Fresh content-first quality scoring. Does not call V2 or V3 scoring."""
    sections = _sections(resume)
    candidate = resume.get("candidate", {})
    findings: List[Dict[str, Any]] = []
    valid_ids = {item.get("id") for item in resume.get("evidence", [])}
    achievements = _bullets(sections, ("experience", "projects", "leadership", "volunteer"))
    experience = _bullets(sections, ("experience",))
    project_bullets = _bullets(sections, ("projects",))
    all_bullets = achievements
    components = []

    # Evidence quality: proportion of substantive bullets with clear action,
    # context and/or measurable outcome. It is deliberately not section counting.
    quality_values = [_score_bullet_quality(item) for item in all_bullets]
    if all_bullets:
        evidence_score = round(WEIGHTS["evidence_quality"] * sum(quality_values) /
                               float(7 * len(all_bullets)))
    else:
        evidence_score = 0
        findings.append(_finding(
            "evidence_quality_no_achievement_bullets",
            "No substantive achievement bullets were extracted", "high",
            "Add concise bullets describing actions, context, and outcomes in experience or projects.",
        ))
    weak_bullets = [
        item for item, value in zip(all_bullets, quality_values) if value <= 2
    ]
    if weak_bullets:
        findings.append(_finding(
            "evidence_quality_weak_bullets",
            "Some bullets lack clear action, context, or outcome",
            "medium",
            "Rewrite these bullets to explain what you did, how you did it, and what changed.",
            [eid for item in weak_bullets for eid in item["evidence_ids"]],
            "{0} of {1} assessed bullets have limited detail.".format(len(weak_bullets), len(all_bullets)),
        ))
    components.append(_component("evidence_quality", evidence_score, findings))

    # Experience depth: actual experience bullets, role context and breadth.
    role_context_items = [
        item for item in sections.get("experience", [])
        if item.get("kind") != "bullet" and _item_text(item)
    ]
    depth_score = min(12, len(experience) * 3)
    if experience and role_context_items:
        depth_score += 4
    if len(experience) >= 3:
        depth_score += 2
    if project_bullets:
        depth_score += min(2, len(project_bullets))
    depth_score = min(20, depth_score)
    if not experience:
        findings.append(_finding(
            "experience_depth_no_work_bullets",
            "No work-experience achievement bullets were identified", "medium",
            "If you have employment or internship experience, include your role, organization, dates and contributions.",
        ))
    elif len(experience) < 2:
        findings.append(_finding(
            "experience_depth_limited",
            "Limited work-experience detail was extracted", "medium",
            "Add another specific contribution where it reflects your actual work.",
            [eid for item in experience for eid in item["evidence_ids"]],
        ))
    components.append(_component("experience_depth", depth_score, findings))

    # Impact: count measurable outcome evidence, scope indicators, and causal
    # statements. A number alone is not automatically treated as impact.
    metric_bullets = [item for item in all_bullets if METRIC_RE.search(item["text"])]
    incomplete_metric_bullets = [
        item for item in all_bullets
        if re.search(r"\bby\s+\d+(?:\.\d+)?\s*$", item["text"], re.I)
    ]
    if incomplete_metric_bullets:
        findings.append(_finding(
            "incomplete_numeric_claim",
            "One or more achievement bullets may have a truncated numeric result",
            "medium",
            "Check the original resume and restore the missing unit or outcome only if it is accurate.",
            [eid for item in incomplete_metric_bullets for eid in item["evidence_ids"]],
            "{0} bullet(s) end with a number but no visible unit.".format(len(incomplete_metric_bullets)),
        ))
    outcome_bullets = [
        item for item in all_bullets
        if re.search(r"\b(?:reduced|increased|improved|accelerated|saved|cut|boosted|"
                     r"raised|lowered|eliminated|streamlined)\b", item["text"], re.I)
    ]
    scope_bullets = [
        item for item in all_bullets
        if re.search(r"\b(?:users|customers|requests|datasets|services|teams|members|"
                     r"records|transactions|classes|systems|workflows)\b", item["text"], re.I)
    ]
    impact_score = min(8, len(metric_bullets) * 3)
    impact_score += min(6, len(outcome_bullets) * 2)
    impact_score += min(6, len(scope_bullets) * 2)
    impact_score = min(20, impact_score)
    if not metric_bullets:
        findings.append(_finding(
            "impact_no_quantified_outcomes",
            "No measurable outcomes were confidently detected", "medium",
            "Where truthful, add scale or results such as latency, adoption, volume, cost, time saved, or accuracy.",
            [eid for item in all_bullets for eid in item["evidence_ids"]][:20],
        ))
    components.append(_component("impact", impact_score, findings))

    skills = resume.get("skills", [])
    demonstrated = [item for item in skills if item.get("demonstrated_evidence_ids")]
    listed_only = [item for item in skills if item.get("listed_evidence_ids") and not item.get("demonstrated_evidence_ids")]
    # Credit is tied to skills shown in work/projects, with a smaller contribution
    # for a skills section. Repeated aliases do not multiply the count.
    # Diminishing returns prevent a long skills inventory from maxing this
    # component. Demonstrated use carries more weight than list-only mentions.
    skill_score = min(12, int(round(len(demonstrated) * 0.6))) + min(
        3, int(round(len(listed_only) * 0.25))
    )
    if not skills:
        findings.append(_finding(
            "skills_none_detected", "No recognized skills were extracted", "medium",
            "Add a focused skills section containing relevant skills you can substantiate.",
        ))
    elif listed_only:
        findings.append(_finding(
            "skills_listed_only",
            "Some skills appear only in the skills list", "low",
            "Where relevant, connect listed skills to a real project or work example.",
            [eid for item in listed_only for eid in item.get("listed_evidence_ids", [])][:20],
            "{0} listed-only skills detected.".format(len(listed_only)),
        ))
    components.append(_component("skills_evidence", skill_score, findings))

    education_items = sections.get("education", [])
    education_text = " ".join(_item_text(item) for item in education_items)
    education_score = 0
    if education_items:
        education_score += 2
        if re.search(r"\b(?:bachelors?|bachelor['’]s|masters?|master['’]s|ph\.?d|b\.?tech|m\.?tech|degree|diploma)\b", education_text, re.I):
            education_score += 3
        if re.search(r"\b(?:university|college|institute|school)\b", education_text, re.I):
            education_score += 2
        if re.search(r"\b(?:19|20)\d{2}\b", education_text):
            education_score += 1
    else:
        findings.append(_finding(
            "education_not_extracted", "Education details were not extracted", "low",
            "Include your qualification and institution if relevant to the role.",
        ))
    components.append(_component("education", education_score, findings))

    # Structure rewards recognizable, non-empty, useful sections; it is a small
    # part of the total so headings alone cannot dominate the result.
    useful = ("experience", "education", "skills", "projects")
    populated = [kind for kind in useful if any(_item_text(item) for item in sections.get(kind, []))]
    structure_score = min(4, len(populated))
    if sections.get("summary"):
        structure_score += 1
    if candidate.get("email") and candidate.get("name"):
        structure_score += 1
    if candidate.get("profile_urls"):
        structure_score += 1
    if len(populated) < 3:
        findings.append(_finding(
            "structure_sections_limited", "Some common resume sections were not identified",
            "low", "Use clear headings and include the sections relevant to your experience.",
        ))
    components.append(_component("structure", structure_score, findings))

    document = resume.get("document", {})
    warnings = resume.get("warnings", [])
    word_count = int(document.get("word_count") or 0)
    pages = document.get("pages")
    readability_score = 5
    if word_count < 150:
        readability_score -= 2
    elif word_count > 1000:
        readability_score -= 1
    if pages and pages > 3:
        readability_score -= 1
    if warnings:
        readability_score -= min(2, len(warnings))
    readability_score = max(0, readability_score)
    if warnings:
        findings.append(_finding(
            "readability_extraction_warnings", "Document extraction warnings need review",
            "low", "Check the parsed resume text for missing, truncated, or incorrectly ordered content.",
            detail=" ".join(str(value) for value in warnings),
        ))
    components.append(_component("readability", readability_score, findings))

    score = sum(item["earned"] for item in components)
    for finding in findings:
        finding["evidence_ids"] = [
            eid for eid in finding.get("evidence_ids", []) if eid in valid_ids
        ]
    return {
        "score": score,
        "version": QUALITY_VERSION,
        "breakdown": components,
        "findings": findings,
        "strengths": [
            {
                "title": "Demonstrated {0} recognized skills".format(len(demonstrated)),
                "evidence_ids": list(dict.fromkeys(
                    eid for skill in demonstrated
                    for eid in skill.get("demonstrated_evidence_ids", [])
                ))[:20],
            }
        ] if demonstrated else [],
        "evidence_summary": {
            "achievement_bullets": len(all_bullets),
            "experience_bullets": len(experience),
            "project_bullets": len(project_bullets),
            "measurable_bullets": len(metric_bullets),
            "incomplete_numeric_claims": len(incomplete_metric_bullets),
            "demonstrated_skills": len(demonstrated),
            "listed_only_skills": len(listed_only),
            "extraction_warnings": list(warnings),
        },
        "summary": (
            "Strong evidence across several dimensions; tailor the resume to each role."
            if score >= 80 else
            "A reasonable foundation; strengthen the evidence and measurable outcomes."
            if score >= 60 else
            "The resume needs clearer, more specific evidence of contributions and outcomes."
            if score >= 40 else
            "The extracted resume content is too limited or generic to support a strong assessment."
        ),
        "disclaimer": "A deterministic content-quality heuristic, not an employer-specific ATS score.",
    }


def _skill_aliases() -> Dict[str, Tuple[str, ...]]:
    aliases = {}
    for canonical, values in SKILL_GROUPS.items():
        aliases[canonical] = tuple(values)
    aliases.update({
        "rest api": ("rest api", "restful api", "rest apis", "restful services"),
        "javascript": ("javascript", "js", "ecmascript"),
        "typescript": ("typescript", "ts"),
        "node.js": ("node.js", "node js", "nodejs"),
        "postgresql": ("postgresql", "postgres"),
        "mongodb": ("mongodb", "mongo db"),
        "machine learning": ("machine learning", "ml"),
        "scikit-learn": ("scikit-learn", "sklearn"),
    })
    return aliases


def _extract_jd_lines(job_description: str) -> List[Dict[str, str]]:
    lines = [re.sub(r"^\s*(?:[-*•●▪]|\d+[.)])\s*", "", line).strip()
             for line in job_description.splitlines()]
    current = "not_assessed"
    output = []
    for line in lines:
        if not line:
            continue
        heading = _norm(line).strip(": -")
        if re.search(r"\b(required qualifications?|requirements?|must have|what you need)\b", heading):
            current = "required"
            continue
        if re.search(r"\b(preferred qualifications?|nice to have|desired qualifications?)\b", heading):
            current = "preferred"
            continue
        if re.search(r"\b(responsibilities|what you will do|your role|key duties)\b", heading):
            current = "responsibility"
            continue
        if re.search(r"\b(about the company|about us|benefits|what we offer)\b", heading):
            current = "not_assessed"
            continue
        output.append({"text": line, "classification": current})
    return output


def _extract_jd_skills(job_description: str) -> List[Dict[str, Any]]:
    aliases = _skill_aliases()
    found: Dict[str, Dict[str, Any]] = {}
    lines = _extract_jd_lines(job_description)
    for index, item in enumerate(lines):
        text = item["text"]
        lowered = _norm(text)
        classification = item["classification"]
        if classification not in ("required", "preferred"):
            if any(re.search(pattern, lowered) for pattern in REQUIRED_CUES):
                classification = "required"
            elif any(re.search(pattern, lowered) for pattern in PREFERRED_CUES):
                classification = "preferred"
            else:
                classification = "not_assessed"
        for canonical, values in aliases.items():
            if any(_has(lowered, alias) for alias in values):
                priority = {"not_assessed": 0, "preferred": 1, "required": 2}
                previous = found.get(canonical)
                if previous and priority[previous["classification"]] >= priority[classification]:
                    continue
                found[canonical] = {
                    "name": canonical, "classification": classification,
                    "source_sentence": text, "line_index": index,
                }
    return sorted(found.values(), key=lambda item: item["name"])


def _resume_skill_map(resume: Dict[str, Any]) -> Dict[str, Dict[str, List[str]]]:
    result = {}
    for skill in resume.get("skills", []):
        name = _norm(skill.get("canonical_name", ""))
        if name:
            result[name] = {
                "all": list(dict.fromkeys(skill.get("evidence_ids", []))),
                "listed": list(dict.fromkeys(skill.get("listed_evidence_ids", []))),
                "demonstrated": list(dict.fromkeys(skill.get("demonstrated_evidence_ids", []))),
            }
    return result


def _tokens(value: str) -> Set[str]:
    tokens = re.findall(r"[a-z][a-z0-9+#.]{1,}", _norm(value))
    return {token for token in tokens if token not in STOP_WORDS and len(token) > 2}


def _similarity(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    # Dice coefficient penalizes long job descriptions and long resume bullets
    # less aggressively than one-sided token recall.
    return (2.0 * len(a & b)) / float(len(a) + len(b))


def _role(text: str) -> Optional[str]:
    lowered = _norm(text)
    matches = []
    for family, phrases in ROLE_TERMS.items():
        if any(_has(lowered, phrase) for phrase in phrases):
            matches.append(family)
    return matches[0] if len(matches) == 1 else None


def _level(text: str) -> Optional[str]:
    lowered = _norm(text)
    for level in ("lead", "senior", "mid", "entry", "intern"):
        if any(_has(lowered, phrase) for phrase in LEVEL_TERMS[level]):
            return level
    return None


def analyze_job_match_v4(resume: Dict[str, Any], job_description: str) -> Dict[str, Any]:
    """Fresh job-specific assessment with persistent JD heading context and normalized coverage."""
    if not job_description or len(job_description.strip()) < 40:
        raise ValueError("Please provide a job description with at least 40 characters.")

    sections = _sections(resume)
    skills = _resume_skill_map(resume)
    jd_skills = _extract_jd_skills(job_description)
    resume_bullets = _bullets(sections, ("experience", "projects", "leadership", "volunteer"))
    required = [item for item in jd_skills if item["classification"] == "required"]
    preferred = [item for item in jd_skills if item["classification"] == "preferred"]
    informational = [item for item in jd_skills if item["classification"] == "not_assessed"]

    skill_matches = []
    skill_gaps = []
    for requirement in required + preferred:
        name = requirement["name"]
        evidence = skills.get(name, {})
        direct = [item for item in resume_bullets
                  if any(_has(item["text"], alias) for alias in _skill_aliases().get(name, (name,)))]
        demonstrated_ids = list(dict.fromkeys(
            eid for item in direct for eid in item["evidence_ids"]
        ))
        listed_ids = evidence.get("listed", [])
        all_ids = list(dict.fromkeys(evidence.get("all", []) + demonstrated_ids))
        status = "demonstrated" if demonstrated_ids else "listed" if listed_ids else "not_found"
        detail = {
            "skill": name, "classification": requirement["classification"],
            "status": status, "resume_evidence_ids": demonstrated_ids or listed_ids or all_ids,
            "job_description_excerpt": requirement["source_sentence"],
        }
        if status == "not_found":
            skill_gaps.append(detail)
        else:
            skill_matches.append(detail)

    def coverage(items: List[Dict[str, Any]], weight: int) -> Tuple[Optional[int], List[Dict[str, Any]]]:
        if not items:
            return None, []
        points = sum(
            1.0 if next((m["status"] for m in skill_matches if m["skill"] == item["name"]), "not_found") == "demonstrated"
            else 0.65 if any(m["skill"] == item["name"] for m in skill_matches)
            else 0.0
            for item in items
        )
        return int(round(weight * points / len(items))), []

    required_score, _ = coverage(required, 40)
    preferred_score, _ = coverage(preferred, 15)

    # Keep all job responsibility lines, including those that mention skills.
    jd_lines = _extract_jd_lines(job_description)
    responsibility_lines = [
        item["text"] for item in jd_lines
        if item["classification"] == "responsibility"
        or re.search(r"\b(you will|responsibilities include|responsible for|build|develop|"
                     r"design|implement|maintain|manage|analy[sz]e|deliver|own|lead|"
                     r"collaborate|support|architect|optimize)\b", item["text"], re.I)
    ]
    responsibility_lines = list(dict.fromkeys(
        line for line in responsibility_lines if len(_tokens(line)) >= 4
    ))
    responsibility_matches = []
    for line in responsibility_lines:
        ranked = sorted(
            ((_similarity(line, bullet["text"]), bullet) for bullet in resume_bullets),
            key=lambda pair: pair[0], reverse=True,
        )
        if ranked and ranked[0][0] >= 0.12:
            value, bullet = ranked[0]
            responsibility_matches.append({
                "job_responsibility": line,
                "resume_excerpt": bullet["text"],
                "similarity": round(value, 3),
                "evidence_ids": bullet["evidence_ids"],
            })
    responsibility_score = None
    if responsibility_lines:
        matched_by_line = {item["job_responsibility"]: item["similarity"] for item in responsibility_matches}
        responsibility_score = int(round(25 * sum(
            min(1.0, matched_by_line.get(line, 0.0) / 0.35)
            for line in responsibility_lines
        ) / len(responsibility_lines)))

    # Candidate role comes from actual experience role-title lines, not all bullet text.
    title_text = " ".join(
        _item_text(item) for item in sections.get("experience", [])
        if item.get("kind") != "bullet"
    )
    candidate_role = _role(title_text)
    target_role = _role(job_description)
    candidate_level = _level(title_text)
    target_level = _level(job_description)
    role_assessment = "not_assessed"
    seniority_assessment = "not_assessed"
    role_level_score = None
    if candidate_role and target_role:
        role_assessment = "aligned" if candidate_role == target_role else "different_signal"
    if candidate_level and target_level:
        seniority_assessment = (
            "aligned" if LEVEL_RANK[candidate_level] >= LEVEL_RANK[target_level]
            else "below_target_signal"
        )
    assessed_role_signals = []
    if candidate_role and target_role:
        assessed_role_signals.append(1.0 if candidate_role == target_role else 0.0)
    if candidate_level and target_level:
        assessed_role_signals.append(
            1.0 if LEVEL_RANK[candidate_level] >= LEVEL_RANK[target_level] else 0.0
        )
    if assessed_role_signals:
        role_level_score = int(round(10 * sum(assessed_role_signals) / len(assessed_role_signals)))

    # Normalize only over dimensions with sufficient source information. Unassessed
    # dimensions do not earn free points and do not count as zero.
    dimensions = [
        ("required_skills", required_score, 40),
        ("preferred_skills", preferred_score, 15),
        ("responsibility_alignment", responsibility_score, 25),
        ("role_seniority", role_level_score, 10),
    ]
    active_weight = sum(weight for _, value, weight in dimensions if value is not None)
    earned = sum(value for _, value, _ in dimensions if value is not None)
    provisional_score = int(round(100.0 * earned / active_weight)) if active_weight else None
    # A role-title/seniority signal alone is too thin to publish as a match
    # score. Require at least 25 of 90 weighted points to be assessed.
    minimum_assessed_weight = 25
    score_is_assessable = active_weight >= minimum_assessed_weight
    score = provisional_score if score_is_assessable else None
    score_status = "assessed" if score_is_assessable else "insufficient_data"
    breakdown = []
    for key, value, weight in dimensions:
        assessed = value is not None
        breakdown.append({
            "key": key, "label": key.replace("_", " ").title(),
            "earned": value if assessed else None,
            "possible": weight if assessed else 0,
            "weight": weight,
            "deducted": weight - value if assessed else None,
            "assessed": assessed,
        })

    findings = []
    if not score_is_assessable:
        findings.append(_finding(
            "job_match_insufficient_coverage",
            "Not enough job-description evidence to calculate a reliable match score",
            "medium",
            "Provide a fuller job description with explicit qualifications and responsibilities. "
            "The provisional figure is not presented as a final match score.",
            detail="Assessed {0} of 90 available weighted points; at least {1} are required.".format(
                active_weight, minimum_assessed_weight
            ),
        ))
    missing_required = [item["skill"] for item in skill_gaps if item["classification"] == "required"]
    missing_preferred = [item["skill"] for item in skill_gaps if item["classification"] == "preferred"]
    if missing_required:
        findings.append(_finding(
            "required_skills_gaps", "Some explicitly required skills were not found",
            "high", "Only add these skills if you genuinely have them; otherwise treat them as learning gaps.",
            detail=", ".join(missing_required),
        ))
    if missing_preferred:
        findings.append(_finding(
            "preferred_skills_gaps", "Some preferred skills were not found",
            "low", "Preferred skills are differentiators; do not claim skills you have not used.",
            detail=", ".join(missing_preferred),
        ))
    if not required and not preferred:
        findings.append(_finding(
            "job_skills_not_classified", "No explicit required or preferred catalog skills were identified",
            "low", "Review the job description manually; neutral skill mentions were not treated as missing.",
            detail="Informational skills: " + ", ".join(item["name"] for item in informational),
        ))
    if responsibility_lines and not responsibility_matches:
        findings.append(_finding(
            "responsibility_matches_not_found", "No strong lexical responsibility matches were found",
            "medium", "Review these duties manually. A low overlap score is not proof that you lack the experience.",
        ))
    if not responsibility_lines:
        findings.append(_finding(
            "responsibilities_not_assessed", "Responsibilities could not be isolated confidently",
            "low", "Review the responsibility section manually; this dimension was excluded from the score.",
        ))
    if role_level_score is None:
        findings.append(_finding(
            "role_seniority_not_assessed", "Role or seniority alignment could not be assessed",
            "low", "The score excludes role/seniority signals when the resume or job description lacks clear titles.",
        ))

    return {
        "score": score,
        "score_status": score_status,
        "provisional_score": provisional_score if not score_is_assessable else None,
        "minimum_assessed_weight": minimum_assessed_weight,
        "version": MATCH_VERSION,
        "score_method": "normalized_assessed_dimensions",
        "assessment_coverage": {
            "assessed_weight": active_weight,
            "available_weight": 90,
            "required_skills": len(required),
            "preferred_skills": len(preferred),
            "informational_skills": len(informational),
            "responsibility_statements": len(responsibility_lines),
            "responsibility_matches": len(responsibility_matches),
        },
        "breakdown": breakdown,
        "requirements": jd_skills,
        "matched_required_skills": sorted(item["skill"] for item in skill_matches if item["classification"] == "required"),
        "missing_required_skills": sorted(missing_required),
        "matched_preferred_skills": sorted(item["skill"] for item in skill_matches if item["classification"] == "preferred"),
        "missing_preferred_skills": sorted(missing_preferred),
        "not_assessed": sorted(item["name"] for item in informational),
        "skill_matches": skill_matches,
        "skill_gaps": skill_gaps,
        "responsibility_matches": responsibility_matches,
        "role_alignment": {
            "candidate_family": candidate_role, "target_family": target_role,
            "assessment": role_assessment,
        },
        "seniority_alignment": {
            "candidate_level": candidate_level, "target_level": target_level,
            "assessment": seniority_assessment,
        },
        "findings": findings,
        "summary": (
            "Insufficient evidence for a reliable match score. Assessed {0}% of the available weighted dimensions; "
            "{1} required and {2} preferred skills identified.".format(
                int(round(100.0 * active_weight / 90)) if active_weight else 0,
                len(required), len(preferred),
            ) if not score_is_assessable else
            "Assessed {0}% of the available weighted dimensions; {1} required and {2} preferred skills identified.".format(
                int(round(100.0 * active_weight / 90)) if active_weight else 0,
                len(required), len(preferred),
            )
        ),
        "disclaimer": "A deterministic evidence-based estimate. Responsibility matching uses lexical overlap, not semantic embeddings or an employer ATS ranking.",
    }
