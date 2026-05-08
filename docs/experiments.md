# Experiments

## Goals

The experiments demonstrate that this is a cloud and distributed systems project, not only a stock prediction notebook.

The benchmark compares:

- pandas feature engineering on local data.
- Spark local-mode feature engineering.
- Different ticker counts.
- Different Spark partition counts.
- Estimated EC2 cost for runtime.

## Default Experiment Matrix

Configured in `config/config.yaml`:

- Ticker counts: `3`, `10`
- Spark partitions: `1`, `2`, `4`
- Instance cost estimate: `t3.large` in `us-east-1`

For a larger EC2 run, edit:

```yaml
benchmark:
  ticker_counts: [10, 100, 500]
  partition_counts: [2, 4, 8, 16]
```

## Commands

```bash
make download TICKER_LIMIT=10
make benchmark
```

For a larger manually configured run:

```bash
python -m src.experiments.benchmark_spark \
  --config config/config.yaml \
  --ticker-counts 10 100 \
  --partition-counts 2 4 8
```

## Metrics Collected

`data/results/benchmark_results.csv` contains:

- `engine`
- `ticker_count`
- `partitions`
- `rows`
- `runtime_seconds`
- `memory_delta_mb`
- `estimated_t3_large_cost_usd`

`data/results/plots/feature_runtime.png` visualizes average runtime by ticker count.

## Expected Discussion

For small datasets, pandas can be faster because Spark has startup and scheduling overhead. Spark becomes more defensible when the dataset grows, when feature logic expands, or when running across a cluster. Partition tuning also matters: too few partitions underuse the cluster; too many partitions add scheduling overhead.

## Report Template For Results

After running the benchmark, summarize:

| Engine | Tickers | Partitions | Runtime seconds | Estimated cost |
|---|---:|---:|---:|---:|
| pandas | 3 | 1 | fill in | fill in |
| spark_local | 3 | 2 | fill in | fill in |
| spark_local | 10 | 4 | fill in | fill in |

Include a short explanation of why results differ and what instance size you used.

