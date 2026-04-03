# Codex Prompt — FixHub Repo Correction

Read `AGENTS.md` and `spec/core.md` first.

Your task is to assess the current repository honestly and improve it in the direction of the real FixHub objective.

If parts of the repo are based on weak or misleading assumptions, you may simplify, refactor, replace, or remove them.

The objective is not to preserve the current codebase at all costs. The objective is to move toward a more truthful and feasible implementation of FixHub as a civil-works coordination platform.

## Priorities

Prioritise:
- coherence of the core model
- operational truth
- realistic coordination flows
- future extensibility toward broader civil works
- reduction of legacy/demo noise that obscures the real product

## Guardrails

- Prefer targeted correction over uncontrolled repo-wide reinvention.
- Keep what reflects real product truth.
- Remove what mainly reflects premature abstraction or incoherent legacy structure.
- Avoid replacing the entire architecture in one unattended pass.
- Preserve anything that already supports a credible pilot unless it directly conflicts with the product thesis.

## Deliverable

Improve the repo toward a truer FixHub core.

After making changes:
1. run relevant tests
2. address issues caused by your work
3. summarise what should be kept, what should be discarded, and why
4. describe the repo's current distance from the actual FixHub goal