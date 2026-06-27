#!/usr/bin/env python
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ALLOWED_SOURCE_TYPES = {
    "official_or_primary",
    "official_school_notice",
    "recruitment_platform_jd",
    "verified_hr_public_post",
    "candidate_experience_secondary",
    "social_media_weak",
    "public_report",
    "user_provided",
}

FORBIDDEN_SOURCE_TYPES = {
    "private_resume",
    "private_chat",
    "private_hr_message",
    "recruiter_backend",
    "login_only_page",
    "non_public_candidate_profile",
}

LOGIN_HINTS = {
    "login",
    "signin",
    "passport",
    "auth",
    "sso",
    "private",
    "admin",
}

SOURCE_HINTS = {
    "official_or_primary": {
        "domains": [
            "join.qq.com",
            "careers.tencent.com",
            "jobs.bytedance.com",
            "talent.alibaba.com",
            "talent.baidu.com",
            "career.huawei.com",
            "wecruit.hotjob.cn",
            "dji.com",
            "catl.com",
            "zhipuai.cn",
        ],
        "terms": ["career", "campus", "join", "jobs", "招聘", "校招", "实习"],
    },
    "official_school_notice": {
        "domains": ["edu.cn"],
        "terms": ["就业", "双选会", "宣讲会", "career", "job"],
    },
    "recruitment_platform_jd": {
        "domains": [
            "zhipin.com",
            "liepin.com",
            "lagou.com",
            "nowcoder.com",
            "shixiseng.com",
            "linkedin.com",
            "indeed.com",
        ],
        "terms": ["boss", "猎聘", "拉勾", "牛客", "实习僧", "job", "jd", "招聘"],
    },
    "verified_hr_public_post": {
        "domains": ["weixin.qq.com", "mp.weixin.qq.com", "nowcoder.com", "zhihu.com"],
        "terms": ["hr", "招聘官", "校招", "内推", "面试", "screening"],
    },
    "candidate_experience_secondary": {
        "domains": ["nowcoder.com", "zhihu.com", "offershow", "kanzhun.com", "github.com"],
        "terms": ["面经", "offer", "复盘", "interview", "experience"],
    },
    "social_media_weak": {
        "domains": ["xiaohongshu.com", "maimai.cn", "zhihu.com", "reddit.com", "teamblind.com", "glassdoor.com"],
        "terms": ["小红书", "脉脉", "讨论", "评价", "review"],
    },
    "public_report": {
        "domains": ["sse.com.cn", "szse.cn", "hkexnews.hk", "sec.gov", "36kr.com", "itjuzi.com"],
        "terms": ["财报", "年报", "招股书", "行业报告", "融资", "regulation"],
    },
}


class PublicSourceDiscoveryError(Exception):
    pass


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
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
        raise PublicSourceDiscoveryError(f"{source_plan_ref}: missing public_source_research_plan")
    return plan


