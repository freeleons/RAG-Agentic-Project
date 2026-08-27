"""feat/obs-provider-error-type: add provider to runs and error_type to run_steps.

中文：为 runs 表增加 provider，为 run_steps 表增加 error_type。

Revision ID: a4b8c1d9e2f0
Revises: 9a1f3c7d2e5b
Create Date: 2026-08-18 06:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a4b8c1d9e2f0"
down_revision = "9a1f3c7d2e5b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("provider", sa.String(length=32), nullable=True))

    with op.batch_alter_table("run_steps", schema=None) as batch_op:
        batch_op.add_column(sa.Column("error_type", sa.String(length=64), nullable=True))


def downgrade():
    with op.batch_alter_table("run_steps", schema=None) as batch_op:
        batch_op.drop_column("error_type")

    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_column("provider")
