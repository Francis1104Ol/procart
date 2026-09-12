import os
import random

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.db import create_db_engine
from app.seed.catalogue import (
    generate_batches,
    generate_product,
    seed_catalogue,
)


@pytest.fixture
def isolated_test_database(monkeypatch):
    test_database_url = os.getenv("TEST_DATABASE_URL")

    if not test_database_url:
        pytest.skip(
            "TEST_DATABASE_URL is not set; "
            "seed integration tests require a dedicated test database"
        )

    parsed_url = make_url(test_database_url)

    if not parsed_url.database or not parsed_url.database.endswith("_test"):
        pytest.fail(
            "TEST_DATABASE_URL must point to a dedicated "
            "database whose name ends with '_test'"
        )

    # seed_catalogue() reads DATABASE_URL, so redirect it to the
    # explicitly configured disposable test database.
    monkeypatch.setenv("DATABASE_URL", test_database_url)

    return test_database_url


def test_seed_generation_is_deterministic():
    first_rng = random.Random(20260911)
    second_rng = random.Random(20260911)

    assert generate_product(8, first_rng) == generate_product(8, second_rng)


def test_seed_has_stable_common_and_rare_search_tokens():
    rows = list(generate_batches(count=20, seed=20260911))
    products = [row for batch in rows for row in batch]

    rare_matches = [row for row in products if "Q7V" in row[2]]
    common_matches = [row for row in products if "Pro" in row[2]]

    assert len(rare_matches) == 7
    assert len(common_matches) > 0


def test_seed_catalogue_rerun_replaces_existing_data(
    isolated_test_database,
):
    test_count = 100
    seed = 20260911

    _, first_count, first_checksum = seed_catalogue(
        count=test_count,
        seed=seed,
    )

    _, second_count, second_checksum = seed_catalogue(
        count=test_count,
        seed=seed,
    )

    engine = create_db_engine()

    with engine.connect() as connection:
        database_count = connection.execute(
            text("SELECT COUNT(*) FROM products")
        ).scalar_one()

    assert first_count == test_count
    assert second_count == test_count
    assert database_count == test_count
    assert first_checksum == second_checksum


def test_seed_catalogue_resynchronizes_identity_sequence(
    isolated_test_database,
):
    test_count = 100
    seed = 20260911

    seed_catalogue(
        count=test_count,
        seed=seed,
    )

    engine = create_db_engine()

    with engine.begin() as connection:
        inserted_id = connection.execute(
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
                VALUES (
                    'TEST-SEQUENCE-0001',
                    'Sequence Regression Product',
                    'Electronics',
                    19.99,
                    1,
                    'LOW_STOCK'
                )
                RETURNING id
                """
            )
        ).scalar_one()

    assert inserted_id == test_count + 1