from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import ORJSONResponse
from sqlalchemy import func, select, text

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
