# Research Log: UoN Student Living Maintenance Context Addendum

Last updated: `2026-04-04 01:11:59 +11:00`

## Document Metadata

- Owner: `uon-student-living-automation`
- Reviewer: `codex-research`
- Status: `active`

## Relationship To Primary Log

This companion append-only addendum extends `docs/uon_student_living_maintenance_context.md` when the primary tracked log already has pending worktree changes and cannot be safely edited in this run. Future automation runs should append here while that condition remains true, then reconcile later without deleting prior entries.

## Document Rule

- never delete prior run entries
- append a new timestamped section for each automation run that lands in this addendum
- keep source links inline so evidence stays auditable
- mark inferences explicitly when the public sources do not confirm the exact operational backend

## Run Entry: `2026-04-04 01:11:59 +11:00`

### Research scope

Capture net-new workflow evidence not already reflected in the primary pending UoN log, especially around contact-channel semantics, combined maintenance/cleaning intake, likely downstream university fulfilment, and the finance/appeal tail after physical work is done.

### Source set used in this run

- [About us - Student Living team structure and contact model](https://www.newcastle.edu.au/campus-life/accommodation/configuration/?a=228835)
- [Security](https://www.newcastle.edu.au/campus-life/accommodation/configuration/campaigns/?a=218675)
- [2026 Callaghan New Resident Welcome Guide](https://www.newcastle.edu.au/__data/assets/pdf_file/0005/1104719/FINAL_2026-Welcome-Guide-New-Callaghan.pdf)
- [2026 Occupancy Licence Agreement - Terms and Conditions](https://www.newcastle.edu.au/__data/assets/pdf_file/0003/1082892/FINAL_2026-Student-OLA-Terms-and-Conditions.pdf)
- [2026 Student OLA - Schedule of Charges - Annexure 2](https://www.newcastle.edu.au/__data/assets/pdf_file/0005/1082894/FINAL_2026-Student-OLA-Schedule-of-Charges-Annexure-2.pdf)
- [Door Breach Appeal Form](https://www.newcastle.edu.au/__data/assets/pdf_file/0003/912936/door-breach-appeal-form.pdf)
- [Maintenance and cleaning - current staff](https://www.newcastle.edu.au/current-staff/working-here/our-work-environment/buildings-and-spaces/maintenance-and-cleaning)

### Net-new findings from this run

The 2026 OLA defines the `University of Newcastle Student Living Portal` as the University's `online payment and communication facility`, not just a request form. Combined with the welcome-guide `Maintenance and Cleaning -> New Job` flow and the OLA charge-payment clauses, the portal should be treated as part of the resident-facing system of record for intake, notices, and account-linked resolution.

The public phone-channel model is more nuanced than a simple `office hours vs after hours` note. The `About us` page shows `Student Living Services` uses `+61 2 4913 8888` during office hours, and the same page shows `After-Hours Duty Officers` use that same number during their rostered periods. The `Security` page separately lists Campus Security as the 24/7 line. For FixHub, that means `channel used` is not enough to infer `accountable team`; the model should preserve both.

The resident self-service entry point is a combined `Maintenance and Cleaning` tab rather than a repair-only form. That matters because UoN's live operating process already mixes:

- resident-requested repairs
- minor replacement-item pickup
- cleaning and housekeeping observations
- after-hours safety/emergency maintenance intake
- later charge and appeal handling

The most useful product implication is a shared intake spine with divergent downstream workstreams, not a repair-only ticket model.

The post-execution accountability tail now has named operational actors. The 2026 Schedule of Charges lists `studentliving-finance@newcastle.edu.au` as the finance contact for charges. The Door Breach Appeal Form requires appeals to `studentliving-appeals@newcastle.edu.au` within 14 days of charge notification, requires supporting documentation, states that fees must still be paid, and notes the value is credited back if the appeal is upheld. This means the real workflow continues through finance and appeals queues after physical work or a standards breach outcome, not just through `complete`.

The strongest public evidence of backstage university fulfilment is now the combination of two source groups:

1. resident-facing sources say Student Living receives requests and that `the University or its contractors will undertake all repairs and alterations`
2. the current staff maintenance page says broader campus maintenance and extra cleaning requests route through `Maximo`, with Infrastructure and Facilities Services handling business-hours emergencies and Security handling after-hours emergencies

Inference from the sources:
Student Living likely sits on top of a broader university asset-service network for at least some fulfilment paths, even though the public student-facing material does not directly confirm whether resident jobs themselves are proxied into Maximo or a related internal facilities workflow.

### Refined workflow addition

#### Best current addition to the process map

1. An issue enters through a contact surface such as the portal, `4913 8888`, or Campus Security.
2. The intake channel resolves to an accountable team based on time band and context:
- `student_living_services` in office hours
- `ahdo` during rostered after-hours coverage
- `security` for 24/7 emergency/fallback handling
3. Student Living determines the active service line:
- `maintenance_repair`
- `cleaning_housekeeping`
- `minor_item_pickup`
- `after_hours_safety`
- `charge_resolution`
4. The case is either fulfilled inside the Student Living/University network, routed to an external contractor, or continued into finance/appeal handling.
5. Resident-facing communication may continue through the portal, email, or other formal notice paths even after the physical work is finished.

#### Newly clarified actor/system edges

| Workflow edge | Current evidence | Best current reading | FixHub implication |
| --- | --- | --- | --- |
| `portal -> case` | welcome guide plus OLA portal definition | portal is intake plus communication/payment surface | add explicit resident-facing channel and notice events |
| `4913 8888 -> team` | `About us` page | same number, different accountable team by time band | separate `channel_used` from `actor_team` |
| `case -> university fulfilment` | OLA plus current staff maintenance page | likely internal handoff exists for some jobs | add `handoff_target` and optional external/internal reference id |
| `case -> finance` | 2026 Schedule of Charges | charges become an account/finance workflow | add finance actors and post-work accountability events |
| `finance -> appeal` | Door Breach Appeal Form | formal evidence-backed appeal queue exists | add appeals actor/events instead of stopping at closure |

### Event-spine implications added in this run

Keep the existing `reception -> triage -> coordination -> execution` stages, but strengthen the event metadata around them.

Suggested additions:

1. `channel_used`
   Suggested values:
   `portal`, `student_living_phone`, `security_phone`, `staff_created`
   Why:
   the same phone number can map to different accountable teams depending on time and circumstance.
2. `service_line`
   Suggested values:
   `maintenance_repair`, `cleaning_housekeeping`, `minor_item_pickup`, `after_hours_safety`, `charge_resolution`
   Why:
   UoN uses one intake surface for adjacent workstreams that diverge after triage.
3. `handoff_target`
   Suggested values:
   `student_living_internal`, `external_contractor`, `university_facilities_inferred`, `security`
   Why:
   resident-facing ownership and fulfilment ownership are not always the same actor.
4. `resident_notice_channel`
   Suggested values:
   `portal`, `email`, `notice_board`
   Why:
   the OLA explicitly ties notices and payment/account communication to named channels.
5. post-work accountability events
   Suggested values:
   `charge_posted_to_account`, `appeal_evidence_received`, `appeal_outcome_recorded`, `account_credit_applied`
   Why:
   the real workflow clearly continues past physical execution into financial and evidentiary resolution.

### Best next research targets

1. confirm whether Student Living Services manually proxy some resident cases into a separate university maintenance platform such as Maximo
2. find direct public evidence for execution-stage resident notifications beyond intake and charge notices
3. confirm whether finance and appeal handling sit inside Student Living Services or a separate back-office owner
4. locate a current generic Student Living appeal form or complaint/escalation path beyond the door-breach-specific form
5. confirm whether cleaning/housekeeping-origin issues reuse the same resident-visible case surface or remain internal-only
