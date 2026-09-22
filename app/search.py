from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import ORJSONResponse
from sqlalchemy import func, select, text

from app.db import create_db_engine
from app.models.product import Product
from app.seed.catalogue import CATEGORIES

router = APIRouter()
engine = create_db_engine()

SUPPORTED_STOCK_STATES = {
    "IN_STOCK",
    "OUT_OF_STOCK",
}


def escape_like_pattern(value: str) -> str:
    return (
        value
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


@router.get(
    "/products/search",
    response_class=ORJSONResponse,
)
def search_products(
    q: str = Query(...),
    category: str | None = Query(default=None),
    min_price: Decimal | None = Query(default=None),
    max_price: Decimal | None = Query(default=None),
    stock_state: str | None = Query(default=None),
):
    keyword = q.strip()

    if not keyword:
        raise HTTPException(
            status_code=400,
            detail="Search keyword must not be empty.",
        )

    if category is not None and category not in CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Filter 'category' does not support value "
                f"'{category}'"
            ),
        )

    if (
        stock_state is not None
        and stock_state not in SUPPORTED_STOCK_STATES
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Filter 'stock_state' does not support value "
                f"'{stock_state}'"
            ),
        )

    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Filter 'price' does not support values "
                f"min_price='{min_price}', "
                f"max_price='{max_price}'"
            ),
        )

    escaped_keyword = escape_like_pattern(keyword)

    conditions = [
        Product.name.ilike(
            f"%{escaped_keyword}%",
            escape="\\",
        )
    ]

    if len(keyword) == 2:
        conditions.insert(
            0,
            func.name_bigrams(Product.name).op("@>")(
                [keyword.lower()]
            ),
        )

    if category is not None:
        conditions.append(
            Product.category == category
        )

    if min_price is not None:
        conditions.append(
            Product.price >= min_price
        )

    if max_price is not None:
        conditions.append(
            Product.price <= max_price
        )

    if stock_state is not None:
        conditions.append(
            Product.stock_state == stock_state
        )

    statement = (
        select(
            Product.id,
            Product.sku,
            Product.name,
            Product.category,
            Product.price,
            Product.stock_quantity,
            Product.stock_state,
        )
        .where(*conditions)
        .order_by(Product.id.asc())
    )

    with engine.connect() as connection:
        connection.execute(
            text("SET LOCAL work_mem = '16MB'")
        )
        rows = (
            connection
            .execute(statement)
            .mappings()
            .all()
        )

    products = [
        {
            "id": row["id"],
            "sku": row["sku"],
            "name": row["name"],
            "category": row["category"],
            "price": str(row["price"]),
            "stock_quantity": row["stock_quantity"],
            "stock_state": row["stock_state"],
        }
        for row in rows
    ]

    return ORJSONResponse(
        content={
            "query": keyword,
            "count": len(products),
            "products": products,
        }
    )