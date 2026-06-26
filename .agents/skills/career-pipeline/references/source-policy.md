# Source Policy

Use this policy for job, company, HR, candidate, and social media information.

## Source Priority

1. Company official website, official career page, official campus page, official JD.
2. Verified HR public account or official-listed HR social account.
3. Public recruitment-platform JD, including BOSS, Lagou, Liepin, Nowcoder enterprise pages, LinkedIn, Indeed.
4. Candidate interview experience, offer review, public referral post, multi-source social media consensus.
5. Single anonymous post, screenshot, comment, or unverified rumor.

For school-company cooperation and campus channels, use this priority:

1. Official school career center, official employment report, official campus recruitment calendar.
2. Official college or department notice, internship-base announcement, school-enterprise cooperation announcement.
3. Official employer campus page or target-company school event page.
4. Public recruitment-platform campus event or public JD.
5. Candidate or social media signal.

School-specific advantages require priority 1-3 evidence. Candidate or social media signals can only support preparation notes.

## Conflict Handling

- Official JD and official career pages override social media claims.
- Verified HR public posts can clarify official process but should not override a current JD.
- Candidate experiences can inform preparation, interview risk, and hidden expectations, but cannot become company requirements alone.
- Social media signals need source type, date, platform, confidence, and whether identity is verified.
- When sources conflict, preserve the conflict and state which source is primary.
- Skill weights and external-display asset weights should be set from current JD/company/school/discipline evidence at runtime. Repository examples are priors, not requirements.
- If a local subagent can research a public or official source, do not ask the user to manually provide that source unless the user volunteers it.

## Privacy

Do not store or reveal:

- private resumes.
- private chat logs or screenshots.
- phone numbers, personal emails, IDs, addresses, WeChat IDs in intermediate reports, logs, or evidence databases.
- non-public HR/candidate information.
- details that identify a candidate without consent.

Allowed:

- public URL.
- paraphrased source summary.
- source type and confidence.
- de-identified aggregate candidate signal.
- user-authorized contact fields in the final resume draft only.

## Resume Truthfulness

Allowed:

- clarify structure.
- improve evidence order.
- translate real work into stronger professional language.
- mark claims that need user confirmation.
- generate an incomplete resume draft only after explicit user consent, omitting missing sections and blocking application direction recommendations.

Forbidden:

- invent education, awards, internships, projects, papers, users, metrics, or ownership.
- turn "participated" into "led" without evidence.
- describe unfinished learning as mastered skill.
- expose confidential project data.
