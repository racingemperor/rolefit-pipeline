# Runtime Orchestration Protocol

This protocol defines how the user-side Codex pipeline should run after the static role prompts and secondary prompt injections are available.

## Scope

`RuntimeOrchestrator` is a runtime execution protocol, not another career-judgment role. It tracks state, dispatches role subagents, merges outputs, handles blockers, and decides whether the next step is research, debate, HR review, factual review, user confirmation, or final packaging.

## State Machine

Runtime execution should move through these stages:

```text
intake_received
  -> input_normalized
  -> context_packet_created
  -> injection_ready
  -> agents_running
  -> merge_pending
  -> debate_required | hr_review_required | factual_review_required | user_confirmation_required | blocked
  -> final_package_ready
```

Do not skip `input_normalized`, `context_packet_created`, or `injection_ready`. Specialist subagents must not run on static prompts alone.

## Run State Packet

Every orchestration step should expose:

```json
{
  "run_state": {
    "run_id": "",
    "stage": "intake_received|input_normalized|context_packet_created|injection_ready|agents_running|merge_pending|debate_required|hr_review_required|factual_review_required|user_confirmation_required|blocked|final_package_ready",
    "task_type": "resume_review|resume_generation|job_search|jd_analysis|company_research|tailored_resume|major_positioning|personal_branding|learning_plan",
    "runtime_context_packet_ref": "",
    "secondary_prompt_injection_refs": [],
    "active_agents": [],
    "completed_agents": [],
    "blocked_agents": [],
    "shared_context_refs": [],
    "evidence_packet_refs": [],
    "debate_topics": [],
    "user_confirmation_points": [],
    "blocked_outputs": [],
    "next_action": "normalize_input|create_injections|dispatch_agents|merge_outputs|run_debate|run_hr_review|run_factual_review|ask_user_once|return_blocked|return_final_package"
  }
}
```

## Dispatch Gates

Before dispatching a specialist role, verify:

- `runtime_context_packet_ref` exists.
- the role has a `secondary_prompt_injection`.
- the injected prompt names the static base prompt, allowed user facts, database files, source policy, research tasks, hard-data weight tasks, required output fields, handoff fields, and debate fields.
- privacy constraints are included.
- blocked outputs are listed when user-owned facts or public evidence are missing.

If any item is missing, set `stage = "blocked"` or keep `stage = "injection_ready"` with `blocked_agents` and `next_action = "create_injections"`.

## Merge Rules

When subagent outputs return:

- preserve each role's `evidence_basis`, `weight_provenance`, `blocked_outputs`, `runtime_research_tasks`, and `needs_user_confirmation`.
- merge claims only when source policy and confidence are compatible.
- keep disagreements in `debate_topics`; do not erase or average away conflicts.
- if a downstream output depends on missing user-owned facts, set `user_confirmation_required`.
- if a downstream output depends on public evidence, create research tasks instead of asking the user.

## Debate And Review Routing

Use these routing rules:

- factual support, inflated claims, privacy, or interview defensibility conflicts go to `FactualReviewer`.
- HR readability, first-screen competitiveness, or personal packaging conflicts go to `HRSupervisor`.
- match, learning, branding, and resume claims with weak or conflicting evidence enter `debate_required`.
- missing user-owned facts enter `user_confirmation_required` with one compact question batch.
- missing public/official evidence becomes `runtime_research_tasks`.

## Completion Rules

Set `final_package_ready` only when:

- all required specialist outputs are present or explicitly blocked.
- unresolved disagreements are either resolved, documented, or converted into user confirmation/research tasks.
- resume drafts have passed `ResumeFormatGate` and `FactualReviewer` when a resume is produced.
- HR-supervised outputs have a `positioning_verdict`.
- all weights used in decisions have `runtime_weights` and/or `weight_provenance`, and unsupported weights are marked `not_available` or `needs_more_sources`.

If completion is impossible, return `blocked` with the minimum missing user facts, missing public research tasks, and the outputs that cannot be produced.
