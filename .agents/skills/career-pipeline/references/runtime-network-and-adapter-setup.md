# Runtime Network And Adapter Setup

Use this reference before enabling real network fetches or real subagent execution for the career pipeline.

The runtime has two separate gates:

- Codex platform permission: whether commands and subagents may use the network at all.
- Career pipeline source permission: whether a specific public source is allowed by `source-policy.md` and the run's public source plan.

Do not treat platform network access as permission to crawl recruitment platforms, login-only pages, private candidate data, private chats, HR backends, or non-public resumes.

## Codex Network Permission

For repeatable local runs, configure Codex command network access in `~/.codex/config.toml` or a trusted project `.codex/config.toml`:

```toml
[sandbox_workspace_write]
network_access = true

[features.network_proxy]
enabled = true
domains = {
  "**.zhipin.com" = "allow",
  "**.liepin.com" = "allow",
  "**.lagou.com" = "allow",
  "**.nowcoder.com" = "allow",
  "**.linkedin.com" = "allow",
  "**.bytedance.com" = "allow",
  "**.tencent.com" = "allow",
  "**.dji.com" = "allow",
  "**.catl.com" = "allow",
  "**.zhipuai.cn" = "allow"
}
```

Restart Codex after changing config. The domain list is an example allowlist; keep it scoped to the sources needed by the run. Do not use a global `*` allow rule unless the user explicitly accepts broad outbound access risk.

Web search and shell network access are separate. A web search result is not a validated evidence packet until it has been converted into a source-plan-backed evidence packet and passed through the source policy checks.

## Pipeline Source Permission

Before any real source fetch:

1. Build a run with `simulate_runtime_run.py` or the future real runner.
2. Build prompt bundles and the public source plan.
3. Ask the user or controller to acknowledge the source policy.
4. Provide an explicit `sources.json` containing only allowed public sources.
5. Fetch and backfill evidence.

Example:

```bash
cd .agents/skills/career-pipeline
python scripts/build_public_source_plan.py --run-dir ../../../.career-pipeline-runs/<run_id>
python scripts/fetch_public_sources.py --run-dir ../../../.career-pipeline-runs/<run_id> --sources-json <allowed_public_sources.json>
python scripts/backfill_public_evidence.py --run-dir ../../../.career-pipeline-runs/<run_id> --evidence-json ../../../.career-pipeline-runs/<run_id>/evidence/fetched_public_evidence.json
```

Minimal `sources.json` shape:

```json
{
  "sources": [
    {
      "task_id": "target-current-jd-verification",
      "source_type": "official_or_primary",
      "source_ref": "https://careers.example.com/jobs/123",
      "field": "current_jd_text"
    }
  ]
}
```

Allowed source types include `official_or_primary`, `official_school_notice`, `recruitment_platform_jd`, `verified_hr_public_post`, `candidate_experience_secondary`, `social_media_weak`, `public_report`, and `user_provided`.

Forbidden sources include `private_resume`, `private_chat`, `private_hr_message`, `recruiter_backend`, `login_only_page`, and `non_public_candidate_profile`. A login-only page remains forbidden even if the user is personally logged in. Social media weak signals must not set final decisions or weights alone.

When `execute_subagent_plan.py` is used with network execution flags, it must include both human approval and source policy acknowledgement:

```bash
python scripts/execute_subagent_plan.py \
  --run-dir ../../../.career-pipeline-runs/<run_id> \
  --execute \
  --human-approved \
  --allow-network \
  --source-policy-ack \
  --adapter <configured-adapter-name-or-path>
```

Without `source_policy_ack`, network execution must fail.

## Real Subagent Adapter

The repository scripts generate adapter-ready contracts. They do not directly call Codex Desktop subagent tools.

Current handoff flow:

```bash
python scripts/build_subagent_plan.py --run-dir ../../../.career-pipeline-runs/<run_id> --build-prompt-bundles
python scripts/build_subagent_work_orders.py --run-dir ../../../.career-pipeline-runs/<run_id>
```

The adapter reads:

- `invocations/subagent_work_orders.json`
- each order's `prompt_bundle_ref`
- each order's `expected_backfill_contract`
- the run's source and privacy constraints

The adapter must return one JSON file per role with:

- `invocation_ref`
- `role_output_packet`
- `error_recovery_state`

Each `role_output_packet` must include the required fields from `role-output-contracts.md`. Failed or malformed role outputs must not include final decision fields such as `fit_score`, `application_priority`, `application_strategy`, `final_resume_draft`, or `tailored_resume`.

Backfill role outputs after the real adapter finishes:

```bash
python scripts/execute_subagent_plan.py \
  --run-dir ../../../.career-pipeline-runs/<run_id> \
  --backfill-output job-scout=C:/path/to/job-scout.output.json \
  --backfill-output hr-supervisor=C:/path/to/hr-supervisor.output.json
```

## Adapter Options

Use one of these adapter patterns:

1. Codex Desktop manual controller adapter.
   - The main Codex thread reads `subagent_work_orders.json`.
   - It reads each `prompt_bundle_ref`.
   - It calls the current-session `spawn_agent` tool for each bounded role task.
   - It asks each subagent to return a strict role output JSON.
   - It writes or supplies those JSON files for backfill.
   - This is valid for interactive testing, but normal Python scripts cannot call the conversation's `spawn_agent` tool directly.

2. Codex CLI adapter.
   - A runner reads each work order.
   - It invokes `codex exec` with the prompt bundle content.
   - It stores each final answer as a role output JSON.
   - It backfills validated outputs into the run.
   - Use this for local automation when Codex CLI access and auth are configured.

3. API or Agents SDK adapter.
   - An external runner calls an agent API with each role prompt bundle.
   - It validates the model output against the role output schema.
   - It backfills accepted packets.
   - Use this for productized execution, billing control, and independent observability.

Do not mark a run as real subagent execution merely because work orders exist. Real execution is true only after adapter-produced role output packets are validated and backfilled.

## Completion Checklist

Before returning a final career package:

- Platform network permission is enabled only when needed.
- The public source plan exists.
- `source_policy_ack` is recorded for network execution.
- No login-only, private, backend, or non-public candidate source is used.
- Each runtime weight has hard-data provenance or is marked `not_available` / `needs_more_sources`.
- Each role output has a valid `role_output_packet`.
- HR supervision and factual review gates are complete when required.
- Blocked outputs remain blocked instead of being converted into guessed recommendations.
