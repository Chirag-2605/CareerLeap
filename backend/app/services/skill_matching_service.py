"""Evidence-aware skill matching service.

Direct aliases are strong evidence. Related concepts are supporting evidence and
receive partial credit; they are never silently promoted to equivalent expertise.
"""
import re
from typing import Any, Dict, Iterable, List


SEMANTIC_EVIDENCE = {
    "api development": {
        "direct": ("api development", "api design", "api implementation", "developed api", "built api", "api endpoints"),
        "supporting": ("rest api", "restful api", "restful services", "http endpoint"),
    },
    "http": {
        "direct": ("http", "http protocol", "http methods", "https"),
        "supporting": ("rest api", "rest apis", "restful api", "restful apis", "restful services"),
    },
    "relational databases": {
        "direct": ("relational database", "relational databases", "postgresql", "postgres", "mysql", "sql server", "sqlite"),
        "supporting": ("sql", "structured query language", "database joins", "database indexing"),
    },
    "database design": {
        "direct": ("database design", "schema design", "database schema", "data modeling", "data modelling"),
        "supporting": ("sql", "postgresql", "mysql", "mongodb", "database schema"),
    },
    "concurrency": {
        "direct": ("concurrency", "concurrent", "multithreading", "multi-threading", "parallel processing", "thread pool", "asyncio"),
        "supporting": ("asynchronous", "async", "parallel"),
    },
    "integration testing": {
        "direct": ("integration testing", "integration tests", "end-to-end testing", "e2e tests"),
        "supporting": ("api tests", "testcontainers", "service tests"),
    },
    "distributed systems": {
        "direct": ("distributed systems", "distributed system", "distributed architecture", "message queue", "event-driven architecture"),
        "supporting": ("microservices", "microservice", "service-to-service", "kafka", "rabbitmq"),
    },
}


def _has(text: str, phrase: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(phrase.lower()).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
    return bool(re.search(pattern, text, re.I))


def match_requirement(requirement: Dict[str, Any], resume_skills: Dict[str, Any],
                      evidence: Iterable[Dict[str, Any]], aliases: Dict[str, tuple]) -> Dict[str, Any]:
    names = requirement.get("alternatives") or [requirement["name"]]
    results = []
    evidence = list(evidence)
    for name in names:
        skill = resume_skills.get(name, {})
        direct_aliases = tuple(aliases.get(name, (name,)))
        direct_ids = []
        supporting_ids = []
        for item in evidence:
            text = item["text"]
            if any(_has(text, alias) for alias in direct_aliases):
                direct_ids.extend(item["evidence_ids"])
            semantic = SEMANTIC_EVIDENCE.get(name, {})
            if any(_has(text, term) for term in semantic.get("direct", ())):
                direct_ids.extend(item["evidence_ids"])
            elif any(_has(text, term) for term in semantic.get("supporting", ())):
                supporting_ids.extend(item["evidence_ids"])
        listed_ids = list(skill.get("listed", []))
        if direct_ids:
            status = "demonstrated"
            ids = direct_ids
        elif listed_ids:
            status = "listed"
            ids = listed_ids
        elif supporting_ids:
            status = "supporting"
            ids = supporting_ids
        else:
            status, ids = "not_found", []
        results.append({"name": name, "status": status,
                        "evidence_ids": list(dict.fromkeys(ids))})
    rank = {"demonstrated": 3, "listed": 2, "supporting": 1, "not_found": 0}
    best = max(results, key=lambda item: rank[item["status"]])
    matched = [item for item in results if item["status"] != "not_found"]
    return {
        "skill": requirement["name"],
        "classification": requirement["classification"],
        "status": best["status"],
        "resume_evidence_ids": list(dict.fromkeys(
            eid for item in matched for eid in item["evidence_ids"]
        )),
        "job_description_excerpt": requirement["source_sentence"],
        **({"alternatives": list(names), "matched_alternatives": [item["name"] for item in matched],
            "match_rule": "any"} if requirement.get("alternatives") else {}),
    }
