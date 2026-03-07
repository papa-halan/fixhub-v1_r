from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RoutingRule


class RoutingRuleNotFoundError(LookupError):
    pass


def lookup_contractor_user_id(
    session: Session,
    residence_id: uuid.UUID,
    category: str,
) -> uuid.UUID:
    contractor_user_id = session.scalar(
        select(RoutingRule.contractor_user_id)
        .where(RoutingRule.residence_id == residence_id)
        .where(RoutingRule.category == category)
        .where(RoutingRule.enabled.is_(True))
        .limit(1)
    )
    if contractor_user_id is None:
        raise RoutingRuleNotFoundError(
            f"No enabled routing rule found for residence_id={residence_id} and category='{category}'"
        )
    return contractor_user_id