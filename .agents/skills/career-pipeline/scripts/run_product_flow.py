#!/usr/bin/env python
import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class ProductFlowError(Exception):
    pass


SKILL_INTRO = (
    "我是 Career Pipeline，一个面向求职规划和简历设计的 Codex Skill。"
    "我会根据你的专业、经历、目标岗位和公开招聘信息，帮你判断适合的岗位方向、补齐能力差距，"
    "并为不同岗位反向设计更贴合的简历；岗位建议会尽量附公开来源，简历内容只基于你能证明的真实经历。"
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def run_python(script_name: str, *args: str) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(script_dir() / script_name), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ProductFlowError(f"{script_name} failed: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProductFlowError(f"{script_name} returned non-JSON output: {exc}") from exc


def response(payload: dict[str, Any], key: str, script_name: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ProductFlowError(f"{script_name}: missing `{key}`")
    return value


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def summarize_known(profile: dict[str, Any], context: dict[str, Any]) -> list[str]:
    education = profile.get("education_status", {})
    target = profile.get("target_direction", {})
    known = []
    major = education.get("major_name") or context.get("major_and_discipline", {}).get("normalized_major")
    if major:
        known.append(f"专业方向：{major}")
    degree = education.get("degree_level")
    grade = education.get("grade_or_year")
    if degree or grade:
        known.append("学习阶段：" + "，".join(str(item) for item in [degree, grade] if item))
    skills = list_value(profile.get("skills_and_tools"))
    if skills:
        known.append("已提到技能：" + "、".join(str(skill) for skill in skills[:8]))
    roles = list_value(target.get("target_roles"))
    target_kind = target.get("internship_or_full_time")
    if roles or target_kind:
        parts = [str(item) for item in roles[:4]]
        if target_kind:
            parts.append(str(target_kind))
        known.append("目标倾向：" + "、".join(parts))
    if not known:
        known.append("你已经提供了一段求职相关自我介绍，可以先做初步整理。")
    return known


def can_do_now(context: dict[str, Any]) -> list[str]:
    domain = context.get("discipline_domain", "unknown")
    actions = [
        "先按现有信息判断大致岗位方向和能力补齐顺序。",
        "生成公开岗位信息的搜索计划，优先看官网、公开 JD、学校就业网和地方公开实习渠道。",
        "把简历方向先拆成通用校招/实习版；等有明确岗位后，再做一岗一简历。",
    ]
    if domain != "engineering":
        actions[0] = "当前工程专业数据库最完整，非工科用户只能先做通用框架分析。"
    return actions


def unavailable_now(context: dict[str, Any]) -> list[str]:
    unavailable = [
        "暂时不直接给精确适配分、最终投递优先级或公司定制权重。",
        "没有公开岗位 URL 或 JD 前，不做具体岗位强推荐。",
        "没有项目、实习、竞赛或作品证据前，不把计划中的学习内容写成已完成经历。",
    ]
    if "domain_static_taxonomy" in list_value(context.get("blocked_outputs")):
        unavailable.append("非工科专业的静态专业数据库还没有补齐，不能给同等细度的专业横向对比。")
    return unavailable


def compact_missing_facts(context: dict[str, Any]) -> list[str]:
    labels = {
        "school_name": "学校",
        "degree_level": "学历层次",
        "graduation_window": "毕业时间",
        "project_competition_research_experience": "项目、竞赛或科研经历",
        "internship_experience": "实习经历",
        "target_location_or_company_if_any": "偏好城市、目标公司或暂时不确定",
    }
    missing = []
    for item in list_value(context.get("missing_user_owned_facts")):
        missing.append(labels.get(str(item), str(item)))
    return missing


def next_actions(has_source_results: bool, has_adapter: bool) -> list[str]:
    if has_source_results and has_adapter:
        return [
            "检查公开来源是否能支撑岗位、公司和 HR 信息。",
            "执行各专业角色分析，并保留每一步的证据。",
            "输出最终规划、学习建议、简历方向和公开 URL。",
        ]
    if has_source_results:
        return [
            "先过滤公开 URL，排除登录墙、私有页面和弱来源。",
            "让各专业角色基于这些公开证据分析岗位和能力差距。",
            "确认是否进入具体简历版本设计。",
        ]
    return [
        "补充你愿意一次性提供的个人信息，能提供多少就先提供多少。",
        "系统继续自动查公开岗位和公司信息，不需要你手动列网站。",
        "有了公开岗位证据后，再给具体岗位池、学习路线和简历设计。",
    ]


def markdown_status(status: dict[str, Any]) -> str:
    sections = [
        status["skill_intro"],
        "## 已整理的信息\n" + "\n".join(f"- {item}" for item in status["known_information_summary"]),
        "## 现在可以先做\n" + "\n".join(f"- {item}" for item in status["what_can_be_done_now"]),
        "## 暂时不能做\n" + "\n".join(f"- {item}" for item in status["currently_unavailable"]),
        "## 还缺哪些信息\n" + "\n".join(f"- {item}" for item in status["missing_user_owned_facts"]),
        "## 下一步 3 个动作\n" + "\n".join(f"- {item}" for item in status["next_three_actions"]),
    ]
    return "\n\n".join(sections)


def build_run(args: argparse.Namespace) -> dict[str, Any]:
    simulate_response = response(
        run_python(
            "simulate_runtime_run.py",
            "--task-type",
            args.task_type,
            "--route",
            args.route,
            "--input-text",
            args.input_text,
            "--run-root",
            str(args.run_root),
        ),
        "runner_response",
        "simulate_runtime_run.py",
    )
    run_id = str(simulate_response.get("run_id") or "")
    if not run_id:
        raise ProductFlowError("simulate_runtime_run.py did not return a run_id")
    run_dir = args.run_root / run_id

    plan_response = response(
        run_python("build_subagent_plan.py", "--run-dir", str(run_dir), "--build-prompt-bundles"),
        "planner_response",
        "build_subagent_plan.py",
    )
    source_plan_response = response(
        run_python("build_public_source_plan.py", "--run-dir", str(run_dir)),
        "source_plan_response",
        "build_public_source_plan.py",
    )
    query_plan_response = response(
        run_python("discover_public_sources.py", "--run-dir", str(run_dir), "--generate-query-plan-only"),
        "public_source_discovery_response",
        "discover_public_sources.py",
    )
    work_order_response = response(
        run_python("build_subagent_work_orders.py", "--run-dir", str(run_dir)),
        "work_order_response",
        "build_subagent_work_orders.py",
    )

    collected_ref = ""
    if args.source_notes_md or args.source_url:
        collector_args = ["--run-dir", str(run_dir)]
        if args.source_notes_md:
            collector_args.extend(["--notes-md", str(args.source_notes_md)])
        for url in args.source_url:
            collector_args.extend(["--url", url])
        collection_response = response(
            run_python("collect_public_source_results.py", *collector_args),
            "public_source_result_collection_response",
            "collect_public_source_results.py",
        )
        collected_ref = collection_response.get("search_results_ref", "")

    profile_ref = "input/normalized/first_round_user_profile.json"
    context_ref = "input/normalized/runtime_context_packet.json"
    profile = load_json(run_dir / profile_ref)["first_round_user_profile"]
    context = load_json(run_dir / context_ref)["runtime_context_packet"]

    status = {
        "skill_intro": SKILL_INTRO,
        "known_information_summary": summarize_known(profile, context),
        "what_can_be_done_now": can_do_now(context),
        "currently_unavailable": unavailable_now(context),
        "missing_user_owned_facts": compact_missing_facts(context),
        "public_source_policy": "只使用公开可检查来源；遇到登录墙、验证码、私有页面或无法公开查看的内容，会自动换公开来源，不能验证的结论不会强行给出。",
        "next_three_actions": next_actions(bool(collected_ref), bool(args.adapter_command)),
    }
    status_ref = "final/user_facing_status.md"
    status_json_ref = "final/user_facing_status.json"
    write_text(run_dir / status_ref, markdown_status(status))
    write_json(run_dir / status_json_ref, {"user_facing_status": status})

    handoff = {
        "run_id": run_id,
        "run_dir_ref": str(run_dir),
        "runtime_context_packet_ref": context_ref,
        "subagent_plan_ref": plan_response.get("subagent_plan_ref", ""),
        "work_orders_ref": work_order_response.get("work_orders_ref", ""),
        "dispatch_strategy": "batched_artifact_handoff",
        "public_source_plan_ref": source_plan_response.get("source_plan_ref", ""),
        "public_source_query_plan_ref": query_plan_response.get("discovery_log_ref", ""),
        "controller_collected_search_results_ref": collected_ref,
        "real_role_execution_next": (
            "dispatch work orders by batch with Codex Desktop/Manual Controller or a configured command/API adapter"
        ),
    }
    return {
        "product_flow_response": {
            "exit_status": "needs_real_role_execution",
            "run_id": run_id,
            "user_facing_status": status,
            "user_facing_status_ref": status_ref,
            "user_facing_status_json_ref": status_json_ref,
            "controller_handoff": handoff,
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start a product-style Career Pipeline flow from plain user text.")
    parser.add_argument("--task-type", default="job_search")
    parser.add_argument("--route", default="job_search")
    parser.add_argument("--input-text", required=True)
    parser.add_argument("--run-root", default=".career-pipeline-runs", type=Path)
    parser.add_argument("--source-notes-md", type=Path)
    parser.add_argument("--source-url", action="append", default=[])
    parser.add_argument("--adapter-command", default="")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build_run(args), ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, KeyError, ProductFlowError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
