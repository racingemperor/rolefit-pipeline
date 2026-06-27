import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / ".agents" / "skills" / "career-pipeline" / "scripts" / "validate_runtime_contracts.py"
SIMULATOR = ROOT / ".agents" / "skills" / "career-pipeline" / "scripts" / "simulate_runtime_run.py"
PLAN_BUILDER = ROOT / ".agents" / "skills" / "career-pipeline" / "scripts" / "build_subagent_plan.py"
PLAN_EXECUTOR = ROOT / ".agents" / "skills" / "career-pipeline" / "scripts" / "execute_subagent_plan.py"
RUN_CONTINUER = ROOT / ".agents" / "skills" / "career-pipeline" / "scripts" / "continue_runtime_run.py"
PROMPT_BUNDLE_BUILDER = ROOT / ".agents" / "skills" / "career-pipeline" / "scripts" / "build_subagent_prompt_bundle.py"
SOURCE_PLAN_BUILDER = ROOT / ".agents" / "skills" / "career-pipeline" / "scripts" / "build_public_source_plan.py"


def run_python(script: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(cwd or ROOT),
        text=True,
        capture_output=True,
        check=False,
    )


def test_validator_rejects_injection_without_runtime_context_packet(tmp_path):
    packet = {
        "secondary_prompt_injections": [
            {
                "target_agent": "job-scout",
                "base_prompt_ref": ".codex/agents/job-scout.toml",
                "runtime_context_packet_ref": "",
                "role_specific_context": {"goal": "find internship options"},
                "allowed_user_facts": ["major_name"],
                "research_tasks": [{"question": "collect current public JDs"}],
                "hard_data_weight_tasks": [{"parameter": "skill_weight"}],
                "database_files_to_read": ["data/major_taxonomy/summary.json"],
                "source_policy_refs": [".agents/skills/career-pipeline/references/source-policy.md"],
                "invocation_contract": {
                    "invocation_id": "inv-001",
                    "run_id": "run-test",
                    "target_agent": "job-scout",
                    "base_prompt_ref": ".codex/agents/job-scout.toml",
                    "secondary_prompt_injection_ref": "injections/job-scout.secondary_prompt_injection.json",
                    "runtime_context_packet_ref": "",
                    "input_packet_ref": "invocations/job-scout.input_packet.json",
                    "allowed_user_facts_ref": "invocations/job-scout.allowed_user_facts.json",
                    "output_artifact_target": "agents/job-scout/output.json",
                    "privacy_constraints": ["redact_contact_fields"],
                    "expected_artifact_types": ["subagent_output"],
                    "required_log_events": ["dispatch", "receive_output"],
                    "on_failure": "return_blocked",
                },
                "required_output_fields": ["role_output_packet"],
                "handoff_contract": ["return blockers to orchestrator"],
                "debate_contract": ["preserve weak evidence challenges"],
            }
        ]
    }
    packet_path = tmp_path / "missing-context.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    result = run_python(VALIDATOR, "--injections", str(packet_path))

    assert result.returncode == 1
    assert "runtime_context_packet_ref" in result.stderr


