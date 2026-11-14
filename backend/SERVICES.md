# Evaluator service boundaries

CareerLeap's analysis pipeline is organized around independent, deterministic evaluator contracts.

## Current service contracts

| Service | Input | Output | Responsibility |
|---|---|---|---|
| Evidence service | Parsed resume | Section-tagged evidence records with source IDs | Normalize source material for downstream evaluators |
| Skill matching service | JD requirement, skill inventory, evidence, aliases | Demonstrated / listed / supporting / not-found result | Match explicit and related skill evidence without overstating proficiency |
| Responsibility matching service | JD responsibility statements and resume bullets | Evidence-linked matches and alignment score | Compare work performed with role responsibilities |
| Experience evaluator | Experience bullets, role context, project evidence, bullet-quality signals | Experience-depth assessment | Reward technical substance and ownership rather than bullet count |
| Project evaluator | Project evidence bullets | Technical-substance assessment and source references | Assess project descriptions without inventing details |
| Scoring orchestrator | Independently assessed weighted dimensions | Normalized score, coverage, and breakdown | Combine only dimensions with sufficient evidence |

## Service contract rules

- Services are deterministic and side-effect free.
- Evidence references must remain traceable to parser evidence IDs.
- Demonstrated, listed, and supporting are distinct evidence strengths.
- Related concepts may provide partial support, but are not silently promoted to direct expertise.
- A skill-list mention is not treated as demonstrated work experience.
- Missing or unassessed dimensions do not receive free points and are not treated as zero.
- The orchestrator owns aggregation; an individual evaluator cannot decide overall candidate suitability.
- Resume quality and job match remain independent assessments.

## Deployment boundary

The current API process invokes these contracts in-process to preserve the existing authenticated POST /api/v1/analyze mobile contract. This is a modular service boundary, not a claim that every evaluator is already a separately deployed network microservice.

The contracts are transport-neutral. A later deployment can move a service behind an internal HTTP or message-bus adapter without changing its domain input/output schema. When extracting a process, add service-specific health checks, timeouts, retries, versioned schemas, authentication between services, and contract/integration tests. Do not add distributed infrastructure until there is an operational need.

## Analysis flow

1. Parser extracts sections, skills, and evidence IDs.
2. Evidence service normalizes source-linked records.
3. Skill, responsibility, experience, and project evaluators run independently.
4. Scoring orchestrator combines assessed dimensions.
5. Suggestion design turns the findings into grouped, prioritized coaching.
6. API adapter preserves the mobile response contract.
