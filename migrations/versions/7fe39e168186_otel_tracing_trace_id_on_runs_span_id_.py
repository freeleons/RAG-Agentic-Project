"""feat/otel-tracing: add trace_id to runs and span_id to run_steps.

中文：为 runs 增加 trace_id，为 run_steps 增加 span_id，用于 OTel 追踪。

Revision ID: 7fe39e168186
Revises: 82af9aa50cfe
Create Date: 2026-08-21 21:22:48.548873

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7fe39e168186'
down_revision = '82af9aa50cfe'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("trace_id", sa.String(length=32), nullable=True))

    with op.batch_alter_table("run_steps", schema=None) as batch_op:
        batch_op.add_column(sa.Column("span_id", sa.String(length=16), nullable=True))


def downgrade():
    with op.batch_alter_table("run_steps", schema=None) as batch_op:
        batch_op.drop_column("span_id")

    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_column("trace_id")
