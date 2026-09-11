# CAT-002 Seed Results

The seed command is deterministic and replaces the existing catalogue contents, so re-running it produces the same products and count instead of doubling the data.

## Seed command

```powershell
docker compose up -d --build

docker compose exec api python -m app.seed.catalogue --count 500000 --seed 20260911
```

The command reports:

- product count
- seed value
- actual product count
- dataset checksum
- generation time

## Measured baseline

Record the result from the sprint reference machine here after the 500,000-product run:

| Dataset | Products | Seed | Dataset checksum | Generation time | Machine / environment |
|---|---:|---:|---:|---|
| Baseline | 500,000 | 20260911 | _pending measurement_ | _pending checksum_ | _pending measurement_ |

## Re-run verification

Run the same command again and verify that the actual product count remains 500,000 and that the dataset checksum is identical rather than doubled or changed.

## Known search-distribution cases

The generated names deliberately include:

- common words such as `Pro`, `Smart`, `Plus`, `Wireless`, and `Premium`
- exactly seven deliberately rare `Q7V` names in the baseline dataset

These stable cases are intended for CAT-003 search verification.
