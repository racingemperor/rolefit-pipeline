# Runtime Weight Engine

This protocol defines how user-side subagents may propose weights, scores, priorities, rankings, thresholds, and confidence adjustments.

## Core Rule

No role may set a concrete weight from intuition, repository examples, popularity assumptions, or model-only reasoning. Every weight must be supported by hard evidence from user-provided materials or current public/official sources. If evidence is missing, return `not_available` or `needs_more_sources`.

## Supported Weight Scopes

Start with these runtime weight scopes:

- `skill_weight`: importance of target skills, tools, methods, credentials, or project evidence.
- `external_asset_weight`: value of GitHub, personal website, portfolio, paper page, blog, demo, report, or public profile.
- `school_signal_weight`: value of school-company cooperation, campus recruiting, internship bases, employment reports, or alumni/employment signals.
- `application_strategy_weight`: priority for apply now, learn first, build evidence first, defer, or skip.
- `hr_screening_weight`: HR first-screen emphasis for clarity, credibility, competitiveness, and risk.

## Weight Object

Use this object whenever a role proposes or checks a weight:

```json
{
  "runtime_weight": {
    "parameter": "",
    "weight_scope": "skill_weight|external_asset_weight|school_signal_weight|application_strategy_weight|hr_screening_weight",
    "proposed_weight": null,
    "weight_unit": "0_to_1|percentage|rank|tier|qualitative",
    "weight_status": "verified|needs_more_sources|not_available",
    "evidence_basis": [],
    "source_count": 0,
    "source_mix": [],
    "freshness": "0_6_months|6_12_months|1_3_years|older|unknown",
    "conflict_notes": [],
    "confidence": "high|medium|low",
    "cannot_decide_alone": true,
    "runtime_research_tasks": []
  }
}
```

`runtime_weights` is the preferred merge format for new runtime decisions. Existing `weight_provenance` fields remain valid for backward compatibility and should reference the same evidence whenever both fields are present.

## Evidence Requirements

Valid support includes:

- current JD text supplied by the user or retrieved from a public page.
- official company career page, campus page, product/technology page, report, or public announcement.
- recruitment-platform public JD.
- verified HR public post.
- official school career center, college notice, employment report, or school-enterprise cooperation announcement.
- public report or multi-source market/candidate signal.
- user-provided materials.

Repository priors may seed research and suggest candidate dimensions, but cannot be the sole source of a final weight.

## Source Strength Rules

- official or primary sources can support strong weights when current and directly relevant.
- recruitment-platform public JDs can support role requirement weights.
- verified HR public posts can support screening preference weights when tied to company, role family, or recruitment season.
- multi-source candidate/interview signals can support medium-confidence trends.
- single anonymous social posts are weak signals only.
- stale sources lower confidence unless they describe stable background facts.

## Decision Rules

- Use `verified` only when evidence is current, relevant, and strong enough for the claimed scope.
- Use `needs_more_sources` when evidence exists but is weak, stale, single-source, or conflicting.
- Use `not_available` when no acceptable evidence exists.
- Set `cannot_decide_alone = true` for repository priors, single weak social posts, stale sources, model inference, or unresolved conflicts.
- Do not average conflicting evidence into a false precise score. Preserve `conflict_notes` and route to debate or research.

## Runtime Weight Handoff

When a role cannot verify a weight, it should output:

```json
{
  "runtime_research_tasks": [
    {
      "research_question": "",
      "target_sources": [],
      "required_freshness": "",
      "needed_for_outputs": []
    }
  ],
  "blocked_outputs": []
}
```

Downstream roles must not use missing weights for fit scores, application priority, resume tailoring, or personal-branding decisions.
