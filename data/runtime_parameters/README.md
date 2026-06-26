# Runtime Parameters

This directory defines which information should come from the user, which information should be researched by local subagents, and which weights should be set at runtime.

Core rule: this repository does not hard-code concrete skill requirements or external-display requirements for every discipline. It provides schemas, evidence rules, and routing contracts. User-deployed subagents investigate current role/company/discipline signals on the user's device and then set weights for skills, external assets, school signals, and application strategy.

Use `parameter_ownership.zh-CN.json` before asking the user follow-up questions. Ask for user-owned facts once in a compact batch, and do not ask the user to manually provide information that local subagents can obtain from allowed public sources.
