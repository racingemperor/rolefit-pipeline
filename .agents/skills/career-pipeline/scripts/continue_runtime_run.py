#!/usr/bin/env python
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


USER_FACT_FIELDS = [
    "school_name",
    "major_name",
    "grade_or_year",
    "degree_level",
    "graduation_window",
    "project_competition_research_experience",
    "internship_experience",
    "target_location_or_company_if_any",
]


class ContinuationError(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def checksum(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert_known_fact(context: dict[str, Any], field: str, value: Any) -> None:
    if value in ("", None, [], {}):
        return
    facts = context.setdefault("known_user_facts", [])
    facts[:] = [fact for fact in facts if fact.get("field") != field]
    facts.append({"field": field, "value": value})


def require_profile(run_dir: Path) -> tuple[Path, dict[str, Any]]:
    profile_path = run_dir / "input" / "normalized" / "first_round_user_profile.json"
    payload = load_json(profile_path)
    profile = payload.get("first_round_user_profile")
    if not isinstance(profile, dict):
        raise ContinuationError("first_round_user_profile.json: missing first_round_user_profile")
    return profile_path, profile


def require_context(run_dir: Path) -> tuple[Path, dict[str, Any]]:
    context_path = run_dir / "input" / "normalized" / "runtime_context_packet.json"
    payload = load_json(context_path)
    context = payload.get("runtime_context_packet")
    if not isinstance(context, dict):
        raise ContinuationError("runtime_context_packet.json: missing runtime_context_packet")
    return context_path, context


def update_profile(profile: dict[str, Any], facts: dict[str, Any]) -> None:
    education = profile.setdefault("education_status", {})
    for field in ["school_name", "major_name", "grade_or_year", "degree_level", "graduation_window"]:
        if facts.get(field):
            education[field] = facts[field]

    if facts.get("project_competition_research_experience"):
        profile["project_competition_research_experience"] = facts[
            "project_competition_research_experience"
        ]
    if facts.get("internship_experience"):
        profile["internship_experience"] = facts["internship_experience"]

    target = profile.setdefault("target_direction", {})
    target_value = facts.get("target_location_or_company_if_any")
    if target_value:
        target.setdefault("target_locations", [])
        if isinstance(target["target_locations"], list) and target_value not in target["target_locations"]:
            target["target_locations"].append(target_value)
        target.setdefault("target_companies", [])
        target["target_note_from_user"] = target_value


def update_context(context: dict[str, Any], profile: dict[str, Any], facts: dict[str, Any]) -> None:
    education = profile.get("education_status", {})
    school_context = context.setdefault("school_context", {})
    for field in ["school_name", "major_name", "grade_or_year"]:
        if education.get(field):
            school_context[field] = education[field]
    for field in ["school_name", "major_name", "grade_or_year", "degree_level", "graduation_window"]:
        if facts.get(field):
            upsert_known_fact(context, field, facts[field])
    if facts.get("major_name"):
        context.setdefault("major_and_discipline", {})["normalized_major"] = facts["major_name"]

    if facts.get("project_competition_research_experience"):
        upsert_known_fact(
            context,
            "project_competition_research_experience",
            facts["project_competition_research_experience"],
        )
    if facts.get("internship_experience"):
        upsert_known_fact(context, "internship_experience", facts["internship_experience"])
    if facts.get("target_location_or_company_if_any"):
        upsert_known_fact(
            context,
            "target_location_or_company_if_any",
            facts["target_location_or_company_if_any"],
        )
        context.setdefault("target_context", {}).setdefault("target_locations", [])
        locations = context["target_context"]["target_locations"]
        if isinstance(locations, list) and facts["target_location_or_company_if_any"] not in locations:
            locations.append(facts["target_location_or_company_if_any"])

    missing = context.get("missing_user_owned_facts", [])
    if isinstance(missing, list):
        provided = {field for field in USER_FACT_FIELDS if facts.get(field)}
        context["missing_user_owned_facts"] = [field for field in missing if field not in provided]
    if not context.get("missing_user_owned_facts"):
        blocked = context.get("blocked_outputs", [])
        if isinstance(blocked, list):
            context["blocked_outputs"] = [
                item for item in blocked if item not in {"final_resume_draft", "application_direction"}
            ]
    context.setdefault("continuation_events", []).append(
        {
            "event_type": "user_fact_update",
            "updated_fields": sorted(field for field in USER_FACT_FIELDS if facts.get(field)),
            "created_at": utc_now(),
            "redaction_applied": True,
        }
    )


def rewrite_allowed_facts(run_dir: Path, context: dict[str, Any]) -> None:
    invocations_dir = run_dir / "invocations"
    if not invocations_dir.is_dir():
        return
    safe_fields = {
        "major_name",
        "grade_or_year",
        "skill",
        "school_name",
        "degree_level",
        "graduation_window",
        "project_competition_research_experience",
        "internship_experience",
        "target_location_or_company_if_any",
    }
    allowed = [
        fact for fact in context.get("known_user_facts", []) if fact.get("field") in safe_fields
    ]
    for path in invocations_dir.glob("*.allowed_user_facts.json"):
        write_json(path, {"allowed_user_facts": allowed})


def update_manifest(run_dir: Path, context_path: Path, profile_path: Path) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    payload = load_json(manifest_path)
    manifest = payload.get("execution_manifest")
    run_state = payload.get("run_state")
    if not isinstance(manifest, dict) or not isinstance(run_state, dict):
        raise ContinuationError("manifest.json: missing execution_manifest or run_state")

    manifest["updated_at"] = utc_now()
    manifest["current_stage"] = "injection_ready"
    run_state["stage"] = "injection_ready"
    manifest.setdefault("gate_status", {})["user_confirmation_resolved_when_needed"] = True
    manifest["gate_status"]["input_normalized"] = True
    manifest["gate_status"]["context_packet_created"] = True
    manifest["gate_status"]["secondary_injections_created"] = True
    run_state["user_confirmation_points"] = []
    run_state["next_action"] = "dispatch_agents"
    run_state["blocked_outputs"] = []
    run_state["active_agents"] = []
    run_state["completed_agents"] = []
    run_state["blocked_agents"] = []
    run_state["failed_invocations"] = []
    run_state["recovery_actions"] = ["run_public_research", "dispatch_agents"]

    for ref in manifest.get("artifact_refs", []):
        path = run_dir / ref.get("path", "")
        if path == context_path or path == profile_path:
            ref["checksum"] = checksum(path)
            ref["created_at"] = utc_now()
    write_json(manifest_path, payload)
    return payload


def continue_run(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    if not run_dir.is_dir():
        raise ContinuationError(f"run directory not found: {run_dir}")
    facts_source = args.user_facts_json
    if args.user_facts_json_file:
        facts_source = args.user_facts_json_file.read_text(encoding="utf-8")
    if not facts_source:
        raise ContinuationError("--user-facts-json or --user-facts-json-file is required")
    facts = json.loads(facts_source)
    if not isinstance(facts, dict):
        raise ContinuationError("--user-facts-json must decode to an object")

    profile_path, profile = require_profile(run_dir)
    context_path, context = require_context(run_dir)
    update_profile(profile, facts)
    update_context(context, profile, facts)
    write_json(profile_path, {"first_round_user_profile": profile})
    write_json(context_path, {"runtime_context_packet": context})
    rewrite_allowed_facts(run_dir, context)
    manifest_payload = update_manifest(run_dir, context_path, profile_path)

    log_path = run_dir / "logs" / "user_continuation_events.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "execution_event": {
                        "event_id": f"{manifest_payload['execution_manifest']['run_id']}-user-continuation",
                        "run_id": manifest_payload["execution_manifest"]["run_id"],
                        "stage": "user_confirmation_required",
                        "agent_id": "career-orchestrator",
                        "event_type": "ask_user",
                        "input_refs": ["user_supplied_followup_facts"],
                        "output_refs": [rel(context_path, run_dir), rel(profile_path, run_dir)],
                        "status": "done",
                        "timestamp_or_sequence": utc_now(),
                        "redaction_applied": True,
                    }
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    return {
        "continuation_response": {
            "exit_status": "ready_for_dispatch",
            "run_id": manifest_payload["execution_manifest"]["run_id"],
            "execution_manifest_ref": str(run_dir / "manifest.json"),
            "runtime_context_packet_ref": rel(context_path, run_dir),
            "next_action": "dispatch_agents",
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Continue an existing career-pipeline run with user-owned facts.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--user-facts-json")
    parser.add_argument("--user-facts-json-file", type=Path)
    args = parser.parse_args(argv)
    try:
        response = continue_run(args)
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, KeyError, ContinuationError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
