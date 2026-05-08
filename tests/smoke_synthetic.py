from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from src.backtesting.backtest import run_backtest
from src.models.train_spark_ml import run_training
from src.spark_pipeline.feature_engineering import run_feature_pipeline
from src.utils.config_loader import load_config, project_path


def generate_synthetic_prices(output_path: Path) -> None:
    rng = np.random.default_rng(42)
    tickers = ["AAPL", "MSFT", "NVDA"]
    dates = pd.bdate_range("2022-01-03", "2024-06-28")
    rows = []
    for offset, ticker in enumerate(tickers):
        price = 100.0 + offset * 25.0
        for current_date in dates:
            seasonal = 0.0008 * math.sin(len(rows) / 17.0)
            shock = rng.normal(0.0004 + seasonal, 0.018)
            open_price = price * (1.0 + rng.normal(0, 0.003))
            close = max(1.0, price * (1.0 + shock))
            high = max(open_price, close) * (1.0 + abs(rng.normal(0, 0.004)))
            low = min(open_price, close) * (1.0 - abs(rng.normal(0, 0.004)))
            volume = int(1_000_000 + rng.normal(0, 80_000) + offset * 50_000)
            rows.append(
                {
                    "date": current_date.date().isoformat(),
                    "ticker": ticker,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "adj_close": close,
                    "volume": max(volume, 1000),
                }
            )
            price = close
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_path, index=False)


def main() -> None:
    config = load_config()
    raw_csv = project_path(config["data"]["raw_csv_path"])
    generate_synthetic_prices(raw_csv)
    run_feature_pipeline(config, input_path=raw_csv)
    run_training(config, model_name="logistic_regression")
    run_backtest(config)

    expected_outputs = [
        project_path(config["features"]["output_path"]),
        project_path("data/predictions/logistic_regression_predictions.parquet"),
        project_path(config["model"]["metrics_output_path"]),
        project_path(config["backtest"]["metrics_output_path"]),
    ]
    missing = [str(path) for path in expected_outputs if not path.exists()]
    if missing:
        raise AssertionError(f"Smoke run missing outputs: {missing}")
    print("Synthetic smoke pipeline completed successfully.")


if __name__ == "__main__":
    main()