def test_validator_converts_secondary_injection_to_invocation_packet(tmp_path):
    packet = {
        "secondary_prompt_injections": [
            {
                "target_agent": "job-scout",
                "base_prompt_ref": ".codex/agents/job-scout.toml",
                "runtime_context_packet_ref": "input/normalized/runtime_context_packet.json",
                "role_specific_context": {"goal": "find internship options"},
                "allowed_user_facts": ["major_name", "grade_or_year"],
                "research_tasks": [{"question": "collect current public JDs"}],
                "hard_data_weight_tasks": [{"parameter": "skill_weight"}],
                "database_files_to_read": ["data/major_taxonomy/summary.json"],
                "source_policy_refs": [".agents/skills/career-pipeline/references/source-policy.md"],
                "invocation_contract": {
                    "invocation_id": "inv-001",
                    "run_id": "run-test",
                    "target_agent": "job-scout",
                    "base_prompt_ref": ".codex/agents/job-scout.toml",
                    "secondary_prompt_injection_ref": "injections/job-scout.secondary_prompt_injection.json",
                    "runtime_context_packet_ref": "input/normalized/runtime_context_packet.json",
                    "input_packet_ref": "invocations/job-scout.input_packet.json",
                    "allowed_user_facts_ref": "invocations/job-scout.allowed_user_facts.json",
                    "database_files_to_read": ["data/major_taxonomy/summary.json"],
                    "source_policy_refs": [".agents/skills/career-pipeline/references/source-policy.md"],
                    "research_tasks": [{"question": "collect current public JDs"}],
                    "hard_data_weight_tasks": [{"parameter": "skill_weight"}],
                    "required_output_fields": ["role_output_packet"],
                    "output_artifact_target": "agents/job-scout/output.json",
                    "privacy_constraints": ["redact_contact_fields"],
                    "handoff_contract": ["return blockers to orchestrator"],
                    "debate_contract": ["preserve weak evidence challenges"],
                    "expected_artifact_types": ["subagent_output"],
                    "required_log_events": ["dispatch", "receive_output"],
                    "retry_allowed": True,
                    "on_failure": "return_blocked",
                    "status": "not_started",
                },
                "required_output_fields": ["role_output_packet"],
                "handoff_contract": ["return blockers to orchestrator"],
                "debate_contract": ["preserve weak evidence challenges"],
            }
        ]
    }
    packet_path = tmp_path / "ready.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    result = run_python(VALIDATOR, "--injections", str(packet_path), "--emit-invocations")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    invocation = payload["subagent_invocations"][0]["subagent_invocation"]
    assert invocation["target_agent"] == "job-scout"
    assert invocation["runtime_context_packet_ref"] == "input/normalized/runtime_context_packet.json"
    assert invocation["status"] == "not_started"
    assert invocation["on_failure"] == "return_blocked"


