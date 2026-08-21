"""feat/audit-log-hardening: add audit hash fields to runs/run_steps and a
guardrail_events table.


Revision ID: 82af9aa50cfe
Revises: a4b8c1d9e2f0
Create Date: 2026-08-21 08:42:27.173752

"""
from alembic import op
import sqlalchemy as sa


revision = "82af9aa50cfe"
down_revision = "a4b8c1d9e2f0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("system_prompt_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("final_output_hash", sa.String(length=64), nullable=True))

    with op.batch_alter_table("run_steps", schema=None) as batch_op:
        batch_op.add_column(sa.Column("arguments_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("result_hash", sa.String(length=64), nullable=True))

    # Not picked up by autogenerate: app.py's create_app() calls db.create_all()
    # on every app-context creation (including the one `flask db migrate` itself
    # builds), which had already created this table locally before Alembic
    # diffed the schema. Written by hand so a fresh DB that never ran
    # db.create_all() first still gets this table from `flask db upgrade`.
  
    op.create_table(
        "guardrail_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("filter_name", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("guardrail_events")

    with op.batch_alter_table("run_steps", schema=None) as batch_op:
        batch_op.drop_column("result_hash")
        batch_op.drop_column("arguments_hash")

    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_column("final_output_hash")
        batch_op.drop_column("system_prompt_hash")
