from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.backtesting.metrics import classification_summary, summarize_returns
from src.utils.config_loader import ensure_parent_dir, load_config, project_path
from src.utils.logger import get_logger


LOGGER = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest prediction-driven strategy.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--predictions", help="Override predictions Parquet path.")
    parser.add_argument("--transaction-cost", type=float, help="Cost per position change.")
    parser.add_argument("--output", help="Override metrics CSV path.")
    return parser.parse_args()


def load_predictions(path_value: str | Path) -> pd.DataFrame:
    path = project_path(path_value)
    if not path.exists():
        raise FileNotFoundError(f"Prediction path does not exist: {path}")
    frame = pd.read_parquet(path)
    required = ["date", "ticker", "future_return", "label", "prediction"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Predictions are missing required columns: {missing}")
    frame["date"] = pd.to_datetime(frame["date"])
    frame["prediction"] = frame["prediction"].astype(float).clip(lower=0.0, upper=1.0)
    frame["future_return"] = pd.to_numeric(frame["future_return"], errors="coerce")
    return frame.dropna(subset=["date", "ticker", "future_return", "prediction"])


def build_strategy_returns(
    predictions: pd.DataFrame, transaction_cost: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = predictions.sort_values(["ticker", "date"]).copy()
    rows["previous_position"] = rows.groupby("ticker")["prediction"].shift(1).fillna(0.0)
    rows["trade_size"] = (rows["prediction"] - rows["previous_position"]).abs()
    rows["transaction_cost"] = rows["trade_size"] * transaction_cost
    rows["strategy_return"] = (
        rows["prediction"] * rows["future_return"] - rows["transaction_cost"]
    )
    rows["buy_hold_return"] = rows["future_return"]

    daily = (
        rows.groupby("date", as_index=False)
        .agg(
            strategy_return=("strategy_return", "mean"),
            buy_hold_return=("buy_hold_return", "mean"),
            mean_position=("prediction", "mean"),
            trades=("trade_size", "sum"),
        )
        .sort_values("date")
    )
    daily["strategy_equity"] = (1.0 + daily["strategy_return"]).cumprod()
    daily["buy_hold_equity"] = (1.0 + daily["buy_hold_return"]).cumprod()
    return rows, daily


def run_backtest(
    config: dict,
    prediction_path: str | Path | None = None,
    transaction_cost: float | None = None,
    metrics_output_path: str | Path | None = None,
) -> pd.DataFrame:
    backtest_cfg = config["backtest"]
    predictions = load_predictions(prediction_path or backtest_cfg["prediction_path"])
    cost = (
        float(transaction_cost)
        if transaction_cost is not None
        else float(backtest_cfg.get("transaction_cost", 0.001))
    )
    trading_days = int(backtest_cfg.get("trading_days_per_year", 252))
    risk_free_rate = float(backtest_cfg.get("risk_free_rate", 0.0))

    per_ticker, daily = build_strategy_returns(predictions, cost)
    summaries = [
        summarize_returns(
            "model_long_cash",
            daily["strategy_return"],
            trading_days=trading_days,
            risk_free_rate=risk_free_rate,
        ),
        summarize_returns(
            "equal_weight_buy_hold",
            daily["buy_hold_return"],
            trading_days=trading_days,
            risk_free_rate=risk_free_rate,
        ),
    ]
    classification = classification_summary(predictions)
    for summary in summaries:
        summary.update(classification)
        summary["transaction_cost"] = cost
        summary["tickers"] = int(predictions["ticker"].nunique())
        summary["prediction_rows"] = int(len(predictions))

    metrics = pd.DataFrame(summaries)
    metrics_path = ensure_parent_dir(metrics_output_path or backtest_cfg["metrics_output_path"])
    equity_path = ensure_parent_dir(backtest_cfg["equity_curve_output_path"])
    metrics.to_csv(metrics_path, index=False)
    daily.to_csv(equity_path, index=False)
    LOGGER.info("Wrote backtest metrics to %s", metrics_path)
    LOGGER.info("Wrote equity curve to %s", equity_path)
    LOGGER.info("Backtested %d prediction rows", len(per_ticker))
    return metrics


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    run_backtest(
        config,
        prediction_path=args.predictions,
        transaction_cost=args.transaction_cost,
        metrics_output_path=args.output,
    )


if __name__ == "__main__":
    main()

