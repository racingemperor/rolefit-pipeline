# Reference Repo Gap Analysis

This note compares Career Pipeline with two related public repositories:

- `LiuMengxuan04/shushu-internship-tool`
- `lishuangqiang/backend-agent-resume-scout`

The goal is not to copy their workflows. The useful pattern is: turn target role evidence into a concrete project, then turn that project into resume evidence and interview preparation.

## What They Do Well

`shushu-internship-tool` is strong at JD-to-project execution:

- turns a JD into 2-3 project candidates;
- scores projects by JD match, onboarding speed, resume value, interview depth, running cost, and modification space;
- plans different run depths such as interview-only, smoke-test, local full run, and remote full run;
- audits project structure, entrypoints, dependencies, API/data/task flows;
- produces modification playbooks and interview packs.

`backend-agent-resume-scout` is strong at project quality control:

- builds a diversified GitHub/Web candidate pool;
- avoids shallow demos, thin LLM wrappers, simple CRUD, browser plugins, and star-count traps;
- verifies local source code before final project claims;
- separates existing project capability, suggested modifications, and resume-ready content;
- outputs project resume packs with project positioning, evidence summary, responsibility bullets, modification plan, and interview questions.

## Gaps In Career Pipeline Before This Update

- Learning guidance was too broad when the user lacked projects.
- Project suggestions were not required to include implementation steps, proof artifacts, and resume-conversion conditions.
- HR questions could be interpreted as model-generated interview guesses instead of company-bound public HR/recruiter signals.
- Final output had a learning/project section, but not a clear project recommendation package.
- The source plan did not explicitly include company-bound HR real-question collection.

## Added In This Update

- `LearningPathStrategist` now requires concrete `project_recommendations`.
- Project recommendations include role fit, recommended project mode, implementation steps, proof artifacts, resume-conversion conditions, and interview-defensibility questions.
- Planned projects are explicitly blocked from becoming completed resume claims.
- `HRSupervisor` now requires company-bound `hr_real_question_bank` and `likely_interview_questions`.
- HR wording must come from the target company or recommended company public sources. If not found, it must be marked unavailable.
- Candidate experience and social media are limited to preparation notes.
- The final user-facing report now includes `HR/面试可能追问` and renders concrete project suggestions.
- Added MVP project scripts:
  - `discover_project_candidates.py` for candidate scoring and shallow-project filtering.
  - `audit_project_repository.py` for local source evidence audit.
  - `build_project_interview_pack.py` for project positioning, existing capability, suggested modifications, resume-ready claims, STAR bullets, interviewer follow-ups, and code explanation paths.

## Still Not Fully Productized

- The project recommendation system does not yet run live GitHub/Gitee search by default; candidates must come from a search adapter, JSON candidate pool, or user-side subagent.
- The project recommendation system does not yet clone public repositories by default.
- There is no generated project resume pack PDF.
- GitHub project discovery is still delegated to user-side public source search or subagents, then passed into `discover_project_candidates.py`.
- Non-engineering project recommendation rubrics are still reserved for later discipline expansion.

## Future Enhancements

- Add an optional project-discovery role that searches GitHub/Gitee and public tutorials by target role family.
- Add a clone/fetch script that writes a source manifest and gates final project recommendations on clone success.
- Expand the project audit script to check entrypoints, runnable commands, and smoke-test logs.
- Add a source-code evidence rule before writing project responsibility bullets.
- Add a resume project pack template for one project, including project intro, personal contribution, technical difficulty, proof artifacts, and interview Q&A.
