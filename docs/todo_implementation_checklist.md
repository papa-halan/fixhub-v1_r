# TODO Implementation Checklist

Last updated: `2026-03-21 18:31:16 +11:00`

## Document Metadata

- Owner: `student-living-platform`
- Reviewer: `schema-test-automation`
- Status: `active`

Use this checklist to track work that is still intentionally deferred after the Phase 0.5 correction pass.

## Current Baseline

- [x] Migrations are the schema authority
- [x] App boot is blocked on stale schema
- [x] Runtime does not rely on `create_all()`
- [x] Normal-mode password login works with an optional bootstrap non-demo user
- [x] Demo shortcuts are explicit and demo-mode-only
- [x] Report creation uses structured `location_id`
- [x] Legacy placeholder locations are removed or quarantined out of the active catalog
- [x] Role labels and UI controls better match real workflow actors

## Deferred Product Work

### Phase 1 Domain Split

- [ ] Introduce a resident-facing request entity separate from execution-facing work orders
- [ ] Add structured visit or dispatch records
- [ ] Add request-level aggregation and multi-work-order flows

### Broader Operational Capability

- [ ] Add richer routing reasons and dispatch history
- [ ] Add governed asset management beyond lightweight per-location asset names
- [ ] Add broader contractor eligibility/routing policies

### Broader Auth And Deployment Capability

- [ ] Add invites, password reset, and fuller role/capability management
- [ ] Add stronger organisation/bootstrap administration tooling
- [ ] Add CI wiring for migration smoke and docs freshness checks

### Out Of Scope For This Phase

- [ ] Public reporting, councils, homeowner verification, or public-sector intake flows
- [ ] GIS, maps, or address parsing/search
- [ ] Scheduling engine or full CMMS feature set
