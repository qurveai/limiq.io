"""prod hardening indexes

Revision ID: 0003_prod_hardening_indexes
Revises: 0002_sprint4_audit_integrity_indexes
Create Date: 2026-02-26 12:30:00
"""

from alembic import op

revision = "0003_prod_hardening_indexes"
down_revision = "0002_sprint4_audit_integrity_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_capabilities_agent_id_status",
        "capabilities",
        ["agent_id", "status"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_agents_fingerprint",
        "agents",
        ["fingerprint"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_revocations_jti",
        "revocations",
        ["jti"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_revocations_jti", table_name="revocations", if_exists=True)
    op.drop_index("ix_agents_fingerprint", table_name="agents", if_exists=True)
    op.drop_index(
        "ix_capabilities_agent_id_status",
        table_name="capabilities",
        if_exists=True,
    )
