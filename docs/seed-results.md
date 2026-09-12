# CAT-002 Seed Results

The catalogue seed is deterministic and replaces the existing catalogue contents. Re-running the same seed therefore reproduces the same products and count instead of doubling the dataset.

## Seed Command

Start the Docker environment:

```powershell
docker compose up -d --build
```

Run the 500,000-product seed:

```powershell
docker compose exec api python -m app.seed.catalogue --count 500000 --seed 20260911
```

The command reports:

- requested product count
- actual product count
- seed value
- dataset checksum
- generation time

## Measured Baseline

The 500,000-product seed was executed repeatedly using the same seed value.

| Dataset | Products | Seed | Dataset checksum | Generation time | Environment |
|---|---:|---:|---|---:|---|
| Baseline run 1 | 500,000 | 20260911 | `bca00325a446bacde186940ee729fd39ba3c44d2f425369fa90bfaee55b96fb6` | 12.62 seconds | Local Docker Compose environment |
| Baseline run 2 | 500,000 | 20260911 | `bca00325a446bacde186940ee729fd39ba3c44d2f425369fa90bfaee55b96fb6` | 13.73 seconds | Local Docker Compose environment |
| Final verification run | 500,000 | 20260911 | `bca00325a446bacde186940ee729fd39ba3c44d2f425369fa90bfaee55b96fb6` | 10.39 seconds | Local Docker Compose environment |

All measured runs completed well below the CAT-002 limit of 10 minutes.

## Re-run Verification

The seed command was executed multiple times with the same product count and seed.

Each run produced:

- 500,000 products
- seed `20260911`
- identical dataset checksum
- the same catalogue size

The identical count and checksum demonstrate that re-running the seed reproduces the same catalogue rather than appending another 500,000 products or changing the generated dataset.

The default 500,000-product baseline also has a known checksum:

```text
bca00325a446bacde186940ee729fd39ba3c44d2f425369fa90bfaee55b96fb6
```

The seed implementation verifies this checksum before committing the default baseline. If the generated dataset changes unexpectedly, the seed raises an error and the database transaction is rolled back.

## PostgreSQL Sequence Verification

The seed uses PostgreSQL `COPY` with explicit product IDs.

After the copy completes, the product ID sequence is synchronized with the highest seeded ID so that subsequent inserts do not reuse an existing ID.

The sequence was verified after the final 500,000-product seed:

```text
last_value | is_called
-----------+----------
500000     | t
```

This confirms that the next automatically generated product ID will follow the seeded catalogue rather than collide with an existing product.

## Search Distribution Verification

The generated names deliberately contain common words and a deliberately rare token.

Observed against the 500,000-product catalogue:

- Common term `Pro` → 100,180 matches
- Rare term `Q7V` → 7 matches

The common term provides a search case matching thousands of rows, while the rare term provides a stable search case matching only a handful.

These cases provide known workloads for CAT-003 search verification.

## Category Distribution Verification

Observed category distribution:

| Category | Products |
|---|---:|
| Phones | 50,467 |
| Wearables | 50,318 |
| Home Appliances | 50,167 |
| Laptops | 50,061 |
| Audio | 49,988 |
| Electronics | 49,981 |
| Office Equipment | 49,873 |
| Gaming | 49,776 |
| Accessories | 49,701 |
| Cameras | 49,668 |

All ten categories contain approximately 50,000 products, providing substantial datasets for category filtering.

## Price Distribution Verification

Observed price values:

- Minimum price: `19.99`
- Maximum price: `2517.98`
- Average price: approximately `1270.26`

The broad price range provides multiple price bands for later filter testing.

## Stock State Distribution Verification

Observed stock-state distribution:

| Stock state | Products |
|---|---:|
| `IN_STOCK` | 339,920 |
| `LOW_STOCK` | 120,137 |
| `OUT_OF_STOCK` | 39,943 |

Every stock state contains tens of thousands of products, providing meaningful cases for stock-state filtering.

## Automated Verification

The project test suite currently passes:

```text
5 passed
```

The seed integration test executes the seed against PostgreSQL twice and verifies that:

- the requested product count is preserved
- re-running the seed does not double the catalogue
- both executions produce the same checksum

## Acceptance Criteria Evidence

1. **At least 500,000 products:** verified with an actual count of 500,000.
2. **Repeatable seed:** repeated runs produced the same 500,000-product count and identical dataset checksum.
3. **Search-name distribution:** `Pro` matched 100,180 products while `Q7V` matched 7.
4. **Filterable data distribution:** ten categories, a `19.99`–`2517.98` price range, and three populated stock states were verified against PostgreSQL.
5. **Seed completes under 10 minutes:** measured runs completed in 10.39–13.73 seconds, far below the 10-minute limit.