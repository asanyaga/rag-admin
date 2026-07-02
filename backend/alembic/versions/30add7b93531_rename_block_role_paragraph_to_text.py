"""rename_block_role_paragraph_to_text

Revision ID: 30add7b93531
Revises: f2a3b4c5d6e7
Create Date: 2026-07-02 12:48:04.824242

"""
from typing import Sequence, Union

from alembic import op


revision: str = '30add7b93531'
down_revision: Union[str, None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # parsed_documents: rewrite role field on each block in the blocks array
    op.execute("""
        UPDATE parsed_documents
        SET content = jsonb_set(
            content,
            '{blocks}',
            (
                SELECT jsonb_agg(
                    CASE
                        WHEN elem->>'role' = 'paragraph'
                        THEN jsonb_set(elem, '{role}', '"text"')
                        ELSE elem
                    END
                )
                FROM jsonb_array_elements(content->'blocks') AS elem
            )
        )
        WHERE EXISTS (
            SELECT 1
            FROM jsonb_array_elements(content->'blocks') AS elem
            WHERE elem->>'role' = 'paragraph'
        )
    """)

    # chunks: rewrite role values in block_roles array
    op.execute("""
        UPDATE chunks
        SET chunk_metadata = (
            jsonb_set(
                chunk_metadata::jsonb,
                '{block_roles}',
                (
                    SELECT jsonb_agg(
                        CASE
                            WHEN elem::text = '"paragraph"' THEN '"text"'::jsonb
                            ELSE elem
                        END
                    )
                    FROM jsonb_array_elements(chunk_metadata::jsonb->'block_roles') AS elem
                )
            )
        )::json
        WHERE chunk_metadata::jsonb ? 'block_roles'
          AND EXISTS (
            SELECT 1
            FROM jsonb_array_elements(chunk_metadata::jsonb->'block_roles') AS elem
            WHERE elem::text = '"paragraph"'
          )
    """)

    # indexes: rewrite role values in blockRoleFilter array
    op.execute("""
        UPDATE indexes
        SET config = (
            jsonb_set(
                config::jsonb,
                '{blockRoleFilter}',
                (
                    SELECT jsonb_agg(
                        CASE
                            WHEN elem::text = '"paragraph"' THEN '"text"'::jsonb
                            ELSE elem
                        END
                    )
                    FROM jsonb_array_elements(config::jsonb->'blockRoleFilter') AS elem
                )
            )
        )::json
        WHERE config::jsonb ? 'blockRoleFilter'
          AND config::jsonb->'blockRoleFilter' IS NOT NULL
          AND EXISTS (
            SELECT 1
            FROM jsonb_array_elements(config::jsonb->'blockRoleFilter') AS elem
            WHERE elem::text = '"paragraph"'
          )
    """)


def downgrade() -> None:
    # parsed_documents: revert text → paragraph
    op.execute("""
        UPDATE parsed_documents
        SET content = jsonb_set(
            content,
            '{blocks}',
            (
                SELECT jsonb_agg(
                    CASE
                        WHEN elem->>'role' = 'text'
                        THEN jsonb_set(elem, '{role}', '"paragraph"')
                        ELSE elem
                    END
                )
                FROM jsonb_array_elements(content->'blocks') AS elem
            )
        )
        WHERE EXISTS (
            SELECT 1
            FROM jsonb_array_elements(content->'blocks') AS elem
            WHERE elem->>'role' = 'text'
        )
    """)

    # chunks: revert text → paragraph
    op.execute("""
        UPDATE chunks
        SET chunk_metadata = (
            jsonb_set(
                chunk_metadata::jsonb,
                '{block_roles}',
                (
                    SELECT jsonb_agg(
                        CASE
                            WHEN elem::text = '"text"' THEN '"paragraph"'::jsonb
                            ELSE elem
                        END
                    )
                    FROM jsonb_array_elements(chunk_metadata::jsonb->'block_roles') AS elem
                )
            )
        )::json
        WHERE chunk_metadata::jsonb ? 'block_roles'
          AND EXISTS (
            SELECT 1
            FROM jsonb_array_elements(chunk_metadata::jsonb->'block_roles') AS elem
            WHERE elem::text = '"text"'
          )
    """)

    # indexes: revert text → paragraph
    op.execute("""
        UPDATE indexes
        SET config = (
            jsonb_set(
                config::jsonb,
                '{blockRoleFilter}',
                (
                    SELECT jsonb_agg(
                        CASE
                            WHEN elem::text = '"text"' THEN '"paragraph"'::jsonb
                            ELSE elem
                        END
                    )
                    FROM jsonb_array_elements(config::jsonb->'blockRoleFilter') AS elem
                )
            )
        )::json
        WHERE config::jsonb ? 'blockRoleFilter'
          AND config::jsonb->'blockRoleFilter' IS NOT NULL
          AND EXISTS (
            SELECT 1
            FROM jsonb_array_elements(config::jsonb->'blockRoleFilter') AS elem
            WHERE elem::text = '"text"'
          )
    """)
