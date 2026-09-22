# CAT-004 - Composable search filters

## Filter contract

`GET /products/search` requires a keyword and supports optional filters that
narrow the existing keyword-search result:

- `category`
- `min_price`
- `max_price`
- `stock_state`

Filters compose by adding predicates to the same search query. They do not
replace the keyword condition or change the existing `id ASC` result order.
The supported stock-state filter values are `IN_STOCK` and `OUT_OF_STOCK`.
Other stock-state values, including the catalogue's `LOW_STOCK` state, are
outside this ticket's filter contract and are refused with HTTP 400.

Unsupported category values are also refused with HTTP 400 rather than
returning an unfiltered product list.

A price band where `min_price` is greater than `max_price` is also refused
with HTTP 400 and reports both offending values.

## Reference measurement

Reference catalogue size: 500,000 products.

The query-plan investigation used the same broad keyword used by CAT-003:

`Pro`

The filters were added progressively:

1. keyword only
2. keyword + `category = 'Audio'`
3. keyword + category + `price BETWEEN 100.00 AND 1000.00`
4. keyword + category + price + `stock_state = 'IN_STOCK'`

Observed result counts:

| Query shape | Rows returned |
| --- | ---: |
| `Pro` | 100,180 |
| `Pro` + Audio | 10,115 |
| `Pro` + Audio + price 100.00-1000.00 | 3,693 |
| `Pro` + Audio + price 100.00-1000.00 + IN_STOCK | 2,533 |

Each added filter narrowed the result set; no added filter broadened an
earlier result.

## All-filter query plan

The final query was measured using:

`EXPLAIN (ANALYZE, BUFFERS)`

with transaction-scoped:

`SET LOCAL work_mem = '16MB';`

Measured query:

    SELECT
        id,
        sku,
        name,
        category,
        price,
        stock_quantity,
        stock_state
    FROM products
    WHERE name ILIKE '%Pro%'
      AND category = 'Audio'
      AND price >= 100.00
      AND price <= 1000.00
      AND stock_state = 'IN_STOCK'
    ORDER BY id ASC;

Captured plan:

    Gather Merge
      (actual time=163.122..169.805 rows=2533 loops=1)
      Workers Planned: 2
      Workers Launched: 2
      Buffers: shared hit=6927
      -> Sort
           (actual time=154.062..154.163 rows=844 loops=3)
           Sort Key: id
           Sort Method: quicksort  Memory: 111kB
           Buffers: shared hit=6927
           Worker 0: Sort Method: quicksort  Memory: 97kB
           Worker 1: Sort Method: quicksort  Memory: 104kB
           -> Parallel Bitmap Heap Scan on products
                (actual time=12.456..152.992 rows=844 loops=3)
                Recheck Cond: ((name)::text ~~* '%Pro%'::text)
                Filter: ((price >= 100.00)
                         AND (price <= 1000.00)
                         AND ((category)::text = 'Audio'::text)
                         AND ((stock_state)::text = 'IN_STOCK'::text))
                Rows Removed by Filter: 32549
                Heap Blocks: exact=2502
                Buffers: shared hit=6913
                -> Bitmap Index Scan on idx_products_name_trgm
                     (actual time=17.924..17.925 rows=100180 loops=1)
                     Index Cond: ((name)::text ~~* '%Pro%'::text)
                     Buffers: shared hit=18
    Planning:
      Buffers: shared hit=239
    Planning Time: 3.673 ms
    Execution Time: 170.499 ms

## How the filters change database work

The keyword remains the indexed candidate-discovery step. PostgreSQL uses
`idx_products_name_trgm` to identify the 100,180 rows whose names match
`%Pro%`.

The category filter narrows the result from 100,180 rows to 10,115. In the
observed all-filter plan, category is not a separate index lookup; it is part
of the filter applied to rows produced by the keyword-backed bitmap scan.

Adding the price band narrows the observed result further from 10,115 to
3,693 rows. The progressive measurement also caused PostgreSQL to choose a
parallel plan with `Gather Merge`, showing that the planner can change the
execution strategy as additional predicates alter the expected amount of
work.

Adding `stock_state = 'IN_STOCK'` narrows the final result from 3,693 to
2,533 rows. In the captured all-filter plan, category, price, and stock state
are evaluated together during the Parallel Bitmap Heap Scan.

The added filters therefore reduce rows that continue to result
materialization and ordering, but they do not reduce the initial trigram
candidate set in this measured plan. The trigram Bitmap Index Scan still
produces 100,180 keyword candidates.

The final all-filter query completed in 170.499 ms on the 500,000-product
reference catalogue.