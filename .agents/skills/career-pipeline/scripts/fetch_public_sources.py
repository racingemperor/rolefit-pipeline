#!/usr/bin/env python
import argparse
import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


ALLOWED_SOURCE_TYPES = {
    "user_provided",
    "official_or_primary",
    "official_school_notice",
    "recruitment_platform_jd",
    "verified_hr_public_post",
    "candidate_experience_secondary",
    "social_media_weak",
    "public_report",
}

FORBIDDEN_SOURCE_TYPES = {
    "private_resume",
    "private_chat",
    "private_hr_message",
    "recruiter_backend",
    "login_only_page",
    "non_public_candidate_profile",
}

FINAL_DECISION_SOURCE_TYPES = {
    "official_or_primary",
    "official_school_notice",
    "recruitment_platform_jd",
    "verified_hr_public_post",
    "user_provided",
    "public_report",
}

WEIGHT_SOURCE_TYPES = FINAL_DECISION_SOURCE_TYPES | {"candidate_experience_secondary"}


class PublicSourceFetchError(Exception):
    pass


def utc_now_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def load_source_plan(run_dir: Path, source_plan_ref: str) -> dict[str, Any]:
    payload = load_json(run_dir / source_plan_ref)
    plan = payload.get("public_source_research_plan")
    if not isinstance(plan, dict):
        raise PublicSourceFetchError(f"{source_plan_ref}: missing public_source_research_plan")
    return plan


def source_tasks_by_id(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks = plan.get("research_tasks")
    if not isinstance(tasks, list) or not tasks:
        raise PublicSourceFetchError("public source plan has no research_tasks")
    return {task["task_id"]: task for task in tasks if isinstance(task, dict) and "task_id" in task}


def unwrap_sources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise PublicSourceFetchError("sources must be a non-empty list")
    return sources


def fetch_text(source_ref: str, timeout_seconds: int) -> str:
    parsed = urlparse(source_ref)
    if parsed.scheme == "file":
        path = unquote(parsed.path)
        if re.match(r"^/[A-Za-z]:/", path):
            path = path[1:]
        return Path(path).read_text(encoding="utf-8", errors="replace")
    if parsed.scheme not in {"http", "https"}:
        raise PublicSourceFetchError(f"unsupported source scheme `{parsed.scheme}`")
    request = urllib.request.Request(
        source_ref,
        headers={"User-Agent": "career-pipeline-public-source-fetcher/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        content_type = response.headers.get("content-type", "")
        if "text" not in content_type and "html" not in content_type and "json" not in content_type:
            raise PublicSourceFetchError(f"unsupported content-type `{content_type}`")
        raw = response.read(512_000)
    return raw.decode("utf-8", errors="replace")


def to_plain_text(raw: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>", " ", raw)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def evidence_strength(source_type: str) -> str:
    if source_type in {"official_or_primary", "official_school_notice", "user_provided"}:
        return "strong"
    if source_type in {"recruitment_platform_jd", "verified_hr_public_post", "public_report"}:
        return "medium"
    return "weak"


def confidence_for(source_type: str) -> str:
    if source_type in {"official_or_primary", "official_school_notice"}:
        return "high"
    if source_type in {"recruitment_platform_jd", "verified_hr_public_post", "user_provided", "public_report"}:
        return "medium"
    return "low"


def validate_source(source: dict[str, Any], tasks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for field in ["task_id", "source_type", "source_ref", "field"]:
        if source.get(field) in ("", None):
            raise PublicSourceFetchError(f"source: `{field}` is required")
    source_type = source["source_type"]
    if source_type in FORBIDDEN_SOURCE_TYPES:
        raise PublicSourceFetchError(f"forbidden source_type `{source_type}`")
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise PublicSourceFetchError(f"unsupported source_type `{source_type}`")
    task_id = source["task_id"]
    if task_id not in tasks:
        raise PublicSourceFetchError(f"task_id `{task_id}` is not in the public source plan")
    plan_task = tasks[task_id]
    if plan_task.get("requires_login") is True:
        raise PublicSourceFetchError(f"task_id `{task_id}` requires login and cannot be fetched")
    if source_type == "social_media_weak":
        source["may_set_final_decision"] = False
        source["may_set_weight"] = False
    else:
        source.setdefault("may_set_final_decision", source_type in FINAL_DECISION_SOURCE_TYPES)
        source.setdefault("may_set_weight", source_type in WEIGHT_SOURCE_TYPES)
    return source


def fetch_sources(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    plan = load_source_plan(run_dir, args.source_plan_ref)
    tasks = source_tasks_by_id(plan)
    sources = unwrap_sources(load_json(args.sources_json))
    packets = []
    source_index = []
    for index, source in enumerate(sources):
        source = validate_source(dict(source), tasks)
        raw = fetch_text(source["source_ref"], args.timeout_seconds)
        plain = to_plain_text(raw)
        if not plain:
            raise PublicSourceFetchError(f"source[{index}] produced empty text")
        excerpt = plain[: args.max_excerpt_chars]
        source_type = source["source_type"]
        evidence_id = source.get("evidence_id") or f"ev-{source['task_id']}-{index}"
        packet = {
            "evidence_packet": {
                "evidence_id": evidence_id,
                "claim_id": source["task_id"],
                "field": source["field"],
                "source_type": source_type,
                "source_ref": source["source_ref"],
                "artifact_ref": "",
                "retrieved_or_published_date": source.get("retrieved_or_published_date") or utc_now_date(),
                "freshness": source.get("freshness") or "0_6_months",
                "evidence_strength": source.get("evidence_strength") or evidence_strength(source_type),
                "inference_level": source.get("inference_level") or "none",
                "privacy_class": "public" if source_type != "user_provided" else "user_private",
                "confidence": source.get("confidence") or confidence_for(source_type),
                "may_set_final_decision": source["may_set_final_decision"],
                "may_set_weight": source["may_set_weight"],
                "excerpt": excerpt,
            }
        }
        packets.append(packet)
        source_index.append(
            {
                "evidence_id": evidence_id,
                "task_id": source["task_id"],
                "source_type": source_type,
                "source_ref": source["source_ref"],
                "excerpt_chars": len(excerpt),
            }
        )
    evidence_path = run_dir / args.output
    source_index_path = run_dir / args.source_index_output
    write_json(evidence_path, {"evidence_packets": packets})
    write_json(source_index_path, {"fetched_source_index": source_index})
    return {
        "public_source_fetch_response": {
            "exit_status": "success",
            "run_id": plan["run_id"],
            "accepted_count": len(packets),
            "evidence_json_ref": rel(evidence_path, run_dir),
            "fetched_source_index_ref": rel(source_index_path, run_dir),
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch allowed public sources into evidence packets.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--sources-json", required=True, type=Path)
    parser.add_argument("--source-plan-ref", default="evidence/public_source_research_plan.json")
    parser.add_argument("--output", default="evidence/fetched_public_evidence.json")
    parser.add_argument("--source-index-output", default="evidence/fetched_source_index.json")
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument("--max-excerpt-chars", type=int, default=1200)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(fetch_sources(args), ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, KeyError, PublicSourceFetchError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
