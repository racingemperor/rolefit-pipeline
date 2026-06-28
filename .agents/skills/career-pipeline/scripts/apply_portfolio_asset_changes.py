#!/usr/bin/env python
import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_plan(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_inside_root(root: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("change path must be a relative path")
    target = (root / relative_path).resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"change path is outside authorized root: {relative_path}") from exc
    return target


def require_authorized(plan: dict[str, Any]) -> Path:
    authorization = plan.get("authorization")
    if not isinstance(authorization, dict) or authorization.get("granted") is not True:
        raise ValueError("portfolio asset change is not authorized")
    allowed_actions = set(authorization.get("allowed_actions") or [])
    if "write_file" not in allowed_actions:
        raise ValueError("write_file action is not authorized")
    allowed_root = authorization.get("allowed_root")
    if not isinstance(allowed_root, str) or not allowed_root.strip():
        raise ValueError("authorization.allowed_root is required")
    root = Path(allowed_root).expanduser().resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    return root


def apply_portfolio_asset_changes(plan: dict[str, Any]) -> dict[str, Any]:
    root = require_authorized(plan)
    changes = plan.get("changes")
    if not isinstance(changes, list) or not changes:
        raise ValueError("changes must be a non-empty list")

    applied_changes: list[dict[str, str]] = []
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            raise ValueError(f"changes[{index}] must be an object")
        path = str(change.get("path") or "")
        content = change.get("content")
        if not isinstance(content, str):
            raise ValueError(f"changes[{index}].content must be a string")
        target = resolve_inside_root(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        applied_changes.append(
            {
                "action": "write_file",
                "path": path,
                "target_ref": str(target),
            }
        )

    return {
        "status": "applied",
        "authorized_root": str(root),
        "applied_changes": applied_changes,
        "handoff_to": ["personal-branding-strategist", "resume-polisher", "factual-reviewer", "hr-supervisor"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply authorized portfolio, website, or README file changes.")
    parser.add_argument("--plan-json", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        response = apply_portfolio_asset_changes(load_plan(args.plan_json))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"portfolio_asset_apply_response": response}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
