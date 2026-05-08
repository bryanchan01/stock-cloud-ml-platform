from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.utils.config_loader import ensure_parent_dir, load_config, project_path
from src.utils.logger import get_logger


LOGGER = get_logger(__name__)
PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download historical OHLCV data.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--tickers", nargs="*", help="Override ticker symbols.")
    parser.add_argument("--ticker-file", help="File with one ticker per line.")
    parser.add_argument("--start", help="Override start date, YYYY-MM-DD.")
    parser.add_argument("--end", help="Override end date, YYYY-MM-DD.")
    parser.add_argument("--limit", type=int, help="Limit ticker count for smoke runs.")
    parser.add_argument("--output-csv", help="Override raw CSV output path.")
    parser.add_argument("--output-parquet", help="Override raw Parquet output path.")
    return parser.parse_args()


def read_ticker_file(path: str | Path) -> list[str]:
    ticker_path = project_path(path)
    with ticker_path.open("r", encoding="utf-8") as handle:
        return [
            line.strip().upper()
            for line in handle
            if line.strip() and not line.strip().startswith("#")
        ]


def resolve_tickers(config: dict, args: argparse.Namespace) -> list[str]:
    if args.tickers:
        tickers = [ticker.upper() for ticker in args.tickers]
    elif args.ticker_file:
        tickers = read_ticker_file(args.ticker_file)
    elif config["data"].get("ticker_file"):
        tickers = read_ticker_file(config["data"]["ticker_file"])
    else:
        tickers = [ticker.upper() for ticker in config["data"]["tickers"]]

    unique_tickers = list(dict.fromkeys(tickers))
    if args.limit:
        unique_tickers = unique_tickers[: args.limit]
    if not unique_tickers:
        raise ValueError("No tickers were provided.")
    return unique_tickers


def normalize_yfinance_frame(raw: pd.DataFrame, tickers: Iterable[str]) -> pd.DataFrame:
    """Convert yfinance output into long-form OHLCV rows."""
    tickers = list(tickers)
    frames: list[pd.DataFrame] = []

    if isinstance(raw.columns, pd.MultiIndex):
        level_zero = set(str(value).upper() for value in raw.columns.get_level_values(0))
        tickers_first = bool(set(tickers) & level_zero)

        for ticker in tickers:
            try:
                ticker_frame = raw[ticker] if tickers_first else raw.xs(ticker, axis=1, level=1)
            except KeyError:
                LOGGER.warning("No downloaded data for ticker=%s", ticker)
                continue
            frames.append(_clean_single_ticker_frame(ticker_frame, ticker))
    else:
        if len(tickers) != 1:
            raise ValueError("Expected MultiIndex columns for multiple tickers.")
        frames.append(_clean_single_ticker_frame(raw, tickers[0]))

    if not frames:
        raise RuntimeError("Download returned no usable ticker data.")

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["date", "ticker", "close"])
    combined = combined.sort_values(["ticker", "date"]).reset_index(drop=True)
    return combined


def _clean_single_ticker_frame(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    clean = frame.copy()
    clean.columns = [
        str(column).strip().lower().replace(" ", "_") for column in clean.columns
    ]
    clean = clean.reset_index()
    clean.columns = [
        str(column).strip().lower().replace(" ", "_") for column in clean.columns
    ]
    if "date" not in clean.columns:
        date_column = "datetime" if "datetime" in clean.columns else clean.columns[0]
        clean = clean.rename(columns={date_column: "date"})

    clean["date"] = pd.to_datetime(clean["date"]).dt.date
    clean["ticker"] = ticker.upper()
    if "adj_close" not in clean.columns:
        clean["adj_close"] = clean.get("close")

    for column in PRICE_COLUMNS:
        if column not in clean.columns:
            clean[column] = pd.NA

    clean = clean[["date", "ticker", *PRICE_COLUMNS]]
    for column in PRICE_COLUMNS:
        clean[column] = pd.to_numeric(clean[column], errors="coerce")
    return clean


def download_prices(config: dict, args: argparse.Namespace) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError(
            "yfinance is required for downloading market data. "
            "Install dependencies with `pip install -r requirements.txt`."
        ) from exc

    tickers = resolve_tickers(config, args)
    start = args.start or config["data"]["start_date"]
    end = args.end or config["data"].get("end_date") or date.today().isoformat()
    interval = config["data"].get("interval", "1d")
    auto_adjust = bool(config["data"].get("auto_adjust", True))

    LOGGER.info(
        "Downloading %d tickers from %s to %s with interval=%s",
        len(tickers),
        start,
        end,
        interval,
    )
    raw = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=auto_adjust,
        group_by="ticker",
        threads=True,
        progress=False,
    )
    return normalize_yfinance_frame(raw, tickers)


def write_outputs(prices: pd.DataFrame, config: dict, args: argparse.Namespace) -> None:
    csv_path = ensure_parent_dir(args.output_csv or config["data"]["raw_csv_path"])
    parquet_path = ensure_parent_dir(
        args.output_parquet or config["data"]["raw_parquet_path"]
    )

    prices.to_csv(csv_path, index=False)
    prices.to_parquet(parquet_path, index=False)
    LOGGER.info("Wrote %d rows to %s", len(prices), csv_path)
    LOGGER.info("Wrote %d rows to %s", len(prices), parquet_path)


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    prices = download_prices(config, args)
    write_outputs(prices, config, args)


if __name__ == "__main__":
    main()

