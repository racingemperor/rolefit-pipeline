#!/usr/bin/env python
import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_plan(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized(path_ref: str) -> str:
    if not path_ref:
        raise ValueError("path ref is required")
    return str(Path(path_ref).expanduser().resolve(strict=False))


def normalized_set(path_refs: list[Any]) -> set[str]:
    return {normalized(str(path_ref)) for path_ref in path_refs if str(path_ref).strip()}


def require_authorized(plan: dict[str, Any]) -> tuple[Path, Path]:
    authorization = plan.get("authorization")
    if not isinstance(authorization, dict) or authorization.get("granted") is not True:
        raise ValueError("resume polish is not authorized")

    source_ref = normalized(str(plan.get("source_resume_ref") or ""))
    output_ref = normalized(str(plan.get("output_resume_ref") or ""))
    allowed_inputs = normalized_set(list(authorization.get("allowed_input_refs") or []))
    allowed_outputs = normalized_set(list(authorization.get("allowed_output_refs") or []))

    if source_ref not in allowed_inputs:
        raise ValueError(f"source_resume_ref is not authorized: {source_ref}")
    if output_ref not in allowed_outputs:
        raise ValueError(f"output_resume_ref is not authorized: {output_ref}")

    return Path(source_ref), Path(output_ref)


def apply_resume_polish(plan: dict[str, Any]) -> dict[str, Any]:
    source_path, output_path = require_authorized(plan)
    if not source_path.is_file():
        raise ValueError(f"source_resume_ref does not exist: {source_path}")

    draft = plan.get("polished_resume_draft")
    if not isinstance(draft, str) or not draft.strip():
        raise ValueError("polished_resume_draft is required")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(draft, encoding="utf-8")

    return {
        "status": "applied",
        "source_resume_ref": str(source_path),
        "output_resume_ref": str(output_path),
        "preserve_user_resume_format": bool(plan.get("preserve_user_resume_format")),
        "applied_changes": [
            {
                "action": "write_polished_resume_draft",
                "target_ref": str(output_path),
                "source_ref": str(source_path),
            }
        ],
        "handoff_to": ["resume-architect", "factual-reviewer", "hr-supervisor"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply an authorized resume polish operation packet.")
    parser.add_argument("--plan-json", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        response = apply_resume_polish(load_plan(args.plan_json))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"resume_polish_apply_response": response}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
