#!/usr/bin/env bash
set -euo pipefail

CONFIG="${CONFIG:-config/config.yaml}"
MODEL="${MODEL:-logistic_regression}"

python -m src.data_ingestion.download_data --config "$CONFIG"
python -m src.spark_pipeline.feature_engineering --config "$CONFIG"
python -m src.models.train_spark_ml --config "$CONFIG" --model "$MODEL"
python -m src.backtesting.backtest --config "$CONFIG"

