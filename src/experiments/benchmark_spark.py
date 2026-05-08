from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

import pandas as pd

from src.spark_pipeline.feature_engineering import (
    build_features,
    create_spark_session,
    read_prices,
)
from src.utils.config_loader import ensure_dir, ensure_parent_dir, load_config, project_path
from src.utils.logger import get_logger


LOGGER = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark pandas and Spark feature ETL.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--input", help="Override raw CSV/Parquet path.")
    parser.add_argument("--ticker-counts", nargs="*", type=int)
    parser.add_argument("--partition-counts", nargs="*", type=int)
    return parser.parse_args()


def current_memory_mb() -> float | None:
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        return None


def pandas_feature_count(raw: pd.DataFrame, config: dict, ticker_count: int) -> int:
    selected = sorted(raw["ticker"].unique())[:ticker_count]
    frame = raw[raw["ticker"].isin(selected)].sort_values(["ticker", "date"]).copy()
    frame["daily_return"] = frame.groupby("ticker")["close"].pct_change()
    frame["volume_change"] = frame.groupby("ticker")["volume"].pct_change()
    for window in config["features"]["moving_average_windows"]:
        frame[f"ma{window}"] = frame.groupby("ticker")["close"].transform(
            lambda values: values.rolling(window, min_periods=window).mean()
        )
    vol_window = int(config["features"]["volatility_window"])
    frame[f"rolling_volatility_{vol_window}"] = frame.groupby("ticker")[
        "daily_return"
    ].transform(lambda values: values.rolling(vol_window, min_periods=vol_window).std())
    for lag in config["features"]["lag_return_days"]:
        frame[f"return_lag_{lag}"] = frame.groupby("ticker")["daily_return"].shift(lag)
    horizon = int(config["features"]["forecast_horizon_days"])
    frame["future_return"] = frame.groupby("ticker")["close"].shift(-horizon) / frame[
        "close"
    ] - 1.0
    frame["label"] = (frame["future_return"] > 0).astype(float)
    return int(frame.dropna(subset=[*config["model"]["features"], "label"]).shape[0])


def benchmark_pandas(raw_path: Path, config: dict, ticker_counts: list[int]) -> list[dict]:
    raw = pd.read_parquet(raw_path) if raw_path.suffix == ".parquet" else pd.read_csv(raw_path)
    raw["date"] = pd.to_datetime(raw["date"])
    results = []
    for ticker_count in ticker_counts:
        start_memory = current_memory_mb()
        started = time.perf_counter()
        rows = pandas_feature_count(raw, config, ticker_count)
        elapsed = time.perf_counter() - started
        end_memory = current_memory_mb()
        results.append(
            {
                "engine": "pandas",
                "ticker_count": ticker_count,
                "partitions": 1,
                "rows": rows,
                "runtime_seconds": elapsed,
                "memory_delta_mb": (
                    end_memory - start_memory
                    if start_memory is not None and end_memory is not None
                    else None
                ),
            }
        )
        LOGGER.info("pandas ticker_count=%d runtime=%.2fs", ticker_count, elapsed)
    return results


def benchmark_spark(
    raw_path: Path,
    config: dict,
    ticker_counts: list[int],
    partition_counts: list[int],
) -> list[dict]:
    spark = create_spark_session(config, app_suffix="Benchmark")
    results = []
    bench_dir = ensure_dir("data/results/benchmark_tmp")
    try:
        prices = read_prices(spark, raw_path).cache()
        tickers = [
            row["ticker"]
            for row in prices.select("ticker").distinct().orderBy("ticker").collect()
        ]
        for ticker_count in ticker_counts:
            selected = tickers[:ticker_count]
            subset = prices.filter(prices.ticker.isin(selected))
            for partitions in partition_counts:
                spark.conf.set("spark.sql.shuffle.partitions", partitions)
                output_path = bench_dir / f"spark_t{ticker_count}_p{partitions}.parquet"
                if output_path.exists():
                    shutil.rmtree(output_path)
                start_memory = current_memory_mb()
                started = time.perf_counter()
                features = build_features(subset.repartition(partitions, "ticker"), config)
                rows = features.count()
                features.repartition(partitions).write.mode("overwrite").parquet(
                    str(output_path)
                )
                elapsed = time.perf_counter() - started
                end_memory = current_memory_mb()
                results.append(
                    {
                        "engine": "spark_local",
                        "ticker_count": ticker_count,
                        "partitions": partitions,
                        "rows": rows,
                        "runtime_seconds": elapsed,
                        "memory_delta_mb": (
                            end_memory - start_memory
                            if start_memory is not None and end_memory is not None
                            else None
                        ),
                    }
                )
                LOGGER.info(
                    "spark ticker_count=%d partitions=%d runtime=%.2fs",
                    ticker_count,
                    partitions,
                    elapsed,
                )
    finally:
        spark.stop()
    return results


def add_cost_estimates(results: pd.DataFrame, config: dict) -> pd.DataFrame:
    hourly = float(config["benchmark"]["aws_cost"]["t3_large_hourly_usd"])
    results = results.copy()
    results["estimated_t3_large_cost_usd"] = (
        results["runtime_seconds"] / 3600.0 * hourly
    )
    return results


def write_plot(results: pd.DataFrame, plots_dir: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        LOGGER.warning("matplotlib is not installed; skipping benchmark plot.")
        return

    plots_dir.mkdir(parents=True, exist_ok=True)
    figure = plt.figure(figsize=(9, 5))
    for engine, group in results.groupby("engine"):
        grouped = group.groupby("ticker_count")["runtime_seconds"].mean()
        plt.plot(grouped.index, grouped.values, marker="o", label=engine)
    plt.xlabel("Ticker count")
    plt.ylabel("Runtime seconds")
    plt.title("Feature engineering runtime")
    plt.legend()
    plt.tight_layout()
    output = plots_dir / "feature_runtime.png"
    figure.savefig(output, dpi=150)
    plt.close(figure)
    LOGGER.info("Wrote benchmark plot to %s", output)


def run_benchmark(
    config: dict,
    input_path: str | Path | None = None,
    ticker_counts: list[int] | None = None,
    partition_counts: list[int] | None = None,
) -> pd.DataFrame:
    raw_path = project_path(input_path or config["data"]["raw_parquet_path"])
    if not raw_path.exists():
        raw_path = project_path(config["data"]["raw_csv_path"])
    if not raw_path.exists():
        raise FileNotFoundError("No raw data found. Run `make download` first.")

    ticker_counts = ticker_counts or [int(value) for value in config["benchmark"]["ticker_counts"]]
    partition_counts = partition_counts or [
        int(value) for value in config["benchmark"]["partition_counts"]
    ]
    rows = []
    rows.extend(benchmark_pandas(raw_path, config, ticker_counts))
    rows.extend(benchmark_spark(raw_path, config, ticker_counts, partition_counts))
    results = add_cost_estimates(pd.DataFrame(rows), config)
    output_path = ensure_parent_dir(config["benchmark"]["results_path"])
    results.to_csv(output_path, index=False)
    write_plot(results, ensure_dir(config["benchmark"]["plots_dir"]))
    LOGGER.info("Wrote benchmark results to %s", output_path)
    return results


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    run_benchmark(
        config,
        input_path=args.input,
        ticker_counts=args.ticker_counts,
        partition_counts=args.partition_counts,
    )


if __name__ == "__main__":
    main()
