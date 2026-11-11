---
name: ponytail-gain
description: >
  Measured impact of the ponytail skill across 39 benchmark tasks: 53% less
  code, 45% fewer tokens, 26% lower cost, 41% faster, same correctness.
  One-shot display. Use for "ponytail gain", "ponytail stats", "is ponytail
  working", /ponytail-gain.
---

# Ponytail Measured Gain

Display the benchmark scoreboard when invoked. One-shot, do NOT edit files,
run tests or change any mode.

## Data Source

Measured on 39 realistic engineering tasks (features, bug fixes, refactors,
small apps), 5 runs each, against the same agent without the skill. 18 of the
tasks have hidden checks for correctness and safety. Each figure is the geometric
mean of the per-task medians. They are measured, not computed from the current repo.
Source: `benchmarks/results/2026-10-07-agentic.md` and the README.

## Scoreboard

Render plain ASCII bars. The bar length shows ponytail as a share of the
no-skill baseline; the label carries the exact figure:

```
  ponytail gain           benchmark · 39 tasks × 5 runs · Opus 5.5

  no-skill        ████████████████████  100%
  Lines of code   █████████···········   47%   ▼ 53%
  Output tokens   ███████████·········   55%   ▼ 45%
  Cost            ███████████████·····   74%   ▼ 26%
  Time            ████████████········   59%   ▼ 41%
  Hidden checks passed   97%  (no-skill 96%)
  Tests where the logic needs one   98%  (no-skill 68%)

  This repo:  /ponytail-debt  (shortcuts you deferred)
              /ponytail-audit (what's still cuttable)
```

## Honesty boundary

These are benchmark averages, not this repo. NEVER print a per-repo savings
number ("you saved X lines/tokens here"): the unbuilt version was never
written, so there is no real baseline to subtract from in a live repo. The
only real per-repo figures come from `/ponytail-debt` (a counted ledger), and
this card points there instead of inventing one.

## Boundaries

One-shot display. Edits nothing, changes no mode.
