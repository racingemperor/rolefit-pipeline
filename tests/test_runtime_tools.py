import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / ".agents" / "skills" / "career-pipeline" / "scripts" / "validate_runtime_contracts.py"
SIMULATOR = ROOT / ".agents" / "skills" / "career-pipeline" / "scripts" / "simulate_runtime_run.py"
PLAN_BUILDER = ROOT / ".agents" / "skills" / "career-pipeline" / "scripts" / "build_subagent_plan.py"


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
