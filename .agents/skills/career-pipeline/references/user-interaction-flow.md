# User Interaction Flow

This protocol defines how the user-side pipeline should handle the user's first materials, missing facts, consent, and next-step messaging.

## Input Principle

The first user message is free-form. Do not force a questionnaire before normalization. Accept vague chats, pasted resumes, Markdown, PDF/DOCX, personal sites, GitHub/Gitee, portfolios, paper pages, JD text, JD links, target company names, target role names, or mixed materials.

## First User-Facing Message

When a real user starts the pipeline, the first assistant response must introduce the skill before asking for information. Keep it simple, professional, and complete enough for the user to understand why the skill is useful.

Use this default opening unless the user has already provided enough context:

```text
我是 Career Pipeline，一个面向求职和简历设计的 Codex Skill。我会根据你的专业、经历、目标岗位和公开招聘信息，帮你判断适合的岗位方向、补齐能力差距，并为不同岗位反向设计更贴合的简历；岗位建议会尽量附公开来源，简历内容只基于你能证明的真实经历。

为了开始，请尽量一次性提供这些信息，能提供多少就先发多少：
1. 学校、专业、学历、年级或毕业时间。
2. 目标：实习、校招、全职、考研/转方向，或暂时不确定。
3. 已有经历：项目、实习、竞赛、科研、课程、技能、证书、作品链接、GitHub/Gitee/个人网站。
4. 偏好和限制：城市、行业、岗位方向、公司规模、时间安排、薪资或稳定性偏好。
5. 如果已有目标岗位，请发 JD 文本或公开链接。
```

Do not make the opening sound like a marketing landing page. The goal is to orient the user, then collect one compact batch of user-owned facts.

## Interaction Flow

```text
first user materials
  -> InputNormalizer extracts first_round_user_profile
  -> summarize known information
  -> explain next_possible_actions
  -> identify blocked outputs
  -> ask one compact batch of missing user-owned facts only when needed
  -> proceed with provided facts or request incomplete-resume consent
```

## Interaction State

User-facing stages should expose:

```json
{
  "user_interaction_state": {
    "interaction_mode": "resume_only|direction_analysis|targeted_application|learning_plan|personal_branding|unknown",
    "information_completeness": "sufficient|partial|insufficient",
    "user_followup_policy": "one_round_only",
    "known_information_summary": "",
    "next_possible_actions": [],
    "missing_user_owned_facts": [],
    "subagent_research_not_asked_from_user": [],
    "incomplete_resume_consent_required": false,
    "incomplete_resume_allowed": false,
    "application_direction_allowed": false,
    "blocked_outputs": [],
    "one_round_followup_prompt": ""
  }
}
```

## One-Round Question Policy

Ask only for facts the user owns and that cannot be extracted from provided materials:

- school, major, degree, grade, graduation window.
- internship/full-time/campus/social recruitment goal.
- target role, target company, target city when the task requires them.
- key projects, internships, competitions, research, coursework, or links.
- final resume contact fields only when drafting a resume and only with consent.

Do not ask the user to manually provide information local subagents can research from public/official sources, such as company development, school-company cooperation, current JD patterns, HR public posts, or market sentiment.

Group missing facts into one compact prompt and allow partial answers.

## Default User-Facing Decisions

- If the user gives only a vague profile, return known facts, missing facts, and what can be done next; do not recommend application direction.
- If the user gives a resume but no target role/company, default to broad campus-recruitment resume review/generation.
- If the user gives a JD or target company, allow safe targeted framing, prepare-first learning paths, exploration targets, and public URL recommendations from available evidence. Exact fit scores, final application priority, apply-now decisions, company-specific weights, targeted resume tailoring, and final ready-to-apply claims still require stronger current JD/company evidence plus user evidence.
- If a public JD or application page lacks opening status, city, onsite days, arrival time, deadline, headcount, or internship duration, put those items in `ask_hr_about` rather than asking the user to supply recruitment-site details.
- If the user is non-graduating, split current internship analysis from future full-time preparation.
- If the user refuses missing facts, ask for explicit consent before an incomplete resume draft.
- If incomplete-resume consent is granted, draft only sections supported by facts; omit missing sections and block application direction recommendations.

## Consent And Privacy

- Redact private contact details in intermediate outputs by default.
- Include phone/email only in final resume drafts when the user explicitly provides and authorizes them.
- Do not store or expose private resumes, private chats, IDs, addresses, non-public HR information, or non-public candidate data.
- When a user provides links or files, record them as user-provided evidence and preserve source notes.

## User-Facing Response Shape

Before specialist work, the pipeline should be able to tell the user:

```text
我已整理出的信息：
- ...

现在可以先做：
- ...

暂时不能做：
- ...

如果你愿意，请一次性补充这些能提供的内容：
- ...
```

Keep this message concise. The goal is to reduce repeated questioning while making the next step clear.
