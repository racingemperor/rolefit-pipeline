# Codex Career Pipeline

**Codex-native career planning and resume design skill for Chinese early-career candidates.**

This repository contains a Codex Skill that helps users move from an incomplete self-introduction to a role-specific application plan: public job evidence, fit analysis, learning gaps, personal branding, and a resume designed backward from the target role.

Current planning scope is **engineering majors and engineering-adjacent backgrounds**. Other disciplines are reserved in the taxonomy and prompt framework, but engineering is the first usable MVP.

[Skill Entry](.agents/skills/career-pipeline/SKILL.md) | [Real User Flow](.agents/skills/career-pipeline/references/real-user-deployment-and-use-flow.md) | [Source Policy](.agents/skills/career-pipeline/references/source-policy.md) | [Archived Old README](docs/archive/README.legacy-2026-06-27.md)

## News

- 2026-06-27: Added public-source recovery rules for login walls, CAPTCHA pages, app-only pages, and dynamic JavaScript shells.
- 2026-06-27: Added limited final-package support for `prepare-first` outputs when exact fit score, final priority, or company-specific tailoring is not yet supported by evidence.
- 2026-06-27: Added Codex Desktop built-in subagent adapter protocol for batched role execution.

## What It Does

Career Pipeline is not a generic resume beautifier. It is designed around one principle:

> **One role, one resume. Start from the target role, then design the candidate presentation backward.**

The skill can help with:

- **Personalized career positioning**: classify the user's major, stage, strengths, constraints, and possible engineering job families.
- **Target-job fit analysis**: compare the user's current evidence with a concrete internship or full-time role.
- **Learning-first planning**: when the user is not ready, propose skills, projects, proof artifacts, and resume-conversion conditions before applying.
- **Role-specific resume strategy**: design a resume around one company or one role family instead of producing a broad, generic resume.
- **Personal branding**: decide whether GitHub, Gitee, personal website, portfolio, paper page, project demo, blog, or other assets matter for the target direction.
- **Public-source job research**: use official career pages, school notices, public JDs, verified HR public posts, reports, local employer sources, small/mid-size company sources, school-local internship notices, and weak social signals with explicit confidence levels.
- **HR-supervised output**: keep the final advice concise, credible, and easy for a recruiter to scan.

## Core Idea

Most resume tools start from "what the user already has." This skill starts from:

1. what the target role screens for;
2. what the target company or comparable companies value;
3. what the user can prove today;
4. what the user can realistically learn or build next;
5. how to express only truthful, interview-defensible evidence in the resume.

The result should be a compact decision package:

- recommended application targets with real public URLs;
- current fit and risks;
- missing skills and concrete learning path;
- proof artifacts to build before applying;
- one-role resume outline or draft;
- HR confirmation items such as city, deadline, headcount, or internship duration when the public page is silent.

The job pool should not be limited to big tech. When the user has no precise target, the skill should consider major companies, small/mid-size companies, startups, local/regional employers, school-recommended internships, industrial-park or incubator employers, and local public internship channels when public evidence exists.

## Pipeline

```text
User Input
  -> InputNormalizer
  -> CareerOrchestrator
  -> MajorClusterClassifier
  -> ProfileExtractor
  -> JDAnalyzer
  -> JobScout
  -> CompanyIntelligenceAnalyst
  -> MarketSentimentAnalyzer
  -> MatchStrategist
  -> LearningPathStrategist
  -> PersonalBrandingStrategist
  -> HRSupervisor
  -> ResumeFormatGate
  -> ResumeArchitect
  -> FactualReviewer
  -> HRSupervisor
  -> Final Decision Package
```

Subagents are dispatched in batches and pass artifacts forward. Completed subagents can be closed; their information is preserved in local JSON artifacts, not in chat memory.

## Key Features

### Role-Specific Resume Design

The resume is not written as a universal document. The pipeline first analyzes the target role, then decides:

