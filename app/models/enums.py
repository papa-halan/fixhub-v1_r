from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    resident = "resident"
    admin = "admin"
    contractor = "contractor"


class OrganisationType(str, Enum):
    university = "university"
    contractor = "contractor"


class JobStatus(str, Enum):
    new = "new"
    assigned = "assigned"
    in_progress = "in_progress"
    completed = "completed"
