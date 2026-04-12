"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # accounts
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("truelayer_account_id", sa.String, nullable=False, unique=True),
        sa.Column("provider_id", sa.String, nullable=False),
        sa.Column("display_name", sa.String, nullable=False),
        sa.Column(
            "account_type",
            sa.Enum("current", "savings", "credit_card", name="accounttype"),
            nullable=False,
        ),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("iban", sa.String, nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # transaction_offsets (created before transactions due to FK)
    op.create_table(
        "transaction_offsets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("debit_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credit_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "offset_type",
            sa.Enum("manual", "auto_detected", name="offsettype"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # transactions
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("truelayer_transaction_id", sa.String, nullable=False),
        sa.Column("provider_transaction_id", sa.String, nullable=True),
        sa.Column("amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("merchant_name", sa.String, nullable=True),
        sa.Column("category", sa.String, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum("debit", "credit", name="transactiontype"),
            nullable=False,
        ),
        sa.Column("transaction_classification", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("running_balance", sa.Numeric(14, 4), nullable=True),
        sa.Column("raw_data", postgresql.JSONB, nullable=False),
        sa.Column("is_pending", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "offset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transaction_offsets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # Add FKs from transaction_offsets → transactions (deferred, table now exists)
    op.create_foreign_key(
        "fk_offset_debit_tx",
        "transaction_offsets",
        "transactions",
        ["debit_transaction_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_offset_credit_tx",
        "transaction_offsets",
        "transactions",
        ["credit_transaction_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # truelayer_tokens
    op.create_table(
        "truelayer_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("access_token_encrypted", sa.Text, nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", sa.String, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # Indexes
    op.create_index(
        "uq_transaction_account",
        "transactions",
        ["truelayer_transaction_id", "account_id"],
        unique=True,
    )
    op.create_index("ix_transaction_account_timestamp", "transactions", ["account_id", "timestamp"])
    op.create_index(
        "ix_transaction_amount_currency_timestamp",
        "transactions",
        ["amount", "currency", "timestamp"],
    )
    op.create_index(
        "ix_transaction_no_offset",
        "transactions",
        ["offset_id"],
        postgresql_where=sa.text("offset_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("truelayer_tokens")
    op.drop_index("ix_transaction_no_offset", table_name="transactions")
    op.drop_index("ix_transaction_amount_currency_timestamp", table_name="transactions")
    op.drop_index("ix_transaction_account_timestamp", table_name="transactions")
    op.drop_index("uq_transaction_account", table_name="transactions")
    op.drop_constraint("fk_offset_credit_tx", "transaction_offsets", type_="foreignkey")
    op.drop_constraint("fk_offset_debit_tx", "transaction_offsets", type_="foreignkey")
    op.drop_table("transactions")
    op.drop_table("transaction_offsets")
    op.drop_table("accounts")
    op.execute("DROP TYPE IF EXISTS transactiontype")
    op.execute("DROP TYPE IF EXISTS offsettype")
    op.execute("DROP TYPE IF EXISTS accounttype")
