from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
from pyspark.ml import Pipeline
from pyspark.ml.classification import LogisticRegression, RandomForestClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator
from pyspark.ml.feature import StandardScaler, VectorAssembler
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from src.spark_pipeline.feature_engineering import create_spark_session
from src.utils.config_loader import ensure_dir, ensure_parent_dir, load_config, project_path
from src.utils.logger import get_logger


LOGGER = get_logger(__name__)
SUPPORTED_MODELS = {"baseline", "logistic_regression", "random_forest", "all"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train Spark MLlib classifiers.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument(
        "--model",
        default=None,
        choices=sorted(SUPPORTED_MODELS),
        help="Model to train. Defaults to config model.default_model.",
    )
    parser.add_argument("--features", help="Override processed feature path.")
    parser.add_argument("--predictions-dir", help="Override prediction output directory.")
    return parser.parse_args()


def split_by_time(features: DataFrame, config: dict) -> tuple[DataFrame, DataFrame, str]:
    split_date = config["model"].get("train_end_date")
    if split_date:
        train = features.filter(F.col("date") <= F.to_date(F.lit(split_date)))
        test = features.filter(F.col("date") > F.to_date(F.lit(split_date)))
        if train.limit(1).count() and test.limit(1).count():
            return train, test, split_date
        LOGGER.warning(
            "Configured split date %s did not produce both train and test rows; "
            "falling back to fractional date split.",
            split_date,
        )

    dates = [
        row["date"]
        for row in features.select("date").distinct().orderBy("date").collect()
    ]
    if len(dates) < 3:
        raise ValueError("Need at least three distinct dates for a time-based split.")
    fraction = float(config["model"].get("train_fraction_if_no_split_date", 0.8))
    index = max(1, min(len(dates) - 2, int(len(dates) * fraction)))
    fallback_date = dates[index].isoformat()
    train = features.filter(F.col("date") <= F.lit(fallback_date))
    test = features.filter(F.col("date") > F.lit(fallback_date))
    return train, test, fallback_date


def evaluate_predictions(predictions: DataFrame, model_name: str, split_date: str) -> dict:
    accuracy = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="accuracy"
    ).evaluate(predictions)
    f1 = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="f1"
    ).evaluate(predictions)

    metrics = {
        "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds"),
        "model": model_name,
        "split_date": split_date,
        "test_rows": predictions.count(),
        "accuracy": accuracy,
        "f1": f1,
    }

    if "rawPrediction" in predictions.columns:
        try:
            auc = BinaryClassificationEvaluator(
                labelCol="label",
                rawPredictionCol="rawPrediction",
                metricName="areaUnderROC",
            ).evaluate(predictions)
            metrics["area_under_roc"] = auc
        except Exception as exc:  # pragma: no cover - Spark evaluator edge case
            LOGGER.warning("Could not compute AUC for %s: %s", model_name, exc)
            metrics["area_under_roc"] = None
    else:
        metrics["area_under_roc"] = None

    return metrics


def write_metrics(metrics: list[dict], path_value: str | Path) -> None:
    path = ensure_parent_dir(path_value)
    new_rows = pd.DataFrame(metrics)
    if path.exists():
        existing = pd.read_csv(path)
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        combined = new_rows
    combined.to_csv(path, index=False)
    LOGGER.info("Wrote model metrics to %s", path)


def prediction_columns(predictions: DataFrame) -> DataFrame:
    optional = [column for column in ["probability", "rawPrediction"] if column in predictions.columns]
    return predictions.select(
        "date",
        "ticker",
        "close",
        "future_return",
        "label",
        "prediction",
        "baseline_prediction",
        *optional,
    )


def train_baseline(test: DataFrame) -> DataFrame:
    return test.withColumn("prediction", F.col("baseline_prediction").cast("double"))


