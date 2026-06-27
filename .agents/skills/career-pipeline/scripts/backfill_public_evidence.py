#!/usr/bin/env python
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_EVIDENCE_FIELDS = [
    "evidence_id",
    "claim_id",
    "field",
    "source_type",
    "source_ref",
    "artifact_ref",
    "retrieved_or_published_date",
    "freshness",
    "evidence_strength",
    "inference_level",
    "privacy_class",
    "confidence",
]

ALLOWED_SOURCE_TYPES = {
    "user_provided",
    "official_or_primary",
    "official_school_notice",
    "recruitment_platform_jd",
    "verified_hr_public_post",
    "candidate_experience_secondary",
    "social_media_weak",
    "repository_prior",
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


class EvidenceBackfillError(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payloads: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for payload in payloads:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def load_source_plan(run_dir: Path, source_plan_ref: str) -> dict[str, Any]:
    payload = load_json(run_dir / source_plan_ref)
    plan = payload.get("public_source_research_plan")
    if not isinstance(plan, dict):
        raise EvidenceBackfillError(f"{source_plan_ref}: missing public_source_research_plan")
    return plan


def unwrap_packets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    packets = payload.get("evidence_packets")
    if packets is None and "evidence_packet" in payload:
        packets = [payload]
    if not isinstance(packets, list) or not packets:
        raise EvidenceBackfillError("evidence_packets must be a non-empty list")
    result = []
    for index, item in enumerate(packets):
        packet = item.get("evidence_packet") if isinstance(item, dict) else None
        if not isinstance(packet, dict):
            raise EvidenceBackfillError(f"evidence_packets[{index}]: missing evidence_packet")
        result.append(packet)
    return result


def validate_packet(packet: dict[str, Any], source_task_ids: set[str]) -> None:
    for field in REQUIRED_EVIDENCE_FIELDS:
        if field not in packet:
            raise EvidenceBackfillError(f"evidence_packet: missing required field `{field}`")
        if field != "artifact_ref" and packet[field] in ("", None, [], {}):
            raise EvidenceBackfillError(f"evidence_packet: required field `{field}` is empty")
    source_type = packet["source_type"]
    if source_type in FORBIDDEN_SOURCE_TYPES:
        raise EvidenceBackfillError(f"forbidden source_type `{source_type}`")
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise EvidenceBackfillError(f"unsupported source_type `{source_type}`")
    if packet["claim_id"] not in source_task_ids:
        raise EvidenceBackfillError(f"claim_id `{packet['claim_id']}` is not in the public source plan")
    if source_type == "social_media_weak" and packet.get("may_set_final_decision") is True:
        raise EvidenceBackfillError("social_media_weak cannot be a final decision basis")
    if source_type == "social_media_weak" and packet.get("may_set_weight") is True:
        raise EvidenceBackfillError("social_media_weak cannot set weights alone")
    if source_type == "candidate_experience_secondary" and packet.get("may_set_final_decision") is True:
        raise EvidenceBackfillError("candidate_experience_secondary cannot be a final decision basis")
    if packet["privacy_class"] not in {"public", "user_private", "redacted", "derived"}:
        raise EvidenceBackfillError("invalid privacy_class for evidence_packet")


def update_manifest(run_dir: Path, evidence_ref: str) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = load_json(manifest_path)
    execution_manifest = manifest.get("execution_manifest")
    run_state = manifest.get("run_state")
    if not isinstance(execution_manifest, dict) or not isinstance(run_state, dict):
        raise EvidenceBackfillError("manifest.json must contain execution_manifest and run_state")
    for target in [execution_manifest, run_state]:
        refs = target.setdefault("evidence_packet_refs", [])
        if evidence_ref not in refs:
            refs.append(evidence_ref)
    artifact_refs = execution_manifest.setdefault("artifact_refs", [])
    artifact_refs.append(
        {
            "artifact_id": "evidence_packet:public_evidence_backfill",
            "run_id": execution_manifest["run_id"],
            "artifact_type": "evidence_packet",
            "path": evidence_ref,
            "created_by": "backfill_public_evidence",
            "created_at": utc_now(),
            "privacy_class": "public",
            "contains_contact": False,
            "contains_private_resume": False,
            "safe_to_share_with_roles": ["career-orchestrator", "factual-reviewer", "hr-supervisor"],
            "checksum": "",
            "retention": "runtime_only",
            "purge_after_days": None,
        }
    )
    write_json(manifest_path, manifest)


def backfill(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    source_plan = load_source_plan(run_dir, args.source_plan_ref)
    source_task_ids = {task["task_id"] for task in source_plan.get("research_tasks", [])}
    packets = unwrap_packets(load_json(args.evidence_json))
    for packet in packets:
        validate_packet(packet, source_task_ids)

    evidence_path = run_dir / args.output
    source_index_path = run_dir / args.source_index_output
    append_jsonl(evidence_path, [{"evidence_packet": packet} for packet in packets])
    source_index = {
        "source_index": [
            {
                "evidence_id": packet["evidence_id"],
                "claim_id": packet["claim_id"],
                "source_type": packet["source_type"],
                "source_ref": packet["source_ref"],
                "freshness": packet["freshness"],
                "evidence_strength": packet["evidence_strength"],
                "confidence": packet["confidence"],
            }
            for packet in packets
        ]
    }
    write_json(source_index_path, source_index)
    evidence_ref = rel(evidence_path, run_dir)
    source_index_ref = rel(source_index_path, run_dir)
    update_manifest(run_dir, evidence_ref)
    return {
        "evidence_backfill_response": {
            "exit_status": "success",
            "run_id": source_plan["run_id"],
            "accepted_count": len(packets),
            "evidence_packets_ref": evidence_ref,
            "source_index_ref": source_index_ref,
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and backfill public evidence packets.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--evidence-json", required=True, type=Path)
    parser.add_argument("--source-plan-ref", default="evidence/public_source_research_plan.json")
    parser.add_argument("--output", default="evidence/evidence_packets.jsonl")
    parser.add_argument("--source-index-output", default="evidence/source_index.json")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(backfill(args), ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, KeyError, EvidenceBackfillError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