- which experiences should be foregrounded;
- which skills should be treated as must-have evidence;
- which projects should be reframed;
- which weak or unsupported claims must be removed;
- which version to generate: broad campus resume, target-company resume, target-role resume, internship resume, or incomplete resume with user consent.

### Learning Before Applying

If a user has useful foundations but is missing a key direction, the skill does not simply reject the target. It can produce a `prepare-first` plan:

- skills to learn;
- projects to build;
- public proof artifacts to create;
- when the new work can truthfully enter the resume;
- what to apply to now versus what to delay.

Example: a student with Python and Java but weak LLM knowledge can be guided toward AI application projects, RAG/Agent basics, evaluation artifacts, and resume bullets only after those artifacts exist.

### Public Evidence And Source Accuracy

Every job or internship recommendation shown to the user must include an inspectable public URL. Sources are ranked:

| Tier | Sources | Can Support |
|---|---|---|
| A | Official JD, official career/campus page, school official notice, user original material | Strong claims, job requirements, school signals, weights |
| B | Public recruitment-platform JD, verified HR public post, credible public report | Role/company signals with recency limits |
| C | Candidate experience, offer review, public referral, multi-source social consensus | Preparation notes and risk signals only |
| D | Login wall, CAPTCHA, app-only/private/backend page, screenshot-only claim, JavaScript shell without public rendered text | Not usable evidence |

If a source hits a login wall, CAPTCHA, app-only page, or dynamic shell, the pipeline should automatically search for a public replacement. It must not ask the user to log in, paste private screenshots, or bypass platform controls.

### HR And Factual Review

`HRSupervisor` checks whether the output is recruiter-readable:

- target role is clear;
- strongest 2-4 competitive signals are visible;
- evidence chain is credible;
- recommendation has public URLs;
- company or big-tech priors do not override current JD evidence.

`FactualReviewer` blocks fake or overclaimed resume content:

- no invented education, awards, projects, papers, metrics, internships, or ownership;
- no planned learning written as completed skill;
- no private or non-public data leakage;
- no weak social source used as a final application basis.

## Repository Layout

```text
.agents/skills/career-pipeline/
  SKILL.md                         # Main Codex Skill entry
  references/                      # Runtime, source, URL, adapter, and user-flow policies
  scripts/                         # Contract validation, simulation, source, and adapter helpers

.codex/agents/
  *.toml                           # Role prompt frameworks for local subagents

data/
  discipline_taxonomy/             # Discipline routing; future non-engineering expansion
  major_taxonomy/                  # Engineering major and employment-cluster database
  company_signals/                 # Company priors, source targets, official entrypoints
  runtime_parameters/              # User-owned vs subagent-researched parameters
  school_signals/                  # School-company signal policy
  resume_formats/                  # Resume section and format rules

tests/
  test_runtime_tools.py            # Runtime contract and prompt-policy regression tests

docs/archive/
  README.legacy-2026-06-27.md      # Previous detailed README preserved for reference
```

## Quick Start

Clone the repository and open Codex in the repo root. The Skill entry is repo-scoped:

```text
.agents/skills/career-pipeline/SKILL.md
```

A user can invoke it naturally:

```text
Use the career-pipeline skill.
我是软件工程大三，本科，做过一个 Java 后端项目和一个 Python 数据分析项目。
我想找互联网后端或 AI 应用实习，但还不确定投哪个公司。
请帮我规划岗位方向、需要补什么能力、简历应该怎么设计。
```

For a target role:

```text
Use the career-pipeline skill.
我是自动化研一，会 C++、ROS、Python，有机器人竞赛经历。
目标是大疆机器人/控制算法实习。请判断现在适不适合投，
如果不适合，告诉我先补什么项目和技能，再设计一版更贴合这个岗位的简历。
```

## Contract Smoke Run

This command checks local wiring only. It does not call real subagents and does not browse live recruitment sites:

