from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import DateType, DoubleType, StringType

from src.utils.config_loader import ensure_parent_dir, load_config, project_path
from src.utils.logger import get_logger


LOGGER = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Spark stock features.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--input", help="Override raw input path.")
    parser.add_argument("--output", help="Override processed feature output path.")
    parser.add_argument("--master", help="Override Spark master.")
    parser.add_argument("--partitions", type=int, help="Override output partitions.")
    return parser.parse_args()


def create_spark_session(config: dict, app_suffix: str = "Features") -> SparkSession:
    spark_cfg = config["spark"]
    master = spark_cfg.get("master", "local[*]")
    app_name = f"{spark_cfg.get('app_name', 'StockCloudML')}-{app_suffix}"
    builder = (
        SparkSession.builder.appName(app_name)
        .master(master)
        .config("spark.sql.shuffle.partitions", spark_cfg.get("shuffle_partitions", 8))
        .config("spark.driver.memory", spark_cfg.get("driver_memory", "2g"))
        .config("spark.sql.session.timeZone", "UTC")
    )
    return builder.getOrCreate()


def remove_existing_output(path: Path) -> None:
    if not path.exists():
        return
    LOGGER.info("Removing existing output at %s", path)
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def read_prices(spark: SparkSession, path_value: str | Path) -> DataFrame:
    path = project_path(path_value)
    if not path.exists():
        raise FileNotFoundError(f"Raw input does not exist: {path}")

    if path.suffix.lower() == ".parquet":
        frame = spark.read.parquet(str(path))
    else:
        frame = spark.read.option("header", True).option("inferSchema", True).csv(str(path))

    normalized = frame
    for column in normalized.columns:
        normalized = normalized.withColumnRenamed(column, column.lower())

    required = ["date", "ticker", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in normalized.columns]
    if missing:
        raise ValueError(f"Raw data is missing required columns: {missing}")

    typed = (
        normalized.withColumn("date", F.col("date").cast(DateType()))
        .withColumn("ticker", F.upper(F.col("ticker").cast(StringType())))
        .withColumn("open", F.col("open").cast(DoubleType()))
        .withColumn("high", F.col("high").cast(DoubleType()))
        .withColumn("low", F.col("low").cast(DoubleType()))
        .withColumn("close", F.col("close").cast(DoubleType()))
        .withColumn("volume", F.col("volume").cast(DoubleType()))
    )
    if "adj_close" in typed.columns:
        typed = typed.withColumn("adj_close", F.col("adj_close").cast(DoubleType()))
    else:
        typed = typed.withColumn("adj_close", F.col("close"))

    return typed.dropna(subset=["date", "ticker", "close"]).dropDuplicates(
        ["date", "ticker"]
    )


def build_features(prices: DataFrame, config: dict) -> DataFrame:
    feature_cfg = config["features"]
    horizon = int(feature_cfg.get("forecast_horizon_days", 1))
    ma_windows = [int(value) for value in feature_cfg.get("moving_average_windows", [])]
    volatility_window = int(feature_cfg.get("volatility_window", 20))
    lag_days = [int(value) for value in feature_cfg.get("lag_return_days", [])]

    ticker_window = Window.partitionBy("ticker").orderBy("date")
    engineered = (
        prices.repartition("ticker")
        .sortWithinPartitions("ticker", "date")
        .withColumn("prev_close", F.lag("close", 1).over(ticker_window))
        .withColumn("prev_volume", F.lag("volume", 1).over(ticker_window))
        .withColumn("daily_return", F.col("close") / F.col("prev_close") - F.lit(1.0))
        .withColumn(
            "volume_change",
            F.when(F.col("prev_volume") > 0, F.col("volume") / F.col("prev_volume") - 1.0),
        )
    )

    for window_size in ma_windows:
        rolling = ticker_window.rowsBetween(-(window_size - 1), 0)
        engineered = engineered.withColumn(
            f"ma{window_size}", F.avg("close").over(rolling)
        )

    volatility_window_spec = ticker_window.rowsBetween(-(volatility_window - 1), 0)
    engineered = engineered.withColumn(
        f"rolling_volatility_{volatility_window}",
        F.stddev_samp("daily_return").over(volatility_window_spec),
    )

    for lag_day in lag_days:
        engineered = engineered.withColumn(
            f"return_lag_{lag_day}", F.lag("daily_return", lag_day).over(ticker_window)
        )

    engineered = (
        engineered.withColumn("future_close", F.lead("close", horizon).over(ticker_window))
        .withColumn("future_return", F.col("future_close") / F.col("close") - F.lit(1.0))
        .withColumn("label", F.when(F.col("future_return") > 0, 1.0).otherwise(0.0))
        .withColumn(
            "baseline_prediction",
            F.when(F.col("ma5") > F.col("ma20"), 1.0).otherwise(0.0),
        )
    )

    feature_columns = config["model"]["features"]
    output_columns = [
        "date",
        "ticker",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "future_return",
        "label",
        "baseline_prediction",
        *feature_columns,
    ]
    cleaned = engineered.select(*output_columns).dropna(subset=[*feature_columns, "label"])
    return cleaned


def run_feature_pipeline(
    config: dict,
    input_path: str | Path | None = None,
    output_path: str | Path | None = None,
    master: str | None = None,
    partitions: int | None = None,
) -> None:
    if master:
        config = {**config, "spark": {**config["spark"], "master": master}}

    spark = create_spark_session(config)
    try:
        source = input_path or config["data"]["raw_parquet_path"]
        if not project_path(source).exists():
            source = config["data"]["raw_csv_path"]
        prices = read_prices(spark, source)
        features = build_features(prices, config)
        output = ensure_parent_dir(output_path or config["features"]["output_path"])
        output_partitions = partitions or int(config["spark"].get("output_partitions", 4))
        remove_existing_output(output)
        (
            features.repartition(output_partitions, "ticker")
            .write.mode("overwrite")
            .parquet(str(output))
        )
        LOGGER.info("Wrote %d feature rows to %s", features.count(), output)
    finally:
        spark.stop()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    run_feature_pipeline(
        config,
        input_path=args.input,
        output_path=args.output,
        master=args.master,
        partitions=args.partitions,
    )


if __name__ == "__main__":
    main()
