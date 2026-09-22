import importlib
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from app.seed.catalogue import generate_batches, seed_catalogue


@pytest.fixture
def search_client(monkeypatch):
    test_database_url = os.getenv("TEST_DATABASE_URL")

    if not test_database_url:
        pytest.skip(
            "TEST_DATABASE_URL is not set; "
            "search integration tests require a dedicated test database"
        )

    parsed_url = make_url(test_database_url)

    if not parsed_url.database or not parsed_url.database.endswith("_test"):
        pytest.fail(
            "TEST_DATABASE_URL must point to a dedicated "
            "database whose name ends with '_test'"
        )

    monkeypatch.setenv("DATABASE_URL", test_database_url)

    seed_catalogue(
        count=100,
        seed=20260911,
    )

    import app.search
    import app.main

    importlib.reload(app.search)
    importlib.reload(app.main)

    return TestClient(app.main.app)


def test_search_is_case_insensitive(search_client):
    upper = search_client.get(
        "/products/search",
        params={"q": "Q7V"},
    )
    lower = search_client.get(
        "/products/search",
        params={"q": "q7v"},
    )

    assert upper.status_code == 200
    assert lower.status_code == 200

    upper_body = upper.json()
    lower_body = lower.json()

    assert upper_body["count"] == lower_body["count"]
    assert upper_body["products"] == lower_body["products"]


