# Error Recovery Protocol

This protocol defines how the pipeline should recover, degrade, or block when runtime execution cannot complete normally.

## Error Categories

Use these categories:

- `missing_user_fact`: school, grade, target, project evidence, contact consent, or other user-owned fact is missing.
- `missing_consent`: incomplete resume, contact fields, or private material use lacks explicit consent.
- `missing_current_jd`: a concrete targeted resume or match decision needs current JD text.
- `network_unavailable`: public research cannot run.
- `source_blocked`: source requires login, bypass, scraping, or permission the pipeline does not have.
- `source_stale`: available source is too old for the decision.
- `source_conflict`: official/JD/HR/social/candidate sources disagree.
- `unsupported_weight`: a weight, score, priority, ranking, threshold, or confidence change lacks hard evidence.
- `subagent_failed`: a role failed or timed out.
- `malformed_output`: a role output is not parseable or violates required fields.
- `schema_validation_failed`: output parses but fails contract validation.
- `privacy_risk`: private or sensitive data appears in the wrong artifact or output.
- `factual_risk`: resume or strategy contains unsupported, inflated, or indefensible claims.

## Error Object

Each error should be structured:

```json
{
  "runtime_error": {
    "error_id": "",
    "run_id": "",
    "stage": "",
    "agent": "",
    "category": "missing_user_fact|missing_consent|missing_current_jd|network_unavailable|source_blocked|source_stale|source_conflict|unsupported_weight|subagent_failed|malformed_output|schema_validation_failed|privacy_risk|factual_risk",
    "severity": "info|warning|blocking|fatal",
    "affected_outputs": [],
    "evidence_or_artifact_refs": [],
    "message": "",
    "recovery_action": "ask_user_once|research_public_source|retry_subagent|repair_schema|rerun_with_narrower_prompt|route_to_hr|route_to_factual_reviewer|degrade_output|block_output|return_blocked_package",
    "owner": "orchestrator|local_subagent|user|hr_supervisor|factual_reviewer",
    "retry_count": 0,
    "resolved": false
  }
}
```

## Recovery State

The orchestrator should maintain:

```json
{
  "error_recovery_state": {
    "status": "not_applicable|recovered|degraded|needs_user_confirmation|needs_public_research|blocked|failed",
    "errors": [],
    "recovery_actions": [],
    "degraded_outputs": [],
    "blocked_outputs": [],
    "safe_outputs": [],
    "next_action": "continue|ask_user_once|run_public_research|retry_agent|run_debate|run_hr_review|run_factual_review|return_blocked_package"
  }
}
```

## Recovery Rules

- Missing user-owned facts: ask once in a compact batch. If the user refuses, request explicit incomplete-resume consent when resume drafting is still desired.
- Missing public evidence: do not ask the user to research manually. Create runtime research tasks for local subagents.
- Network unavailable: return current evidence-bound outputs and mark public-research-dependent outputs as degraded or blocked.
- Source blocked by login or anti-scraping: do not bypass. Request user-provided text or choose another public source.
- Stale source: use as background only; do not use it for current weights or final priorities.
- Unsupported weights: set `weight_status = "not_available"` or `needs_more_sources`; block dependent decisions.
- Malformed output: retry once with a narrower schema-repair prompt. If still malformed, mark the role failed and keep its downstream outputs blocked.
- Subagent failure: retry only when the missing context or failure mode is clear. Otherwise degrade or block; do not loop indefinitely.
- Privacy risk: stop propagation of the affected artifact, create a redacted replacement, and route to FactualReviewer when resume claims are affected.
- Factual risk: route to FactualReviewer and block final resume approval until resolved.

## Degraded Output Rules

Degraded output is allowed only when it is honest about its limits:

- It may summarize known user facts.
- It may list research tasks.
- It may give learning preparation options when clearly marked as conditional.
- It may not give final application priority, fit score, company-specific resume tailoring, or HR pass status without required evidence.
- It may not include fabricated resume content.

## Blocked Package

If completion is impossible, return:

```json
{
  "blocked_package": {
    "run_id": "",
    "blocked_outputs": [],
    "safe_outputs": [],
    "missing_user_owned_facts": [],
    "public_research_tasks": [],
    "consent_requests": [],
    "failed_agents": [],
    "source_conflicts": [],
    "next_possible_actions": []
  }
}
```

The blocked package should still be useful: show what is known, what cannot be produced, and the smallest next step.
