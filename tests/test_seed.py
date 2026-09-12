import random

from sqlalchemy import text

from app.db import create_db_engine
from app.seed.catalogue import generate_product, generate_batches, seed_catalogue


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


def test_seed_catalogue_rerun_replaces_existing_data():
    test_count = 100
    seed = 20260911

    _, first_count, first_checksum = seed_catalogue(
        count=test_count,
        seed=seed,
    )

    engine = create_db_engine()

    with engine.connect() as connection:
        first_db_count = connection.execute(
            text("SELECT COUNT(*) FROM products")
        ).scalar_one()

    _, second_count, second_checksum = seed_catalogue(
        count=test_count,
        seed=seed,
    )

    with engine.connect() as connection:
        second_db_count = connection.execute(
            text("SELECT COUNT(*) FROM products")
        ).scalar_one()

    assert first_count == test_count
    assert second_count == test_count
    assert first_db_count == test_count
    assert second_db_count == test_count
    assert first_checksum == second_checksum