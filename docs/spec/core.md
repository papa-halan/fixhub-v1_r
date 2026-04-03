# FixHub Core Objective and Guardrails

FixHub is being built toward one goal:

A coordination platform for civil works that becomes the shared source of truth for what is happening across a physical job.

The long-term objective is not to build a generic maintenance app, ticketing tool, or internal asset management system. The objective is to build an external coordination layer for physical infrastructure work.

## Product thesis

Every civil job involves multiple actors, partial information, weak visibility, and coordination failures across organisational boundaries.

FixHub should solve this by making each job a truthful, auditable, structured timeline of actions tied to a real location and visible to the right participants.

The product should evolve toward:
- shared truth across residents, contractors, staff, and organisations
- accountability for who did what and when
- reduced ambiguity and repeated contact
- a persistent operational record that can later support governance, analytics, and broader infrastructure coordination

## First practical wedge

The immediate wedge is recurring maintenance coordination in a constrained environment such as university residences.

That wedge is only a starting environment. The broader objective remains a coordination layer for civil works in general.

## What matters most

When making decisions, optimise for:
1. truthfulness of the operational record
2. clarity of actor and location relationships
3. low-friction updates from real participants
4. trustworthy progress visibility
5. future expansion into broader civil coordination without requiring the first version to model everything

## Architectural direction

The platform should move toward:
- event-backed job history
- structured location references
- clear actor roles
- lifecycle state derived from meaningful actions
- minimal ambiguity between what happened and what the system claims happened

## Development rule

Prefer decisions that make FixHub more like a real coordination layer and less like a generic CRUD app.

When forced to choose, prefer:
- truth over convenience
- coherence over feature count
- realistic workflows over demo features
- a smaller but more correct wedge over a broader but less truthful system

## Allowed scope for autonomous work

Autonomous changes may:
- refactor existing models, services, schemas, routes, and tests
- add helpers, migrations, and focused modules
- remove clearly misleading demo or legacy code
- simplify lifecycle logic
- improve event-backed coordination behavior
- improve pilot realism

Autonomous changes should usually avoid:
- introducing many new top-level concepts at once
- broad UI redesigns
- speculative abstractions for future markets
- replacing the entire architecture in one pass
- deleting working auth or seed flows unless they clearly obstruct the real product

## Hard guardrails

Do not:
- convert the product into a generic asset management system
- turn the system into a generic kanban/task board
- weaken structured location handling in favor of free text
- treat mutable status as more authoritative than recorded operational history
- expand scope just because a broader platform might eventually need it
- preserve architectural incoherence simply to avoid refactoring

## Immediate objective

Bring the current codebase closer to a truthful FixHub core and a credible first pilot.

A change is good if it moves the repo closer to:
- a usable coordination layer for a constrained real environment
- a truthful job timeline
- clearer role and location relationships
- lower ambiguity in what happened and who did it
- a system that can later expand into broader civil works coordination