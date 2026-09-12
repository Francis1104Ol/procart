from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import ORJSONResponse
from sqlalchemy import select, text

from app.db import create_db_engine
from app.models.product import Product


router = APIRouter()
engine = create_db_engine()


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
def search_products(q: str = Query(...)):
    keyword = q.strip()

    if not keyword:
        raise HTTPException(
            status_code=400,
            detail="Search keyword must not be empty.",
        )
    if len(keyword) < 3:
        raise HTTPException(
        status_code=400,
        detail="Search keyword must be at least 3 characters.",
    )
    escaped_keyword = escape_like_pattern(keyword)

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
        .where(
            Product.name.ilike(
                f"%{escaped_keyword}%",
                escape="\\",
            )
        )
        .order_by(Product.id.asc())
    )

    with engine.connect() as connection:
        connection.execute(
            text("SET LOCAL work_mem = '16MB'")
        )
        rows = connection.execute(statement).mappings().all()

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