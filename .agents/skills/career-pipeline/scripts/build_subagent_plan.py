#!/usr/bin/env python
import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def read_invocation(run_dir: Path, invocation_ref: str) -> dict[str, Any]:
    payload = load_json(run_dir / invocation_ref)
    invocation = payload.get("subagent_invocation")
    if not isinstance(invocation, dict):
        raise ValueError(f"{invocation_ref}: missing subagent_invocation")
    return invocation


def build_plan(run_dir: Path) -> dict[str, Any]:
    manifest_payload = load_json(run_dir / "manifest.json")
    manifest = manifest_payload.get("execution_manifest")
    if not isinstance(manifest, dict):
        raise ValueError("manifest.json: missing execution_manifest")

    invocation_refs = manifest.get("subagent_invocation_refs")
    if not isinstance(invocation_refs, list) or not invocation_refs:
        raise ValueError("manifest.json: missing subagent_invocation_refs")

    queue = []
    for index, invocation_ref in enumerate(invocation_refs):
        invocation = read_invocation(run_dir, invocation_ref)
        input_packet_ref = invocation["input_packet_ref"]
        allowed_user_facts_ref = invocation["allowed_user_facts_ref"]
        context_ref = invocation["runtime_context_packet_ref"]
        queue.append(
            {
                "queue_index": index,
                "target_agent": invocation["target_agent"],
                "invocation_ref": invocation_ref,
                "input_refs": [context_ref, input_packet_ref, allowed_user_facts_ref],
                "output_artifact_target": invocation["output_artifact_target"],
                "dispatch_mode": "plan_only",
                "status": "planned",
                "allowed_network": False,
                "requires_human_approval": True,
                "privacy_class": "derived",
                "blocked_until": [
                    "human_confirms_real_subagent_execution",
                    "allowed_network_policy_resolved",
                    "source_policy_loaded",
                ],
            }
        )

    return {
        "subagent_invocation_plan": {
            "run_id": manifest["run_id"],
            "plan_status": "ready",
            "created_from_manifest_ref": "manifest.json",
            "dispatch_queue": queue,
            "execution_note": "Plan only: this file is not proof that subagents ran.",
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a plan-only subagent dispatch queue for a simulated run.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output", default="invocations/subagent_invocation_plan.json")
    args = parser.parse_args(argv)
    try:
        plan = build_plan(args.run_dir)
        output_path = args.run_dir / args.output
        write_json(output_path, plan)
        print(
            json.dumps(
                {
                    "planner_response": {
                        "exit_status": "success",
                        "run_id": plan["subagent_invocation_plan"]["run_id"],
                        "subagent_plan_ref": rel(output_path, args.run_dir),
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
