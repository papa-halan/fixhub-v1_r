# Research Log: UoN Student Living Maintenance Context

Last updated: `2026-03-22 19:11:47 +11:00`

## Document Metadata

- Owner: `uon-student-living-automation`
- Reviewer: `codex-research`
- Status: `active`

## Purpose

This append-only log captures how maintenance appears to move through The University of Newcastle's Student Living operation and how FixHub should map to that real workflow. Future runs should append new timestamped entries rather than replace prior findings.

## Document Rule

- never delete prior run entries
- append a new timestamped section for each automation run
- keep source links inline so the workflow evidence stays auditable

## Run Entry: `2026-03-22 17:40:31 +11:00`

### Research scope

Understand the current Student Living maintenance flow at the University of Newcastle, identify the actors involved, and translate that flow into FixHub's accountability-first event spine.

### Source set used in this run

- [Student Living guides and resources](https://www.newcastle.edu.au/campus-life/accommodation/on-campus-accommodation/resources)
- [2026 Callaghan New Resident Welcome Guide](https://www.newcastle.edu.au/__data/assets/pdf_file/0005/1104719/FINAL_2026-Welcome-Guide-New-Callaghan.pdf)
- [2026 Occupancy Licence Agreement - Terms and Conditions](https://www.newcastle.edu.au/__data/assets/pdf_file/0003/1082892/FINAL_2026-Student-OLA-Terms-and-Conditions.pdf)
- [2026 New Residents - Applications Guide](https://www.newcastle.edu.au/__data/assets/pdf_file/0010/843571/FINAL-2026-New-App-Guide-.pdf)
- [West Residence page](https://www.newcastle.edu.au/campus-life/accommodation/on-campus-accommodation/where-can-i-live/west-residence)
- [Why choose Student Living](https://www.newcastle.edu.au/campus-life/accommodation/on-campus-accommodation/why-choose-us)

### What the university sources show

The current official Student Living resource hub exposes a 2026 document set, with the key terms and conditions published on 9 September 2025, annexures published on 9-11 September 2025, and the Callaghan welcome guide published on 13 January 2026. That means the process evidence below is anchored in current-cycle 2026 Student Living material rather than older generic accommodation guidance.

The clearest resident-facing maintenance flow is documented in the 2026 Callaghan welcome guide:

1. The resident uses the Student Living Portal.
2. Under `Maintenance and Cleaning`, the resident selects `New Job`.
3. The resident enters `where`, `category`, `item`, and a note with the maintenance details.
4. The Student Living team receives the job request.
5. The Student Living team organises external contractors to inspect the issue.
6. Some jobs pause while parts are ordered or further planning is done.
7. Some minor replacement items are not field repairs at all; they are made ready for pickup from Student Living Reception.

The same guide also shows that maintenance can originate from another trigger. During check-in, the resident completes a room inventory/check-in inspection report in the Student Living Portal. If the resident disputes the recorded room condition, Student Living may clarify the issue and lodge a maintenance request on the resident's behalf. That matters because the real process has at least two request origins:

- resident-initiated request
- staff-initiated request arising from an inspection or condition dispute

The 2026 Occupancy Licence Agreement shows that maintenance is not only a portal workflow. The University and its authorised representatives, including Security and After Hours Duty Officers, may enter common areas without prior notice for emergency situations, cleaning, repairs and maintenance, and inspections. The same agreement also gives the University broad room-entry rights when necessary to protect property, resident wellbeing, or good order. This means the real workflow has an operational authority layer that sits beside the resident portal.

The agreement also shows an explicit after-hours path: if an issue is urgent and occurs outside normal office hours, the resident is expected to report it to Security or after-hours duty officers. The 2026 applications guide reinforces this by stating that After-Hours Duty Officers help with basics like lock-outs and emergency maintenance, while 24/7 security handles broader safety coverage.

Finally, the agreement and schedule of charges show that accountability is financially meaningful, not just operationally visible. UoN distinguishes normal maintenance from resident-responsible charges such as damage, lock-outs, lost keys, pest treatment non-compliance, and other misuse-related costs. That is a strong signal that any realistic digital workflow has to preserve cause, responsibility, and evidence at closure.

### Actor map inferred from the sources

| Real-world actor | Evidence from source set | Likely operational role in the maintenance flow | Current FixHub nearest role |
| --- | --- | --- | --- |
| Resident | portal `New Job`, inventory report, after-hours reporting obligation | reports issue, adds context, tracks outcome | `resident` |
| Student Living Reception / office | welcome guide and residence pages | front-door support, issue clarification, pickup point for minor items, office-hours contact surface | `reception_admin` |
| Student Living team | welcome guide says the team receives job requests | initial review, triage, coordination with contractors, resident communication | split across `triage_officer` and `coordinator` |
| Manager / authorised university representatives | occupancy agreement | authority to inspect, arrange access, protect property/order, supervise maintenance | `triage_officer` or `admin` |
| External contractors | welcome guide says Student Living organises external contractors | inspect, repair, revisit, complete work | `contractor` |
| Internal maintenance technician / maintenance team | implied by pickup flow and current FixHub role vocabulary | handles internal or simple fulfilment paths | `contractor` with `maintenance_team` mode |
| After-Hours Duty Officers (AHDOs) | applications guide and residence pages | after-hours support, emergency maintenance escalation, lock-outs | no clean first-class match; closest is `reception_admin` plus escalation metadata |
| Security | occupancy agreement and support material | emergency / urgent after-hours response and access authority | no clean first-class match; closest is escalation or admin-side event capture |
| Residential Mentor | applications guide | support and wayfinding, likely directs residents to the right channel rather than owning maintenance itself | note-only support actor, not first-class in current model |

### Workflow model inferred from the sources

#### Normal-hours path

1. Resident identifies an issue in a room, shared apartment, building area, or common area.
2. Resident logs the issue through the Student Living Portal as a maintenance `New Job`, providing location and descriptive detail.
3. Student Living receives the request and decides whether it needs clarification, direct fulfilment, or contractor inspection.
4. Student Living either:
- resolves it as a minor fulfilment item for reception pickup
- coordinates an inspection or repair with an external contractor
- pauses while parts, further planning, or access arrangements are needed
5. Work is carried out, deferred, revisited, or completed.
6. Accountability may continue beyond the repair itself if the outcome results in charges, room-condition follow-up, or a dispute about responsibility.

#### Inspection-origin path

1. Resident completes the check-in inventory report.
2. Student Living reviews disagreements about room condition.
3. Student Living may create the maintenance request on the resident's behalf.
4. The rest of the flow rejoins the normal-hours path.

#### After-hours / urgent path

1. Resident encounters an urgent issue outside office hours.
2. Resident reports it to Security or an AHDO.
3. The after-hours team handles immediate support, lock-out access, or emergency maintenance triage.
4. The issue then needs a controlled handoff back into the daytime Student Living workflow for inspection, contractor dispatch, or closure evidence.

This handoff is operationally important because the after-hours responder is not necessarily the repair owner.

### What this means for FixHub's event spine

The current FixHub model already has the right high-level idea: one shared timeline with stable location context and explicit accountability on each event. The UoN process strengthens that direction rather than replacing it.

The most useful event-spine interpretation of the UoN flow is:

- `report_created`: resident submits a portal maintenance request, or Student Living creates one from an inventory dispute
- `note`: clarification from reception, Residential Mentor, Student Living staff, or after-hours responder
- `assignment`: Student Living routes work to a maintenance team or external contractor
- `schedule`: access or inspection visit is arranged
- `status_change`: triaged, on hold, blocked, cancelled, reopened
- `escalation`: after-hours emergency escalation, safety issue, or management review
- `completion`: repair finished, item made ready for pickup, or request closed with responsibility evidence
- `follow_up`: return visit, further parts required, or post-inspection continuation

The UoN workflow also maps cleanly onto FixHub's implemented responsibility stages:

| UoN workflow slice | Best current FixHub stage |
| --- | --- |
| resident portal intake, reception clarification, after-hours first contact | `reception` |
| Student Living review, urgency judgment, responsibility assessment | `triage` |
| contractor selection, access arrangement, parts/follow-up planning | `coordination` |
| field inspection, onsite repair, blocked/no-access/complete outcomes | `execution` |

### Current FixHub fit against the observed process

#### Strong fit

- shared resident-to-operations-to-contractor timeline
- explicit assignment to either a contractor organisation or a direct contractor user
- clear `blocked`, `on_hold`, `escalated`, `completed`, and `follow_up_scheduled` states that match real maintenance variance
- event-level accountability metadata (`reason_code`, `responsibility_stage`, `owner_scope`, `responsibility_owner`)
- generic location tree that can represent `University -> Student Living -> residence/building -> room/shared space/common area`

#### Gaps exposed by the UoN workflow

1. `Job` still collapses the resident-facing request and the execution work. UoN's own language uses `job request`, which is closer to a request intake than a full contractor work order.
2. There is no first-class `Visit` object for inspection attendance, no-access outcomes, emergency callout attendance, or return visits.
3. After-hours actors are operationally real but do not fit neatly into the current role set.
4. Request origin is important but not modeled. UoN shows at least:
- resident portal request
- inventory-inspection-originated request
- urgent after-hours report
5. Closure accountability is thinner than the real workflow because UoN distinguishes ordinary maintenance from resident-liable damage, key loss, pest-treatment non-compliance, and other chargeable outcomes.
6. Minor pickup fulfilment is a different path from onsite repair, but both currently collapse into generic completion.

### Product implications for the next FixHub iterations

#### Keep

- the accountability-first event spine
- shared timeline visibility
- generic campus location hierarchy
- explicit assignment and handoff history

#### Add soon

1. `Request -> WorkOrder`
   Why:
   UoN's resident portal intake is a request surface, while contractor execution is downstream work.
2. `Visit`
   Why:
   the real process includes inspection, access, return visits, emergency attendance, and pickup-vs-onsite fulfilment differences.
3. structured request origin
   Suggested values:
   `resident_portal`, `inventory_inspection`, `after_hours_call`, `staff_created`
4. structured closure / accountability fields
   Suggested values:
   `fair_wear_and_tear`, `resident_damage`, `safety_emergency`, `parts_pending`, `no_access`, `minor_item_replaced`

#### Add later if the university fit remains strong

- an explicit support/after-hours handoff record
- a chargeability or liability decision entity
- resident communication events separate from internal notes
- access-authority / access-attempt outcomes on visits

### Working assumptions and open questions

These are plausible inferences from the sources, not yet directly confirmed by a UoN operations interview:

- Student Living likely combines front-desk intake, property management, and dispatch functions under one public-facing team name, even if different staff handle them internally.
- The public material confirms external contractors, but it does not fully expose when UoN uses internal maintenance staff versus external vendors.
- The public material shows the resident portal as the request surface, but it does not fully document resident-facing status notifications, service levels, or contractor booking communications.

### Next research targets

Future runs should try to confirm:

1. whether residents receive email, portal, or SMS updates at each stage
2. whether UoN classifies maintenance by urgency, priority, or SLA
3. how after-hours incidents are handed back to business-hours staff
4. whether contractor visits are booked into resident-access windows
5. whether common-area issues are resident-reported, staff-reported, or both

## Run Entry: `2026-03-22 18:12:37 +11:00`

### Research scope

Tighten the process map around actor boundaries, access authority, inspections and housekeeping triggers, after-hours coverage, and how maintenance outcomes become chargeable or appealable.

### Additional source set used in this run

- [Security](https://www.newcastle.edu.au/campus-life/accommodation/on-campus-accommodation/why-choose-us/security)
- [Facilities and inclusions](https://www.newcastle.edu.au/campus-life/accommodation/on-campus-accommodation/why-choose-us/facilities-and-inclusions)
- [2026 Student Living Community Standards](https://www.newcastle.edu.au/__data/assets/pdf_file/0004/1082821/2026-Student-Living-Community-Standards.pdf)
- [2026 Occupancy Licence Agreement - Terms and Conditions](https://www.newcastle.edu.au/__data/assets/pdf_file/0003/1082892/FINAL_2026-Student-OLA-Terms-and-Conditions.pdf)
- [2026 Student OLA - Schedule of Charges - Annexure 2](https://www.newcastle.edu.au/__data/assets/pdf_file/0005/1082894/FINAL_2026-Student-OLA-Schedule-of-Charges-Annexure-2.pdf)
- [Callaghan New Resident Welcome Guide](https://www.newcastle.edu.au/__data/assets/pdf_file/0005/1104719/FINAL_2026-Welcome-Guide-New-Callaghan.pdf)
- [2026 New Residents - Applications Guide](https://www.newcastle.edu.au/__data/assets/pdf_file/0010/843571/FINAL-2026-New-App-Guide-.pdf)

### What this run clarified

Maintenance is broader than the resident portal flow. Current UoN sources now confirm at least five live intake paths into the same operational system:

1. resident portal `New Job`
2. disputed check-in inventory item reviewed by the Facilities Team
3. cleaning or community-standards inspections
4. office-hours staff interactions through the Student Living Office / Reception
5. after-hours reports through AHDOs or Security

The public material is also clearer about who is actually involved:

| Real-world actor | Current source evidence | Operational role in the workflow | FixHub implication |
| --- | --- | --- | --- |
| Student Living Office / Reception | security page and welcome guide | office-hours front door, customer service, mail, finance, identity verification for lockouts, minor-item pickup point | keep `reception` as a distinct accountability stage |
| Student Living team | welcome guide | receives requests and organises external contractors | primary triage / coordination owner |
| Facilities Team | welcome guide inventory process | reviews disputed room-condition items and decides repair, replacement, or note-only outcome | add request origin and assessment outcome metadata |
| Maintenance team | welcome guide minor-item path | handles simple replacement fulfilment and pickup-ready outcomes | distinguish pickup fulfilment from onsite repair |
| Housekeeping / cleaners | OLA, community standards, facilities page | scheduled cleaning access, visibility into common/shared-space issues, potential trigger for extra cleaning or follow-up work | add non-resident operational issue origins |
| AHDOs | security page and applications guide | after-hours lockouts, emergency maintenance response, safety support | add after-hours handoff actor and event type |
| Campus Security | security page and OLA | 24/7 emergency/security response, access authority, incident support | capture as escalation actor, not default repair owner |
| Residential Mentors | applications guide and security page | general wellbeing, transition support, first-aid support, likely route residents to the right channel | support actor, not a first-class maintenance owner |
| University contractors | welcome guide and OLA | inspect and repair when coordinated by Student Living | execution actor under University control |

### Access, entry, and common-area findings

This run materially changed the access model. The OLA does not treat resident approval as the base gate for maintenance attendance:

- no notice is required where entry to a room is needed to respond to a maintenance request
- common areas can be entered without prior notice for cleaning, general repairs and maintenance, and general inspections
- routine room checks get reasonable notice where possible
- community standards state that all rooms and facilities are subject to inspections with at least 24 hours notice

That means FixHub should model `authority_to_enter` and `notice_mode` before it models resident-chosen appointment windows.

The current common-area process is also more operationally specific than the first pass suggested:

- residents have shared responsibility to keep common areas tidy and shared-unit residents are expected to participate in cleaning rosters
- housekeeping services clean kitchens and bathrooms, while common rooms and study spaces are checked daily and cleaned as needed
- extra cleaning costs in shared spaces can be split across the affected unit / room occupants
- if common-area damage occurs and the responsible person cannot be identified using reasonable efforts, UoN can allocate equal responsibility across the relevant shared-unit or building lodgers

This confirms that accountability in Student Living is not just `who logged the issue`; it often becomes `who is jointly responsible when the cause is unclear`.

### Refined workflow interpretation for FixHub

#### Expanded request origins

- `resident_portal`
- `check_in_inventory`
- `inspection_housekeeping`
- `after_hours_security`
- `staff_created`

#### Refined handoff spine

1. Intake enters through the portal, office, inspection, or after-hours path.
2. Student Living decides whether the issue is:
- note-only / record correction
- minor replacement for reception pickup
- contractor or maintenance inspection / repair
- cleaning-compliance or shared-space accountability follow-up
- urgent safety escalation through AHDOs / Security
3. Access authority and notice handling are determined.
4. Work is executed by the maintenance team, cleaners, or contractors.
5. Closure preserves accountability evidence and, where relevant, feeds a charge / appeal path through email notice and the portal.

### Product implications added in this run

#### Keep

- the shared event spine
- stage-based accountability (`reception -> triage -> coordination -> execution`)
- explicit event metadata over note-only history

#### Add next

1. structured `request_origin`
   Suggested values:
   `resident_portal`, `check_in_inventory`, `inspection_housekeeping`, `after_hours_security`, `staff_created`
2. structured `access_mode`
   Suggested values:
   `maintenance_request_no_notice`, `routine_notice`, `common_area_open_access`, `after_hours_emergency`
3. structured `fulfilment_mode`
   Suggested values:
   `onsite_repair`, `inspection_only`, `pickup_replacement`, `cleaning_follow_up`
4. structured `chargeability_outcome`
   Suggested values:
   `fair_wear_and_tear`, `resident_damage`, `shared_space_split`, `cleaning_charge`, `lockout_fine`, `key_replacement`, `pest_non_compliance`
5. actor typing on events even before permissions diverge
   Suggested event actor labels:
   `student_living_reception`, `student_living_team`, `facilities_team`, `housekeeping`, `ahdo`, `security`, `contractor`

### What remains unconfirmed

- public sources still do not expose a maintenance SLA or urgency matrix
- public sources still do not show whether contractors update the portal directly or whether Student Living proxies those updates
- public sources still do not confirm resident-facing maintenance status notifications beyond the portal being the request surface and email being used for formal charge notices
- public sources still do not expose the exact record shape of the AHDO / Security to daytime Student Living handoff

## Run Entry: `2026-03-22 19:11:47 +11:00`

### Research scope

Clarify which named UoN Student Living teams actually own maintenance operations, how after-hours and staff-created reports formally enter the process, and where accountability continues after the physical work is done.

### Additional source set used in this run

- [About us - Student Living team structure and office hours](https://www.newcastle.edu.au/campus-life/accommodation/configuration/?a=228835)
- [Student Living guides and resources](https://www.newcastle.edu.au/campus-life/accommodation/on-campus-accommodation/resources)
- [2026 Occupancy Licence Agreement - Terms and Conditions](https://www.newcastle.edu.au/__data/assets/pdf_file/0003/1082892/FINAL_2026-Student-OLA-Terms-and-Conditions.pdf)
- [2026 Student OLA - Schedule of Charges - Annexure 2](https://www.newcastle.edu.au/__data/assets/pdf_file/0005/1082894/FINAL_2026-Student-OLA-Schedule-of-Charges-Annexure-2.pdf)
- [Security](https://www.newcastle.edu.au/campus-life/accommodation/on-campus-accommodation/why-choose-us/security)
- [2026 Callaghan New Resident Welcome Guide](https://www.newcastle.edu.au/__data/assets/pdf_file/0005/1104719/FINAL_2026-Welcome-Guide-New-Callaghan.pdf)

### What this run clarified

The public Student Living `About us` page sharpens the operational ownership model. UoN now presents Student Living as distinct team groupings rather than one generic accommodation office: `Student Living Services`, `Student Living Support`, `After Hours Duty Officers`, and `Residential Mentors`. The key line for FixHub is that the Student Living Services team handles the practical operation of the precincts, including `maintenance requests`, from the Student Living Office at West Residence during office hours. That means maintenance ownership sits more cleanly with a named service operation than the earlier `reception / triage` shorthand implied.

This same source also helps narrow the role of adjacent actors. Student Living Support is positioned around resident wellbeing, transition, disability support, welfare, discipline, and student success. Residential Mentors are peer support and community-presence actors. Both matter in the real environment, but neither should be treated as a default maintenance owner. In FixHub terms, they are support/escalation participants who may add context or help route a resident, not the normal holder of the repair workflow.

The 2026 OLA makes the intake model more explicit than the welcome guide alone. Clause 22 requires residents to report damage or loss either in the Student Living Portal, to University staff, or to Security / AHDOs after hours. That is stronger evidence than a simple portal instruction: the official operating model already recognises three sanctioned intake channels:

- resident self-service in the portal
- staff-mediated reporting during normal operations
- after-hours reporting through Security or AHDOs

That strengthens the conclusion that FixHub should not treat resident-submitted reports as the only canonical source of truth. A real UoN-aligned event spine needs first-class on-behalf intake and after-hours handoff events.

The OLA also adds a governance detail that matters for the product model: UoN expressly reserves the right to share resident information with `staff, contractors, security personnel and other persons reasonably required` for administration of Student Living. This confirms that external contractors and security responders are not edge-case participants; they are authorised workflow actors inside the same governed operating process. That supports keeping contractor and security participation explicit on events instead of collapsing them into internal notes.

The strongest new accountability finding is that UoN's maintenance process continues past repair completion into a formal notice, payment, and appeal sequence when liability is involved. The current resources page still publishes the 2026 `Schedule of Charges` and a live `Appeal Form`, while the 2026 OLA requires charge notices to be sent to the resident's registered email, posted to the portal, paid within 14 days, and then contested through the published appeal path if the resident disputes them. In other words, the real Student Living workflow is not just:

`report -> triage -> repair -> complete`

It is often:

`report -> triage -> repair -> liability decision -> charge notice -> payment or appeal -> final resolution`

This is a material fit signal for FixHub's accountability-first positioning. The event spine is valuable precisely because UoN's real process depends on preserving who reported the issue, who assessed responsibility, who attended, what was found, and why a cost became chargeable.

### Refined actor ownership model

| Actor | Strongest current evidence | Operational meaning for the workflow | FixHub mapping implication |
| --- | --- | --- | --- |
| Student Living Services | `About us` page says the team manages accommodation precincts and `maintenance requests` | office-hours intake, operational ownership, service-desk handling, likely first daytime handoff target | keep `reception`, but type the actor as `student_living_services` rather than a generic front desk |
| Student Living Support | `About us` page describes wellbeing, disability, welfare, discipline, and student success support | supportive context and escalation path, not default repair ownership | support-note actor, not assignee by default |
| AHDOs | security page plus OLA after-hours clauses | urgent out-of-hours intake and immediate response | add explicit after-hours handoff actor/events |
| Security | OLA and security page | emergency response, authorised after-hours intake, access authority | explicit escalation/intake actor, not the normal repair owner |
| Contractors | welcome guide plus OLA data-sharing clause | authorised execution and inspection participants under University coordination | keep first-class execution actors with auditable event history |
| Resident | portal, OLA reporting duty, appeal/payment path | reporter, access context holder, liable or non-liable party, appeal initiator | retain resident timeline visibility and accountability evidence |

### Event-spine implications added in this run

The current four-stage FixHub flow still looks directionally right:

- `reception`: Student Living Services intake, clarification, after-hours handoff receipt
- `triage`: daytime assessment, liability review, dispatch decision
- `coordination`: contractor routing, access planning, follow-up ordering
- `execution`: inspection, repair, pickup fulfilment, blocked/no-access outcomes

The gap is now clearer at the tail of the workflow. A UoN-aligned event spine should add explicit post-execution accountability records before introducing heavier entities:

1. `reported_via` or `request_origin`
   Suggested values:
   `resident_portal`, `staff_created`, `security_after_hours`, `check_in_inventory`, `inspection_housekeeping`
2. `after_hours_handoff_received`
   Why:
   the public operating model recognises Security/AHDO intake, but daytime Student Living Services still appears to own the continuing job
3. `liability_assessed`
   Why:
   UoN distinguishes fair wear/repair from resident-liable outcomes and shared-cost scenarios
4. `charge_notice_issued`
   Why:
   the real process uses formal notice and portal posting, not just silent completion
5. `charge_appeal_submitted` and `charge_resolved`
   Why:
   the resources pack and OLA show that contested accountability is part of the live workflow

This suggests FixHub should keep the current stage model for now, but extend the event vocabulary so the product can preserve accountability all the way through financial resolution.

### What remains unconfirmed after this run

- public sources still do not show the resident-facing status updates used during repair execution, only the intake surface and formal charge notice path
- public sources still do not expose the exact business-hours owner of liability decisions or whether that sits solely with Student Living Services
- public sources still do not expose an urgency / SLA matrix for maintenance categories
- public sources still do not document the exact record passed from Security or AHDOs into the daytime Services workflow
