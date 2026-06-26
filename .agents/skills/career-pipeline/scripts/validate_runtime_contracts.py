#!/usr/bin/env python
import argparse
import json
import sys
from pathlib import Path
from typing import Any


INJECTION_REQUIRED_FIELDS = [
    "target_agent",
    "base_prompt_ref",
    "runtime_context_packet_ref",
    "role_specific_context",
    "allowed_user_facts",
    "research_tasks",
    "hard_data_weight_tasks",
    "database_files_to_read",
    "source_policy_refs",
    "invocation_contract",
    "required_output_fields",
    "handoff_contract",
    "debate_contract",
]

INVOCATION_REQUIRED_FIELDS = [
    "invocation_id",
    "run_id",
    "target_agent",
    "base_prompt_ref",
    "secondary_prompt_injection_ref",
    "runtime_context_packet_ref",
    "input_packet_ref",
    "allowed_user_facts_ref",
    "output_artifact_target",
    "privacy_constraints",
    "expected_artifact_types",
    "required_log_events",
    "retry_allowed",
    "on_failure",
    "status",
]

LIST_FIELDS = [
    "allowed_user_facts",
    "research_tasks",
    "hard_data_weight_tasks",
    "database_files_to_read",
    "source_policy_refs",
    "required_output_fields",
    "handoff_contract",
    "debate_contract",
]

FINAL_GATE_FIELDS = [
    "input_normalized",
    "context_packet_created",
    "secondary_injections_created",
    "specialists_completed_or_blocked",
    "debate_completed_or_recorded",
    "hr_review_completed",
    "factual_review_completed_when_needed",
    "user_confirmation_resolved_when_needed",
]

ALLOWED_FAILURE_ACTIONS = {
    "return_blocked",
    "rerun_with_more_context",
    "handoff_to_orchestrator",
}

ALLOWED_INVOCATION_STATUSES = {
    "not_started",
    "running",
    "done",
    "blocked",
    "failed",
    "malformed",
}


class ValidationError(Exception):
    pass


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def require_non_empty(value: Any, field: str, where: str) -> None:
    if value in ("", None, [], {}):
        raise ValidationError(f"{where}: required field `{field}` is empty")


def require_list(value: Any, field: str, where: str) -> None:
    if not isinstance(value, list):
        raise ValidationError(f"{where}: `{field}` must be a list")


def get_injections(payload: dict[str, Any]) -> list[dict[str, Any]]:
    injections = payload.get("secondary_prompt_injections")
    if injections is None and "secondary_prompt_injection" in payload:
        injections = [payload["secondary_prompt_injection"]]
    if not isinstance(injections, list) or not injections:
        raise ValidationError("root: `secondary_prompt_injections` must be a non-empty list")
    return injections


def validate_injection(injection: dict[str, Any], index: int) -> None:
    where = f"secondary_prompt_injections[{index}]"
    for field in INJECTION_REQUIRED_FIELDS:
        if field not in injection:
            raise ValidationError(f"{where}: missing required field `{field}`")
        require_non_empty(injection[field], field, where)

    for field in LIST_FIELDS:
        require_list(injection[field], field, where)
        require_non_empty(injection[field], field, where)

    if not isinstance(injection["role_specific_context"], dict):
        raise ValidationError(f"{where}: `role_specific_context` must be an object")

    target_agent = injection["target_agent"]
    expected_base = f".codex/agents/{target_agent}.toml"
    if injection["base_prompt_ref"] != expected_base:
        raise ValidationError(
            f"{where}: `base_prompt_ref` must be `{expected_base}` for target `{target_agent}`"
        )

    contract = injection["invocation_contract"]
    if not isinstance(contract, dict):
        raise ValidationError(f"{where}: `invocation_contract` must be an object")
    validate_invocation_contract(injection, contract, where)


def validate_invocation_contract(
    injection: dict[str, Any],
    contract: dict[str, Any],
    where: str,
) -> None:
    for field in INVOCATION_REQUIRED_FIELDS:
        if field not in contract:
            raise ValidationError(f"{where}.invocation_contract: missing required field `{field}`")
        require_non_empty(contract[field], field, f"{where}.invocation_contract")

    for field in [
        "database_files_to_read",
        "source_policy_refs",
        "research_tasks",
        "hard_data_weight_tasks",
        "required_output_fields",
        "privacy_constraints",
        "handoff_contract",
        "debate_contract",
        "expected_artifact_types",
        "required_log_events",
    ]:
        if field in contract:
            require_list(contract[field], field, f"{where}.invocation_contract")

    for field in ["target_agent", "base_prompt_ref", "runtime_context_packet_ref"]:
        if contract[field] != injection[field]:
            raise ValidationError(
                f"{where}.invocation_contract: `{field}` must match secondary injection"
            )

    if contract["on_failure"] not in ALLOWED_FAILURE_ACTIONS:
        raise ValidationError(
            f"{where}.invocation_contract: `on_failure` must be one of {sorted(ALLOWED_FAILURE_ACTIONS)}"
        )
    if contract["status"] not in ALLOWED_INVOCATION_STATUSES:
        raise ValidationError(
            f"{where}.invocation_contract: `status` must be one of {sorted(ALLOWED_INVOCATION_STATUSES)}"
        )