def source_tasks_by_id(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks = plan.get("research_tasks")
    if not isinstance(tasks, list) or not tasks:
        raise PublicSourceDiscoveryError("public source plan has no research_tasks")
    return {task["task_id"]: task for task in tasks if isinstance(task, dict) and task.get("task_id")}


def unwrap_search_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = payload.get("search_results")
    if results is None:
        results = payload.get("results")
    if not isinstance(results, list):
        raise PublicSourceDiscoveryError("search_results must be a list")
    return results


def normalized_host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def contains_login_or_private_hint(result: dict[str, Any]) -> bool:
    parsed = urlparse(str(result.get("url", "")))
    haystack = " ".join(
        str(result.get(field, "")).lower()
        for field in ["url", "title", "snippet"]
    )
    path_parts = [part.lower() for part in parsed.path.split("/") if part]
    if "recruiter backend" in haystack or "hr backend" in haystack:
        return True
    return any(hint in haystack or hint in path_parts for hint in LOGIN_HINTS)


def infer_source_type(result: dict[str, Any], task: dict[str, Any]) -> str:
    explicit_source_type = result.get("source_type")
    if explicit_source_type in ALLOWED_SOURCE_TYPES:
        return str(explicit_source_type)
    url = str(result.get("url", ""))
    host = normalized_host(url)
    haystack = " ".join(
        str(result.get(field, "")).lower()
        for field in ["url", "title", "snippet"]
    )
    for source_type, hints in SOURCE_HINTS.items():
        if any(domain in host for domain in hints["domains"]):
            return source_type
        if any(term.lower() in haystack for term in hints["terms"]):
            return source_type
    task_source_type = task.get("source_type")
    if task_source_type in ALLOWED_SOURCE_TYPES:
        return str(task_source_type)
    return "user_provided"


def source_field(task: dict[str, Any]) -> str:
    return str(task.get("claim_field") or task.get("field") or "public_source_evidence")


def source_permissions(source_type: str) -> dict[str, bool]:
    if source_type == "social_media_weak":
        return {"may_set_final_decision": False, "may_set_weight": False}
    if source_type == "candidate_experience_secondary":
        return {"may_set_final_decision": False, "may_set_weight": True}
    return {
        "may_set_final_decision": source_type in {
            "official_or_primary",
            "official_school_notice",
            "recruitment_platform_jd",
            "verified_hr_public_post",
            "public_report",
            "user_provided",
        },
        "may_set_weight": source_type != "social_media_weak",
    }


def build_search_queries(plan: dict[str, Any]) -> list[dict[str, Any]]:
    target_terms = " ".join(str(term) for term in plan.get("target_terms", []) if term)
    queries = []
    for task in plan.get("research_tasks", []):
        query_template = str(task.get("query_template") or "").strip()
        display_sources = task.get("display_sources") or []
        display = " ".join(str(item) for item in display_sources[:4])
        query = " ".join(part for part in [target_terms, query_template, display] if part).strip()
        queries.append(
            {
                "task_id": task.get("task_id"),
                "source_type": task.get("source_type"),
                "query": re.sub(r"\s+", " ", query),
                "user_instruction_required": False,
                "source_matrix_ref": task.get("source_matrix_ref") or plan.get("source_matrix_ref", ""),
            }
        )
    return queries


def discover_sources(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    plan = load_source_plan(run_dir, args.source_plan_ref)
    tasks = source_tasks_by_id(plan)
    search_queries = build_search_queries(plan)
    if args.generate_query_plan_only:
        discovery_log_path = run_dir / args.discovery_log_output
        write_json(
            discovery_log_path,
            {
                "public_source_discovery": {
                    "run_id": plan["run_id"],
                    "source_discovery_mode": "auto_search_adapter",
                    "user_instruction_required": False,
                    "source_plan_ref": args.source_plan_ref,
                    "search_queries": search_queries,
                    "accepted_sources": [],
                    "rejected_sources": [],
                    "next_action": "run_search_adapter",
                }
            },
        )
        return {
            "public_source_discovery_response": {
                "exit_status": "needs_search_results",
                "run_id": plan["run_id"],
                "user_instruction_required": False,
                "accepted_count": 0,
                "rejected_count": 0,
                "generated_sources_ref": "",
                "discovery_log_ref": rel(discovery_log_path, run_dir),
            }
        }
    if not args.search_results_json:
        raise PublicSourceDiscoveryError("--search-results-json is required unless --generate-query-plan-only is set")
    search_results = unwrap_search_results(load_json(args.search_results_json))
    accepted = []
    rejected = []
    seen_refs = set()
    for index, result in enumerate(search_results):
        task_id = result.get("task_id")
        url = str(result.get("url") or result.get("source_ref") or "").strip()
        if not task_id or task_id not in tasks:
            rejected.append({"index": index, "url": url, "reason": "task_id_not_in_source_plan"})
            continue
        if not url:
            rejected.append({"index": index, "task_id": task_id, "reason": "missing_url"})
            continue
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https", "file"}:
            rejected.append({"index": index, "task_id": task_id, "url": url, "reason": "unsupported_scheme"})
            continue
        if contains_login_or_private_hint(result):
            rejected.append({"index": index, "task_id": task_id, "url": url, "reason": "login_or_private_hint"})
            continue
        task = tasks[task_id]
        source_type = infer_source_type(result, task)
        if source_type in FORBIDDEN_SOURCE_TYPES:
            rejected.append({"index": index, "task_id": task_id, "url": url, "reason": f"forbidden_{source_type}"})
            continue
        if source_type not in ALLOWED_SOURCE_TYPES:
            rejected.append({"index": index, "task_id": task_id, "url": url, "reason": f"unsupported_{source_type}"})
            continue
        key = (task_id, url)
        if key in seen_refs:
            rejected.append({"index": index, "task_id": task_id, "url": url, "reason": "duplicate"})
            continue
        seen_refs.add(key)
        permissions = source_permissions(source_type)
        accepted.append(
            {
                "task_id": task_id,
                "source_type": source_type,
                "source_ref": url,
                "field": source_field(task),
                "title": result.get("title", ""),
                "snippet": result.get("snippet", ""),
                "discovery_method": "search_adapter",
                "source_matrix_ref": task.get("source_matrix_ref") or plan.get("source_matrix_ref", ""),
                **permissions,
            }
        )

    generated_sources_path = run_dir / args.output
    discovery_log_path = run_dir / args.discovery_log_output
    write_json(
        generated_sources_path,
        {
            "metadata": {
                "run_id": plan["run_id"],
                "source_discovery_mode": "auto_search_adapter",
                "user_instruction_required": False,
                "source_plan_ref": args.source_plan_ref,
            },
            "sources": accepted,
        },
    )
    write_json(
        discovery_log_path,
        {
            "public_source_discovery": {
                "run_id": plan["run_id"],
                "source_discovery_mode": "auto_search_adapter",
                "user_instruction_required": False,
                "source_plan_ref": args.source_plan_ref,
                "search_queries": search_queries,
                "accepted_sources": accepted,
                "rejected_sources": rejected,
            }
        },
    )
    return {
        "public_source_discovery_response": {
            "exit_status": "success",
            "run_id": plan["run_id"],
            "user_instruction_required": False,
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "generated_sources_ref": rel(generated_sources_path, run_dir),
            "discovery_log_ref": rel(discovery_log_path, run_dir),
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert public search-adapter results into allowed public sources for fetching."
    )
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--search-results-json", type=Path)
    parser.add_argument("--generate-query-plan-only", action="store_true")
    parser.add_argument("--source-plan-ref", default="evidence/public_source_research_plan.json")
    parser.add_argument("--output", default="evidence/allowed_public_sources.generated.json")
    parser.add_argument("--discovery-log-output", default="evidence/public_source_discovery_log.json")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(discover_sources(args), ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, KeyError, PublicSourceDiscoveryError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
