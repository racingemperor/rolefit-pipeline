#!/usr/bin/env python
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class PublicSourceResultCollectionError(Exception):
    pass


URL_PATTERN = re.compile(r"https?://[^\s\]\)>\"']+")
KEY_VALUE_PATTERN = re.compile(r"\b(title|snippet|source_type|task_id)=([^=]+?)(?=\s+\w+=|$)")


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
        raise PublicSourceResultCollectionError(f"{source_plan_ref}: missing public_source_research_plan")
    tasks = plan.get("research_tasks")
    if not isinstance(tasks, list) or not tasks:
        raise PublicSourceResultCollectionError(f"{source_plan_ref}: missing research_tasks")
    return plan


def source_type_for_url(url: str, explicit: str = "") -> str:
    if explicit:
        return explicit
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    if "mp.weixin.qq.com" in host or "weixin.qq.com" in host:
        return "verified_hr_public_post"
    if any(domain in host for domain in ["nowcoder.com", "zhipin.com", "liepin.com", "lagou.com", "shixiseng.com", "linkedin.com", "indeed.com"]):
        return "recruitment_platform_jd"
    if host.endswith("edu.cn") or ".edu.cn" in host:
        return "official_school_notice"
    if any(domain in host for domain in ["xiaohongshu.com", "zhihu.com", "maimai.cn", "teamblind.com", "glassdoor.com"]):
        return "social_media_weak"
    if any(term in host + path for term in ["sec.gov", "sse.com.cn", "szse.cn", "hkexnews.hk", "36kr.com", "itjuzi.com", "report"]):
        return "public_report"
    return "official_or_primary"


def choose_task_id(plan: dict[str, Any], source_type: str, text: str) -> str:
    tasks = [task for task in plan["research_tasks"] if isinstance(task, dict)]
    lowered = text.lower()
    if source_type == "verified_hr_public_post":
        preferred = ["company-bound-hr-real-questions", "verified-hr-public-post", "target-learning-gap-evidence"]
    elif source_type == "recruitment_platform_jd":
        preferred = ["target-current-jd-verification", "recruitment-platform-public-jd"]
    elif source_type == "official_school_notice":
        preferred = ["official-school-career-signal"]
    elif source_type == "public_report":
        preferred = ["public-company-development-report"]
    elif source_type == "social_media_weak":
        preferred = ["social-media-weak-signal"]
    else:
        preferred = ["official-company-career", "target-current-jd-verification"]
    if "hr" in lowered or "screen" in lowered or "interview" in lowered:
        preferred = ["company-bound-hr-real-questions", "verified-hr-public-post"] + preferred
    for task_id in preferred:
        if any(task.get("task_id") == task_id for task in tasks):
            return task_id
    for task in tasks:
        if task.get("source_type") == source_type:
            return str(task["task_id"])
    return str(tasks[0]["task_id"])


def parse_kv(line: str) -> dict[str, str]:
    return {match.group(1): match.group(2).strip() for match in KEY_VALUE_PATTERN.finditer(line)}


def clean_url(url: str) -> str:
    return url.rstrip(".,;，。；)")


def result_from_line(plan: dict[str, Any], line: str) -> dict[str, Any] | None:
    match = URL_PATTERN.search(line)
    if not match:
        return None
    url = clean_url(match.group(0))
    kv = parse_kv(line)
    source_type = source_type_for_url(url, kv.get("source_type", ""))
    task_id = kv.get("task_id") or choose_task_id(plan, source_type, line)
    title = kv.get("title") or line.replace(match.group(0), "").strip(" -:：")[:80] or "Public source"
    snippet = kv.get("snippet") or line.strip()
    return {
        "task_id": task_id,
        "url": url,
        "title": title,
        "snippet": snippet,
        "source_type": source_type,
        "provider": "controller-collected",
    }


def results_from_notes(plan: dict[str, Any], notes_path: Path) -> list[dict[str, Any]]:
    text = notes_path.read_text(encoding="utf-8-sig")
    results = []
    seen = set()
    for line in text.splitlines():
        result = result_from_line(plan, line)
        if not result:
            continue
        key = (result["task_id"], result["url"])
        if key in seen:
            continue
        seen.add(key)
        results.append(result)
    return results


def results_from_urls(plan: dict[str, Any], urls: list[str]) -> list[dict[str, Any]]:
    results = []
    seen = set()
    for url in urls:
        url = clean_url(url)
        if not url:
            continue
        source_type = source_type_for_url(url)
        task_id = choose_task_id(plan, source_type, url)
        key = (task_id, url)
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "task_id": task_id,
                "url": url,
                "title": "Controller-collected public URL",
                "snippet": "Public URL collected by the controller or browser search.",
                "source_type": source_type,
                "provider": "controller-collected",
            }
        )
    return results


def collect_results(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    plan = load_source_plan(run_dir, args.source_plan_ref)
    results: list[dict[str, Any]] = []
    if args.notes_md:
        results.extend(results_from_notes(plan, args.notes_md))
    if args.url:
        results.extend(results_from_urls(plan, args.url))
    deduped = []
    seen = set()
    for result in results:
        if not result.get("task_id") or not result.get("url"):
            continue
        key = (result["task_id"], result["url"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    if not deduped:
        raise PublicSourceResultCollectionError("no public URLs found; provide --url or --notes-md with http(s) links")
    output_path = run_dir / args.output
    write_json(
        output_path,
        {
            "metadata": {
                "run_id": plan["run_id"],
                "provider": "controller-collected",
                "provider_mode": "controller_collected",
                "real_time_search": True,
                "user_instruction_required": False,
                "source_plan_ref": args.source_plan_ref,
                "note": (
                    "Controller-collected public URL candidates. These are still candidates until "
                    "search_public_sources.py, discover_public_sources.py, fetch/backfill, and final gates accept them."
                ),
            },
            "search_results": deduped,
        },
    )
    return {
        "public_source_result_collection_response": {
            "exit_status": "success",
            "run_id": plan["run_id"],
            "user_instruction_required": False,
            "search_results_ref": rel(output_path, run_dir),
            "result_count": len(deduped),
            "next_action": "pass_to_search_public_sources_external_json",
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert controller/browser-collected public URLs or Markdown notes into search_results.json."
    )
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--source-plan-ref", default="evidence/public_source_research_plan.json")
    parser.add_argument("--notes-md", type=Path)
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--output", default="evidence/search_results.controller_collected.json")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(collect_results(args), ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, KeyError, PublicSourceResultCollectionError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