```bash
cd .agents/skills/career-pipeline
python scripts/career_pipeline_run.py --task-type target_job_fit --route target_job_fit --input-text "computer science senior, assess fit for Tencent backend role. JD: Java and MySQL" --run-root ../../../.career-pipeline-runs --source-adapter seed --subagent-adapter mock-blocked
```

Expected behavior:

- `mock-blocked` produces schema-valid blocked role outputs.
- `real_subagent_execution = false`.
- `.career-pipeline-runs/<run_id>/` stores local artifacts.
- The `seed` source adapter is deterministic and local, not fresh web evidence.

Run verification:

```bash
python .agents/skills/career-pipeline/scripts/validate_runtime_contracts.py --repo-root .
pytest -q
```

## Real User-Side Execution

For real output in Codex Desktop, prefer the **Codex Desktop built-in subagent adapter** when current-session `multi_agent_v1.spawn_agent` is available.

High-level flow:

1. Normalize the user's first-round profile.
2. Build a runtime context packet and secondary prompt injections.
3. Generate subagent work orders.
4. Search public sources from the source matrix.
5. Dispatch role subagents by batch.
6. Persist strict JSON role outputs.
7. Run HR and factual review gates.
8. Return a final or degraded decision package.

See:

- [Codex Desktop Subagent Adapter](.agents/skills/career-pipeline/references/codex-desktop-subagent-adapter.md)
- [Manual Controller Runtime Flow](.agents/skills/career-pipeline/references/manual-controller-runtime-flow.md)
- [Runtime Network And Adapter Setup](.agents/skills/career-pipeline/references/runtime-network-and-adapter-setup.md)

## Output Style

The final user-facing answer should be professional and compact:

```text
1. Positioning conclusion
2. Recommended targets with public URLs
3. Why these targets fit
4. Gaps to fix before application
5. Resume design direction
6. ask_hr_about confirmation items
7. Next three actions
```

If public evidence is incomplete, the output should still give safe planning advice, but exact fit score, final application priority, apply-now decision, company-specific skill weights, and targeted resume tailoring remain unavailable until evidence supports them.

If a JD or URL does not state opening status, freshness, city, work location, onsite days, arrival time, deadline, headcount, or internship duration, do not block the recommendation only for that reason. Add those fields to `ask_hr_about` and tell the user to confirm with HR or the recruiter.

## Current Status

Implemented:

- Codex Skill entry and role prompt frameworks.
- Engineering major taxonomy and employment clusters.
- Company, school, runtime-parameter, and resume-format seed databases.
- Public-source policy, URL policy, local/small-company source coverage, access-wall recovery, and accuracy tiers.
- Deterministic local simulation and contract validation scripts.
- Batched subagent work-order protocol.
- Manual Controller MVP and Codex Desktop adapter documentation.

Not yet packaged:

- No `.codex-plugin/plugin.json` yet.
- No marketplace-style plugin distribution yet.
- Real live recruitment search depends on the user's Codex environment and adapter path.

## Roadmap

- Productize the repo-scoped Skill into a Codex plugin after the user-side workflow stabilizes.
- Add stronger real-source adapters for public JD and official career-page discovery.
- Add DOCX/LaTeX/Markdown resume rendering.
- Expand beyond engineering into science, humanities, social science, business, arts/design, medicine, agriculture, law/public affairs, and interdisciplinary users.
- Add interview preparation from the final resume and target JD.

## Safety Principles

- Do not fabricate experience.
- Do not scrape private resumes or candidate profiles.
- Do not bypass login, CAPTCHA, anti-scraping, or platform access controls.
- Do not treat social media as stronger than official JD evidence.
- Do not write planned learning as completed skill.
- Do not recommend a concrete application target without a public URL.

## Citation

This is currently a design and runtime-contract repository for a Codex-native Skill. If you use or extend it, cite the repository URL and the `career-pipeline` Skill entry.

## License

Add a license before public redistribution.
