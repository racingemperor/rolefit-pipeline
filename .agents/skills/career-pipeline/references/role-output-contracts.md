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

## Collaboration And Debate Fields

Roles that make judgments about fit, learning, branding, resume structure, HR readability, or factual risk should also include:

```json
{
  "agent_claims": [],
  "evidence_challenges": [],
  "disagreements_with": [
    {
      "agent": "",
      "field": "",
      "reason": "",
      "requested_resolution": ""
    }
  ],
  "handoff_questions": []
}
```

Use these fields when one role challenges another role's conclusion. Do not silently erase disagreements. If a conflict depends on missing user evidence, return a user-confirmation point instead of forcing a final recommendation.

## Input Normalization Fields

The first stage should expose:

```json
{
  "input_type": "chat_brief|resume_text|markdown_file|pdf_docx|personal_website|github_or_portfolio|jd_text|jd_link|mixed|unknown",
  "known_information_summary": "",
  "next_possible_actions": [],
  "candidate_stage": "non_graduating|graduating|graduate|unknown",
  "school_context": {},
  "application_scenarios": {
    "internship": {},
    "future_full_time": {},
    "current_full_time": {}
  },
  "missing_user_owned_facts": [],
  "one_round_followup_prompt": "",
  "job_direction_blocked": false
}
```

Use these fields to support vague chat introductions, complete files, websites, Markdown, links, and mixed materials without forcing the user into repeated Q&A. `next_possible_actions` should tell the user what can be done with current information before asking for missing facts.

## Parameter Ownership Fields

Roles that ask questions, research public data, or set weights should expose:

```json
{
  "parameter_ownership": {
    "user_required_minimal": [],
    "user_optional": [],
    "subagent_research": [],
    "runtime_weight_config": []
  },
  "runtime_weight_config": {
    "skill_weights": [],
    "external_asset_weights": [],
    "school_signal_weights": []
  }
}
```

Do not hard-code concrete skill or external-display requirements from repository examples alone. Let local subagents research current role, company, school, and discipline evidence, then configure weights at runtime.

## HR Supervision Status

HR-supervised steps should expose:

```json
{
  "hr_readability_score": 0,
  "company_hr_signal_refs": [],
  "target_company_screening_bias": [],
  "big_tech_hr_screening_notes": [],
  "competitive_signal_summary": [],
  "hr_first_screen_risks": [],
  "positioning_verdict": "pass|revise|required_user_confirmation",
  "pass_to_next_stage": false
}
```

`HRSupervisor` checks whether the pipeline output is understandable, credible, and competitive from a first-screen HR perspective. It cannot override `FactualReviewer` on truthfulness.

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
  "factual_review_status": "not_reviewed|pass|revise|required_user_confirmation",
  "incomplete_resume_allowed_with_user_consent": false,
  "incomplete_resume": false,
  "job_direction_blocked": false
}
```

`ResumeFormatGate` decides whether drafting is allowed. `ResumeArchitect` cannot mark final approval. Only `FactualReviewer` can mark the final resume as `pass`.

If the user refuses to provide missing information, incomplete resume drafting requires explicit consent. Missing sections must be omitted rather than filled with placeholders, and application direction recommendations must remain blocked.
