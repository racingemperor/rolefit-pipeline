# Role Output Contracts

All role outputs should be structured enough for the orchestrator to merge.

## Common Fields

Every role should include:

```json
{
  "role": "",
  "task_summary": "",
  "inputs_used": [],
  "database_files_used": [],
  "source_notes": [],
  "confidence": "high|medium|low",
  "needs_user_confirmation": []
}
```

## Evidence Notes

Use `source_notes` to distinguish:

- `official_or_primary`
- `recruitment_platform_jd`
- `verified_hr_public_post`
- `candidate_experience_secondary`
- `social_media_weak`
- `user_provided`
- `inference`

## Resume Approval Status

Resume-producing steps must use:

```json
{
  "format_gate_status": "pass|revise_required|user_confirmation_required",
  "format_status": "accepted|rejected|needs_user_confirmation",
  "factual_review_status": "not_reviewed|pass|revise|required_user_confirmation"
}
```

`ResumeFormatGate` decides whether drafting is allowed. `ResumeArchitect` cannot mark final approval. Only `FactualReviewer` can mark the final resume as `pass`.
