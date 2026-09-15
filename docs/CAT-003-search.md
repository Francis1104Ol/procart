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

The current implementation temporarily rejects keywords shorter than three
characters with HTTP 400. This restriction was introduced after the original
two-character `Pr` query exceeded the one-second performance target.

The three-character minimum is not treated as an agreed product contract.
Subsequent investigation demonstrated that two-character search can meet the
target using an experimental bigram indexing strategy. The short-keyword
design therefore remains under evaluation rather than being presented as a
settled acceptance-criteria change.
## Full-size benchmark

Reference catalogue size: 500,000 products.

Broad benchmark query:

`Pro`

Matches:

100,180 products.

Final measured database execution time:

328.551 ms

The broad three-character `Pro` query completed in 328.551 ms at the full
500,000-row reference seed, below the one-second database-query target.

This measurement demonstrates the performance of the existing trigram-backed
path for this broad three-character query. It does not establish a general
minimum keyword length or imply that shorter searches are inherently unable
to meet the target.

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

## Short-keyword performance investigation

The initial implementation used the same `ILIKE '%keyword%'` search shape for
all keyword lengths.

At the full 500,000-product reference seed, a two-character search for `Pr`
returned 200,137 products but exceeded the one-second database-query target.

Captured baseline:

    Index Scan using products_pkey on products
      Filter: ((name)::text ~~* '%Pr%'::text)
      Rows Removed by Filter: 299863
    Execution Time: 2402.741 ms

PostgreSQL could not use the existing trigram GIN index for normal candidate
narrowing because the two-character search term did not provide a usable
three-character trigram.

This initially motivated a proposed minimum search length of three characters.
The minimum was then investigated as a product trade-off rather than assumed
to be necessary.

### Broad-result cost isolation

The broad single-character `P` case was further measured using a count-only
query to separate match discovery from full result materialization and
ordering.

The query:

    SELECT count(*)
    FROM products
    WHERE name ILIKE '%P%';

returned the same 416,584 matches with:

    Execution Time: 357.801 ms

By comparison, returning all 416,584 complete product rows in stable `id ASC`
order measured:

    Execution Time: 1178.558 ms

This indicates that the observed one-second breach is not solely the cost of
finding rows that contain `P`. A substantial part of the full-query workload
comes from materializing and returning an extremely large unpaginated result
set while preserving stable ordering.

Pagination is outside CAT-003 and is owned by CAT-005. This measurement is
therefore recorded as a boundary of the current unpaginated search shape
rather than evidence that all single-character matching is inherently slow.

### Two-character alternative

An experimental bigram representation was tested to determine whether
two-character substring searches could remain supported.

The experiment generated overlapping two-character sequences from the
lower-cased product name and created a GIN index over those sequences.

For example:

    ProCart -> {pr,ro,oc,ca,ar,rt}

Experimental index size:

    18 MB

The query used the bigram index for candidate narrowing while retaining the
original `ILIKE '%Pr%'` predicate as the final correctness check.

The captured plan included:

    Bitmap Index Scan on idx_products_name_bigram_test
      Index Cond: (name_bigrams((name)::text) @> '{pr}'::text[])

    Bitmap Heap Scan on products
      Recheck Cond: (name_bigrams((name)::text) @> '{pr}'::text[])
      Filter: ((name)::text ~~* '%Pr%'::text)

    Sort
      Sort Key: id
      Sort Method: quicksort

Three complete measurements were:

    766.909 ms
    690.840 ms
    615.604 ms

All three were below the one-second database-query target.

This demonstrates that the measured two-character `Pr` case can meet the
current 500,000-row database-query target with a different indexing strategy.
It therefore weakens the case for rejecting all two-character searches solely
because the existing trigram index cannot narrow them. A short-keyword
indexing strategy can preserve two-character search, although it introduces
additional index storage and write/maintenance cost that must be considered.

### One-character behaviour

Single-character searches were also measured to determine whether keyword
length itself was the limiting factor.

A broad search for `P` returned 416,584 of the 500,000 products and produced:

    Execution Time: 1178.558 ms

This exceeded the one-second target.

A less-common single-character search for `Q` returned 49,880 products and
produced:

    Execution Time: 537.638 ms

This was below the target.

The difference shows that one-character performance is strongly affected by
result cardinality rather than keyword length alone.

For the broad `P` query, PostgreSQL selected a primary-key scan that preserved
the required `id ASC` ordering while applying the `ILIKE` filter.

A forced sequential-scan and sort alternative was also measured:

    Seq Scan on products
      Filter: ((name)::text ~~* '%P%'::text)

    Sort
      Sort Key: id
      Sort Method: quicksort

    Execution Time: 1303.811 ms

This was slower than PostgreSQL's normal 1178.558 ms plan and was rejected as
an optimization.

### Current conclusion

The evidence does not support treating a three-character minimum as a
necessary consequence of the database design.

At 500,000 products:

- Three-character `Pro`: 100,180 matches, trigram GIN, 328.551 ms.
- Two-character `Pr`: 200,137 matches, original path, 2402.741 ms.
- Two-character `Pr`: experimental bigram GIN, 615.604–766.909 ms.
- One-character `Q`: 49,880 matches, 537.638 ms.
- One-character `P`: 416,584 matches, 1178.558 ms.
- One-character `P`, forced sequential scan and sort: 1303.811 ms.

The experiment therefore changes the earlier conclusion: two-character
search can meet the database-query target with a different indexing strategy.
Of the short-keyword cases measured in this investigation, the remaining
observed breach is the broad single-character `P` query, whose result set
contains approximately 83% of the catalogue.

The bigram index remains an experimental result at this stage. Its read
performance and 18 MB index size have been measured, but its write and
maintenance cost have not yet been measured. It should not be treated as a
production decision until those trade-offs are evaluated.

