#!/usr/bin/env python
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUCCESS_ROLE_OUTPUT_STATUSES = {"done", "done_with_warnings"}
ALLOWED_LIMITED_FINAL_BLOCKED_OUTPUTS = {
    "fit_score",
    "application_priority",
    "final_application_priority",
    "targeted_resume_tailoring",
    "company_specific_skill_weight_ranking",
    "unsupported_weight",
    "unsupported_weights",
}


class FinalizerError(Exception):
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


def load_manifest(run_dir: Path) -> dict[str, Any]:
    payload = load_json(run_dir / "manifest.json")
    if not isinstance(payload.get("execution_manifest"), dict) or not isinstance(payload.get("run_state"), dict):
        raise FinalizerError("manifest.json must contain execution_manifest and run_state")
    return payload


def load_plan(run_dir: Path, plan_ref: str) -> dict[str, Any]:
    payload = load_json(run_dir / plan_ref)
    plan = payload.get("subagent_invocation_plan")
    if not isinstance(plan, dict):
        raise FinalizerError(f"{plan_ref}: missing subagent_invocation_plan")
    queue = plan.get("dispatch_queue")
    if not isinstance(queue, list) or not queue:
        raise FinalizerError(f"{plan_ref}: dispatch_queue must be non-empty")
    return plan


def load_role_output(run_dir: Path, output_ref: str) -> dict[str, Any]:
    path = run_dir / output_ref
    if not path.is_file():
        raise FinalizerError(f"missing role output: {output_ref}")
    payload = load_json(path)
    packet = payload.get("role_output_packet")
    if not isinstance(packet, dict):
        raise FinalizerError(f"{output_ref}: missing role_output_packet")
    return payload


def validate_final_role_output(
    payload: dict[str, Any],
    target_agent: str,
    real_subagent_execution_required: bool,
    execution_mode: str,
) -> list[str]:
    packet = payload["role_output_packet"]
    if packet.get("target_agent") != target_agent:
        raise FinalizerError(f"{target_agent}: role output target_agent mismatch")
    status = packet.get("status")
    if status not in SUCCESS_ROLE_OUTPUT_STATUSES:
        raise FinalizerError(f"{target_agent}: role output status `{status}` blocks final package")
    recovery = payload.get("error_recovery_state")
    if not isinstance(recovery, dict):
        raise FinalizerError(f"{target_agent}: missing error_recovery_state")
    blocked_outputs = sorted(
        {
            str(item)
            for item in (packet.get("blocked_outputs") or []) + (recovery.get("blocked_outputs") or [])
            if item
        }
    )
    unsupported_blockers = [
        item for item in blocked_outputs if item not in ALLOWED_LIMITED_FINAL_BLOCKED_OUTPUTS
    ]
    if unsupported_blockers:
        raise FinalizerError(
            f"{target_agent}: blocked_outputs contain final-package blockers: "
            + ", ".join(unsupported_blockers)
        )
    metadata = payload.get("adapter_metadata")
    if real_subagent_execution_required:
        if not isinstance(metadata, dict) or metadata.get("real_subagent_execution") is not True:
            raise FinalizerError(f"{target_agent}: real adapter metadata is required before final package")
        if metadata.get("adapter_mode") == "mock-blocked" or metadata.get("mock_or_seed_source") is True:
            raise FinalizerError(f"{target_agent}: mock outputs cannot be finalized")
        if execution_mode == "manual-controller":
            if metadata.get("adapter_mode") != "manual-controller":
                raise FinalizerError(
                    f"{target_agent}: manual-controller execution mode requires manual-controller metadata"
                )
            if metadata.get("manual_controller_execution") is not True:
                raise FinalizerError(
                    f"{target_agent}: manual-controller execution must be explicitly acknowledged"
                )
    return blocked_outputs


def evidence_refs_from_manifest(manifest_payload: dict[str, Any]) -> list[str]:
    refs = manifest_payload["execution_manifest"].get("evidence_packet_refs")
    return refs if isinstance(refs, list) else []


