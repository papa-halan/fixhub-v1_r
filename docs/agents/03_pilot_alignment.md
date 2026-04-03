# Codex Prompt — FixHub Pilot Alignment

Read `AGENTS.md` and `spec/core.md` first.

Your task is to move the repository closer to a realistic first pilot while keeping it aligned with the long-term FixHub vision.

The pilot should demonstrate a truthful coordination loop in a constrained maintenance environment, not just a generic app demo.

Focus on:
- making the user flow more operationally realistic
- improving role interactions between resident, staff, and contractor
- reducing demo-only behavior that obscures the true product
- improving the visibility and usefulness of progress updates
- preserving or improving the system's ability to later expand into broader civil works coordination

You may modify any necessary part of the repository, but prefer focused product-coherent changes over broad rewrites.

## Guardrails

- Do not optimize for flashy breadth.
- Do not add speculative features for distant future markets.
- Do not destroy working flows merely to chase architectural purity.
- Keep the pilot grounded in a constrained environment with repeated jobs, real locations, and recurring coordination failures.

## Deliverable

Make the repo more pilot-ready without losing the FixHub thesis.

After making changes:
1. run relevant tests
2. fix failures caused by your changes
3. explain how the repo is now more pilot-ready
4. explain what still prevents a credible real-world trial