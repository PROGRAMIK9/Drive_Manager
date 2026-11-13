"""Add email automation storage and SPC review queue.

Revision ID: 3a1c8f9d2b40
Revises: cd53e8a412bf
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "3a1c8f9d2b40"
down_revision: Union[str, Sequence[str], None] = "cd53e8a412bf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gmailintegration",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("email_address", sa.String(length=320), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
        sa.Column("connected", sa.Boolean(), nullable=False),
        sa.Column("last_history_id", sa.String(length=128), nullable=True),
        sa.Column("watch_expiration", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_gmailintegration_email_address", "gmailintegration", ["email_address"])

    op.create_table(
        "processedemail",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("gmail_message_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("gmail_thread_id", sa.String(length=255), nullable=True),
        sa.Column("sender", sa.String(length=320), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("classification", sa.String(length=40), nullable=False),
        sa.Column("processing_status", sa.String(length=40), nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("extracted_data", sa.JSON(), nullable=False),
        sa.Column("source_link", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_processedemail_gmail_message_id", "processedemail", ["gmail_message_id"])
    op.create_index("ix_processedemail_gmail_thread_id", "processedemail", ["gmail_thread_id"])
    op.create_index("ix_processedemail_processing_status", "processedemail", ["processing_status"])
    op.create_index("ix_processedemail_content_hash", "processedemail", ["content_hash"])

    op.create_table(
        "pendingplacementopportunity",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("opportunity_type", sa.String(length=80), nullable=True),
        sa.Column("eligible_courses", sa.JSON(), nullable=False),
        sa.Column("eligible_branches", sa.JSON(), nullable=False),
        sa.Column("eligible_batches", sa.JSON(), nullable=False),
        sa.Column("minimum_cgpa", sa.Float(), nullable=True),
        sa.Column("backlog_allowed", sa.Boolean(), nullable=True),
        sa.Column("maximum_backlogs", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("compensation", sa.String(length=255), nullable=True),
        sa.Column("internship_duration", sa.String(length=255), nullable=True),
        sa.Column("application_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("department_submission_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assessment_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("group_discussion_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interview_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("application_link", sa.Text(), nullable=True),
        sa.Column("eligibility_status", sa.String(length=24), nullable=False),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("missing_information", sa.JSON(), nullable=False),
        sa.Column("source_email_id", sa.Integer(), sa.ForeignKey("processedemail.id"), nullable=True),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("published_company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in ("company_name", "eligibility_status", "source_email_id", "review_status"):
        op.create_index(f"ix_pendingplacementopportunity_{column}", "pendingplacementopportunity", [column])


def downgrade() -> None:
    op.drop_table("pendingplacementopportunity")
    op.drop_table("processedemail")
    op.drop_table("gmailintegration")
