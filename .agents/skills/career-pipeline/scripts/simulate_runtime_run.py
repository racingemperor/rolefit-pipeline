#!/usr/bin/env python
import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


TASK_TYPES = {
    "resume_review",
    "resume_generation",
    "job_search",
    "jd_analysis",
    "company_research",
    "tailored_resume",
    "major_positioning",
    "personal_branding",
    "learning_plan",
}

ROUTES = {
    "single_job_scout": ["job-scout"],
    "job_search": [
        "major-cluster-classifier",
        "profile-extractor",
        "job-scout",
        "jd-analyzer",
        "match-strategist",
        "learning-path-strategist",
    ],
}


def write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path.as_posix()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def detect_major(text: str) -> str:
    if "计算机" in text or "软件" in text or "人工智能" in text:
        return "计算机类"
    if "机械" in text:
        return "机械类"
    if "电子" in text or "通信" in text:
        return "电子信息类"
    return ""


def detect_candidate_stage(text: str) -> str:
    if any(token in text for token in ["大一", "大二", "大三", "研一", "研二", "非毕业"]):
        return "non_graduating"
    if any(token in text for token in ["大四", "研三", "应届", "毕业"]):
        return "graduating"
    return "unknown"


def extract_skills(text: str) -> list[str]:
    candidates = ["Python", "Java", "C++", "Go", "SQL", "LLM", "机器学习", "深度学习"]
    lowered = text.lower()
    skills: list[str] = []
    for skill in candidates:
        if skill.lower() in lowered or skill in text:
            skills.append(skill)
    return skills


