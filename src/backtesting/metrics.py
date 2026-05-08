from __future__ import annotations

import math

import numpy as np
import pandas as pd


def cumulative_return(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    return float((1.0 + returns.fillna(0.0)).prod() - 1.0)


def annualized_return(returns: pd.Series, trading_days: int = 252) -> float:
    if returns.empty:
        return 0.0
    total = cumulative_return(returns)
    years = max(len(returns) / trading_days, 1.0 / trading_days)
    return float((1.0 + total) ** (1.0 / years) - 1.0)


def sharpe_ratio(
    returns: pd.Series, risk_free_rate: float = 0.0, trading_days: int = 252
) -> float:
    clean = returns.dropna()
    if clean.empty:
        return 0.0
    excess = clean - (risk_free_rate / trading_days)
    std = excess.std(ddof=1)
    if std == 0 or math.isnan(std):
        return 0.0
    return float(math.sqrt(trading_days) * excess.mean() / std)


def max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    running_max = equity_curve.cummax()
    drawdowns = equity_curve / running_max - 1.0
    return float(drawdowns.min())


def win_rate(returns: pd.Series) -> float:
    clean = returns.dropna()
    if clean.empty:
        return 0.0
    return float((clean > 0).mean())


def summarize_returns(
    name: str,
    returns: pd.Series,
    trading_days: int = 252,
    risk_free_rate: float = 0.0,
) -> dict:
    clean = returns.fillna(0.0)
    equity = (1.0 + clean).cumprod()
    return {
        "strategy": name,
        "periods": int(len(clean)),
        "cumulative_return": cumulative_return(clean),
        "annualized_return": annualized_return(clean, trading_days),
        "sharpe_ratio": sharpe_ratio(clean, risk_free_rate, trading_days),
        "max_drawdown": max_drawdown(equity),
        "win_rate": win_rate(clean),
        "mean_daily_return": float(clean.mean()) if len(clean) else 0.0,
        "daily_volatility": float(clean.std(ddof=1)) if len(clean) > 1 else 0.0,
    }


def classification_summary(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {"accuracy": 0.0, "f1": 0.0}
    y_true = frame["label"].astype(int)
    y_pred = frame["prediction"].astype(int)
    accuracy = float((y_true == y_pred).mean())
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"accuracy": accuracy, "f1": float(f1)}

