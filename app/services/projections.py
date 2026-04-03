from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from app.models import JobStatus


def _event_order_key(event: Any) -> tuple[datetime, Any]:
    return (event.created_at, event.id)


def derive_job_status_from_events(events: Iterable[Any]) -> JobStatus:
    derived_status = JobStatus.new

    for event in sorted(events, key=_event_order_key):
        target_status = getattr(event, "target_status", None)
        if target_status is not None:
            derived_status = target_status

    return derived_status


def sync_job_status_from_events(job: Any) -> JobStatus:
    job.status = derive_job_status_from_events(job.events)
    return job.status