def redact_contact_like_text(text: str) -> str:
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[redacted-email]", text)
    return re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[redacted-phone]", text)


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def repository_ref(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except OSError:
        pass
    return str(repo_root)


def artifact_ref(
    run_id: str,
    run_dir: Path,
    path: Path,
    artifact_type: str,
    created_by: str,
    privacy_class: str = "derived",
    safe_roles: list[str] | None = None,
    contains_contact: bool = False,
    contains_private_resume: bool = False,
) -> dict[str, Any]:
    content = path.read_bytes() if path.exists() else b""
    checksum = hashlib.sha256(content).hexdigest() if content else ""
    return {
        "artifact_id": f"{artifact_type}:{path.stem}",
        "run_id": run_id,
        "artifact_type": artifact_type,
        "path": rel(path, run_dir),
        "created_by": created_by,
        "created_at": utc_now(),
        "privacy_class": privacy_class,
        "contains_contact": contains_contact,
        "contains_private_resume": contains_private_resume,
        "safe_to_share_with_roles": safe_roles or [],
        "checksum": checksum,
        "retention": "runtime_only",
        "purge_after_days": None,
    }


def build_profile(input_text: str) -> dict[str, Any]:
    major_name = detect_major(input_text)
    candidate_stage = detect_candidate_stage(input_text)
    skills = extract_skills(input_text)
    target_roles = ["AI 实习"] if re.search(r"AI|人工智能|大模型|LLM", input_text, re.I) else []
    target_kind = "internship" if "实习" in input_text else ""
    return {
        "identity_and_contact": {
            "name_or_preferred_label": "",
            "contact_fields_for_final_resume": {},
            "resume_contact_fields_authorized": False,
            "redaction_required_for_intermediate_outputs": True,
        },
        "education_status": {
            "school_name": "",
            "college_or_department": "",
            "major_name": major_name,
            "degree_level": "",
            "grade_or_year": "大二" if "大二" in input_text else "",
            "graduation_window": "",
            "education_status": candidate_stage,
        },
        "major_and_discipline": {
            "discipline_domain": "engineering" if major_name else "",
            "major_cluster": major_name,
        },
        "internship_experience": [],
        "project_competition_research_experience": [],
        "skills_and_tools": skills,
        "external_assets": [],
        "target_direction": {
            "target_roles": target_roles,
            "target_companies": [],
            "target_industries": [],
            "target_locations": [],
            "internship_or_full_time": target_kind,
        },
        "preferences_constraints": [],
        "current_concerns": [],
        "materials_provided": [{"type": "chat_brief", "description": "first-round user text"}],
    }


def build_context_packet(
    run_id: str,
    profile_ref: str,
    context_ref: str,
    profile: dict[str, Any],
    task_type: str,
) -> dict[str, Any]:
    known_user_facts = []
    education = profile["education_status"]
    if education["major_name"]:
        known_user_facts.append({"field": "major_name", "value": education["major_name"]})
    if education["grade_or_year"]:
        known_user_facts.append({"field": "grade_or_year", "value": education["grade_or_year"]})
    for skill in profile["skills_and_tools"]:
        known_user_facts.append({"field": "skill", "value": skill})

    missing_user_owned_facts = [
        "school_name",
        "degree_level",
        "graduation_window",
        "project_competition_research_experience",
        "internship_experience",
        "target_location_or_company_if_any",
    ]
    public_research_needed = [
        {
            "research_question": "Collect current public JD and company evidence before role-specific recommendations.",
            "target_sources": [
                "official company career pages",
                "public recruitment platform JDs",
                "official school career center notices",
            ],
            "needed_for_outputs": ["application_direction", "runtime_weights", "resume_tailoring"],
        }
    ]
    return {
        "packet_id": f"{run_id}-context",
        "artifact_ref": context_ref,
        "context_packet_version": "0.1",
        "created_from": "first_round_user_profile",
        "first_round_user_profile_ref": profile_ref,
        "user_goal": "simulate local runtime contract without network or real subagent execution",
        "task_type": task_type,
        "known_user_facts": known_user_facts,
        "candidate_stage": profile["education_status"]["education_status"],
        "discipline_domain": profile["major_and_discipline"].get("discipline_domain", ""),
        "school_context": {
            "school_name": education["school_name"],
            "major_name": education["major_name"],
            "grade_or_year": education["grade_or_year"],
            "school_signal_research_needed": ["official school-company cooperation evidence"],
        },
        "target_context": profile["target_direction"],
        "provided_materials": profile["materials_provided"],
        "missing_user_owned_facts": missing_user_owned_facts,
        "public_research_needed": public_research_needed,
        "runtime_weight_questions": [
            "skill_weight",
            "external_asset_weight",
            "school_signal_weight",
            "application_strategy_weight",
            "hr_screening_weight",
        ],
        "privacy_constraints": ["redact_contact_fields", "do_not_copy_private_resume_to_shared_context"],
        "consent_flags": {"incomplete_resume_consent": False},
        "blocked_outputs": ["application_direction", "final_resume_draft"],
        "next_possible_actions": [
            "Ask user once for missing user-owned facts.",
            "Run public research subagents for current JD/company/school evidence.",
            "Keep final recommendations blocked until required evidence exists.",
        ],
    }


def build_injection(
    run_id: str,
    target_agent: str,
    context_ref: str,
    injection_ref: str,
    input_packet_ref: str,
    allowed_user_facts_ref: str,
    output_ref: str,
) -> dict[str, Any]:
    base_prompt_ref = f".codex/agents/{target_agent}.toml"
    return {
        "target_agent": target_agent,
        "base_prompt_ref": base_prompt_ref,
        "runtime_context_packet_ref": context_ref,
        "role_specific_context": {
            "simulation_scope": "contract_only_no_network_no_real_subagent",
            "must_return_blockers_instead_of_final_judgment": True,
        },
        "allowed_user_facts": ["major_name", "grade_or_year", "skills_and_tools", "target_direction"],
        "research_tasks": [
            {
                "research_question": "Gather current public JD/company/school evidence before setting fit or priority.",
                "target_sources": [
                    "official company career pages",
                    "public recruitment platform JDs",
                    "official school notices",
                ],
                "required_freshness": "0_6_months preferred; otherwise mark weak or stale",
                "needed_for_outputs": ["runtime_weights", "application_strategy"],
            }
        ],
        "hard_data_weight_tasks": [
            {
                "parameter": "skill_weight",
                "rule": "verified only with current JD or public official evidence; otherwise not_available",
            }
        ],
        "database_files_to_read": [
            "data/runtime_parameters/parameter_ownership.zh-CN.json",
            "data/major_taxonomy/summary.json",
            "data/company_signals/summary.json",
        ],
        "source_policy_refs": [".agents/skills/career-pipeline/references/source-policy.md"],
        "invocation_contract": {
            "invocation_id": f"{run_id}-{target_agent}",
            "run_id": run_id,
            "target_agent": target_agent,
            "base_prompt_ref": base_prompt_ref,
            "secondary_prompt_injection_ref": injection_ref,
            "runtime_context_packet_ref": context_ref,
            "input_packet_ref": input_packet_ref,
            "allowed_user_facts_ref": allowed_user_facts_ref,
            "database_files_to_read": [
                "data/runtime_parameters/parameter_ownership.zh-CN.json",
                "data/major_taxonomy/summary.json",
                "data/company_signals/summary.json",
            ],
            "source_policy_refs": [".agents/skills/career-pipeline/references/source-policy.md"],
            "research_tasks": [
                {
                    "research_question": "Gather current public JD/company/school evidence before setting fit or priority.",
                    "target_sources": [
                        "official company career pages",
                        "public recruitment platform JDs",
                        "official school notices",
                    ],
                    "required_freshness": "0_6_months preferred; otherwise mark weak or stale",
                    "needed_for_outputs": ["runtime_weights", "application_strategy"],
                }
            ],
            "hard_data_weight_tasks": [
                {
                    "parameter": "skill_weight",
                    "rule": "verified only with current JD or public official evidence; otherwise not_available",
                }
            ],
            "required_output_fields": [
                "role_output_packet",
                "error_recovery_state",
                "blocked_outputs",
                "runtime_research_tasks",
            ],
            "output_artifact_target": output_ref,
            "privacy_constraints": ["redact_contact_fields", "share_only_allowed_user_facts"],
            "handoff_contract": ["return blockers to CareerOrchestrator"],
            "debate_contract": ["challenge unsupported weights instead of creating scores"],
            "expected_artifact_types": ["subagent_output", "evidence_packet", "redacted_log"],
            "required_log_events": ["dispatch", "receive_output", "validate_output"],
            "timeout_or_budget_hint": "simulation-no-dispatch",
            "retry_allowed": True,
            "on_failure": "return_blocked",
            "status": "not_started",
        },
        "blocked_outputs": ["fit_score", "application_strategy", "final_resume_draft"],
        "required_output_fields": [
            "role_output_packet",
            "error_recovery_state",
            "blocked_outputs",
            "runtime_research_tasks",
        ],
        "handoff_contract": ["return blockers to CareerOrchestrator"],
        "debate_contract": ["challenge unsupported weights instead of creating scores"],
    }


def build_invocation(injection: dict[str, Any]) -> dict[str, Any]:
    contract = dict(injection["invocation_contract"])
    return {"subagent_invocation": contract}


def build_input_packet(
    run_id: str,
    target_agent: str,
    context_ref: str,
    injection_ref: str,
) -> dict[str, Any]:
    return {
        "input_packet": {
            "run_id": run_id,
            "target_agent": target_agent,
            "runtime_context_packet_ref": context_ref,
            "secondary_prompt_injection_ref": injection_ref,
            "prompt_composition_order": [
                "static role prompt",
                "runtime context packet reference",
                "secondary prompt injection",
                "minimum database subset",
                "source/privacy/weight/debate rules",
                "required output schema",
            ],
            "simulation_note": "No real subagent is dispatched by this script.",
        }
    }


def simulate(args: argparse.Namespace) -> dict[str, Any]:
    if args.task_type not in TASK_TYPES:
        raise ValueError(f"unsupported task type: {args.task_type}")

    repo_root = Path(__file__).resolve().parents[4]
    run_id = args.run_id or f"run-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    run_root = Path(args.run_root)
    run_dir = run_root / run_id
    created_at = utc_now()

    profile = build_profile(args.input_text)

    raw_ref_path = run_dir / "input" / "raw_refs.json"
    profile_path = run_dir / "input" / "normalized" / "first_round_user_profile.json"
    context_path = run_dir / "input" / "normalized" / "runtime_context_packet.json"

    write_json(
        raw_ref_path,
        {
            "raw_input_refs": [
                {
                    "input_id": "first-round-chat",
                    "input_type": "chat_brief",
                    "storage": "inline_excerpt_for_simulation",
                    "redaction_applied": True,
                    "excerpt": redact_contact_like_text(args.input_text[:240]),
                }
            ]
        },
    )
    write_json(profile_path, {"first_round_user_profile": profile})
    context_ref = rel(context_path, run_dir)
    profile_ref = rel(profile_path, run_dir)
    context = build_context_packet(run_id, profile_ref, context_ref, profile, args.task_type)
    write_json(context_path, {"runtime_context_packet": context})

    target_agents = ROUTES[args.route]
    injection_paths: list[Path] = []
    invocation_paths: list[Path] = []
    generated_role_output_paths: list[tuple[str, Path]] = []

    for target_agent in target_agents:
        injection_path = run_dir / "injections" / f"{target_agent}.secondary_prompt_injection.json"
        input_packet_path = run_dir / "invocations" / f"{target_agent}.input_packet.json"
        allowed_facts_path = run_dir / "invocations" / f"{target_agent}.allowed_user_facts.json"
        invocation_path = run_dir / "invocations" / f"{target_agent}.invocation.json"
        role_output_path = run_dir / "agents" / target_agent / "output.json"

        injection = build_injection(
            run_id,
            target_agent,
            context_ref,
            rel(injection_path, run_dir),
            rel(input_packet_path, run_dir),
            rel(allowed_facts_path, run_dir),
            rel(role_output_path, run_dir),
        )
        write_json(injection_path, {"secondary_prompt_injection": injection})
        write_json(input_packet_path, build_input_packet(run_id, target_agent, context_ref, rel(injection_path, run_dir)))
        write_json(
            allowed_facts_path,
            {
                "allowed_user_facts": [
                    fact
                    for fact in context["known_user_facts"]
                    if fact["field"] in {"major_name", "grade_or_year", "skill"}
                ]
            },
        )
        invocation = build_invocation(injection)
        write_json(invocation_path, invocation)

        role_output = {
            "role_output_packet": {
                "invocation_id": invocation["subagent_invocation"]["invocation_id"],
                "target_agent": target_agent,
                "status": "blocked",
                "role_output_ref": rel(role_output_path, run_dir),
                "evidence_packet_refs": [],
                "runtime_weights_ref": "merge/runtime_weights.json",
                "artifact_refs": [],
                "blocked_outputs": ["fit_score", "application_strategy", "final_resume_draft"],
                "runtime_research_tasks": context["public_research_needed"],
                "needs_user_confirmation": context["missing_user_owned_facts"],
                "handoff_to": ["career-orchestrator"],
                "errors": [
                    {
                        "category": "missing_user_fact",
                        "severity": "blocking",
                        "message": "Simulation keeps user-owned facts and public evidence incomplete.",
                    }
                ],
                "confidence": "low",
            }
        }
        write_json(role_output_path, role_output)
        injection_paths.append(injection_path)
        invocation_paths.append(invocation_path)
        generated_role_output_paths.append((target_agent, role_output_path))

    runtime_weights_path = run_dir / "merge" / "runtime_weights.json"
    write_json(
        runtime_weights_path,
        {
            "runtime_weights": [
                {
                    "parameter": "skill_weight",
                    "weight_scope": "skill_weight",
                    "proposed_weight": None,
                    "weight_unit": "qualitative",
                    "weight_status": "not_available",
                    "evidence_basis": [],
                    "source_count": 0,
                    "source_mix": [],
                    "freshness": "unknown",
                    "conflict_notes": ["No network or real subagent research ran in simulation mode."],
                    "confidence": "low",
                    "cannot_decide_alone": True,
                    "runtime_research_tasks": context["public_research_needed"],
                }
            ]
        },
    )

    error_path = run_dir / "merge" / "error_recovery_state.json"
    error_recovery_state = {
        "error_recovery_state": {
            "status": "blocked",
            "errors": [
                {
                    "runtime_error": {
                        "error_id": f"{run_id}-missing-user-facts",
                        "run_id": run_id,
                        "stage": "blocked",
                        "agent": "career-orchestrator",
                        "category": "missing_user_fact",
                        "severity": "blocking",
                        "affected_outputs": ["final_resume_draft", "application_direction"],
                        "evidence_or_artifact_refs": [context_ref],
                        "message": "Required user-owned facts are missing.",
                        "recovery_action": "ask_user_once",
                        "owner": "user",
                        "retry_count": 0,
                        "resolved": False,
                    }
                },
                {
                    "runtime_error": {
                        "error_id": f"{run_id}-missing-public-evidence",
                        "run_id": run_id,
                        "stage": "blocked",
                        "agent": "job-scout",
                        "category": "unsupported_weight",
                        "severity": "blocking",
                        "affected_outputs": ["fit_score", "application_strategy"],
                        "evidence_or_artifact_refs": [],
                        "message": "Runtime weights cannot be set without current public or user-provided evidence.",
                        "recovery_action": "research_public_source",
                        "owner": "local_subagent",
                        "retry_count": 0,
                        "resolved": False,
                    }
                },
            ],
            "recovery_actions": ["ask_user_once", "run_public_research"],
            "degraded_outputs": ["known_information_summary"],
            "blocked_outputs": ["missing_user_facts", "public_research_required", "final_resume_draft"],
            "safe_outputs": ["first_round_user_profile", "runtime_context_packet", "subagent_invocation_plan"],
            "next_action": "return_blocked_package",
        }
    }
    write_json(error_path, error_recovery_state)

    blocked_path = run_dir / "final" / "blocked_package.json"
    blocked_package = {
        "blocked_package": {
            "run_id": run_id,
            "blocked_outputs": ["missing_user_facts", "public_research_required", "final_resume_draft"],
            "safe_outputs": [
                "known user facts can be summarized",
                "public research tasks can be handed to runtime subagents",
                "resume draft remains blocked until consent and evidence gates pass",
            ],
            "missing_user_owned_facts": context["missing_user_owned_facts"],
            "public_research_tasks": context["public_research_needed"],
            "consent_requests": ["incomplete_resume_consent if the user refuses missing facts"],
            "failed_agents": [],
            "source_conflicts": [],
            "next_possible_actions": context["next_possible_actions"],
        }
    }
    write_json(blocked_path, blocked_package)

    manifest_path = run_dir / "manifest.json"
    artifact_refs = [
        artifact_ref(
            run_id,
            run_dir,
            raw_ref_path,
            "raw_input_ref",
            "simulate_runtime_run",
            "user_private",
            contains_contact=True,
            contains_private_resume=True,
        ),
        artifact_ref(
            run_id,
            run_dir,
            profile_path,
            "normalized_profile",
            "input-normalizer",
            "user_private",
            contains_private_resume=True,
        ),
        artifact_ref(
            run_id,
            run_dir,
            context_path,
            "runtime_context_packet",
            "input-normalizer",
            "user_private",
            contains_private_resume=True,
        ),
        artifact_ref(run_id, run_dir, runtime_weights_path, "merge_result", "career-orchestrator"),
        artifact_ref(run_id, run_dir, error_path, "merge_result", "career-orchestrator"),
        artifact_ref(run_id, run_dir, blocked_path, "final_package", "career-orchestrator"),
    ]
    for path in injection_paths:
        artifact_refs.append(artifact_ref(run_id, run_dir, path, "secondary_prompt_injection", "career-orchestrator"))
    for path in invocation_paths:
        artifact_refs.append(artifact_ref(run_id, run_dir, path, "subagent_input", "career-orchestrator"))
    for target_agent, path in generated_role_output_paths:
        artifact_refs.append(artifact_ref(run_id, run_dir, path, "subagent_output", target_agent))

    manifest = {
        "execution_manifest": {
            "run_id": run_id,
            "created_at": created_at,
            "updated_at": utc_now(),
            "codex_surface": "desktop",
            "repository_ref": repository_ref(repo_root),
            "skill_ref": ".agents/skills/career-pipeline/SKILL.md",
            "task_type": args.task_type,
            "user_goal_summary": "local simulation of career pipeline runtime contracts",
            "privacy_mode": "redacted_intermediate",
            "run_dir_ref": str(run_dir),
            "current_stage": "blocked",
            "runtime_context_packet_ref": context_ref,
            "secondary_prompt_injection_refs": [rel(path, run_dir) for path in injection_paths],
            "subagent_invocation_refs": [rel(path, run_dir) for path in invocation_paths],
            "artifact_manifest_ref": "manifest.json",
            "artifact_refs": artifact_refs,
            "evidence_packet_refs": [],
            "runtime_weights_ref": rel(runtime_weights_path, run_dir),
            "gate_status": {
                "input_normalized": True,
                "context_packet_created": True,
                "secondary_injections_created": True,
                "specialists_completed_or_blocked": True,
                "debate_completed_or_recorded": False,
                "hr_review_completed": False,
                "factual_review_completed_when_needed": False,
                "user_confirmation_resolved_when_needed": False,
            },
            "error_recovery_state_ref": rel(error_path, run_dir),
            "final_package_ref": "",
        },
        "run_state": {
            "run_id": run_id,
            "stage": "blocked",
            "task_type": args.task_type,
            "runtime_context_packet_ref": context_ref,
            "secondary_prompt_injection_refs": [rel(path, run_dir) for path in injection_paths],
            "subagent_invocation_refs": [rel(path, run_dir) for path in invocation_paths],
            "active_agents": [],
            "completed_agents": [],
            "blocked_agents": target_agents,
            "failed_invocations": [],
            "artifact_manifest_ref": "manifest.json",
            "shared_context_refs": [context_ref],
            "evidence_packet_refs": [],
            "execution_log_refs": [],
            "debate_topics": [],
            "user_confirmation_points": context["missing_user_owned_facts"],
            "blocked_outputs": blocked_package["blocked_package"]["blocked_outputs"],
            "degraded_outputs": ["known_information_summary"],
            "recovery_actions": ["ask_user_once", "run_public_research"],
            "next_action": "return_blocked",
        },
    }
    write_json(manifest_path, manifest)

    return {
        "runner_response": {
            "exit_status": "blocked",
            "run_id": run_id,
            "execution_manifest_ref": str(manifest_path),
            "final_package_ref": "",
            "blocked_package_ref": str(blocked_path),
            "error_recovery_state_ref": str(error_path),
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulate a local career-pipeline runtime run.")
    parser.add_argument("--task-type", default="resume_generation", choices=sorted(TASK_TYPES))
    parser.add_argument("--input-text", required=True)
    parser.add_argument("--run-root", default=".career-pipeline-runs")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--route", default="single_job_scout", choices=sorted(ROUTES))
    args = parser.parse_args(argv)
    try:
        response = simulate(args)
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
