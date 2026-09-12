# CAT-003 — Keyword Search Over Product Names

## Search semantics

Endpoint:

`GET /products/search?q=<keyword>`

Search performs a case-insensitive literal substring match over `products.name`.

Characters that are meaningful to SQL `LIKE` / `ILIKE`, including `%`, `_`,
and the escape character `\`, are escaped before the pattern is constructed.
This means shopper input is interpreted as literal search text rather than
as an SQL pattern.

A blank keyword is rejected with HTTP 400. A missing query parameter is
rejected with HTTP 422.

## Stable ordering

Search results are returned in ascending product ID order:

`ORDER BY products.id ASC`

Product ID is unique, so repeated searches against unchanged catalogue data
produce the same ordering.

## Full-size benchmark

Reference catalogue size: 500,000 products.

Broad benchmark query:

`Pro`

Matches:

100,180 products.

Final measured database execution time:

328.551 ms

This is below the CAT-003 database-query target of one second.

The full unpaginated HTTP response is substantially larger: the broad query
returns approximately 15.75 MB of JSON and was measured at approximately
1.31–2.04 seconds end-to-end. Pagination is intentionally deferred to
CAT-005.

## Final query plan

The production search query was measured using:

`EXPLAIN (ANALYZE, BUFFERS)`

with transaction-scoped:

`SET LOCAL work_mem = '16MB';`

Captured plan:

    Sort  (cost=18246.38..18498.91 rows=101010 width=75)
          (actual time=315.279..321.784 rows=100180 loops=1)
      Sort Key: id
      Sort Method: quicksort  Memory: 13336kB
      Buffers: shared hit=6913
      -> Bitmap Heap Scan on products
           (actual time=16.577..279.711 rows=100180 loops=1)
           Recheck Cond: ((name)::text ~~* '%Pro%'::text)
           Heap Blocks: exact=6895
           Buffers: shared hit=6913
           -> Bitmap Index Scan on idx_products_name_trgm
                (actual time=15.311..15.311 rows=100180 loops=1)
                Index Cond: ((name)::text ~~* '%Pro%'::text)
                Buffers: shared hit=18
    Planning Time: 0.542 ms
    Execution Time: 328.551 ms

## Index behaviour

`products.name` has a PostgreSQL `pg_trgm` GIN index:

    CREATE INDEX idx_products_name_trgm
    ON products
    USING GIN (name gin_trgm_ops);

An ordinary B-tree index cannot efficiently seek an arbitrary contains
pattern such as `%Pro%` because the search begins with a wildcard.

The trigram GIN index can efficiently narrow substring searches when the
literal search text contains extractable trigrams. Three consecutive
characters are required to form a trigram, so a one- or two-character search
term does not provide a normal search trigram for the index to use to narrow
candidates. PostgreSQL may therefore need to inspect substantially more data
for those searches.

The GIN index also does not provide the required `id ASC` ordering. Matching
rows are sorted separately.

The broad `Pro` query demonstrates the indexed three-character case:
PostgreSQL selected a Bitmap Index Scan on `idx_products_name_trgm`, followed
by a Bitmap Heap Scan and an in-memory quicksort by product ID.

## Short-keyword boundary

A two-character search was also measured:

`Pr`

Captured plan:

    Index Scan using products_pkey on products
      (actual time=0.443..1747.173 rows=200137 loops=1)
      Filter: ((name)::text ~~* '%Pr%'::text)
      Rows Removed by Filter: 299863
      Buffers: shared hit=8264
    Planning Time: 4.436 ms
    Execution Time: 1771.276 ms

For this two-character query, PostgreSQL did not use the trigram GIN index to
narrow the search. The query scanned products in primary-key order and applied
the ILIKE filter to the full catalogue.

This contrasts with the three-character `Pro` query, where PostgreSQL used the
GIN trigram index and completed in 328.551 ms.

This demonstrates the practical lower-bound behaviour of trigram search:
three-character terms can produce a normal trigram for index-assisted
candidate narrowing, while shorter terms may require scanning substantially
more of the table.