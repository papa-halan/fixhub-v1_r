"""Make work order completion time database-derived.

Revision ID: 20260308_0003
Revises: 20260307_0002
Create Date: 2026-03-08 11:35:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260308_0003"
down_revision: str | None = "20260307_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CHECK_NAME = "ck_work_orders_completed_at_matches_status"
_TRIGGER_NAME = "trg_work_orders_sync_completed_at"
_FUNCTION_NAME = "sync_work_order_completed_at"


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _check_constraint_exists(table_name: str, constraint_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    constraints = sa.inspect(op.get_bind()).get_check_constraints(table_name)
    return any(constraint["name"] == constraint_name for constraint in constraints)


def upgrade() -> None:
    if not _table_exists("work_orders"):
        return

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {_FUNCTION_NAME}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.status = 'completed' THEN
                    NEW.completed_at := CURRENT_TIMESTAMP;
                ELSE
                    NEW.completed_at := NULL;
                END IF;
                RETURN NEW;
            END IF;

            IF NEW.status = 'completed' THEN
                IF OLD.status IS DISTINCT FROM NEW.status THEN
                    NEW.completed_at := CURRENT_TIMESTAMP;
                ELSE
                    NEW.completed_at := OLD.completed_at;
                END IF;
            ELSE
                NEW.completed_at := NULL;
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute(
        """
        UPDATE work_orders
        SET completed_at = NULL
        WHERE status != 'completed'
        """
    )
    op.execute(
        """
        UPDATE work_orders
        SET completed_at = COALESCE(completed_at, updated_at)
        WHERE status = 'completed'
        """
    )

    if not _check_constraint_exists("work_orders", _CHECK_NAME):
        op.create_check_constraint(
            _CHECK_NAME,
            "work_orders",
            "(status = 'completed' AND completed_at IS NOT NULL) "
            "OR (status != 'completed' AND completed_at IS NULL)",
        )

    op.execute(f"DROP TRIGGER IF EXISTS {_TRIGGER_NAME} ON work_orders")
    op.execute(
        f"""
        CREATE TRIGGER {_TRIGGER_NAME}
        BEFORE INSERT OR UPDATE OF status, completed_at
        ON work_orders
        FOR EACH ROW
        EXECUTE FUNCTION {_FUNCTION_NAME}()
        """
    )


def downgrade() -> None:
    if not _table_exists("work_orders"):
        return

    op.execute(f"DROP TRIGGER IF EXISTS {_TRIGGER_NAME} ON work_orders")
    op.execute(f"DROP FUNCTION IF EXISTS {_FUNCTION_NAME}()")

    if _check_constraint_exists("work_orders", _CHECK_NAME):
        op.drop_constraint(_CHECK_NAME, "work_orders", type_="check")