def test_validator_rejects_final_package_when_required_gate_is_blocked(tmp_path):
    manifest = {
        "execution_manifest": {
            "run_id": "run-test",
            "current_stage": "final_package_ready",
            "runtime_context_packet_ref": "input/normalized/runtime_context_packet.json",
            "secondary_prompt_injection_refs": ["injections/job-scout.secondary_prompt_injection.json"],
            "subagent_invocation_refs": ["invocations/job-scout.invocation.json"],
            "gate_status": {
                "input_normalized": True,
                "context_packet_created": True,
                "secondary_injections_created": True,
                "specialists_completed_or_blocked": True,
                "debate_completed_or_recorded": True,
                "hr_review_completed": False,
                "factual_review_completed_when_needed": False,
                "user_confirmation_resolved_when_needed": True,
            },
            "final_package_ref": "final/decision_package.json",
        },
        "run_state": {
            "run_id": "run-test",
            "stage": "final_package_ready",
            "task_type": "resume_generation",
            "runtime_context_packet_ref": "input/normalized/runtime_context_packet.json",
            "secondary_prompt_injection_refs": ["injections/job-scout.secondary_prompt_injection.json"],
            "subagent_invocation_refs": ["invocations/job-scout.invocation.json"],
            "blocked_outputs": [],
            "next_action": "return_final_package",
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_python(VALIDATOR, "--manifest", str(manifest_path))

    assert result.returncode == 1
    assert "hr_review_completed" in result.stderr
    assert "final_package_ready" in result.stderr


def test_validator_rejects_final_package_without_traceable_runtime_refs(tmp_path):
    manifest = {
        "execution_manifest": {
            "run_id": "run-test",
            "current_stage": "final_package_ready",
            "runtime_context_packet_ref": "",
            "secondary_prompt_injection_refs": [],
            "subagent_invocation_refs": [],
            "gate_status": {
                "input_normalized": True,
                "context_packet_created": True,
                "secondary_injections_created": True,
                "specialists_completed_or_blocked": True,
                "debate_completed_or_recorded": True,
                "hr_review_completed": True,
                "factual_review_completed_when_needed": True,
                "user_confirmation_resolved_when_needed": True,
            },
            "final_package_ref": "final/decision_package.json",
        },
        "run_state": {
            "run_id": "run-test",
            "stage": "final_package_ready",
            "task_type": "resume_generation",
            "runtime_context_packet_ref": "",
            "secondary_prompt_injection_refs": [],
            "subagent_invocation_refs": [],
            "blocked_outputs": [],
            "next_action": "return_final_package",
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_python(VALIDATOR, "--manifest", str(manifest_path))

    assert result.returncode == 1
    assert "runtime_context_packet_ref" in result.stderr


def test_simulator_creates_private_blocked_run_artifacts(tmp_path):
    result = run_python(
        SIMULATOR,
        "--task-type",
        "resume_generation",
        "--input-text",
        "我是计算机专业大二，会 Python，想找 AI 实习。",
        "--run-root",
        str(tmp_path / ".career-pipeline-runs"),
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["runner_response"]["exit_status"] == "blocked"

    run_dir = tmp_path / ".career-pipeline-runs" / response["runner_response"]["run_id"]
    assert run_dir.is_dir()
    assert (run_dir / "manifest.json").is_file()
    assert (run_dir / "input" / "normalized" / "runtime_context_packet.json").is_file()
    assert (run_dir / "injections" / "job-scout.secondary_prompt_injection.json").is_file()
    assert (run_dir / "invocations" / "job-scout.invocation.json").is_file()
    assert (run_dir / "final" / "blocked_package.json").is_file()

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["execution_manifest"]["current_stage"] == "blocked"
    assert manifest["run_state"]["stage"] == "blocked"
    assert manifest["execution_manifest"]["final_package_ref"] == ""
    assert "missing_user_facts" in json.loads((run_dir / "final" / "blocked_package.json").read_text(encoding="utf-8"))["blocked_package"]["blocked_outputs"]


def test_simulator_redacts_contact_like_input_from_raw_refs(tmp_path):
    result = run_python(
        SIMULATOR,
        "--task-type",
        "resume_generation",
        "--input-text",
        "我是计算机专业大二，电话 13812345678，邮箱 test@example.com，会 Python。",
        "--run-root",
        str(tmp_path / ".career-pipeline-runs"),
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    run_dir = tmp_path / ".career-pipeline-runs" / response["runner_response"]["run_id"]
    raw_refs = (run_dir / "input" / "raw_refs.json").read_text(encoding="utf-8")
    assert "13812345678" not in raw_refs
    assert "test@example.com" not in raw_refs
    assert "[redacted-phone]" in raw_refs
    assert "[redacted-email]" in raw_refs


def test_simulator_marks_user_derived_artifacts_as_private(tmp_path):
    result = run_python(
        SIMULATOR,
        "--task-type",
        "resume_generation",
        "--input-text",
        "我是计算机专业大二，会 Python，想找 AI 实习。",
        "--run-root",
        str(tmp_path / ".career-pipeline-runs"),
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    run_dir = tmp_path / ".career-pipeline-runs" / response["runner_response"]["run_id"]
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    refs = {
        ref["path"]: ref
        for ref in manifest["execution_manifest"]["artifact_refs"]
    }

    for path in [
        "input/raw_refs.json",
        "input/normalized/first_round_user_profile.json",
        "input/normalized/runtime_context_packet.json",
    ]:
        assert refs[path]["privacy_class"] == "user_private"
        assert refs[path]["contains_private_resume"] is True

    assert refs["input/raw_refs.json"]["contains_contact"] is True
    assert refs["injections/job-scout.secondary_prompt_injection.json"]["privacy_class"] == "derived"


def test_repository_role_prompts_satisfy_runtime_traceability_contract():
    result = run_python(VALIDATOR)

    assert result.returncode == 0, result.stderr


def test_plan_builder_creates_plan_only_dispatch_queue(tmp_path):
    run_root = tmp_path / ".career-pipeline-runs"
    simulate = run_python(
        SIMULATOR,
        "--task-type",
        "job_search",
        "--input-text",
        "我是计算机专业大二，会 Python，想找 AI 实习。",
        "--run-root",
        str(run_root),
        "--route",
        "job_search",
    )
    assert simulate.returncode == 0, simulate.stderr
    run_id = json.loads(simulate.stdout)["runner_response"]["run_id"]
    run_dir = run_root / run_id

    result = run_python(PLAN_BUILDER, "--run-dir", str(run_dir))

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["planner_response"]["exit_status"] == "success"
    plan_path = run_dir / response["planner_response"]["subagent_plan_ref"]
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    queue = plan["subagent_invocation_plan"]["dispatch_queue"]
    agents = [item["target_agent"] for item in queue]
    assert agents == [
        "major-cluster-classifier",
        "profile-extractor",
        "job-scout",
        "jd-analyzer",
        "match-strategist",
        "learning-path-strategist",
    ]
    assert all(item["dispatch_mode"] == "plan_only" for item in queue)
    assert all(item["status"] == "planned" for item in queue)
    assert not any("input/raw_refs.json" in item["input_refs"] for item in queue)

    validation = run_python(VALIDATOR, "--subagent-plan", str(plan_path))
    assert validation.returncode == 0, validation.stderr


def test_validator_rejects_subagent_plan_that_is_not_plan_only(tmp_path):
    plan = {
        "subagent_invocation_plan": {
            "run_id": "run-test",
            "plan_status": "ready",
            "dispatch_queue": [
                {
                    "queue_index": 0,
                    "target_agent": "job-scout",
                    "invocation_ref": "invocations/job-scout.invocation.json",
                    "input_refs": ["input/normalized/runtime_context_packet.json"],
                    "output_artifact_target": "agents/job-scout/output.json",
                    "dispatch_mode": "execute",
                    "status": "running",
                    "allowed_network": True,
                    "requires_human_approval": False,
                    "privacy_class": "derived",
                    "blocked_until": ["human_confirms_real_subagent_execution"],
                }
            ],
        }
    }
    plan_path = tmp_path / "bad-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result = run_python(VALIDATOR, "--subagent-plan", str(plan_path))

    assert result.returncode == 1
    assert "plan_only" in result.stderr


def test_validator_rejects_subagent_plan_that_exposes_raw_input(tmp_path):
    plan = {
        "subagent_invocation_plan": {
            "run_id": "run-test",
            "plan_status": "ready",
            "dispatch_queue": [
                {
                    "queue_index": 0,
                    "target_agent": "job-scout",
                    "invocation_ref": "invocations/job-scout.invocation.json",
                    "input_refs": [
                        "input/raw_refs.json",
                        "input/normalized/runtime_context_packet.json",
                    ],
                    "output_artifact_target": "agents/job-scout/output.json",
                    "dispatch_mode": "plan_only",
                    "status": "planned",
                    "allowed_network": False,
                    "requires_human_approval": True,
                    "privacy_class": "derived",
                    "blocked_until": ["human_confirms_real_subagent_execution"],
                }
            ],
        }
    }
    plan_path = tmp_path / "raw-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result = run_python(VALIDATOR, "--subagent-plan", str(plan_path))

    assert result.returncode == 1
    assert "raw input" in result.stderr


def test_executor_dry_run_preserves_plan_and_invocation_statuses(tmp_path):
    run_root = tmp_path / ".career-pipeline-runs"
    simulate = run_python(
        SIMULATOR,
        "--task-type",
        "job_search",
        "--input-text",
        "computer science sophomore, Python, looking for AI internship",
        "--run-root",
        str(run_root),
        "--route",
        "job_search",
    )
    assert simulate.returncode == 0, simulate.stderr
    run_id = json.loads(simulate.stdout)["runner_response"]["run_id"]
    run_dir = run_root / run_id
    plan = run_python(PLAN_BUILDER, "--run-dir", str(run_dir))
    assert plan.returncode == 0, plan.stderr

    result = run_python(PLAN_EXECUTOR, "--run-dir", str(run_dir))

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["executor_response"]["exit_status"] == "dry_run"
    event_log = run_dir / response["executor_response"]["execution_events_ref"]
    assert event_log.is_file()

    plan_path = run_dir / "invocations" / "subagent_invocation_plan.json"
    plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
    assert all(
        item["status"] == "planned"
        for item in plan_payload["subagent_invocation_plan"]["dispatch_queue"]
    )
    first_invocation_ref = plan_payload["subagent_invocation_plan"]["dispatch_queue"][0]["invocation_ref"]
    first_invocation = json.loads((run_dir / first_invocation_ref).read_text(encoding="utf-8"))
    assert first_invocation["subagent_invocation"]["status"] == "not_started"
    assert "dry_run" in event_log.read_text(encoding="utf-8")


def test_executor_execute_requires_human_approval(tmp_path):
    run_root = tmp_path / ".career-pipeline-runs"
    simulate = run_python(
        SIMULATOR,
        "--task-type",
        "job_search",
        "--input-text",
        "computer science sophomore, Python, looking for AI internship",
        "--run-root",
        str(run_root),
        "--route",
        "job_search",
    )
    assert simulate.returncode == 0, simulate.stderr
    run_id = json.loads(simulate.stdout)["runner_response"]["run_id"]
    run_dir = run_root / run_id
    assert run_python(PLAN_BUILDER, "--run-dir", str(run_dir)).returncode == 0

    result = run_python(PLAN_EXECUTOR, "--run-dir", str(run_dir), "--execute")

    assert result.returncode == 1
    assert "human approval" in result.stderr.lower()


def test_executor_network_execution_requires_source_policy_ack(tmp_path):
    run_root = tmp_path / ".career-pipeline-runs"
    simulate = run_python(
        SIMULATOR,
        "--task-type",
        "job_search",
        "--input-text",
        "computer science sophomore, Python, looking for AI internship",
        "--run-root",
        str(run_root),
        "--route",
        "job_search",
    )
    assert simulate.returncode == 0, simulate.stderr
    run_id = json.loads(simulate.stdout)["runner_response"]["run_id"]
    run_dir = run_root / run_id
    assert run_python(PLAN_BUILDER, "--run-dir", str(run_dir)).returncode == 0

    result = run_python(
        PLAN_EXECUTOR,
        "--run-dir",
        str(run_dir),
        "--execute",
        "--human-approved",
        "--allow-network",
    )

    assert result.returncode == 1
    assert "source policy" in result.stderr.lower()


def test_executor_network_execution_requires_source_plan(tmp_path):
    run_root = tmp_path / ".career-pipeline-runs"
    simulate = run_python(
        SIMULATOR,
        "--task-type",
        "job_search",
        "--input-text",
        "computer science sophomore, Python, looking for AI internship",
        "--run-root",
        str(run_root),
        "--route",
        "job_search",
    )
    assert simulate.returncode == 0, simulate.stderr
    run_id = json.loads(simulate.stdout)["runner_response"]["run_id"]
    run_dir = run_root / run_id
    assert run_python(PLAN_BUILDER, "--run-dir", str(run_dir)).returncode == 0

    result = run_python(
        PLAN_EXECUTOR,
        "--run-dir",
        str(run_dir),
        "--execute",
        "--human-approved",
        "--allow-network",
        "--source-policy-ack",
    )

    assert result.returncode == 1
    assert "source plan" in result.stderr.lower()


def test_executor_network_execution_rejects_invalid_source_plan(tmp_path):
    run_root = tmp_path / ".career-pipeline-runs"
    simulate = run_python(
        SIMULATOR,
        "--task-type",
        "job_search",
        "--input-text",
        "computer science sophomore, Python, looking for AI internship",
        "--run-root",
        str(run_root),
        "--route",
        "job_search",
    )
    assert simulate.returncode == 0, simulate.stderr
    run_id = json.loads(simulate.stdout)["runner_response"]["run_id"]
    run_dir = run_root / run_id
    assert run_python(PLAN_BUILDER, "--run-dir", str(run_dir)).returncode == 0
    source_plan_path = run_dir / "evidence" / "public_source_research_plan.json"
    source_plan_path.parent.mkdir(parents=True, exist_ok=True)
    source_plan_path.write_text(
        json.dumps(
            {
                "public_source_research_plan": {
                    "run_id": run_id,
                    "policy_ref": ".agents/skills/career-pipeline/references/source-policy.md",
                    "network_execution_default": "disabled_until_human_and_source_policy_ack",
                    "research_tasks": [
                        {
                            "task_id": "login-only-jd",
                            "agent": "job-scout",
                            "claim_field": "jd_requirement",
                            "source_type": "recruitment_platform_jd",
                            "source_priority": 3,
                            "allowed": True,
                            "requires_login": True,
                            "may_set_weight": True,
                            "may_set_final_decision": True,
                            "evidence_strength_floor": "medium",
                            "privacy_action": "cache_metadata_only",
                            "query_template": "login-only JD",
                            "output_fields": ["evidence_basis"],
                        }
                    ],
                    "blocked_source_types": [],
                }
            }
        ),
        encoding="utf-8",
    )

    result = run_python(
        PLAN_EXECUTOR,
        "--run-dir",
        str(run_dir),
        "--execute",
        "--human-approved",
        "--allow-network",
        "--source-policy-ack",
    )

    assert result.returncode == 1
    assert "requires_login" in result.stderr


def test_validator_rejects_role_output_without_traceability(tmp_path):
    output = {
        "role_output_packet": {
            "invocation_id": "run-test-job-scout",
            "target_agent": "job-scout",
            "status": "done",
            "role_output_ref": "agents/job-scout/output.json",
            "evidence_packet_refs": [],
            "runtime_weights_ref": "merge/runtime_weights.json",
            "artifact_refs": [],
            "blocked_outputs": [],
            "runtime_research_tasks": [],
            "needs_user_confirmation": [],
            "handoff_to": [],
            "errors": [],
            "confidence": "medium",
        }
    }
    output_path = tmp_path / "role-output.json"
    output_path.write_text(json.dumps(output), encoding="utf-8")

    result = run_python(VALIDATOR, "--role-output", str(output_path))

    assert result.returncode == 1
    assert "invocation_ref" in result.stderr
    assert "error_recovery_state" in result.stderr


def test_validator_rejects_failed_role_output_with_final_decision_fields(tmp_path):
    output = {
        "invocation_ref": "invocations/job-scout.invocation.json",
        "role_output_packet": {
            "invocation_id": "run-test-job-scout",
            "target_agent": "job-scout",
            "status": "failed",
            "role_output_ref": "agents/job-scout/output.json",
            "evidence_packet_refs": [],
            "runtime_weights_ref": "merge/runtime_weights.json",
            "artifact_refs": [],
            "blocked_outputs": ["application_strategy"],
            "runtime_research_tasks": [],
            "needs_user_confirmation": [],
            "handoff_to": [],
            "errors": [{"category": "subagent_failed"}],
            "confidence": "low",
        },
        "error_recovery_state": {
            "status": "failed",
            "errors": [],
            "recovery_actions": ["return_blocked_package"],
            "degraded_outputs": [],
            "blocked_outputs": ["application_strategy"],
            "safe_outputs": [],
            "next_action": "return_blocked_package",
        },
        "application_strategy": {"priority": "apply now"},
    }
    output_path = tmp_path / "failed-output.json"
    output_path.write_text(json.dumps(output), encoding="utf-8")

    result = run_python(VALIDATOR, "--role-output", str(output_path))

    assert result.returncode == 1
    assert "failed or malformed" in result.stderr


def test_executor_rejects_malformed_backfill_output(tmp_path):
    run_root = tmp_path / ".career-pipeline-runs"
    simulate = run_python(
        SIMULATOR,
        "--task-type",
        "job_search",
        "--input-text",
        "computer science sophomore, Python, looking for AI internship",
        "--run-root",
        str(run_root),
        "--route",
        "job_search",
    )
    assert simulate.returncode == 0, simulate.stderr
    run_id = json.loads(simulate.stdout)["runner_response"]["run_id"]
    run_dir = run_root / run_id
    assert run_python(PLAN_BUILDER, "--run-dir", str(run_dir)).returncode == 0
    bad_output = tmp_path / "bad-output.json"
    bad_output.write_text(json.dumps({"not_role_output_packet": {}}), encoding="utf-8")

    result = run_python(
        PLAN_EXECUTOR,
        "--run-dir",
        str(run_dir),
        "--backfill-output",
        f"job-scout={bad_output}",
    )

    assert result.returncode == 1
    assert "role_output_packet" in result.stderr


def test_continue_runtime_run_accepts_user_facts_and_updates_same_run(tmp_path):
    run_root = tmp_path / ".career-pipeline-runs"
    simulate = run_python(
        SIMULATOR,
        "--task-type",
        "resume_generation",
        "--input-text",
        "computer science sophomore, Python, looking for AI internship",
        "--run-root",
        str(run_root),
    )
    assert simulate.returncode == 0, simulate.stderr
    run_id = json.loads(simulate.stdout)["runner_response"]["run_id"]
    run_dir = run_root / run_id
    facts = {
        "school_name": "Example University",
        "degree_level": "bachelor",
        "graduation_window": "2028",
        "project_competition_research_experience": [
            {"name": "LLM resume parser", "evidence": "course project"}
        ],
        "internship_experience": [{"company": "Example Lab", "role": "assistant"}],
        "target_location_or_company_if_any": "Shanghai AI internship",
    }

    result = run_python(
        RUN_CONTINUER,
        "--run-dir",
        str(run_dir),
        "--user-facts-json",
        json.dumps(facts),
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["continuation_response"]["run_id"] == run_id
    assert response["continuation_response"]["exit_status"] == "ready_for_dispatch"

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["execution_manifest"]["run_id"] == run_id
    assert manifest["execution_manifest"]["current_stage"] == "injection_ready"
    assert manifest["run_state"]["next_action"] == "dispatch_agents"
    assert manifest["run_state"]["blocked_agents"] == []

    context = json.loads(
        (run_dir / "input" / "normalized" / "runtime_context_packet.json").read_text(encoding="utf-8")
    )["runtime_context_packet"]
    assert context["school_context"]["school_name"] == "Example University"
    assert context["missing_user_owned_facts"] == []
    known_fields = {fact["field"] for fact in context["known_user_facts"]}
    assert {"school_name", "degree_level", "graduation_window"}.issubset(known_fields)


def test_simulator_supports_resume_generation_route(tmp_path):
    result = run_python(
        SIMULATOR,
        "--task-type",
        "resume_generation",
        "--input-text",
        "computer science senior, Python, Java, resume generation",
        "--run-root",
        str(tmp_path / ".career-pipeline-runs"),
        "--route",
        "resume_generation",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    run_dir = tmp_path / ".career-pipeline-runs" / response["runner_response"]["run_id"]
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    agents = [
        Path(ref).name.replace(".invocation.json", "")
        for ref in manifest["execution_manifest"]["subagent_invocation_refs"]
    ]
    assert agents == [
        "major-cluster-classifier",
        "profile-extractor",
        "resume-format-gate",
        "resume-architect",
        "factual-reviewer",
        "hr-supervisor",
    ]


def test_prompt_bundle_builder_creates_subagent_ready_context(tmp_path):
    run_root = tmp_path / ".career-pipeline-runs"
    simulate = run_python(
        SIMULATOR,
        "--task-type",
        "job_search",
        "--input-text",
        "computer science sophomore, Python, looking for AI internship",
        "--run-root",
        str(run_root),
        "--route",
        "job_search",
    )
    assert simulate.returncode == 0, simulate.stderr
    run_id = json.loads(simulate.stdout)["runner_response"]["run_id"]
    run_dir = run_root / run_id
    invocation_ref = "invocations/job-scout.invocation.json"

    result = run_python(PROMPT_BUNDLE_BUILDER, "--run-dir", str(run_dir), "--invocation-ref", invocation_ref)

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    bundle_ref = response["prompt_bundle_response"]["prompt_bundle_ref"]
    bundle_path = run_dir / bundle_ref
    assert bundle_path.is_file()
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))["subagent_prompt_bundle"]
    assert bundle["target_agent"] == "job-scout"
    assert bundle["invocation_ref"] == invocation_ref
    assert bundle["base_prompt_ref"] == ".codex/agents/job-scout.toml"
    assert bundle["runtime_context_packet_ref"] == "input/normalized/runtime_context_packet.json"
    assert bundle["secondary_prompt_injection_ref"] == "injections/job-scout.secondary_prompt_injection.json"
    assert "static_role_prompt" in bundle["prompt_sections"]
    assert "runtime_context_packet" in bundle["prompt_sections"]
    assert "secondary_prompt_injection" in bundle["prompt_sections"]
    assert "source_policy" in bundle["prompt_sections"]
    assert "required_output_contract" in bundle["prompt_sections"]
    assert "role_output_packet" in bundle["required_output_fields"]
    assert "error_recovery_state" in bundle["required_output_fields"]
    assert "input/raw_refs.json" not in json.dumps(bundle, ensure_ascii=False)


def test_plan_builder_attaches_prompt_bundle_refs(tmp_path):
    run_root = tmp_path / ".career-pipeline-runs"
    simulate = run_python(
        SIMULATOR,
        "--task-type",
        "job_search",
        "--input-text",
        "computer science sophomore, Python, looking for AI internship",
        "--run-root",
        str(run_root),
        "--route",
        "job_search",
    )
    assert simulate.returncode == 0, simulate.stderr
    run_id = json.loads(simulate.stdout)["runner_response"]["run_id"]
    run_dir = run_root / run_id

    result = run_python(PLAN_BUILDER, "--run-dir", str(run_dir), "--build-prompt-bundles")

    assert result.returncode == 0, result.stderr
    plan_ref = json.loads(result.stdout)["planner_response"]["subagent_plan_ref"]
    plan = json.loads((run_dir / plan_ref).read_text(encoding="utf-8"))["subagent_invocation_plan"]
    first = plan["dispatch_queue"][0]
    assert first["prompt_bundle_ref"].startswith("prompts/")
    assert (run_dir / first["prompt_bundle_ref"]).is_file()
    validation = run_python(VALIDATOR, "--subagent-plan", str(run_dir / plan_ref))
    assert validation.returncode == 0, validation.stderr


def test_public_source_plan_builder_creates_policy_bound_tasks(tmp_path):
    run_root = tmp_path / ".career-pipeline-runs"
    simulate = run_python(
        SIMULATOR,
        "--task-type",
        "job_search",
        "--input-text",
        "computer science sophomore, Python, looking for AI internship at ByteDance or DJI",
        "--run-root",
        str(run_root),
        "--route",
        "job_search",
    )
    assert simulate.returncode == 0, simulate.stderr
    run_id = json.loads(simulate.stdout)["runner_response"]["run_id"]
    run_dir = run_root / run_id

    result = run_python(SOURCE_PLAN_BUILDER, "--run-dir", str(run_dir))

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    source_plan_ref = response["source_plan_response"]["source_plan_ref"]
    source_plan = json.loads((run_dir / source_plan_ref).read_text(encoding="utf-8"))[
        "public_source_research_plan"
    ]
    assert source_plan["run_id"] == run_id
    assert source_plan["policy_ref"] == ".agents/skills/career-pipeline/references/source-policy.md"
    assert source_plan["network_execution_default"] == "disabled_until_human_and_source_policy_ack"
    source_types = {task["source_type"] for task in source_plan["research_tasks"]}
    assert "official_or_primary" in source_types
    assert "recruitment_platform_jd" in source_types
    assert "verified_hr_public_post" in source_types
    assert "social_media_weak" in source_types
    assert all(task["allowed"] is True for task in source_plan["research_tasks"])
    assert source_plan["blocked_source_types"]


def test_source_policy_validator_rejects_login_only_and_private_sources(tmp_path):
    source_plan = {
        "public_source_research_plan": {
            "run_id": "run-test",
            "policy_ref": ".agents/skills/career-pipeline/references/source-policy.md",
            "network_execution_default": "disabled_until_human_and_source_policy_ack",
            "research_tasks": [
                {
                    "task_id": "bad-private-resume",
                    "agent": "job-scout",
                    "claim_field": "candidate_condition",
                    "source_type": "private_resume",
                    "source_priority": 0,
                    "allowed": True,
                    "requires_login": False,
                    "may_set_weight": True,
                    "may_set_final_decision": True,
                    "evidence_strength_floor": "strong",
                    "privacy_action": "none",
                    "query_template": "collect private resumes",
                    "output_fields": ["weight_provenance"],
                },
                {
                    "task_id": "bad-login",
                    "agent": "job-scout",
                    "claim_field": "jd_requirement",
                    "source_type": "recruitment_platform_jd",
                    "source_priority": 3,
                    "allowed": True,
                    "requires_login": True,
                    "may_set_weight": True,
                    "may_set_final_decision": True,
                    "evidence_strength_floor": "medium",
                    "privacy_action": "cache_metadata_only",
                    "query_template": "crawl login-only JD",
                    "output_fields": ["evidence_basis"],
                },
            ],
            "blocked_source_types": [],
        }
    }
    plan_path = tmp_path / "bad-source-plan.json"
    plan_path.write_text(json.dumps(source_plan), encoding="utf-8")

    result = run_python(VALIDATOR, "--source-plan", str(plan_path))

    assert result.returncode == 1
    assert "private_resume" in result.stderr
    assert "requires_login" in result.stderr


def test_source_policy_validator_rejects_weak_social_media_as_final_basis(tmp_path):
    source_plan = {
        "public_source_research_plan": {
            "run_id": "run-test",
            "policy_ref": ".agents/skills/career-pipeline/references/source-policy.md",
            "network_execution_default": "disabled_until_human_and_source_policy_ack",
            "research_tasks": [
                {
                    "task_id": "weak-social",
                    "agent": "market-sentiment-analyzer",
                    "claim_field": "company_reputation",
                    "source_type": "social_media_weak",
                    "source_priority": 5,
                    "allowed": True,
                    "requires_login": False,
                    "may_set_weight": True,
                    "may_set_final_decision": True,
                    "evidence_strength_floor": "weak",
                    "privacy_action": "aggregate_deidentified_only",
                    "query_template": "single anonymous post",
                    "output_fields": ["weight_provenance"],
                }
            ],
            "blocked_source_types": [],
        }
    }
    plan_path = tmp_path / "weak-source-plan.json"
    plan_path.write_text(json.dumps(source_plan), encoding="utf-8")

    result = run_python(VALIDATOR, "--source-plan", str(plan_path))

    assert result.returncode == 1
    assert "social_media_weak" in result.stderr
    assert "final" in result.stderr.lower()
