from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .parser_v2 import SKILL_GROUPS

QUALITY_VERSION = "quality-v4.5"
MATCH_VERSION = "match-v4.5"

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
    "software_engineering": (
        "software engineer", "software development engineer", "software developer",
        "software development engineer in test", "sdet", "test automation engineer",
        "qa automation engineer", "backend", "frontend", "full stack", "fullstack",
        "developer", "engineering",
    ),
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

PROGRAMMING_LANGUAGE_SKILLS = (
    "c++", "c#", "java", "kotlin", "python", "javascript", "typescript",
    "go", "rust", "ruby", "php", "swift",
)
RELATIONAL_DATABASE_SKILLS = ("postgresql", "mysql")


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
    """Return achievement bullets only; headings and role metadata are context, not achievements."""
    output = []
    for kind in kinds:
        for item in sections.get(kind, []):
            text = _item_text(item)
            if text and item.get("kind") == "bullet":
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
        "data structures and algorithms": ("data structures and algorithms", "data structures & algorithms", "data structures", "algorithms", "dsa"),
        "object-oriented programming": ("object-oriented programming", "object oriented programming", "object-oriented design", "object oriented design", "oop", "ood"),
        "api development": ("api development", "api design", "api implementation"),
        "http": ("http", "http protocols"),
        "relational databases": ("relational databases", "relational database"),
        "database design": ("database design",),
        "indexing": ("indexing", "database indexing"),
        "query optimization": ("query optimization", "sql optimization"),
        "joins": ("joins", "sql joins", "database joins"),
        "concurrency": ("concurrency", "multithreading", "multi-threading"),
        "distributed systems": ("distributed systems",),
        "gradle": ("gradle",),
        "maven": ("maven",),
        "unit testing": ("unit testing", "unit tests"),
        "integration testing": ("integration testing", "integration tests"),
    })
    return aliases


