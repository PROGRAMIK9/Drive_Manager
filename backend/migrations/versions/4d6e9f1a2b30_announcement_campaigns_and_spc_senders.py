"""Add per-SPC Gmail senders and placement announcement records."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d6e9f1a2b30"
down_revision: Union[str, Sequence[str], None] = "8d2f6a1c9b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gmailoauthstate", sa.Column("purpose", sa.String(length=24), nullable=False, server_default="inbox"))

    op.create_table(
        "gmailsendingaccount",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("email_address", sa.String(length=320), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("signature_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("connected", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_gmailsendingaccount_user_id"),
    )
    op.create_index("ix_gmailsendingaccount_user_id", "gmailsendingaccount", ["user_id"])
    op.create_index("ix_gmailsendingaccount_email_address", "gmailsendingaccount", ["email_address"])

    op.create_table(
        "placementrecipientlist",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("list_key", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("list_key", name="uq_placementrecipientlist_list_key"),
    )

    op.create_table(
        "placementrecipient",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipient_list_id", sa.Integer(), sa.ForeignKey("placementrecipientlist.id"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("recipient_list_id", "email", name="uq_placement_recipient_list_email"),
    )
    op.create_index("ix_placementrecipient_recipient_list_id", "placementrecipient", ["recipient_list_id"])
    op.create_index("ix_placementrecipient_email", "placementrecipient", ["email"])

    op.create_table(
        "placementannouncementsettings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("placement_director_email", sa.String(length=320), nullable=True),
        sa.Column("co_spc_emails", sa.JSON(), nullable=False),
        sa.Column("staff_coordinator_email", sa.String(length=320), nullable=True),
        sa.Column("templates", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "placementcampaign",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("recipient_list_id", sa.Integer(), sa.ForeignKey("placementrecipientlist.id"), nullable=False),
        sa.Column("initiated_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("sender_email", sa.String(length=320), nullable=False),
        sa.Column("template_key", sa.String(length=40), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("signature_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("include_signature", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("to_emails", sa.JSON(), nullable=False),
        sa.Column("cc_emails", sa.JSON(), nullable=False),
        sa.Column("bcc_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consent_form_url", sa.String(length=2000), nullable=False),
        sa.Column("links", sa.JSON(), nullable=False),
        sa.Column("attachments", sa.JSON(), nullable=False),
        sa.Column("attachment_names", sa.JSON(), nullable=False),
        sa.Column("gmail_message_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="DRAFT"),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.Column("request_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("request_key", name="uq_placementcampaign_request_key"),
    )
    op.create_index("ix_placementcampaign_company_id", "placementcampaign", ["company_id"])
    op.create_index("ix_placementcampaign_recipient_list_id", "placementcampaign", ["recipient_list_id"])
    op.create_index("ix_placementcampaign_initiated_by", "placementcampaign", ["initiated_by"])
    op.create_index("ix_placementcampaign_status", "placementcampaign", ["status"])
    op.create_index("ix_placementcampaign_request_key", "placementcampaign", ["request_key"])

    op.create_table(
        "placementattachment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_placementattachment_uploaded_by", "placementattachment", ["uploaded_by"])


def downgrade() -> None:
    op.drop_index("ix_placementattachment_uploaded_by", table_name="placementattachment")
    op.drop_table("placementattachment")
    op.drop_index("ix_placementcampaign_request_key", table_name="placementcampaign")
    op.drop_index("ix_placementcampaign_status", table_name="placementcampaign")
    op.drop_index("ix_placementcampaign_initiated_by", table_name="placementcampaign")
    op.drop_index("ix_placementcampaign_company_id", table_name="placementcampaign")
    op.drop_index("ix_placementcampaign_recipient_list_id", table_name="placementcampaign")
    op.drop_table("placementcampaign")
    op.drop_table("placementannouncementsettings")
    op.drop_index("ix_placementrecipient_email", table_name="placementrecipient")
    op.drop_index("ix_placementrecipient_recipient_list_id", table_name="placementrecipient")
    op.drop_table("placementrecipient")
    op.drop_table("placementrecipientlist")
    op.drop_index("ix_gmailsendingaccount_email_address", table_name="gmailsendingaccount")
    op.drop_index("ix_gmailsendingaccount_user_id", table_name="gmailsendingaccount")
    op.drop_table("gmailsendingaccount")
    op.drop_column("gmailoauthstate", "purpose")