def train_logistic_regression(train: DataFrame, test: DataFrame, config: dict):
    feature_cols = config["model"]["features"]
    lr_cfg = config["model"].get("logistic_regression", {})
    assembler = VectorAssembler(
        inputCols=feature_cols, outputCol="raw_features", handleInvalid="skip"
    )
    scaler = StandardScaler(inputCol="raw_features", outputCol="features")
    classifier = LogisticRegression(
        labelCol="label",
        featuresCol="features",
        maxIter=int(lr_cfg.get("max_iter", 50)),
        regParam=float(lr_cfg.get("reg_param", 0.01)),
        elasticNetParam=float(lr_cfg.get("elastic_net_param", 0.0)),
    )
    pipeline = Pipeline(stages=[assembler, scaler, classifier])
    model = pipeline.fit(train)
    return model, model.transform(test)


def train_random_forest(train: DataFrame, test: DataFrame, config: dict):
    feature_cols = config["model"]["features"]
    rf_cfg = config["model"].get("random_forest", {})
    assembler = VectorAssembler(
        inputCols=feature_cols, outputCol="features", handleInvalid="skip"
    )
    classifier = RandomForestClassifier(
        labelCol="label",
        featuresCol="features",
        numTrees=int(rf_cfg.get("num_trees", 80)),
        maxDepth=int(rf_cfg.get("max_depth", 6)),
        seed=int(config["project"].get("random_seed", 42)),
    )
    pipeline = Pipeline(stages=[assembler, classifier])
    model = pipeline.fit(train)
    return model, model.transform(test)


def save_predictions(
    predictions: DataFrame,
    predictions_dir: str | Path,
    model_name: str,
) -> Path:
    output_dir = ensure_dir(predictions_dir)
    output_path = output_dir / f"{model_name}_predictions.parquet"
    prediction_columns(predictions).write.mode("overwrite").parquet(str(output_path))
    LOGGER.info("Wrote %s predictions to %s", model_name, output_path)
    return output_path


def save_model(model, config: dict, model_name: str) -> None:
    if model is None:
        return
    output_dir = ensure_dir(config["model"]["model_output_dir"])
    output_path = output_dir / model_name
    model.write().overwrite().save(str(output_path))
    LOGGER.info("Saved %s model to %s", model_name, output_path)


def run_training(
    config: dict,
    model_name: str,
    feature_path: str | Path | None = None,
    predictions_dir: str | Path | None = None,
) -> list[dict]:
    spark = create_spark_session(config, app_suffix="Train")
    try:
        features_source = project_path(feature_path or config["features"]["output_path"])
        if not features_source.exists():
            raise FileNotFoundError(f"Feature path does not exist: {features_source}")
        features = spark.read.parquet(str(features_source)).cache()
        train, test, split_date = split_by_time(features, config)
        LOGGER.info("Training rows=%d test rows=%d", train.count(), test.count())

        models_to_run = (
            ["baseline", "logistic_regression", "random_forest"]
            if model_name == "all"
            else [model_name]
        )
        metrics: list[dict] = []
        pred_dir = predictions_dir or config["model"]["prediction_output_dir"]

        for current_model in models_to_run:
            LOGGER.info("Running model=%s", current_model)
            fitted = None
            if current_model == "baseline":
                predictions = train_baseline(test)
            elif current_model == "logistic_regression":
                fitted, predictions = train_logistic_regression(train, test, config)
            elif current_model == "random_forest":
                fitted, predictions = train_random_forest(train, test, config)
            else:
                raise ValueError(f"Unsupported model: {current_model}")

            predictions = predictions.cache()
            metrics.append(evaluate_predictions(predictions, current_model, split_date))
            save_predictions(predictions, pred_dir, current_model)
            save_model(fitted, config, current_model)

        write_metrics(metrics, config["model"]["metrics_output_path"])
        return metrics
    finally:
        spark.stop()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    model_name = args.model or config["model"]["default_model"]
    run_training(
        config,
        model_name=model_name,
        feature_path=args.features,
        predictions_dir=args.predictions_dir,
    )


if __name__ == "__main__":
    main()

