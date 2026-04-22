"""add cdm persistence tables

Revision ID: 011ace2ca7ef
Revises: a8b9c0d1e2f3
Create Date: 2026-04-22 13:44:42.073595

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "011ace2ca7ef"
down_revision: Union[str, None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sha256", sa.CHAR(64), nullable=False, unique=True),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_source_documents_sha256", "source_documents", ["sha256"], unique=True)

    op.create_table(
        "parse_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parser", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=True),
        sa.Column("representation_kind", sa.Text(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("config_hash", sa.CHAR(64), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("cost", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("failed_pages", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("provider_refs", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "ux_parse_runs_content_config",
        "parse_runs",
        ["source_document_id", "representation_kind", "config_hash"],
        unique=True,
    )
    op.create_index("ix_parse_runs_status", "parse_runs", ["status"])
    op.create_index("ix_parse_runs_source_document_id", "parse_runs", ["source_document_id"])

    op.create_table(
        "parsed_documents",
        sa.Column("parse_run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("parse_runs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("full_markdown", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("block_count", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "ix_parsed_documents_source_document_id",
        "parsed_documents",
        ["source_document_id"],
    )

    op.add_column(
        "documents",
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_source_document_id",
        "documents",
        "source_documents",
        ["source_document_id"],
        ["id"],
    )
    op.create_index("ix_documents_source_document_id", "documents", ["source_document_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_source_document_id", table_name="documents")
    op.drop_constraint("fk_documents_source_document_id", "documents", type_="foreignkey")
    op.drop_column("documents", "source_document_id")

    op.drop_index("ix_parsed_documents_source_document_id", table_name="parsed_documents")
    op.drop_table("parsed_documents")

    op.drop_index("ix_parse_runs_source_document_id", table_name="parse_runs")
    op.drop_index("ix_parse_runs_status", table_name="parse_runs")
    op.drop_index("ux_parse_runs_content_config", table_name="parse_runs")
    op.drop_table("parse_runs")

    op.drop_index("ix_source_documents_sha256", table_name="source_documents")
    op.drop_table("source_documents")