def test_search_returns_known_rare_matches(search_client):
    response = search_client.get(
        "/products/search",
        params={"q": "Q7V"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["query"] == "Q7V"
    assert body["count"] == 7
    assert len(body["products"]) == 7

    for product in body["products"]:
        assert "q7v" in product["name"].lower()


def test_search_matches_substring_anywhere(search_client):
    batches = list(
        generate_batches(
            count=100,
            seed=20260911,
        )
    )

    seeded_products = [
        row
        for batch in batches
        for row in batch
    ]

    target = seeded_products[20]
    target_id = target[0]
    target_name = target[2]

    # Take characters from inside the product name rather than
    # from its beginning, proving leading-wildcard substring search.
    substring = target_name[2:7]

    assert substring
    assert len(substring) >= 3
    assert not target_name.lower().startswith(substring.lower())

    response = search_client.get(
        "/products/search",
        params={"q": substring},
    )

    assert response.status_code == 200

    body = response.json()

    returned_ids = {
        product["id"]
        for product in body["products"]
    }

    assert target_id in returned_ids

    for product in body["products"]:
        assert substring.lower() in product["name"].lower()


def test_search_uses_stable_id_order(search_client):
    first = search_client.get(
        "/products/search",
        params={"q": "Q7V"},
    )
    second = search_client.get(
        "/products/search",
        params={"q": "Q7V"},
    )

    assert first.status_code == 200
    assert second.status_code == 200

    first_products = first.json()["products"]
    second_products = second.json()["products"]

    first_ids = [
        product["id"]
        for product in first_products
    ]
    second_ids = [
        product["id"]
        for product in second_products
    ]

    assert first_ids == sorted(first_ids)
    assert first_ids == second_ids


def test_search_no_match_returns_empty_result_shape(search_client):
    response = search_client.get(
        "/products/search",
        params={"q": "zzzz-not-found"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "query": "zzzz-not-found",
        "count": 0,
        "products": [],
    }


def test_search_rejects_blank_query(search_client):
    response = search_client.get(
        "/products/search",
        params={"q": "   "},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Search keyword must not be empty."
    }


def test_search_rejects_missing_query(search_client):
    response = search_client.get(
        "/products/search",
    )

    assert response.status_code == 422


def test_search_accepts_two_character_keyword(search_client):
    response = search_client.get(
        "/products/search",
        params={"q": "Pr"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["query"] == "Pr"
    assert body["count"] > 0

    ids = [
        product["id"]
        for product in body["products"]
    ]

    assert ids == sorted(ids)

    for product in body["products"]:
        assert "pr" in product["name"].lower()


def test_search_treats_single_percent_as_literal(search_client):
    from sqlalchemy import text

    from app.db import create_db_engine

    engine = create_db_engine()

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO products (
                    sku,
                    name,
                    category,
                    price,
                    stock_quantity,
                    stock_state
                )
                VALUES
                    (
                        'TEST-SINGLE-PERCENT-001',
                        'Discount % Special',
                        'Electronics',
                        19.99,
                        5,
                        'IN_STOCK'
                    ),
                    (
                        'TEST-SINGLE-PERCENT-002',
                        'Discount Special',
                        'Electronics',
                        19.99,
                        5,
                        'IN_STOCK'
                    )
                """
            )
        )

    response = search_client.get(
        "/products/search",
        params={"q": "%"},
    )

    assert response.status_code == 200

    names = [
        product["name"]
        for product in response.json()["products"]
    ]

    assert "Discount % Special" in names
    assert "Discount Special" not in names

    for name in names:
        assert "%" in name


def test_search_treats_single_underscore_as_literal(search_client):
    from sqlalchemy import text

    from app.db import create_db_engine

    engine = create_db_engine()

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO products (
                    sku,
                    name,
                    category,
                    price,
                    stock_quantity,
                    stock_state
                )
                VALUES
                    (
                        'TEST-SINGLE-UNDERSCORE-001',
                        'Model_X Product',
                        'Electronics',
                        19.99,
                        5,
                        'IN_STOCK'
                    ),
                    (
                        'TEST-SINGLE-UNDERSCORE-002',
                        'ModelAX Product',
                        'Electronics',
                        19.99,
                        5,
                        'IN_STOCK'
                    )
                """
            )
        )

    response = search_client.get(
        "/products/search",
        params={"q": "_"},
    )

    assert response.status_code == 200

    names = [
        product["name"]
        for product in response.json()["products"]
    ]

    assert "Model_X Product" in names
    assert "ModelAX Product" not in names

    for name in names:
        assert "_" in name


def test_search_treats_percent_as_literal_in_valid_keyword(
    search_client,
):
    from sqlalchemy import text

    from app.db import create_db_engine

    engine = create_db_engine()

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO products (
                    sku,
                    name,
                    category,
                    price,
                    stock_quantity,
                    stock_state
                )
                VALUES
                    (
                        'TEST-PERCENT-001',
                        'Save 50% Today',
                        'Electronics',
                        19.99,
                        5,
                        'IN_STOCK'
                    ),
                    (
                        'TEST-PERCENT-002',
                        'Save 50 Dollars Today',
                        'Electronics',
                        19.99,
                        5,
                        'IN_STOCK'
                    )
                """
            )
        )

    response = search_client.get(
        "/products/search",
        params={"q": "50%"},
    )

    assert response.status_code == 200

    body = response.json()

    names = [
        product["name"]
        for product in body["products"]
    ]

    assert "Save 50% Today" in names
    assert "Save 50 Dollars Today" not in names


def test_search_treats_underscore_as_literal_in_valid_keyword(
    search_client,
):
    from sqlalchemy import text

    from app.db import create_db_engine

    engine = create_db_engine()

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO products (
                    sku,
                    name,
                    category,
                    price,
                    stock_quantity,
                    stock_state
                )
                VALUES
                    (
                        'TEST-UNDERSCORE-001',
                        'abc_def product',
                        'Electronics',
                        19.99,
                        5,
                        'IN_STOCK'
                    ),
                    (
                        'TEST-UNDERSCORE-002',
                        'abcXdef product',
                        'Electronics',
                        19.99,
                        5,
                        'IN_STOCK'
                    )
                """
            )
        )

    response = search_client.get(
        "/products/search",
        params={"q": "abc_def"},
    )

    assert response.status_code == 200

    body = response.json()

    names = [
        product["name"]
        for product in body["products"]
    ]

    assert "abc_def product" in names
    assert "abcXdef product" not in names


def test_escape_like_pattern_escapes_pattern_metacharacters():
    from app.search import escape_like_pattern

    assert (
        escape_like_pattern(r"50%_off\sale")
        == r"50\%\_off\\sale"
    )
def test_search_filters_by_category(search_client):
    response = search_client.get(
        "/products/search",
        params={
            "q": "Pro",
            "category": "Electronics",
        },
    )

    assert response.status_code == 200

    products = response.json()["products"]

    assert products

    for product in products:
        assert "pro" in product["name"].lower()
        assert product["category"] == "Electronics"


def test_search_filters_by_price_band(search_client):
    response = search_client.get(
        "/products/search",
        params={
            "q": "Pro",
            "min_price": "100.00",
            "max_price": "500.00",
        },
    )

    assert response.status_code == 200

    products = response.json()["products"]

    assert products

    for product in products:
        price = float(product["price"])

        assert "pro" in product["name"].lower()
        assert 100.00 <= price <= 500.00


def test_search_filters_by_stock_state(search_client):
    response = search_client.get(
        "/products/search",
        params={
            "q": "Pro",
            "stock_state": "IN_STOCK",
        },
    )

    assert response.status_code == 200

    products = response.json()["products"]

    assert products

    for product in products:
        assert "pro" in product["name"].lower()
        assert product["stock_state"] == "IN_STOCK"
def test_search_combines_category_and_price_filters(search_client):
    response = search_client.get(
        "/products/search",
        params={
            "q": "Pro",
            "category": "Electronics",
            "min_price": "100.00",
            "max_price": "1000.00",
        },
    )

    assert response.status_code == 200

    products = response.json()["products"]

    assert products

    for product in products:
        price = float(product["price"])

        assert "pro" in product["name"].lower()
        assert product["category"] == "Electronics"
        assert 100.00 <= price <= 1000.00


def test_search_combines_category_and_price_filters(search_client):
    from sqlalchemy import text

    from app.db import create_db_engine

    engine = create_db_engine()

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO products (
                    sku,
                    name,
                    category,
                    price,
                    stock_quantity,
                    stock_state
                )
                VALUES
                    (
                        'TEST-FILTER-COMBO-001',
                        'FilterCombo Pro Laptop',
                        'Electronics',
                        250.00,
                        10,
                        'IN_STOCK'
                    ),
                    (
                        'TEST-FILTER-COMBO-002',
                        'FilterCombo Pro Laptop',
                        'Electronics',
                        1500.00,
                        10,
                        'IN_STOCK'
                    ),
                    (
                        'TEST-FILTER-COMBO-003',
                        'FilterCombo Pro Laptop',
                        'Gaming',
                        250.00,
                        10,
                        'IN_STOCK'
                    )
                """
            )
        )

    response = search_client.get(
        "/products/search",
        params={
            "q": "FilterCombo",
            "category": "Electronics",
            "min_price": "100.00",
            "max_price": "1000.00",
        },
    )

    assert response.status_code == 200

    products = response.json()["products"]

    assert len(products) == 1
    assert products[0]["sku"] == "TEST-FILTER-COMBO-001"
    assert products[0]["category"] == "Electronics"
    assert products[0]["price"] == "250.00"

def test_search_combines_price_and_stock_filters(search_client):
    response = search_client.get(
        "/products/search",
        params={
            "q": "Pro",
            "min_price": "100.00",
            "max_price": "1000.00",
            "stock_state": "IN_STOCK",
        },
    )

    assert response.status_code == 200

    products = response.json()["products"]

    assert products

    for product in products:
        price = float(product["price"])

        assert "pro" in product["name"].lower()
        assert 100.00 <= price <= 1000.00
        assert product["stock_state"] == "IN_STOCK"


def test_search_combines_all_three_filters(search_client):
    from sqlalchemy import text

    from app.db import create_db_engine

    engine = create_db_engine()

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO products (
                    sku,
                    name,
                    category,
                    price,
                    stock_quantity,
                    stock_state
                )
                VALUES
                    (
                        'TEST-ALL-FILTERS-001',
                        'AllFilters Pro Laptop',
                        'Electronics',
                        250.00,
                        10,
                        'IN_STOCK'
                    ),
                    (
                        'TEST-ALL-FILTERS-002',
                        'AllFilters Pro Laptop',
                        'Electronics',
                        250.00,
                        0,
                        'OUT_OF_STOCK'
                    ),
                    (
                        'TEST-ALL-FILTERS-003',
                        'AllFilters Pro Laptop',
                        'Electronics',
                        1500.00,
                        10,
                        'IN_STOCK'
                    ),
                    (
                        'TEST-ALL-FILTERS-004',
                        'AllFilters Pro Laptop',
                        'Gaming',
                        250.00,
                        10,
                        'IN_STOCK'
                    )
                """
            )
        )

    response = search_client.get(
        "/products/search",
        params={
            "q": "AllFilters",
            "category": "Electronics",
            "min_price": "100.00",
            "max_price": "1000.00",
            "stock_state": "IN_STOCK",
        },
    )

    assert response.status_code == 200

    products = response.json()["products"]

    assert len(products) == 1
    assert products[0]["sku"] == "TEST-ALL-FILTERS-001"
    assert products[0]["category"] == "Electronics"
    assert products[0]["price"] == "250.00"
    assert products[0]["stock_state"] == "IN_STOCK"
