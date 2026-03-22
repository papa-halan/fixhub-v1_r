# Research: Schema For Civil Workflow Digital Twins

Date: `2026-03-22 16:28:59 +11:00`

## Purpose

Assess how current civil workflow and digital twin systems structure their schema relations, then compare that to the current FixHub schema so the next model changes stay realistic for a solo-founder build.

## Current FixHub Baseline

The implemented FixHub core is an external-coordination workflow ledger built around:

- `Organisation -> Location -> Asset -> Job -> Event`
- `User -> Organisation`
- `Job -> assigned_org` or `Job -> assigned_contractor_user`
- `Event -> actor_user`, `actor_org`, `location`, and optional `asset`

That gives FixHub a credible Phase 0.5 coordination spine already:

- resident intake exists
- operations triage exists
- external contractor coordination exists
- completion and accountability history exists
- location and asset context exists, but remains lightweight

This is not yet a full digital twin. It is a workflow system with twin-ready primitives.

## What Current Systems Commonly Model

### 1. Enterprise maintenance systems center on request, work order, asset, and location

IBM describes work orders as maintenance documents containing the company, job location, assigned technician or service provider, expected and actual completion dates, and priority, with a lifecycle that starts from work request submission and evaluation before conversion into a work order. That confirms the common enterprise pattern is:

- `request -> evaluation -> work_order`
- `work_order -> location`
- `work_order -> asset`
- `work_order -> assigned provider`
- `work_order -> schedule / due date / priority`
- `work_order -> closure record`

FixHub already covers the last four in lightweight form, but it still collapses `request` and `work_order` into one `Job`.

### 2. Civil / built-environment twins center on spatial hierarchy first

buildingSMART IFC 4.3 keeps the spatial backbone explicit:

- `Project -> Site -> Facility -> FacilityPart -> Space`
- infrastructure variants such as `Road`, `Railway`, and `Bridge` fit the same composition model

This matters because the same relation pattern can support university housing now and civil coordination later. FixHub already has the right idea with `Location.parent_id` and typed locations. The main gap is not hierarchy itself; it is richer semantics around the hierarchy and external references later.

### 3. Digital twin products attach operational context to assets and spaces

Autodesk Tandem positions the twin as a place to keep maintenance data attached to assets and spaces, including manuals, warranties, install dates, and contextual navigation to the affected equipment. Bentley iTwin positions the twin as a single lens over BIM, reality, LiDAR, and IoT across engineering, construction, operations, and maintenance.

The pattern here is consistent:

- `asset -> space/location`
- `asset -> documents`
- `asset -> system`
- `issue/observation -> asset/location`
- `event/state -> timestamp`
- optional later links to telemetry, model objects, and reality capture

FixHub should copy only the first and fourth relations in the near term. The rest are later-stage twin enrichments.

### 4. University housing platforms stay workflow-first and configuration-heavy

StarRez Academy exposes maintenance and work orders, inspections, roommate and room workflows, custom fields, and data subscriptions. StarRez customer material also emphasizes custom fields and data subscriptions inside the resident portal stack.

That suggests the lower-end university baseline is usually:

- `resident/case reporter -> room/unit`
- `maintenance request -> room/unit`
- optional `inspection -> room/unit`
- configuration-heavy metadata rather than deep domain modeling

FixHub should not copy the configuration-heavy approach. Its advantage is structured external coordination, not becoming a giant configurable housing suite.

## Comparison Against Current FixHub Schema

### Relations that are already directionally correct

- `Organisation -> Location` is the right top-level containment model
- `Location -> parent Location` is the correct general-purpose hierarchy for campus now and civil domains later
- `Location -> Asset` is the correct lightweight anchor for reported equipment context
- `Job -> assigned_org | assigned_contractor_user` correctly reflects external coordination instead of internal-only dispatch
- `Event -> Job + actor + location + asset` is the right ledger pattern for accountability and handoff history

### Relations that are currently missing but are common in real systems

#### 1. `Request -> WorkOrder`

This is the most important missing relation.

Why it matters:

- residents report problems, not execution units
- staff may split one report into multiple contractor work packages
- civil coordination often needs one public-facing issue and several execution tracks

Why it is still solo-founder realistic:

- it is the smallest model split that materially improves external coordination
- it can be introduced without GIS, telemetry, or heavy asset governance

#### 2. `WorkOrder -> Visit`

This is the second most important missing relation.

Why it matters:

- scheduling is not the same as execution
- no-access, partial completion, quote required, return visit, and contractor attendance are all visit-level facts
- digital twin workflows need planned vs actual field movement before they need simulation

Why it is still realistic:

- a `Visit` table is much cheaper than a scheduling engine
- it gives FixHub structured field evidence without overbuilding

