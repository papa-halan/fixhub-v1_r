# Codex Prompt — FixHub Foundation

Read `AGENTS.md` and `spec/core.md` first.

Your task is to improve the repository so it better reflects FixHub's real objective: becoming a coordination platform for civil works built around truthful shared operational records.

Focus on the highest-leverage foundational changes.

Prioritise:
- clarifying or strengthening the core data model
- making lifecycle handling more truthful
- improving event/history architecture
- reducing contradictions between what the code claims and what FixHub is meant to be
- preserving a realistic path toward a constrained pilot

You may inspect the repo broadly and make changes where necessary, but prefer targeted changes over repo-wide reinvention.

## Guardrails

- Preserve the product as an external coordination layer, not a generic AMS.
- Do not broaden the product into speculative platform features.
- Do not replace large parts of the repo unless they are clearly blocking the core objective.
- Prefer evolution toward a truthful event-backed core over wholesale redesign.
- Preserve working auth, seed, and location flows unless they clearly conflict with the FixHub objective.

## Deliverable

Make the best targeted foundational changes you can to move the repo closer to:
- truthful operational history
- coherent lifecycle handling
- clearer role/location relationships
- credible pilotability

After making changes:
1. run relevant tests
2. fix issues introduced by your work
3. summarise what changed
4. explain why it moves the repo closer to FixHub's actual goal
5. list remaining architectural tensions