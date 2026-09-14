import argparse
import csv
import hashlib
import io
import random
import time
from collections.abc import Iterator

from app.db import create_db_engine
from app.models.product import Base


DEFAULT_COUNT = 500_000
DEFAULT_SEED = 20260911
BATCH_SIZE = 10_000

KNOWN_BASELINE_CHECKSUM = (
    "bca00325a446bacde186940ee729fd39ba3c44d2f425369fa90bfaee55b96fb6"
)

CATEGORIES = (
    "Electronics",
    "Phones",
    "Laptops",
    "Audio",
    "Accessories",
    "Home Appliances",
    "Office Equipment",
    "Gaming",
    "Cameras",
    "Wearables",
)

COMMON_WORDS = (
    "Pro",
    "Smart",
    "Plus",
    "Wireless",
    "Premium",
)

PRODUCT_TYPES = (
    "Adapter",
    "Speaker",
    "Keyboard",
    "Mouse",
    "Monitor",
    "Headphones",
    "Camera",
    "Tablet",
    "Router",
    "Charger",
)


def generate_product(product_id: int, rng: random.Random) -> tuple:
    category = CATEGORIES[rng.randrange(len(CATEGORIES))]
    product_type = PRODUCT_TYPES[rng.randrange(len(PRODUCT_TYPES))]

    # Seven deliberately rare names make a stable handful-match search case.
    if product_id <= 7:
        name = f"Q7V {product_type} {product_id}"
    else:
        common_word = COMMON_WORDS[rng.randrange(len(COMMON_WORDS))]
        name = (
            f"{common_word} {product_type} "
            f"{category} {product_id:06d}"
        )

    # Keep prices in a realistic retail range while remaining deterministic.
    price_cents = 1_999 + rng.randrange(0, 249_802)
    price = f"{price_cents / 100:.2f}"

    stock_quantity = rng.choices(
        population=(0, 1, 2, 5, 10, 25, 50, 100),
        weights=(8, 6, 8, 10, 18, 18, 16, 16),
        k=1,
    )[0]

    if stock_quantity == 0:
        stock_state = "OUT_OF_STOCK"
    elif stock_quantity <= 5:
        stock_state = "LOW_STOCK"
    else:
        stock_state = "IN_STOCK"

    sku = f"PC-{product_id:07d}"

    return (
        product_id,
        sku,
        name,
        category,
        price,
        stock_quantity,
        stock_state,
    )


def generate_batches(
    count: int,
    seed: int,
) -> Iterator[list[tuple]]:
    rng = random.Random(seed)
    batch: list[tuple] = []

    for product_id in range(1, count + 1):
        batch.append(generate_product(product_id, rng))

        if len(batch) == BATCH_SIZE:
            yield batch
            batch = []

    if batch:
        yield batch


def _batch_as_csv(rows: list[tuple]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(rows)
    return buffer.getvalue()


def seed_catalogue(
    count: int = DEFAULT_COUNT,
    seed: int = DEFAULT_SEED,
) -> tuple[float, int, str]:
    if count < 1:
        raise ValueError("count must be at least 1")

    engine = create_db_engine()
    started = time.perf_counter()

    Base.metadata.create_all(engine)

    checksum = hashlib.sha256()

    with engine.raw_connection() as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "TRUNCATE TABLE products RESTART IDENTITY"
                )

                for batch in generate_batches(count, seed):
                    csv_data = _batch_as_csv(batch)
                    checksum.update(csv_data.encode("utf-8"))

                    with cursor.copy(
                        "COPY products "
                        "(id, sku, name, category, price, "
                        "stock_quantity, stock_state) "
                        "FROM STDIN WITH (FORMAT CSV)"
                    ) as copy:
                        copy.write(csv_data)

                # COPY uses explicit IDs, so synchronize the sequence
                # with the highest seeded product ID.
                cursor.execute(
                    """
                    SELECT setval(
                        pg_get_serial_sequence('products', 'id'),
                        COALESCE(
                            (SELECT MAX(id) FROM products),
                            1
                        ),
                        true
                    )
                    """
                )

                cursor.execute("SELECT COUNT(*) FROM products")
                actual_count = cursor.fetchone()[0]

            dataset_checksum = checksum.hexdigest()

            if count == DEFAULT_COUNT and seed == DEFAULT_SEED:
                if dataset_checksum != KNOWN_BASELINE_CHECKSUM:
                    raise RuntimeError(
                        "Default catalogue checksum changed unexpectedly: "
                        f"{dataset_checksum}"
                    )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    elapsed = time.perf_counter() - started

    return elapsed, actual_count, dataset_checksum

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the ProCart catalogue"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
    )

    args = parser.parse_args()

    elapsed, actual_count, checksum = seed_catalogue(
        count=args.count,
        seed=args.seed,
    )

    print("Catalogue seed complete")
    print(f"Requested products: {args.count}")
    print(f"Actual products: {actual_count}")
    print(f"Seed: {args.seed}")
    print(f"Dataset checksum: {checksum}")
    print(f"Generation time: {elapsed:.2f} seconds")


if __name__ == "__main__":
    main()