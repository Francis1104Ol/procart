"""add bigram search index

Revision ID: 0002
Revises: 947f8603219c
"""

from alembic import op


revision = "0002"
down_revision = "947f8603219c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.name_bigrams(input text)
        RETURNS text[]
        LANGUAGE sql
        IMMUTABLE STRICT PARALLEL SAFE
        AS $$
            SELECT COALESCE(
                array_agg(substr(lower(input), n, 2)),
                ARRAY[]::text[]
            )
            FROM generate_series(1, length(input) - 1) AS n
        $$
        """
    )

    op.execute(
        """
        CREATE INDEX idx_products_name_bigram
        ON products
        USING GIN (name_bigrams(name))
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS idx_products_name_bigram"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.name_bigrams(text)"
    )