def canonical_invocation(injection: dict[str, Any]) -> dict[str, Any]:
    contract = dict(injection["invocation_contract"])
    for field in [
        "database_files_to_read",
        "source_policy_refs",
        "research_tasks",
        "hard_data_weight_tasks",
        "required_output_fields",
        "privacy_constraints",
        "handoff_contract",
        "debate_contract",
    ]:
        contract[field] = contract.get(field) or injection[field]
    contract.setdefault("timeout_or_budget_hint", "")
    contract.setdefault("retry_allowed", True)
    contract.setdefault("status", "not_started")
    return {"subagent_invocation": contract}


def build_invocations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    injections = get_injections(payload)
    for index, injection in enumerate(injections):
        validate_injection(injection, index)
    return [canonical_invocation(injection) for injection in injections]


def validate_injections(payload: dict[str, Any]) -> None:
    build_invocations(payload)


def validate_manifest(payload: dict[str, Any]) -> None:
    manifest = payload.get("execution_manifest")
    run_state = payload.get("run_state")
    if not isinstance(manifest, dict):
        raise ValidationError("root: missing `execution_manifest` object")
    if not isinstance(run_state, dict):
        raise ValidationError("root: missing `run_state` object")

    current_stage = manifest.get("current_stage")
    run_stage = run_state.get("stage")
    require_non_empty(current_stage, "current_stage", "execution_manifest")
    require_non_empty(run_stage, "stage", "run_state")
    if current_stage != run_stage:
        raise ValidationError(
            "execution_manifest.current_stage must equal run_state.stage before dispatch continues"
        )

    for field in [
        "runtime_context_packet_ref",
        "secondary_prompt_injection_refs",
        "subagent_invocation_refs",
    ]:
        manifest_value = manifest.get(field)
        run_state_value = run_state.get(field)
        if manifest_value != run_state_value:
            raise ValidationError(f"`{field}` must match between execution_manifest and run_state")

    if current_stage == "final_package_ready":
        gate_status = manifest.get("gate_status")
        if not isinstance(gate_status, dict):
            raise ValidationError(
                "execution_manifest: `gate_status` is required for final_package_ready"
            )
        missing_or_false = [
            field for field in FINAL_GATE_FIELDS if gate_status.get(field) is not True
        ]
        if missing_or_false:
            names = ", ".join(missing_or_false)
            raise ValidationError(
                f"final_package_ready is invalid while required gates are blocked or false: {names}"
            )
        require_non_empty(
            manifest.get("final_package_ref"),
            "final_package_ref",
            "execution_manifest",
        )
        for field in [
            "runtime_context_packet_ref",
            "secondary_prompt_injection_refs",
            "subagent_invocation_refs",
        ]:
            require_non_empty(manifest.get(field), field, "execution_manifest")

    if current_stage == "blocked" and manifest.get("final_package_ref"):
        raise ValidationError("blocked runs must not set `final_package_ref`")


def validate_repository(root: Path) -> None:
    agents_dir = root / ".codex" / "agents"
    skill_file = root / ".agents" / "skills" / "career-pipeline" / "SKILL.md"
    if not skill_file.is_file():
        raise ValidationError("repository: missing career-pipeline SKILL.md")
    if not agents_dir.is_dir():
        raise ValidationError("repository: missing .codex/agents directory")
    agent_files = sorted(agents_dir.glob("*.toml"))
    if not agent_files:
        raise ValidationError("repository: no role prompt TOML files found")
    for agent_file in agent_files:
        text = agent_file.read_text(encoding="utf-8")
        for needle in [
            "runtime_context_packet_ref",
            "role_output_packet",
            "error_recovery_state",
            "Hard-data weight rule",
        ]:
            if needle not in text:
                raise ValidationError(f"{agent_file}: missing `{needle}`")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate local career-pipeline runtime contracts."
    )
    parser.add_argument("--injections", type=Path, help="JSON file containing secondary_prompt_injections")
    parser.add_argument("--manifest", type=Path, help="JSON file containing execution_manifest and run_state")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to validate")
    parser.add_argument("--emit-invocations", action="store_true", help="Emit canonical subagent_invocations")
    args = parser.parse_args(argv)

    try:
        output: dict[str, Any] = {"status": "ok"}
        if args.injections:
            payload = load_json(args.injections)
            invocations = build_invocations(payload)
            if args.emit_invocations:
                output["subagent_invocations"] = invocations
        if args.manifest:
            validate_manifest(load_json(args.manifest))
        if not args.injections and not args.manifest:
            validate_repository(args.repo_root)
        if args.emit_invocations:
            print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
