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