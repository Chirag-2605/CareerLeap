"""Post-analysis suggestion design.

This layer consumes completed deterministic analysis and turns its findings into
prioritized, evidence-linked coaching. It does not change scores or invent facts.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .parser_v2 import SKILL_GROUPS

SKILL_TERMS = list(SKILL_GROUPS.keys())

VERSION = "suggestion-design-v1"

SECTION_ALIASES = {
    "summary": {"summary", "professional summary", "profile", "objective", "career objective", "about me"},
    "experience": {"experience", "work experience", "professional experience", "employment", "internship"},
    "projects": {"projects", "personal projects", "academic projects", "selected projects"},
    "skills": {"skills", "my skills", "technical skills", "key skills", "core competencies", "competencies", "skill set"},
    "education": {"education", "academic background", "qualifications"},
    "certifications": {"certifications", "certificates", "licenses"},
    "leadership": {"leadership", "leadership experience", "positions of responsibility"},
    "volunteer": {"volunteer experience", "volunteering", "community involvement"},
    "coding_platforms": {"coding platforms", "competitive programming", "problem solving profiles"},
}
BULLET_RE = re.compile(r"^\s*(?:[•●▪◦‣∙·*-]|\d+[.)])\s+")
VAGUE_STARTS = {"worked", "helped", "assisted", "involved", "responsible", "participated", "did", "learned", "attended"}
ACTION_STARTS = {
    "built", "developed", "designed", "implemented", "created", "optimized",
    "automated", "delivered", "launched", "integrated", "migrated", "deployed",
    "engineered", "configured", "resolved", "fixed", "analyzed", "improved",
}
TECHNICAL_DETAIL_RE = re.compile(\n    r"\\b(?:api|apis|websocket|websockets|socket\\.io|webrtc|jwt|oauth|authentication|authorization|"\n    r"database|schema|microservice|real[- ]time|peer[- ]to[- ]peer|message history|integration|"\n    r"deployment|deployed|pipeline|cache|query|endpoint|framework|architecture|model|workflow)\\b",\n    re.I,\n)\nGENERIC_PHRASES = (
    "different projects", "many new technologies", "whenever required",
    "some frontend and backend work", "helped seniors", "useful for managing things",
    "created a website", "added some features", "made the design look good",
)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _section_name(line: str) -> Optional[str]:
    value = _normalize(line).strip(": -")
    for name, aliases in SECTION_ALIASES.items():
        if value in aliases:
            return name
    return None


def _contains_skill(text: str) -> bool:
    value = _normalize(text)
    return any(
        re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", value)
        for term in SKILL_TERMS
    )


def _source_lines(resume_text: str) -> List[Dict[str, Any]]:
    section = "header"
    result = []
    for number, raw in enumerate(str(resume_text or "").splitlines(), 1):
        text = raw.strip()
        if not text:
            continue
        detected = _section_name(text)
        if detected:
            section = detected
            continue
        result.append({"line": number, "text": text, "section": section})
    return result


def _rewrite_template(text: str) -> str:
    value = BULLET_RE.sub("", text).strip().rstrip(".")
    first = re.findall(r"[a-z]+", value.lower())[:1]
    verb = first[0] if first else ""
    if verb in {"worked", "did"}:
        return (
            "Contributed to [specific feature, component, or workflow] by [your individual action] "
            "using [technology or method], resulting in [verified outcome or scope]."
        )
    if verb in {"helped", "assisted"}:
        return (
            "Supported [specific engineering task] by [your individual contribution] using "
            "[technology or method], resulting in [verified outcome or scope]."
        )
    if verb == "fixed":
        return (
            "Diagnosed and resolved [specific bug or issue] in [component] using "
            "[debugging approach or technology], improving [verified behavior or reliability outcome]."
        )
    if verb in {"attended", "participated"}:
        return (
            "Collaborated with [team or stakeholders] to [specific decision or deliverable], "
            "contributing to [verified outcome]."
        )
    if verb == "learned":
        return (
            "Applied [technology] to [specific task or project], demonstrating [verified capability "
            "or deliverable]. Keep this only if you actually used the technology."
        )
    if verb in {"responsible", "involved"}:
        return (
            "Owned or contributed to [specific responsibility] by [your action] using "
            "[technology or method], resulting in [verified outcome or scope]."
        )
    return (
        value + " by [describe your specific action] using [technology or method], "
        "resulting in [verified outcome or scope]."
    )


def _weak_bullet(item: Dict[str, Any]) -> bool:
    clean = BULLET_RE.sub("", item["text"]).strip()
    words = re.findall(r"\b[\w+#.]+\b", clean)
    first = re.findall(r"[a-z]+", clean.lower())[:1]
    lowered = clean.lower()
    if first and first[0] in VAGUE_STARTS:
        return True
    if any(phrase in lowered for phrase in GENERIC_PHRASES):
        return True
    # Short bullets without a concrete technical signal or outcome need context.
    return len(words) < 8 and not _contains_skill(clean) and not re.search(
        r"\b(?:users|requests|customers|latency|accuracy|revenue|time|cost|workflow)\b", lowered
    )


def _suggestion(
    code: str,
    category: str,
    priority: str,
    title: str,
    rationale: str,
    where_to_edit: str,
    source: Optional[Dict[str, Any]] = None,
    questions: Optional[List[str]] = None,
    rewrite: Optional[str] = None,
    impact_guidance: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "code": code,
        "category": category,
        "priority": priority,
        "title": title,
        "why_it_matters": rationale,
        "where_to_edit": where_to_edit,
        "source_line": (
            {"line": source["line"], "text": BULLET_RE.sub("", source["text"]).strip()}
            if source else None
        ),
        "questions_to_answer": questions or [],
        "rewrite_template": rewrite,
        "impact_guidance": impact_guidance,
        "safety_note": "Use only details you can verify. Keep metrics, tools, ownership and outcomes unchanged unless you can substantiate a correction.",
    }


def design_suggestions(
    resume_text: str,
    quality: Dict[str, Any],
    job_match: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Design a ranked improvement plan from analyzer outputs and source resume text."""
    lines = _source_lines(resume_text)
    items: List[Dict[str, Any]] = []
    achievement_lines = [item for item in lines if item["section"] in {"experience", "projects", "leadership", "volunteer"}
                         and BULLET_RE.match(item["text"])]
    weak = [item for item in achievement_lines if _weak_bullet(item)]
    # Reserve space for project and skills evidence; otherwise a long list of
    # weak internship bullets can crowd every other useful recommendation out.
    selected_weak = (
        [item for item in weak if item["section"] == "experience"][:3]
        + [item for item in weak if item["section"] == "projects"][:2]
        + [item for item in weak if item["section"] in {"leadership", "volunteer"}][:1]
    )

    for item in selected_weak:
        section = item["section"]
        label = "project" if section == "projects" else "experience"
        items.append(_suggestion(
            code="clarify_{0}_line_{1}".format(section, item["line"]),
            category="project_evidence" if section == "projects" else "experience_evidence",
            priority="high" if section == "experience" else "medium",
            title="Add your individual contribution to this {0} bullet".format(label),
            rationale="The current line is too broad to show what you personally delivered. A recruiter cannot yet identify the task, technical approach or result.",
            where_to_edit="{0} section · extracted line {1}".format(section.title(), item["line"]),
            source=item,
            questions=[
                "Which exact feature, component, bug, or workflow did you work on?",
                "What did you personally implement, change, investigate, or deliver?",
                "Which technology, tool, or method did you actually use?",
                "What changed as a result, or what was the scope of the work?",
            ],
            rewrite=_rewrite_template(item["text"]),
            impact_guidance=(
                "If you have a defensible number, add it. If not, describe the real scope, complexity, "
                "users, workflow, reliability improvement, or deliverable instead."
            ),
        ))

    # A project heading with little technical detail deserves a project-level prompt,
    # not an assumption that the project itself was trivial.
    project_lines = [item for item in lines if item["section"] == "projects"]
    project_bullets = [item for item in project_lines if BULLET_RE.match(item["text"])]
    substantive_project_bullets = [
        item for item in project_bullets
        if len(re.findall(r"\b[\w+#.]+\b", item["text"])) >= 9 and _contains_skill(item["text"])
    ]
    if project_lines and (not project_bullets or len(substantive_project_bullets) < min(2, len(project_lines))):
        source = next((item for item in project_lines if not BULLET_RE.match(item["text"])), project_lines[0])
        items.append(_suggestion(
            code="expand_project_technical_evidence",
            category="project_evidence",
            priority="medium",
            title="Make the project description technically assessable",
            rationale="A project title alone does not reveal its problem, architecture, your contribution, or the technologies used. The current extraction is not enough to judge its depth.",
            where_to_edit="Projects section · extracted line {0}".format(source["line"]),
            source=source,
            questions=[
                "What problem does the project solve, and who is it for?",
                "What did you build yourself (key feature, API, UI, data model, or workflow)?",
                "Which languages, frameworks, databases, or services did you use?",
                "What technical challenge did you solve?",
                "What can you demonstrate: a working feature, test, deployment, user flow, or measured result?",
            ],
            rewrite="[Project/action] built using [verified technologies] to solve [problem]. Implemented [your contribution], including [technical detail], and [verified outcome or demonstrable deliverable].",
            impact_guidance="A metric is optional. A concrete feature, architecture decision, tested workflow, or deployed deliverable is useful evidence too.",
        ))

    # Skills listed without a work/project example should be framed as an evidence
    # gap, not as proof the candidate lacks the skill.
    skills_lines = [item for item in lines if item["section"] == "skills"]
    experience_project_text = " ".join(
        item["text"] for item in lines if item["section"] in {"experience", "projects"}
    )
    coding_platform_text = " ".join(
        item["text"] for item in lines if item["section"] == "coding_platforms"
    )
    listed_only = []
    for skill in SKILL_TERMS:
        has_project_or_experience_evidence = re.search(
            r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])", experience_project_text.lower()
        )
        # Competitive-programming profiles are supporting evidence for DSA, even
        # though they are not a substitute for a concrete engineering example.
        has_dsa_support = skill == "data structures and algorithms" and bool(re.search(
            r"leetcode|geeksforgeeks|codeforces|codechef|coding ninjas", coding_platform_text, re.I
        ))
        if any(re.search(r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])", item["text"].lower())
               for item in skills_lines) and not has_project_or_experience_evidence and not has_dsa_support:
            listed_only.append(skill)
    if listed_only:
        items.append(_suggestion(
            code="connect_listed_skills_to_evidence",
            category="skills_evidence",
            priority="medium",
            title="Connect listed skills to real examples",
            rationale="These skills appear in the Skills section but were not found in the extracted experience or project text: {0}. This is an evidence gap, not proof that you lack them.".format(", ".join(listed_only[:6])),
            where_to_edit="Relevant Experience or Projects bullet",
            questions=[
                "Which of these skills have you actually used in a project, internship, coursework, or independent build?",
                "What specific task did you complete with that skill?",
                "Can you add one factual example under the project or role where you used it?",
            ],
            rewrite="Used [skill] to [specific task] in [project or role], implementing [verified contribution].",
        ))

    quality_codes = {item.get("code") for item in quality.get("findings", [])}
    if "few_metrics" in quality_codes or "impact_no_quantified_outcomes" in quality_codes:
        items.append(_suggestion(
            code="describe_outcomes_without_inventing_metrics",
            category="impact",
            priority="medium",
            title="Show the outcome, even when you do not have a metric",
            rationale="The analysis found limited quantified outcomes. Do not manufacture percentages or numbers; make the actual result or scope visible.",
            where_to_edit="Experience and Projects bullets",
            questions=[
                "Did the work reduce manual steps, prevent errors, improve reliability, or make a workflow easier?",
                "How many users, services, datasets, records, or teams were involved, if you know?",
                "What shipped, changed, became faster, or became possible?",
                "If no measurement exists, what concrete qualitative deliverable or technical complexity can you verify?",
            ],
            rewrite="[Action] [component or workflow] using [method], enabling [verified qualitative result or scope].",
            impact_guidance="Use a number only when you can explain its source. Otherwise state a concrete before/after, scope, reliability change, or shipped capability.",
        ))

    # Convert job-match findings into contextual edits. Missing skills are never
    # instructions to add keywords without supporting experience.
    if job_match:
        # V4 exposes evidence-backed skill_gaps rather than V1's actionable_suggestions.
        for gap in job_match.get("skill_gaps", []):
            skill = gap.get("skill", "").strip()
            if not skill:
                continue
            classification = gap.get("classification", "preferred")
            priority = "high" if classification == "required" else "medium"
            alternatives = gap.get("alternatives") or []
            skill_label = " or ".join(alternatives) if alternatives else skill
            items.append(_suggestion(
                code="job_skill_evidence_" + re.sub(r"[^a-z0-9]+", "_", skill.lower()).strip("_"),
                category="job_match",
                priority=priority,
                title="Check whether you can evidence {0}".format(skill_label),
                rationale=(
                    "The job description identifies {0} as a {1} requirement, but the analyzer did not find "
                    "resume evidence for it. This is an evidence gap, not proof that you lack the skill. "
                    "Add it only if you have genuinely used it."
                ).format(skill_label, classification),
                where_to_edit="Relevant Skills, Experience, or Projects section",
                source=None,
                questions=[
                    "Have you used {0} in a real project, internship, coursework, or independent build?".format(skill_label),
                    "What did you personally do with it, and where can that example be shown?",
                ],
                rewrite="Used {0} to [specific task] in [project or role], resulting in [verified deliverable or outcome].".format(skill_label),
            ))

    # Optional polish must not be presented as a mandatory ATS requirement.
    if not any(item["section"] == "summary" for item in lines):
        items.append(_suggestion(
            code="optional_targeted_summary",
            category="presentation",
            priority="low",
            title="Optionally add a targeted professional summary",
            rationale="A summary can help a recruiter understand your target role and strongest evidence quickly, but it is optional and not a universal ATS requirement.",
            where_to_edit="Below contact details and before Experience",
            questions=[
                "What role are you targeting?",
                "Which two or three strengths are supported by your experience or projects?",
                "What is one concrete system, feature, or outcome you can substantiate?",
            ],
            rewrite="[Target role] with hands-on experience in [verified technologies] through [internship/project]. Built or improved [specific system or deliverable], focusing on [relevant strength].",
        ))

    if not re.search(r"(?:https?://|www\.|linkedin\.com|github\.com)", resume_text, re.I):
        items.append(_suggestion(
            code="optional_professional_profile_link",
            category="presentation",
            priority="low",
            title="Optionally add a professional profile link",
            rationale="A relevant LinkedIn, GitHub, or portfolio link can make your work easier to verify. It is useful polish, not a requirement for every candidate.",
            where_to_edit="Contact header",
            questions=["Do you have a maintained LinkedIn, GitHub, or portfolio page that supports this application?"],
        ))

    rank = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda item: (rank.get(item["priority"], 3), item["category"], item["code"]))
    # Keep the plan focused; detailed findings remain available in the analysis.
    items = items[:8]
    return {
        "version": VERSION,
        "items": items,
        "count": len(items),
        "priority_order": ["high", "medium", "low"],
        "principles": [
            "Prioritize evidence-rich experience and project edits before optional presentation polish.",
            "Quantification is encouraged only when verifiable; concrete qualitative outcomes and scope also count.",
            "A missing keyword is a prompt to check experience, never an instruction to claim an unsupported skill.",
        ],
        "disclaimer": "Suggestions are deterministic coaching prompts generated after analysis. They do not rewrite or verify resume facts.",
    }
