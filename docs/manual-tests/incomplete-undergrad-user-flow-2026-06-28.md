# Incomplete Undergraduate User Flow Test

Date: 2026-06-28

Scope: engineering-only Career Pipeline user-side flow.

This is a manual product-flow test, not an automated contract test. Use it to check whether a real user can start the Skill smoothly with incomplete information.

## Test User Input

```text
我现在是本科大三，专业和计算机有点相关，会 Python，也写过一点 Java。
做过一个课程项目，但是没有正式实习经历。
我想找一个暑期实习，方向还不确定，最好是互联网或者 AI 相关。
你帮我看看我适合投什么，以及简历怎么准备。
```

## Expected First Assistant Response

The first response should begin by introducing the Skill before asking for information:

```text
我是 Career Pipeline，一个面向求职和简历设计的 Codex Skill。我会根据你的专业、经历、目标岗位和公开招聘信息，帮你判断适合的岗位方向、补齐能力差距，并为不同岗位反向设计更贴合的简历；岗位建议会尽量附公开来源，简历内容只基于你能证明的真实经历。
```

Then it should summarize what is already known:

- undergraduate junior.
- engineering/computer-related major, exact major unknown.
- knows Python and some Java.
- has one course project.
- no formal internship.
- wants summer internship.
- interested in internet or AI, but no concrete target role.

Then it should state what can be done now:

- classify broad engineering/computer-related directions.
- suggest exploration role families such as backend intern, data/AI application intern, test/development intern, campus/local software intern, or small-company engineering intern.
- propose a learning and proof-artifact path before applying to AI-heavy roles.
- provide broad campus resume preparation advice.

Then it should state what cannot be done yet:

- exact fit score.
- final application priority.
- company-specific resume tailoring.
- apply-now recommendation.
- concrete recommended application target without public URL evidence.

Then it should ask one compact batch of user-owned facts:

```text
为了做得更准，请你能补多少就补多少：
1. 学校、具体专业、学历、预计毕业时间。
2. 课程项目做了什么：技术栈、你的职责、是否有代码/GitHub/文档/演示。
3. Python/Java 掌握程度：能否独立写后端、数据处理、爬虫、模型调用或脚本工具。
4. 城市、暑期实习时间、是否接受中小厂/地方企业/线下到岗。
5. 如果有目标岗位或 JD，请发公开链接；没有也可以，我会先按方向探索。
```

## Expected Source Behavior

For job discovery, JobScout should not limit the search to major companies.

It should prepare public-source tasks for:

- major companies and official career pages.
- small/mid-size companies and startups with public JDs.
- school career center notices.
- local/regional employer official pages.
- local public talent-service pages.
- industrial-park, incubator, or high-tech-zone internship notices.
- public recruitment-platform JDs that do not require login.

It must not use:

- login-only pages.
- screenshots.
- private HR messages.
- private candidate profiles.
- single anonymous social posts as recommendation evidence.

## Expected Planning Result After User Adds Details

When the user provides more facts, the pipeline should produce a concise package:

1. Positioning conclusion.
2. 2-4 suitable role families, not just one job.
3. Public URL targets or exploration URLs.
4. Current evidence strengths.
5. Learnable gaps.
6. Projects or artifacts to build before applying.
7. Resume direction for each role family.
8. `ask_hr_about` items for missing operational details.
9. Next three actions.

## Failure Signals

Treat these as product-flow bugs:

- Starts by asking a long questionnaire without introducing the Skill.
- Asks the user to find job sites that local subagents should search.
- Recommends only big companies when the user has no strong target.
- Ignores small/mid-size companies, school-local opportunities, and local internships.
- Gives exact fit score without current JD/public evidence.
- Writes planned learning as completed resume skill.
- Suggests an AI role but gives no learning path or proof-artifact plan.
- Gives concrete application targets without public URLs.
- Exposes internal fields such as `blocked_outputs`, run directories, schemas, or raw role packets.

## Current Feedback

The prompt framework is strong enough to guide this flow, but the next real test should check natural-language quality. The main remaining risk is not contract shape; it is whether the final user-facing answer feels like a professional career tool instead of an internal pipeline report.
