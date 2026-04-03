# Codex Prompt — FixHub Workflow Truth

Read `AGENTS.md` and `spec/core.md` first.

Your task is to make the workflow and lifecycle logic more truthful to the real-world coordination process FixHub is intended to represent.

Focus on:
- making state changes correspond more closely to meaningful actions
- reducing silent or misleading mutations
- improving the relationship between events, job state, and visible progress
- making the operational timeline more trustworthy
- preserving usability for a realistic first pilot

You may change relevant workflow, service, schema, route, and test code needed to make the workflow model more coherent.

## Guardrails

- Keep the product centered on coordination across actors, not generic internal task tracking.
- Prefer explicit operational history over hidden mutable state.
- Do not introduce broad new subsystems unless clearly necessary.
- Do not turn the repo into a general-purpose workflow engine.
- Keep resident, staff, and contractor interactions legible and grounded in realistic use.

## Deliverable

Move the workflow closer to a real coordination layer.

After making changes:
1. run relevant tests
2. repair anything broken
3. describe how the workflow is now closer to a truthful coordination model
4. identify remaining false assumptions in the repo