def test_adding_filter_never_broadens_results(search_client):
    category_response = search_client.get(
        "/products/search",
        params={
            "q": "Pro",
            "category": "Electronics",
        },
    )

    combined_response = search_client.get(
        "/products/search",
        params={
            "q": "Pro",
            "category": "Electronics",
            "stock_state": "IN_STOCK",
        },
    )

    assert category_response.status_code == 200
    assert combined_response.status_code == 200

    category_ids = {
        product["id"]
        for product in category_response.json()["products"]
    }
    combined_ids = {
        product["id"]
        for product in combined_response.json()["products"]
    }

    assert combined_ids
    assert combined_ids <= category_ids
def test_search_rejects_unsupported_category(search_client):
    response = search_client.get(
        "/products/search",
        params={
            "q": "Pro",
            "category": "elektronik",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Filter 'category' does not support value 'elektronik'"
    }


def test_search_rejects_unsupported_stock_state(search_client):
    response = search_client.get(
        "/products/search",
        params={
            "q": "Pro",
            "stock_state": "UNKNOWN",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Filter 'stock_state' does not support value 'UNKNOWN'"
    }
def test_search_rejects_price_band_when_min_exceeds_max(search_client):
    response = search_client.get(
        "/products/search",
        params={
            "q": "Pro",
            "min_price": "500.00",
            "max_price": "100.00",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": (
            "Filter 'price' does not support values "
            "min_price='500.00', max_price='100.00'"
        )
    }
def test_search_filters_by_out_of_stock_state(search_client):
    response = search_client.get(
        "/products/search",
        params={
            "q": "Pro",
            "stock_state": "OUT_OF_STOCK",
        },
    )

    assert response.status_code == 200

    products = response.json()["products"]
    assert products

    for product in products:
        assert "pro" in product["name"].lower()
        assert product["stock_state"] == "OUT_OF_STOCK"


def test_search_rejects_low_stock_as_unsupported_filter(search_client):
    response = search_client.get(
        "/products/search",
        params={
            "q": "Pro",
            "stock_state": "LOW_STOCK",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": (
            "Filter 'stock_state' does not support value 'LOW_STOCK'"
        )
    }