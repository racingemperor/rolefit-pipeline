# Runtime Artifact Schema

This protocol defines local files produced during a user-side run. Runtime artifacts are private working data and should not be committed to git.

## Default Run Directory

Use an ignored local directory:

```text
.career-pipeline-runs/
  <run_id>/
    manifest.json
    input/
      raw_refs.json
      normalized/
        first_round_user_profile.json
        runtime_context_packet.json
    injections/
      <agent>.secondary_prompt_injection.json
    invocations/
      <agent>.input_packet.json
      <agent>.invocation.json
    agents/
      <agent>/
        output.json
        evidence.json
        redacted.log
    evidence/
      evidence_packets.jsonl
      source_index.json
    merge/
      merged_context.json
      debate_topics.json
      runtime_weights.json
      hr_review.json
      factual_review.json
    final/
      decision_package.json
      resume_draft.md
    logs/
      orchestrator.redacted.log
    cache/
      public_sources/
```

Use references instead of copying large files when possible. If a user-provided file is copied into the run directory, mark it as private and do not pass it to roles that do not need it.

`cache/public_sources/` is optional. Prefer storing source metadata and excerpts needed for evidence checks instead of raw page copies. Do not cache identifiable candidate resumes, private chats, recruiter backend content, login-only pages, or full social-media threads containing personal identifiers.

## Artifact Reference

Any file used across roles should be referenced as:

```json
{
  "artifact_ref": {
    "artifact_id": "",
    "run_id": "",
    "artifact_type": "raw_input_ref|normalized_profile|runtime_context_packet|secondary_prompt_injection|subagent_input|subagent_output|evidence_packet|source_cache|merge_result|debate_record|hr_review|factual_review|resume_draft|final_package|redacted_log",
    "path": "",
    "created_by": "",
    "created_at": "",
    "privacy_class": "public|user_private|redacted|derived|sensitive_contact",
    "contains_contact": false,
    "contains_private_resume": false,
    "safe_to_share_with_roles": [],
    "checksum": "",
    "retention": "runtime_only|user_export|cache_until_stale",
    "purge_after_days": null
  }
}
```

Intermediate packets should prefer `redacted` or `derived` artifacts. Final resume drafts may include contact fields only when the user explicitly authorized them.

## Evidence Packet

Public and user-provided evidence should use:

```json
{
  "evidence_packet": {
    "evidence_id": "",
    "claim_id": "",
    "field": "",
    "source_type": "user_provided|official_or_primary|recruitment_platform_jd|verified_hr_public_post|candidate_experience_secondary|social_media_weak|repository_prior|inference",
    "source_ref": "",
    "artifact_ref": "",
    "retrieved_or_published_date": "",
    "freshness": "0_6_months|6_12_months|1_3_years|older|unknown",
    "evidence_strength": "strong|medium|weak|missing",
    "inference_level": "none|low|medium|high",
    "privacy_class": "public|user_private|redacted|derived|sensitive_contact",
    "confidence": "high|medium|low"
  }
}
```

Repository priors must be marked as `repository_prior`. They cannot be the sole basis for final weights, scores, priorities, rankings, thresholds, or confidence adjustments.

## Redaction Rules

- Redact phone numbers, private emails, IDs, addresses, and private chat identifiers in intermediate logs.
- Do not write raw private resumes into shared context when extracted fields are enough.
- Do not pass all user materials to every role.
- Do not store private HR messages, recruiter backend data, private candidate profiles, or login-only content.
- Public-source caches should use source-type retention:
  - official/company/school/JD metadata may use `cache_until_stale` with a freshness check.
  - verified HR public posts should store source refs and short evidence notes; avoid raw full-page cache unless needed and purge when stale.
  - candidate experience and social-media signals should store aggregated, de-identified notes only and default to `runtime_only`.
  - single weak anonymous posts should not be cached beyond the run.
- Do not commit `.career-pipeline-runs/`, source caches, private input files, or generated resumes unless the user explicitly asks for a sanitized export.

## Final Package References

The final decision package should reference artifacts rather than embedding all intermediate content:

```json
{
  "final_package_refs": {
    "run_manifest_ref": "",
    "candidate_summary_ref": "",
    "evidence_index_ref": "",
    "runtime_weights_ref": "",
    "debate_record_ref": "",
    "hr_review_ref": "",
    "factual_review_ref": "",
    "resume_draft_ref": "",
    "blocked_package_ref": ""
  }
}
```

If no resume is produced, set `resume_draft_ref` to an empty string and list the blocked reason.
