# Runtime Execution Layer

This protocol defines the local execution shell for a Codex-native career pipeline. It is a design contract, not a deployed runner.

## Scope

The execution layer coordinates a local run. It does not make career judgments. It:

- creates a run manifest.
- records input and output artifacts.
- invokes role subagents from `.codex/agents/*.toml`.
- enforces prompt-injection, privacy, source, weight, debate, HR, and factual gates.
- tracks errors, degraded outputs, and blocked outputs.

Do not hide required state in chat history. Any state needed by another role should be written as a structured artifact or referenced by an `artifact_ref`.

## Execution Sequence

Use this sequence for a full user-side run:

```text
create run_id and run directory
  -> capture user input/material references
  -> invoke InputNormalizer
  -> persist first_round_user_profile and runtime_context_packet
  -> invoke CareerOrchestrator to create secondary_prompt_injections
  -> convert each secondary_prompt_injection into a subagent invocation packet
  -> dispatch required role subagents
  -> validate role outputs against role-output-contracts
  -> merge evidence, blocked outputs, runtime weights, and debate fields
  -> run debate routes when conflicts remain
  -> run HRSupervisor for presentation readiness
  -> run ResumeFormatGate, ResumeArchitect, and FactualReviewer when a resume is produced
  -> produce final decision package or blocked package
```

Specialist subagents must not run before `runtime_context_packet` and `secondary_prompt_injections` exist.

## Execution Manifest

Each run should create a manifest:

```json
{
  "execution_manifest": {
    "run_id": "",
    "created_at": "",
    "updated_at": "",
    "codex_surface": "desktop|cli|plugin|unknown",
    "repository_ref": "",
    "skill_ref": ".agents/skills/career-pipeline/SKILL.md",
    "task_type": "resume_review|resume_generation|job_search|jd_analysis|company_research|tailored_resume|major_positioning|personal_branding|learning_plan",
    "user_goal_summary": "",
    "privacy_mode": "redacted_intermediate|user_authorized_final_contact|strict_no_contact",
    "run_dir_ref": "",
    "current_stage": "intake_received|input_normalized|context_packet_created|injection_ready|agents_running|merge_pending|debate_required|hr_review_required|factual_review_required|user_confirmation_required|blocked|final_package_ready",
    "runtime_context_packet_ref": "",
    "secondary_prompt_injection_refs": [],
    "subagent_invocation_refs": [],
    "artifact_manifest_ref": "",
    "artifact_refs": [],
    "evidence_packet_refs": [],
    "runtime_weights_ref": "",
    "gate_status": {
      "input_normalized": false,
      "context_packet_created": false,
      "secondary_injections_created": false,
      "specialists_completed_or_blocked": false,
      "debate_completed_or_recorded": false,
      "hr_review_completed": false,
      "factual_review_completed_when_needed": false,
      "user_confirmation_resolved_when_needed": false
    },
    "error_recovery_state_ref": "",
    "final_package_ref": ""
  }
}
```

`repository_ref` may be a git commit hash, branch name, or local path when git metadata is unavailable.

`execution_manifest.current_stage` must equal `run_state.stage` for the same run. If they differ, the orchestrator should mark the run as `schema_validation_failed` and repair the manifest before dispatching more agents.

## Stage Responsibilities

- `InputNormalizer`: normalize free-form user materials, produce `first_round_user_profile`, `runtime_context_packet`, and one compact missing-fact prompt.
- `CareerOrchestrator`: choose route, create `secondary_prompt_injections`, and create the subagent invocation plan.
- role subagents: collect or check role-specific evidence, output structured role packets, and avoid cross-role decisions.
- merge step: combine evidence and conflicts without erasing disagreements.
- HR gate: check first-screen readability, credibility, and competitive signal clarity.
- factual gate: check truthfulness, privacy, overclaiming, and interview defensibility.

## Completion Rules

Return `final_package_ready` only when every required gate for the requested final output is completed or documented as not applicable.

Do not mark a run as `final_package_ready` when a required gate is blocked. If a required gate is blocked, return `blocked` with a `blocked_package`. If safe partial outputs exist, return a degraded or blocked package that names those outputs rather than a final package.

If a required role fails or evidence is missing, return a blocked or degraded package with:

- exact blocked outputs.
- missing user-owned facts, if any.
- public research tasks, if any.
- degraded outputs that remain safe to show.
- next action for the orchestrator or user.

## Local Runner Contract

This repository does not ship an executable runner yet, but a future runner should expose this contract:

```json
{
  "runner_request": {
    "command": "career-pipeline-run",
    "mode": "simulate|execute",
    "task_type": "",
    "input_refs": [],
    "allowed_network": true,
    "run_dir": ".career-pipeline-runs/<run_id>",
    "requested_outputs": []
  },
  "runner_response": {
    "exit_status": "success|blocked|degraded|failed",
    "run_id": "",
    "execution_manifest_ref": "",
    "final_package_ref": "",
    "blocked_package_ref": "",
    "error_recovery_state_ref": ""
  }
}
```

Suggested exit semantics:

- `success`: final package is ready and required gates passed.
- `blocked`: final package is not produced; blocked package explains missing user facts, public research, consent, or failed gates.
- `degraded`: only safe partial outputs are available.
- `failed`: runner or schema validation failed before a safe package could be produced.

## Non-Goals

- This protocol does not define a specific CLI command.
- This protocol does not require network access for every run.
- This protocol does not store private user data in git.
- This protocol does not replace the source policy, weight engine, or role output contracts.
