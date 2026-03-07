from __future__ import annotations

from app.core.database import session_scope
from app.services.seed import ensure_seed_data


if __name__ == "__main__":
    with session_scope() as session:
        seed_data = ensure_seed_data(session)

    print("Seeded minimal MVP data:")
    print(f"  org_id={seed_data.org_id}")
    print(f"  residence_id={seed_data.residence_id}")
    print(f"  unit_id={seed_data.unit_id}")
    print(f"  resident_user_id={seed_data.resident_user_id}")
    print(f"  contractor_user_id={seed_data.contractor_user_id}")
    print(f"  category={seed_data.category}")