import random

from app.seed.catalogue import generate_product, generate_batches


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
