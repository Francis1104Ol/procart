"""create products table

Revision ID: 0001
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "sku",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "price",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            "stock_quantity",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "stock_state",
            sa.String(length=16),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "sku",
            name="uq_products_sku",
        ),
    )


def downgrade() -> None:
    op.drop_table("products")