def _is_analyzer_payload(value: str) -> bool:
    """Identify serialized analyzer output accidentally supplied as a job description."""
    try:
        payload = json.loads(value)
    except (TypeError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    analyzer_keys = {
        "score", "breakdown", "requirements", "responsibility_matches",
        "skill_matches", "skill_gaps", "assessment_coverage", "version",
        "quality", "job_match", "resume", "candidate",
    }
    return len(analyzer_keys.intersection(payload.keys())) >= 2


def _clean_job_description(job_description: str) -> Tuple[str, List[str]]:
    """Remove analyzer-result JSON contamination while preserving genuine JD text."""
    raw = str(job_description or "").strip()
    if _is_analyzer_payload(raw):
        return "", [
            "The supplied content is serialized analyzer output, not a readable job description."
        ]
    kept = []
    removed = False
    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if not stripped:
            kept.append(line)
            continue
        if _is_analyzer_payload(stripped) or re.search(
            r'"(?:score|breakdown|responsibility_matches|skill_matches|assessment_coverage|quality|job_match)"\s*:',
            stripped,
        ):
            removed = True
            continue
        kept.append(line)
    warnings = (
        ["Structured analyzer-result content was removed from the job description; review the remaining text."]
        if removed else []
    )
    return "\n".join(kept).strip(), warnings


def _normalize_jd_lines(job_description: str) -> List[str]:
    """Normalize common Markdown/plain-text JD formatting without discarding content."""
    text = str(job_description or "").replace("\r\n", "\n").replace("\r", "\n")
    # Markdown heading markers can be inline when a frontend collapses newlines.
    text = re.sub(r"\s*#{1,6}\s*", "\\n", text)
    text = text.replace("**", "").replace("__", "")
    # Preserve bullet boundaries even when a client collapses paragraph newlines.
    text = re.sub(r"\s+([-*•●▪])\s+(?=\S)", r"\n\1 ", text)
    return [line.strip() for line in text.split("\n") if line.strip()]


def _extract_jd_lines(job_description: str) -> List[Dict[str, str]]:
    lines = _normalize_jd_lines(job_description)
    current = "not_assessed"
    output = []
    for raw_line in lines:
        line = re.sub(r"^\s*(?:[-*•●▪]|\d+[.)])\s*", "", raw_line).strip()
        line = line.strip()
        if not line:
            continue
        heading = _norm(line).strip(": -")
        # Accept common variants, including "Required Skills and Qualifications".
        if re.search(
            r"\b(required(?:\s+skills)?(?:\s+and)?\s+qualifications?|"
            r"required\s+skills|requirements?|must have|what you need|"
            r"minimum qualifications?|minimum requirements?)\b",
            heading,
        ):
            current = "required"
            # A heading and its first statement may share a line.
            remainder = re.sub(
                r"^.*?\b(?:required(?:\s+skills)?(?:\s+and)?\s+qualifications?|"
                r"required\s+skills|requirements?|must have|what you need|"
                r"minimum qualifications?|minimum requirements?)\b\s*[:\-–—]?\s*",
                "", line, flags=re.I,
            ).strip()
            if remainder:
                output.append({"text": remainder, "classification": current})
            continue
        if re.search(
            r"\b(preferred(?:\s+skills)?(?:\s+and)?\s+qualifications?|"
            r"preferred\s+skills|nice to have|desired qualifications?|"
            r"bonus qualifications?)\b",
            heading,
        ):
            current = "preferred"
            remainder = re.sub(
                r"^.*?\b(?:preferred(?:\s+skills)?(?:\s+and)?\s+qualifications?|"
                r"preferred\s+skills|nice to have|desired qualifications?|"
                r"bonus qualifications?)\b\s*[:\-–—]?\s*",
                "", line, flags=re.I,
            ).strip()
            if remainder:
                output.append({"text": remainder, "classification": current})
            continue
        if re.search(
            r"\b(key\s+)?(responsibilities|what you will do|what you’ll do|"
            r"what you'll do|what you will be doing|what you'll be doing|"
            r"what you’ll be doing|what you will work on|what you'll work on|"
            r"what you will be responsible for|what you'll be responsible for|"
            r"your role|key duties|duties and responsibilities|role responsibilities|"
            r"the impact you'll make|the impact you will make)\b",
            heading,
        ):
            current = "responsibility"
            remainder = re.sub(
                r"^.*?\b(?:key\s+)?(?:responsibilities|what you will do|"
                r"what you’ll do|what you'll do|what you will be doing|what you'll be doing|"
                r"what you’ll be doing|what you will work on|what you'll work on|"
                r"what you will be responsible for|what you'll be responsible for|"
                r"your role|key duties|duties and responsibilities|role responsibilities|"
                r"the impact you'll make|the impact you will make)\b\s*[:\-–—]?\s*",
                "", line, flags=re.I,
            ).strip()
            if remainder:
                output.append({"text": remainder, "classification": current})
            continue
        if re.search(r"\b(about the company|about us|benefits|what we offer)\b", heading):
            current = "not_assessed"
            continue
        output.append({"text": line, "classification": current})
    return output

def _extract_jd_skills(job_description: str) -> List[Dict[str, Any]]:
    """Extract normalized requirements while preserving AND/OR and preference semantics."""
    aliases = _skill_aliases()
    found: Dict[str, Dict[str, Any]] = {}
    lines = _extract_jd_lines(job_description)
    groups: List[Dict[str, Any]] = []
    grouped_line_names = set()

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

        generic_language = bool(re.search(
            r"\b(?:at\s+least\s+one|one|a|any)\s+(?:programming|coding)\s+languages?\b",
            lowered,
        ))
        if generic_language and classification in ("required", "preferred"):
            groups.append({
                "name": "programming_language",
                "classification": "preferred" if classification == "preferred" else "required",
                "match_rule": "any_language",
                "source_sentence": text,
                "line_index": index,
            })
            if re.search(r"\bpreferably\b", lowered):
                groups.append({
                    "name": "preferred_programming_language",
                    "classification": "preferred",
                    "alternatives": ["java", "kotlin"],
                    "match_rule": "any",
                    "source_sentence": text,
                    "line_index": index,
                })
                grouped_line_names.update(((index, "java"), (index, "kotlin")))

        for canonical, values in aliases.items():
            if not any(_has(lowered, alias) for alias in values):
                continue
            if generic_language and canonical in ("java", "kotlin") and re.search(r"\bpreferably\b", lowered):
                continue
            priority = {"not_assessed": 0, "preferred": 1, "required": 2}
            previous = found.get(canonical)
            if previous and priority[previous["classification"]] >= priority[classification]:
                continue
            found[canonical] = {
                "name": canonical, "classification": classification,
                "source_sentence": text, "line_index": index,
            }

    alternative_patterns = (
        ("database", ("postgresql", "mysql")),
        ("build_tool", ("gradle", "maven")),
        ("programming_language", ("java", "kotlin")),
    )
    for line_index, line in enumerate(lines):
        lowered = _norm(line["text"])
        for group_name, alternatives in alternative_patterns:
            left, right = alternatives
            pattern = r"\b" + re.escape(left) + r"\b\s+or\s+\b" + re.escape(right) + r"\b"
            if not re.search(pattern, lowered):
                continue
            if group_name == "programming_language" and re.search(
                r"\b(?:at\s+least\s+one|one|a|any)\s+(?:programming|coding)\s+languages?\b",
                lowered,
            ):
                continue
            classification = line["classification"]
            if classification not in ("required", "preferred"):
                if any(re.search(cue, lowered) for cue in REQUIRED_CUES):
                    classification = "required"
                elif any(re.search(cue, lowered) for cue in PREFERRED_CUES):
                    classification = "preferred"
            if classification not in ("required", "preferred"):
                continue
            if group_name == "database" and re.search(r"\brelational\s+databases?\b", lowered):
                group_name = "relational databases"
            groups.append({
                "name": group_name, "classification": classification,
                "alternatives": list(alternatives), "match_rule": "any",
                "source_sentence": line["text"], "line_index": line_index,
            })
            grouped_line_names.update(((line_index, left), (line_index, right)))
            if group_name == "relational databases":
                grouped_line_names.add((line_index, "relational databases"))

    has_preferred_language_group = any(
        item["name"] == "preferred_programming_language" for item in groups
    )
    individual = [
        value for key, value in found.items()
        if (value["line_index"], key) not in grouped_line_names
        and not (
            has_preferred_language_group
            and key in ("java", "kotlin")
            and value["classification"] == "preferred"
        )
    ]
    return sorted(individual + groups, key=lambda item: (item["name"], item["line_index"]))


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
RESPONSIBILITY_STOP_WORDS = STOP_WORDS | {
    "reliable", "reliability", "scalable", "scale", "clean", "efficient",
    "maintainable", "software", "strong", "good", "knowledge",
    "understanding", "ability", "including", "new", "other",
}
RESPONSIBILITY_SYNONYMS = {
    "built": "build_action", "building": "build_action", "developed": "build_action",
    "develop": "build_action", "developing": "build_action", "implemented": "build_action",
    "implement": "build_action", "created": "build_action", "creating": "build_action",
    "designed": "build_action", "design": "build_action", "engineered": "build_action",
    "delivered": "build_action", "deliver": "build_action",
    "maintained": "maintain", "maintaining": "maintain", "maintain": "maintain",
    "api": "endpoint", "apis": "endpoint", "restful": "rest",
    "service": "software_artifact", "services": "software_artifact",
    "module": "software_artifact", "modules": "software_artifact",
    "component": "software_artifact", "components": "software_artifact",
    "application": "software_artifact", "applications": "software_artifact",
    "platform": "software_artifact", "dashboard": "software_artifact",
    "tool": "software_artifact", "tools": "software_artifact",
    "query": "database_query", "queries": "database_query", "sql": "database_query",
}
RESPONSIBILITY_CONCEPT_PATTERNS = {
    "software_delivery": (
        r"\b(?:build|built|develop|developed|design|designed|implement|implemented|engineered|create|created|deliver|delivered)\b",
        r"\b(?:software|application|applications|app|system|systems|dashboard|platform|service|services|module|modules|component|components|tool|tools|api|apis|code)\b",
    ),
    "frontend_development": (r"\b(?:frontend|front-end|ui|interface|dashboard|react|web app|user interface)\b",),
    "backend_development": (r"\b(?:backend|back-end|server-side|endpoint|endpoints|api|apis|node\.js|express(?:\.js)?|fastapi|django|flask|spring boot)\b",),
    "testing_quality": (r"\b(?:test(?:s|ed|ing)?(?!\s+failures?)|unit tests?|integration tests?|automated tests?|test cases?|test suites?|validation|validat\w*|p0 scenarios)\b",),
    "diagnostics": (r"\b(?:debug|debugging|troubleshoot|troubleshooting|diagnos|diagnosis|root cause|failure analysis|crash|crashes|logs?|log analyzer|error analysis)\b",),
    "automation": (r"\b(?:automat|automation|automated|workflow|workflows|script|scripts|scheduled|orchestrat)\w*\b",),
    "data_persistence": (r"\b(?:database|databases|sql|mysql|postgresql|mongodb|dynamodb|storage|persistence|data store|queries)\b",),
    "cloud_infrastructure": (r"\b(?:aws|cloud|ssm|s3|bedrock|lambda|infrastructure|deploy|deployed|deployment|server|servers|iam)\b",),
    "monitoring_operations": (r"\b(?:monitor|monitoring|monitored|alert|alerts|notification|notifications|compliance|status checks?|health checks?|offline-server)\b",),
    "performance_improvement": (r"\b(?:performance|latency|throughput|optimi[sz]|reduced|reducing|improv|accelerat|eliminat|streamlin|hours?|minutes?)\w*\b",),
    "collaboration": (r"\b(?:collaborat\w*|partnered with|coordinated with|worked with|liaised with|cross-functional)\b",),
    "code_quality": (
        r"\b(?:code reviews?|code quality|best practices|clean code|maintainable code|refactor|coding standards)\b",
        r"\b(?:clean|efficient|maintainable)\b.{0,50}\bcode\b",
    ),
    "version_control": (r"\b(?:git|version control|source control)\b",),
    "documentation": (r"\b(?:documentation|documenting|technical docs|readme)\b",),
    "security_auth": (r"\b(?:authentication|authorization|oauth|jwt|security|access control)\b",),
    "real_time_systems": (r"\b(?:real[- ]time|websocket|socket\.io|webrtc|live messaging)\b",),
    "process_improvement": (r"\b(?:process improvement|engineering processes|manual effort|manual checks|manual reproduction|manual collection|intervention|efficiency)\b",),
    "database_optimization": (
        r"\b(?:index(?:es|ing)?|indexed|optimi[sz]\w*\s+(?:\w+\s+){0,2}(?:sql\s+)?quer(?:y|ies)|"
        r"(?:sql\s+)?quer(?:y|ies)\s+(?:performance|optimization|optimisation)|"
        r"database\s+(?:design|index(?:es|ing)?|optimization|optimisation)|sql\s+joins?|joins?)\b",
    ),
}

def _responsibility_concepts(value: str) -> Set[str]:
    lowered = _norm(value)
    concepts = set()
    for concept, patterns in RESPONSIBILITY_CONCEPT_PATTERNS.items():
        if concept == "software_delivery":
            if re.search(patterns[0], lowered) and re.search(patterns[1], lowered):
                concepts.add(concept)
        elif any(re.search(pattern, lowered) for pattern in patterns):
            concepts.add(concept)
    return concepts


def _responsibility_tokens(value: str) -> Set[str]:
    raw = re.findall(r"[a-z][a-z0-9+#.]{1,}", _norm(value))
    output = set()
    for raw_token in raw:
        token = raw_token.rstrip(".,;:!?")
        if token in RESPONSIBILITY_STOP_WORDS or len(token) <= 2:
            continue
        output.add(RESPONSIBILITY_SYNONYMS.get(token, token))
    return output


def _responsibility_similarity(left: str, right: str) -> float:
    """Asymmetric retrieval score: cover JD concepts while tolerating richer resume bullets."""
    required = _responsibility_concepts(left)
    evidence = _responsibility_concepts(right)
    if not required or not evidence:
        return 0.0
    shared = required & evidence
    if not shared:
        return 0.0
    # Domain-specific duties require matching domain-specific evidence. Generic
    # performance, delivery, or audience terms cannot substitute for SQL tuning,
    # backend implementation, testing, collaboration, or engineering practices.
    evidence_gates = {
        "backend_development", "testing_quality", "database_optimization",
        "collaboration", "code_quality", "version_control", "documentation",
        "security_auth", "real_time_systems",
    }
    required_gates = required & evidence_gates
    if required_gates and not (required_gates & evidence):
        # Broad build/test/maintain duties can still receive partial credit for
        # demonstrated delivery evidence even when the testing sub-part is absent.
        if not ("software_delivery" in required and "software_delivery" in shared):
            return 0.0
    concept_recall = len(shared) / float(len(required))
    left_tokens, right_tokens = _responsibility_tokens(left), _responsibility_tokens(right)
    lexical = len(left_tokens & right_tokens) / float(len(left_tokens)) if left_tokens else 0.0
    return min(1.0, 0.82 * concept_recall + 0.18 * lexical)


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
    cleaned_job_description, jd_input_warnings = _clean_job_description(job_description)
    if not cleaned_job_description or len(cleaned_job_description.strip()) < 40:
        if jd_input_warnings:
            raise ValueError("The supplied content does not appear to be a readable job description. Paste the actual job posting text.")
        raise ValueError("Please provide a job description with at least 40 characters.")

    job_description = cleaned_job_description
    sections = _sections(resume)
    skills = _resume_skill_map(resume)
    jd_skills = _extract_jd_skills(job_description)
    resume_bullets = _bullets(sections, ("experience", "projects", "leadership", "volunteer"))
    # Skills-section mentions may support a duty, but remain explicitly listed-only
    # evidence and receive less weight than demonstrated experience/project bullets.
    resume_evidence = list(resume_bullets)
    for item in sections.get("skills", []):
        text = _item_text(item)
        if text:
            resume_evidence.append({
                "section": "skills", "text": text,
                "evidence_ids": _item_ids(item), "provenance": "listed",
            })
    required = [item for item in jd_skills if item["classification"] == "required"]
    preferred = [item for item in jd_skills if item["classification"] == "preferred"]
    informational = [item for item in jd_skills if item["classification"] == "not_assessed"]

    skill_matches = []
    skill_gaps = []
    aliases_by_name = _skill_aliases()
    for requirement in required + preferred:
        names = requirement.get("alternatives") or [requirement["name"]]
        if requirement.get("match_rule") == "any_language":
            names = list(PROGRAMMING_LANGUAGE_SKILLS)
        elif requirement["name"] == "relational databases" and not requirement.get("alternatives"):
            names = list(RELATIONAL_DATABASE_SKILLS)
        alternative_results = []
        for name in names:
            evidence = skills.get(name, {})
            direct = [item for item in resume_bullets
                      if any(_has(item["text"], alias) for alias in aliases_by_name.get(name, (name,)))]
            demonstrated_ids = list(dict.fromkeys(
                eid for item in direct for eid in item["evidence_ids"]
            ))
            listed_ids = evidence.get("listed", [])
            status = "demonstrated" if demonstrated_ids else "listed" if listed_ids else "not_found"
            alternative_results.append({
                "name": name, "status": status,
                "evidence_ids": demonstrated_ids or listed_ids or evidence.get("all", []),
            })
        matched = [item for item in alternative_results if item["status"] != "not_found"]
        status = (
            "demonstrated" if any(item["status"] == "demonstrated" for item in matched)
            else "listed" if matched else "not_found"
        )
        detail = {
            "skill": requirement["name"],
            "classification": requirement["classification"],
            "status": status,
            "resume_evidence_ids": list(dict.fromkeys(
                eid for item in matched for eid in item["evidence_ids"]
            )),
            "job_description_excerpt": requirement["source_sentence"],
        }
        if requirement.get("alternatives") or requirement.get("match_rule") == "any_language":
            detail["alternatives"] = list(names)
            detail["matched_alternatives"] = [item["name"] for item in matched]
            detail["match_rule"] = requirement.get("match_rule", "any")
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
    explicit_responsibilities = [
        item["text"] for item in jd_lines if item["classification"] == "responsibility"
    ]
    if explicit_responsibilities:
        responsibility_lines = explicit_responsibilities
    else:
        # Infer duties only when no dedicated responsibilities heading exists;
        # qualification bullets must never leak into this dimension.
        responsibility_lines = [
            item["text"] for item in jd_lines
            if item["classification"] == "not_assessed"
            and re.search(
                r"\b(you will|responsibilities include|responsible for|build|develop|"
                r"design|implement|maintain|manage|analy[sz]e|deliver|own|lead|"
                r"collaborate|support|architect|optimize|debug|test|automate)\b",
                item["text"], re.I,
            )
        ]
    responsibility_lines = list(dict.fromkeys(
        line for line in responsibility_lines if len(_tokens(line)) >= 3
    ))
    responsibility_matches = []
    responsibility_listed_evidence = []
    for line in responsibility_lines:
        ranked = []
        for evidence in resume_evidence:
            raw_similarity = _responsibility_similarity(line, evidence["text"])
            is_listed = evidence.get("provenance") == "listed"
            ranked.append((raw_similarity, evidence, is_listed))
        ranked.sort(key=lambda item: item[0], reverse=True)
        demonstrated = [(value, evidence) for value, evidence, listed in ranked
                        if not listed and value >= 0.18][:2]
        listed = [(value, evidence) for value, evidence, is_listed in ranked
                  if is_listed and value >= 0.18][:2]
        if listed:
            listed_value, listed_item = listed[0]
            responsibility_listed_evidence.append({
                "job_responsibility": line,
                "resume_excerpt": listed_item["text"],
                "similarity": round(listed_value, 3),
                "evidence_ids": list(listed_item["evidence_ids"]),
                "evidence_status": "listed",
            })
        if demonstrated:
            best_value, best_bullet = demonstrated[0]
            matched_concepts = sorted(
                _responsibility_concepts(line) & _responsibility_concepts(best_bullet["text"])
            )
            primary_ids = list(dict.fromkeys(best_bullet["evidence_ids"]))
            responsibility_matches.append({
                "job_responsibility": line,
                "resume_excerpt": best_bullet["text"],
                "similarity": round(best_value, 3),
                "matched_concepts": matched_concepts,
                "primary_evidence_ids": primary_ids,
                "evidence_ids": list(dict.fromkeys(
                    eid for _, evidence in demonstrated for eid in evidence["evidence_ids"]
                )),
                "evidence_type": (
                    "direct" if best_value >= 0.48 and len(matched_concepts) >= 2 else
                    "supporting"
                ),
                "evidence_status": "demonstrated",
                "supporting_excerpts": [evidence["text"] for _, evidence in demonstrated[1:]],
            })
    responsibility_score = None
    if responsibility_lines:
        matched_by_line = {
            item["job_responsibility"]: item["similarity"] for item in responsibility_matches
        }
        responsibility_score = int(round(25 * sum(
            min(1.0, matched_by_line.get(line, 0.0) / 0.62)
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
        entry_experience_window = bool(re.search(
            r"\b0\s*(?:-|–|—|to)\s*2\s*(?:years?|yrs?)\b",
            _norm(job_description),
        ))
        internship_counts_for_entry = (
            candidate_level == "intern" and target_level == "entry"
            and entry_experience_window
        )
        seniority_assessment = (
            "aligned" if LEVEL_RANK[candidate_level] >= LEVEL_RANK[target_level]
            or internship_counts_for_entry else "below_target_signal"
        )
    assessed_role_signals = []
    if candidate_role and target_role:
        assessed_role_signals.append(1.0 if candidate_role == target_role else 0.0)
    if candidate_level and target_level:
        assessed_role_signals.append(1.0 if seniority_assessment == "aligned" else 0.0)
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
    # score. Require meaningful coverage across at least two dimensions.
    minimum_assessed_weight = 35
    assessed_dimensions = sum(1 for _, value, _ in dimensions if value is not None)
    score_is_assessable = (
        active_weight >= minimum_assessed_weight and assessed_dimensions >= 2
    )
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
    if jd_input_warnings:
        findings.append(_finding(
            "job_description_contaminated",
            "Structured analyzer output was detected in the job description",
            "high",
            "Paste the original job posting text rather than a previous analysis result. Re-run the comparison after checking the input.",
            detail=" ".join(jd_input_warnings),
        ))
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
        "assessed_dimensions": assessed_dimensions,
        "input_warnings": jd_input_warnings,
        "version": MATCH_VERSION,
        "score_method": "normalized_assessed_dimensions",
        "responsibility_method": "domain_gated_concept_retrieval_v2",
        "skill_requirement_method": "taxonomy_provenance_and_alternatives",
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
        "responsibility_listed_evidence": responsibility_listed_evidence,
        "role_alignment": {
            "candidate_family": candidate_role, "target_family": target_role,
            "candidate_specialization": (
                "quality_engineering" if re.search(
                    r"\b(?:sdet|software development engineer in test|test automation|qa automation)\b",
                    _norm(title_text),
                ) else None
            ),
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
        "disclaimer": "A deterministic evidence-based estimate using explicit skill provenance and concept-aware responsibility retrieval; it is not an employer ATS ranking.",
    }