def validate_source_discovery(run_dir: Path, search_results_ref: str, allowed_sources_ref: str) -> tuple[bool, list[str]]:
    search_path = run_dir / search_results_ref
    allowed_path = run_dir / allowed_sources_ref
    if not search_path.is_file():
        raise FinalizerError(f"missing search results: {search_results_ref}")
    if not allowed_path.is_file():
        raise FinalizerError(f"missing allowed public sources: {allowed_sources_ref}")
    search_payload = load_json(search_path)
    metadata = search_payload.get("metadata", {})
    if metadata.get("provider") == "seed" or metadata.get("real_time_search") is not True:
        raise FinalizerError("final package requires non-seed real-time public source search metadata")
    allowed_payload = load_json(allowed_path)
    sources = allowed_payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise FinalizerError("final package requires at least one source-policy-accepted public source")
    return True, [allowed_sources_ref]


def source_accuracy_tier(source_type: str) -> str:
    if source_type in {"official_or_primary", "official_school_notice", "user_provided"}:
        return "A"
    if source_type in {"recruitment_platform_jd", "verified_hr_public_post", "public_report"}:
        return "B"
    if source_type in {"candidate_experience_secondary", "social_media_weak"}:
        return "C"
    return "D"


def public_source_index(allowed_sources_payload: dict[str, Any]) -> list[dict[str, Any]]:
    sources = allowed_sources_payload.get("sources")
    if not isinstance(sources, list):
        return []
    index: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            continue
        url = str(source.get("source_ref") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        source_type = str(source.get("source_type") or "user_provided")
        index.append(
            {
                "title": str(source.get("title") or "公开来源"),
                "url": url,
                "source_type": source_type,
                "source_accuracy_tier": source_accuracy_tier(source_type),
                "may_support_application_claims": bool(source.get("may_set_final_decision")),
                "note": str(source.get("snippet") or "")[:180],
            }
        )
    return index


def urls_from_target(target: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for url in target.get("public_urls") or []:
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            urls.append(url)
    for candidate in target.get("application_url_candidates") or []:
        if not isinstance(candidate, dict):
            continue
        url = str(candidate.get("url") or "").strip()
        requires_login = candidate.get("requires_login") is True
        tier = str(candidate.get("source_accuracy_tier") or "")
        if url.startswith(("http://", "https://")) and not requires_login and tier != "D":
            urls.append(url)
    return list(dict.fromkeys(urls))


def collect_recommended_targets(role_outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for payload in role_outputs:
        for target in payload.get("recommended_application_targets") or []:
            if not isinstance(target, dict):
                continue
            urls = urls_from_target(target)
            if not urls:
                continue
            company = str(target.get("company") or "").strip()
            role = str(target.get("title_or_role_family") or target.get("role_family") or "").strip()
            key = (company, role, tuple(urls))
            if key in seen:
                continue
            seen.add(key)
            targets.append(
                {
                    "company": company or "待确认公司",
                    "title_or_role_family": role or "待确认岗位方向",
                    "scenario": str(target.get("scenario") or "explore"),
                    "public_urls": urls,
                    "why_this_target": str(target.get("why_this_target") or "公开来源可检查，适合作为下一步探索对象。"),
                    "ask_hr_about": [
                        str(item)
                        for item in target.get("ask_hr_about") or []
                        if str(item).strip()
                    ],
                }
            )
    return targets


def collect_learning_gaps(role_outputs: list[dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    for payload in role_outputs:
        gap_analysis = payload.get("skill_gap_analysis")
        if isinstance(gap_analysis, dict):
            for field in [
                "must_have_gaps",
                "nice_to_have_gaps",
                "project_evidence_gaps",
                "interview_defensibility_gaps",
                "evidence_gaps",
                "narrative_gaps",
            ]:
                for item in gap_analysis.get(field) or []:
                    text = str(item).strip()
                    if text:
                        gaps.append(text)
        learning = payload.get("learning_plan_before_application")
        if isinstance(learning, dict):
            for field in ["skills_to_learn", "projects_to_build", "proof_artifacts"]:
                for item in learning.get(field) or []:
                    text = str(item).strip()
                    if text:
                        gaps.append(text)
    return list(dict.fromkeys(gaps))[:6]


def collect_ask_hr_about(role_outputs: list[dict[str, Any]]) -> list[str]:
    items: list[str] = []
    for payload in role_outputs:
        for target in payload.get("recommended_application_targets") or []:
            if isinstance(target, dict):
                items.extend(str(item) for item in target.get("ask_hr_about") or [])
        review = payload.get("application_url_review")
        if isinstance(review, dict):
            items.extend(str(item) for item in review.get("ask_hr_about") or [])
        learning = payload.get("learning_plan_before_application")
        if isinstance(learning, dict):
            items.extend(str(item) for item in learning.get("ask_hr_about") or [])
    cleaned = [item for item in (text.strip() for text in items) if item]
    return list(dict.fromkeys(cleaned))


def build_user_facing_package(
    plan: dict[str, Any],
    manifest_payload: dict[str, Any],
    allowed_sources_payload: dict[str, Any],
    role_outputs: list[dict[str, Any]],
    limited_blocked_outputs: list[str],
) -> dict[str, Any]:
    task_type = str(manifest_payload["execution_manifest"].get("task_type") or plan.get("task_type") or "")
    source_index = public_source_index(allowed_sources_payload)
    recommended_targets = collect_recommended_targets(role_outputs)
    gaps = collect_learning_gaps(role_outputs)
    ask_hr = collect_ask_hr_about(role_outputs)
    if not ask_hr:
        ask_hr = [
            "如果公开页面没有写明岗位状态、城市、到岗时间、截止日期或实习周期，投递前向 HR 或招聘联系人确认。"
        ]
    unavailable_items = []
    if limited_blocked_outputs:
        unavailable_items.append(
            "精确适配分、最终投递优先级或公司定制权重需要更强的当前 JD、公开来源和个人经历证据。"
        )
    if recommended_targets:
        conclusion = (
            "已完成公开来源和角色输出校验，可以基于下列公开入口继续做岗位探索、准备优先级和一岗一简历设计。"
        )
    else:
        conclusion = (
            "已完成公开来源和角色输出校验；当前更适合先做岗位方向探索、能力补齐和简历素材整理，"
            "具体投递目标需要继续绑定公开 JD 或官方入口。"
        )
    return {
        "positioning_conclusion": conclusion,
        "task_type": task_type,
        "evidence_status": "公开来源已通过策略校验；角色输出已完成运行检查。",
        "recommended_targets": recommended_targets,
        "public_source_index": source_index,
        "gaps_to_fix_before_application": gaps
        or [
            "围绕目标岗位补齐可验证的项目、技能和成果证据。",
            "未完成的学习内容只能写入学习计划，不能写成已掌握技能或已完成项目。",
        ],
        "resume_reverse_design": (
            "有明确目标岗位时，按该岗位 JD、公开来源和可证明经历生成一岗一简历；"
            "没有明确目标时，先生成覆盖面更广的校招/实习版简历。"
        ),
        "ask_hr_about": ask_hr,
        "currently_unavailable": unavailable_items,
        "next_three_actions": [
            "先打开公开来源，确认岗位方向、投递入口和你愿意接受的城市/到岗方式。",
            "补充学校、专业、项目职责、代码/作品链接、实习时间等用户自有信息，以便提高匹配和简历质量。",
            "选定一个目标岗位或 JD 后，进入一岗一简历流程：岗位要求分析、能力补齐、简历反向设计和事实审核。",
        ],
    }


def bullet_lines(items: list[Any], fallback: str) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        cleaned = [fallback]
    return "\n".join(f"- {item}" for item in cleaned)


def render_public_urls(source_index: list[dict[str, Any]]) -> str:
    if not source_index:
        return "- 暂无可展示的公开 URL；需要继续执行公开来源搜索。"
    lines = []
    for source in source_index[:8]:
        title = str(source.get("title") or "公开来源").strip()
        url = str(source.get("url") or "").strip()
        tier = str(source.get("source_accuracy_tier") or "").strip()
        if url:
            lines.append(f"- {title}（{tier}）：{url}")
    return "\n".join(lines) if lines else "- 暂无可展示的公开 URL；需要继续执行公开来源搜索。"


def render_recommended_targets(targets: list[dict[str, Any]]) -> str:
    if not targets:
        return "- 当前不直接给具体岗位强推荐；先按岗位方向探索，等绑定公开 JD 或官方入口后再做投递优先级。"
    lines = []
    for target in targets[:6]:
        company = str(target.get("company") or "待确认公司")
        role = str(target.get("title_or_role_family") or "待确认岗位方向")
        scenario = str(target.get("scenario") or "explore")
        urls = ", ".join(str(url) for url in target.get("public_urls") or [])
        lines.append(f"- {company}｜{role}｜{scenario}：{urls}")
    return "\n".join(lines)


def render_why_targets(targets: list[dict[str, Any]], source_index: list[dict[str, Any]]) -> str:
    reasons = []
    for target in targets[:4]:
        reason = str(target.get("why_this_target") or "").strip()
        if reason:
            reasons.append(reason)
    if not reasons and source_index:
        reasons.append("已有公开来源可检查，适合先作为探索入口，不直接等同于最终投递建议。")
    return bullet_lines(
        reasons,
        "当前信息不足以判断具体岗位适配度；先基于专业、技能和公开岗位方向做探索。",
    )


def build_user_facing_report_zh(user_facing_package: dict[str, Any]) -> str:
    targets = user_facing_package.get("recommended_targets") or []
    source_index = user_facing_package.get("public_source_index") or []
    gaps = user_facing_package.get("gaps_to_fix_before_application") or []
    ask_hr = user_facing_package.get("ask_hr_about") or []
    unavailable = user_facing_package.get("currently_unavailable") or []
    next_actions = user_facing_package.get("next_three_actions") or []
    return "\n\n".join(
        [
            "## 当前定位\n"
            + str(user_facing_package.get("positioning_conclusion") or "已完成初步整理，后续建议以公开岗位信息和用户补充经历继续收敛。"),
            "## 推荐方向/岗位池\n" + render_recommended_targets(targets),
            "## 为什么适合\n" + render_why_targets(targets, source_index),
            "## 还差什么\n"
            + bullet_lines(
                gaps + unavailable,
                "需要补充学校、专业、项目职责、作品链接、实习时间或目标 JD，才能做更精确判断。",
            ),
            "## 先学什么/做什么项目\n"
            + bullet_lines(
                gaps,
                "先做一个能公开展示的项目或作品，把技能、职责、结果和可验证链接沉淀下来。",
            ),
            "## 简历怎么写\n"
            + str(
                user_facing_package.get("resume_reverse_design")
                or "没有明确目标岗位时先做通用校招/实习版；有 JD 后按一岗一简历反向设计。"
            ),
            "## 推荐查看的公开 URL\n" + render_public_urls(source_index),
            "## 需要问 HR 的事项\n" + bullet_lines(ask_hr, "确认岗位状态、城市/到岗要求、截止时间、实习周期和招聘流程。"),
            "## 下一步 3 个动作\n" + bullet_lines(next_actions[:3], "补充关键信息后继续收敛岗位和简历方向。"),
        ]
    )


def update_manifest_for_final(
    run_dir: Path,
    manifest_payload: dict[str, Any],
    final_ref: str,
    role_output_refs: list[str],
    real_subagent_execution: bool,
    blocked_outputs: list[str],
    degraded_outputs: list[str],
) -> None:
    manifest = manifest_payload["execution_manifest"]
    run_state = manifest_payload["run_state"]
    manifest["updated_at"] = utc_now()
    manifest["current_stage"] = "final_package_ready"
    manifest["final_package_ref"] = final_ref
    manifest["artifact_refs"] = manifest.get("artifact_refs", [])
    manifest["gate_status"] = {
        "input_normalized": True,
        "context_packet_created": True,
        "secondary_injections_created": True,
        "specialists_completed_or_blocked": True,
        "required_specialists_completed": True,
        "blocked_specialists_absent_for_final": True,
        "debate_completed_or_recorded": True,
        "hr_review_completed": True,
        "factual_review_completed_when_needed": True,
        "user_confirmation_resolved_when_needed": True,
    }
    run_state["stage"] = "final_package_ready"
    run_state["completed_agents"] = [
        ref.split("/")[-2] if "/" in ref else ref for ref in role_output_refs
    ]
    run_state["blocked_agents"] = []
    run_state["failed_invocations"] = []
    run_state["blocked_outputs"] = blocked_outputs
    run_state["degraded_outputs"] = degraded_outputs
    run_state["recovery_actions"] = []
    run_state["next_action"] = "return_final_package"
    run_state["shared_context_refs"] = list(dict.fromkeys(run_state.get("shared_context_refs", []) + role_output_refs))
    run_state["real_subagent_execution"] = real_subagent_execution
    write_json(run_dir / "manifest.json", manifest_payload)


def finalize(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    plan = load_plan(run_dir, args.plan_ref)
    manifest_payload = load_manifest(run_dir)
    source_discovery_ready, source_gate_refs = validate_source_discovery(
        run_dir,
        args.search_results_ref,
        args.allowed_sources_ref,
    )
    allowed_sources_payload = load_json(run_dir / args.allowed_sources_ref)
    role_output_refs = []
    role_packets = []
    role_outputs = []
    limited_blocked_outputs: list[str] = []
    for item in plan["dispatch_queue"]:
        output_ref = item["output_artifact_target"]
        payload = load_role_output(run_dir, output_ref)
        role_blocked_outputs = validate_final_role_output(
            payload,
            item["target_agent"],
            args.real_subagent_execution,
            args.execution_mode,
        )
        limited_blocked_outputs.extend(role_blocked_outputs)
        role_output_refs.append(output_ref)
        role_outputs.append(payload)
        role_packets.append(payload["role_output_packet"])
    limited_blocked_outputs = sorted(set(limited_blocked_outputs))
    user_facing_package = build_user_facing_package(
        plan,
        manifest_payload,
        allowed_sources_payload,
        role_outputs,
        limited_blocked_outputs,
    )
    user_facing_report_zh = build_user_facing_report_zh(user_facing_package)
    final_ref = args.output
    final_path = run_dir / final_ref
    decision_package = {
        "decision_package": {
            "run_id": plan["run_id"],
            "created_at": utc_now(),
            "task_type": manifest_payload["execution_manifest"].get("task_type", ""),
            "real_subagent_execution": args.real_subagent_execution,
            "execution_mode": args.execution_mode,
            "source_discovery_ready": source_discovery_ready,
            "finalizer_validation_status": "passed",
            "role_output_refs": role_output_refs,
            "role_output_statuses": [
                {
                    "target_agent": packet["target_agent"],
                    "status": packet["status"],
                    "confidence": packet["confidence"],
                }
                for packet in role_packets
            ],
            "evidence_packet_refs": evidence_refs_from_manifest(manifest_payload),
            "runtime_weights_ref": manifest_payload["execution_manifest"].get(
                "runtime_weights_ref",
                "merge/runtime_weights.json",
            ),
            "gate_evidence_refs": role_output_refs + source_gate_refs,
            "user_facing_package": user_facing_package,
            "user_facing_report_zh": user_facing_report_zh,
            "blocked_outputs": limited_blocked_outputs,
            "degraded_outputs": limited_blocked_outputs,
            "decision_summary": (
                "All required role outputs passed runtime schema/status checks. "
                "This package records final readiness for the local run; role-specific "
                "career text remains evidence-bound to the accepted role outputs. "
                "Fields listed in blocked_outputs are unavailable exact fields, not blockers "
                "for safe prepare-first or exploration guidance."
            ),
        }
    }
    write_json(final_path, decision_package)
    update_manifest_for_final(
        run_dir,
        manifest_payload,
        final_ref,
        role_output_refs,
        args.real_subagent_execution,
        limited_blocked_outputs,
        limited_blocked_outputs,
    )
    return {
        "finalizer_response": {
            "exit_status": "success",
            "run_id": plan["run_id"],
            "final_package_ref": rel(final_path, run_dir),
            "role_output_refs": role_output_refs,
            "real_subagent_execution": args.real_subagent_execution,
            "source_discovery_ready": source_discovery_ready,
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finalize a career-pipeline run after role outputs are complete.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--plan-ref", default="invocations/subagent_invocation_plan.json")
    parser.add_argument("--output", default="final/decision_package.json")
    parser.add_argument("--real-subagent-execution", action="store_true")
    parser.add_argument(
        "--execution-mode",
        choices=["external-command", "manual-controller"],
        default="external-command",
    )
    parser.add_argument("--search-results-ref", default="evidence/search_results.generated.json")
    parser.add_argument("--allowed-sources-ref", default="evidence/allowed_public_sources.generated.json")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(finalize(args), ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, KeyError, FinalizerError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
