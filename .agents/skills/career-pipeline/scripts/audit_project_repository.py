#!/usr/bin/env python
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
}

DEPENDENCY_NAMES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "package.json",
    "pom.xml",
    "build.gradle",
    "go.mod",
    "Cargo.toml",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "makefile",
}

SIGNAL_PATTERNS = {
    "api_backend": ("api", "route", "router", "controller", "handler", "service", "endpoint", "app.py"),
    "database_state": ("schema", "migration", "repository", "dao", "entity", "model", "database", "db", "sql", "redis", "cache"),
    "async_jobs": ("worker", "queue", "job", "task", "scheduler", "consumer", "producer", "kafka", "rabbit"),
    "devops_deploy": ("docker", "k8s", "kubernetes", "deploy", "ci", "workflow", "pipeline"),
    "testing_quality": ("test", "spec", "mock", "fixture", "coverage", "benchmark", "e2e"),
    "agent_or_ai": ("agent", "tool", "planner", "rag", "llm", "eval", "embedding", "model"),
}

LANGUAGE_SUFFIXES = {
    ".py": "Python",
    ".java": "Java",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".sql": "SQL",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
}


class AuditError(Exception):
    pass


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def collect_files(repo: Path, max_files: int = 8000) -> list[Path]:
    files: list[Path] = []
    for root, dirs, filenames in os.walk(repo):
        dirs[:] = [item for item in sorted(dirs) if item.lower() not in EXCLUDED_DIRS]
        rel_root = Path(root).relative_to(repo)
        if any(part.lower() in EXCLUDED_DIRS for part in rel_root.parts):
            continue
        for filename in sorted(filenames):
            rel = (Path(root) / filename).relative_to(repo)
            if any(part.lower() in EXCLUDED_DIRS for part in rel.parts):
                continue
            files.append(rel)
            if len(files) >= max_files:
                return files
    return files


def read_sample(path: Path, max_chars: int = 1600) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except OSError:
        return ""


def classify_signals(files: list[Path]) -> dict[str, list[str]]:
    signals: dict[str, list[str]] = defaultdict(list)
    for rel in files:
        rel_text = rel.as_posix().lower()
        stem = rel.stem.lower()
        for category, patterns in SIGNAL_PATTERNS.items():
            if any(pattern in rel_text or pattern in stem for pattern in patterns):
                signals[category].append(rel.as_posix())
    return {key: value[:40] for key, value in sorted(signals.items())}


def source_evidence_points(audit: dict[str, Any]) -> list[dict[str, str]]:
    points: list[dict[str, str]] = []
    for field, label in [
        ("readme_files", "README/documentation"),
        ("dependency_files", "dependency/runtime setup"),
        ("docker_files", "Docker or deploy path"),
        ("test_files", "test or quality evidence"),
    ]:
        for path in audit.get(field, [])[:3]:
            points.append({"evidence_type": label, "path": path, "claim_supported": label})
    for category, paths in audit.get("signals", {}).items():
        for path in paths[:2]:
            points.append({"evidence_type": category, "path": path, "claim_supported": category})
    seen: set[tuple[str, str]] = set()
    unique = []
    for point in points:
        key = (point["evidence_type"], point["path"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(point)
    return unique[:20]


def render_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Project Repository Audit",
        "",
        f"- Name: {audit['name']}",
        f"- Repo path: {audit['repo_path']}",
        f"- Files scanned: {audit['summary']['file_count_scanned']}",
        "",
        "## Source Evidence Points",
    ]
    for point in audit["source_evidence_points"]:
        lines.append(f"- {point['evidence_type']}: `{point['path']}`")
    lines.extend(["", "## Signals"])
    for category, paths in audit["signals"].items():
        lines.append(f"- {category}: {', '.join(paths[:8])}")
    return "\n".join(lines) + "\n"


def audit_repo(repo: Path, name: str) -> dict[str, Any]:
    if not repo.is_dir():
        raise AuditError(f"repo path does not exist or is not a directory: {repo}")
    files = collect_files(repo)
    readmes = [path.as_posix() for path in files if path.name.lower().startswith("readme")]
    dependency_files = [
        path.as_posix()
        for path in files
        if path.name.lower() in {item.lower() for item in DEPENDENCY_NAMES}
        or path.name.lower().startswith("requirements")
    ]
    docker_files = [
        path.as_posix()
        for path in files
        if "docker" in path.as_posix().lower() or path.name.lower() == "dockerfile"
    ]
    test_files = [
        path.as_posix()
        for path in files
        if "test" in path.name.lower() or any(part.lower() in {"tests", "test"} for part in path.parts)
    ]
    language_counts = Counter(LANGUAGE_SUFFIXES.get(path.suffix.lower(), "Other") for path in files)
    ext_counts = Counter(path.suffix.lower() or "[no extension]" for path in files)
    readme_samples = {path: read_sample(repo / path) for path in readmes[:3]}
    audit: dict[str, Any] = {
        "name": name,
        "repo_path": str(repo.resolve()),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "summary": {
            "file_count_scanned": len(files),
            "top_extensions": ext_counts.most_common(12),
            "language_counts": language_counts.most_common(),
        },
        "readme_files": readmes[:20],
        "dependency_files": sorted(dependency_files)[:40],
        "docker_files": sorted(docker_files)[:40],
        "test_files": sorted(test_files)[:60],
        "signals": classify_signals(files),
        "readme_samples": readme_samples,
    }
    audit["source_evidence_points"] = source_evidence_points(audit)
    audit["resume_claim_gate"] = {
        "source_verified": len(audit["source_evidence_points"]) >= 5,
        "minimum_evidence_points_required": 5,
        "rule": "Resume project claims require local source evidence; README-only claims are not enough.",
    }
    return {"project_repo_audit": audit}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a local project repository for resume/interview evidence.")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--name", default="")
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        payload = audit_repo(args.repo, args.name or args.repo.name)
        json_path = args.out_dir / "project_repo_audit.json"
        md_path = args.out_dir / "project_repo_audit.md"
        write_json(json_path, payload)
        write_text(md_path, render_markdown(payload["project_repo_audit"]))
        print(
            json.dumps(
                {
                    "project_repo_audit_response": {
                        "exit_status": "success",
                        "audit_json": json_path.name,
                        "audit_md": md_path.name,
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (OSError, AuditError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
