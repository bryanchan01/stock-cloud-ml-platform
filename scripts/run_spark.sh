#!/usr/bin/env bash
set -euo pipefail

CONFIG="${CONFIG:-config/config.yaml}"
SPARK_MASTER="${SPARK_MASTER:-local[*]}"
MODEL="${MODEL:-logistic_regression}"

python -m src.spark_pipeline.feature_engineering --config "$CONFIG" --master "$SPARK_MASTER"
python -m src.models.train_spark_ml --config "$CONFIG" --model "$MODEL"
python -m src.backtesting.backtest --config "$CONFIG"