#### 3. `WorkOrder -> RoutingDecision` or `Job -> HandoffRecord`

Current events capture history, but structured routing is still thin.

Why it matters:

- external coordination needs explicit reasoned handoffs
- universities, councils, and civil owners all need to know why work was routed to internal staff, panel contractor, specialist, or follow-up inspection

Why it is realistic:

- this can be a small relation with reason code, from-party, to-party, and timestamp
- it directly strengthens the event spine instead of replacing it

## Relations FixHub Should Add Next

### Recommendation 1: Split the operational object into request and work order

Minimal relation set:

- `Request -> created_by resident/user`
- `Request -> organisation`
- `Request -> location`
- `Request -> asset (optional)`
- `Request -> many WorkOrders`
- `WorkOrder -> request`
- `WorkOrder -> assigned_org or assigned_contractor_user`

Why this is the right next step:

- it matches IBM-style maintenance flow
- it supports one resident report becoming multiple execution tracks
- it preserves FixHub's external coordination focus

### Recommendation 2: Add a first-class visit relation

Minimal relation set:

- `Visit -> work_order`
- `Visit -> assigned_org or assigned_contractor_user`
- `Visit -> location`
- `Visit -> asset (optional)`
- `Visit -> scheduled_window_start/end`
- `Visit -> actual_started_at/ended_at`
- `Visit -> outcome_code`

Why this is the right second step:

- it captures planned vs actual without needing a full twin stack
- it supports "attended but could not access", "quote only", "temporary fix", and "return required"
- it becomes the future anchor for mobile sync later

### Recommendation 3: Add structured handoff / routing relations

Minimal relation set:

- `RoutingDecision -> request or work_order`
- `RoutingDecision -> from_org/from_user`
- `RoutingDecision -> to_org/to_user`
- `RoutingDecision -> reason_code`
- `RoutingDecision -> decision_type`

Why this fits FixHub:

- external coordination is the product's novelty
- handoffs are more strategically important than inventory or preventive maintenance right now

## Relations FixHub Should Delay

These are real in mature digital twins, but they should stay out of the near-term schema:

- `Asset -> telemetry streams`
- `Asset -> condition / risk / lifecycle strategy`
- `Location/Asset -> BIM model element references`
- `WorkOrder -> inventory / parts / procurement`
- `WorkOrder -> crew / vehicle / toolbox / permit packs`
- `Network/System -> dependent systems graph`
- `Observation -> confidence / source freshness / tolerance`

Those relations are valid later, but they are not necessary for a solo founder proving external coordination in university maintenance.

## Minimal Civil-Trajectory Location Model

The current `Location` table can already stretch further than student living if the semantics stay generic:

- `organisation`
- `site`
- `building` or `facility_part`
- `space` or `unit`

For later civil domains, the same parent-child relation can represent:

- campus -> building -> room
- council area -> facility -> zone
- road corridor -> segment -> worksite
- utility service area -> asset cluster -> access point

The schema should therefore preserve one generic parent-child location tree instead of introducing domain-specific trees too early.

## Minimal Civil-Trajectory Asset Model

FixHub should keep `Asset` lightweight for now, but the next safe additions later are relational, not governance-heavy:

- `Asset -> organisation`
- `Asset -> location`
- `Asset -> external_ref` from source system
- `Asset -> asset_type` or classification

It should not jump yet to full EAM semantics such as depreciation, maintenance plans, spare parts, or risk modeling.

## Decision

If FixHub is constrained to realistic solo-founder scope, the most defensible schema path is:

1. keep the current event spine
2. split `Job` into `Request` and `WorkOrder`
3. add `Visit`
4. add structured routing / handoff records
5. only then add external references and broader twin-ready integration metadata

That path supports university maintenance immediately while preserving a credible trajectory to broader civil coordination without pretending FixHub is already Maximo, a GIS platform, or a full digital twin.

## Sources

- [IBM: What is a work order?](https://www.ibm.com/think/topics/work-order)
- [IBM: Maximo work order management](https://www.ibm.com/products/process-mining/integrations/work-order-management-maximo)
- [buildingSMART IFC 4.3: Spatial Composition](https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/concepts/Object_Composition/Aggregation/Spatial_Composition/content.html)
- [buildingSMART IFC 4.3: Spatial Decomposition](https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/concepts/Object_Composition/Aggregation/Spatial_Decomposition/content.html)
- [Autodesk Tandem: Twinning Autodesk](https://intandem.autodesk.com/resource/twinning-autodesk/)
- [Bentley iTwin overview](https://www.bentley.com/software/itwin/)
- [NIST: Essential Elements](https://www.nist.gov/digital-twins/essential-elements)
- [StarRez Academy](https://academy.starrez.com/)
- [StarRez customer story: Georgetown](https://www.starrez.com/customers/georgetown-university)
