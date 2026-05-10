from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.utils.logger import get_logger


LOGGER = get_logger(__name__)
RESULT_FILES = {
    "model": "model_metrics.csv",
    "backtest": "backtest_metrics.csv",
    "benchmark": "benchmark_results.csv",
}
PLOTS_DIR_NAME = "summary_plots"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize experiment run outputs.")
    parser.add_argument(
        "--experiments-dir",
        default="experiments",
        help="Directory containing experiment run folders.",
    )
    return parser.parse_args()


def parse_metadata(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    metadata: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("- ") or line.endswith(":"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            metadata[key.strip()] = value.strip()
    return metadata


def infer_ticker_limit(run_id: str, metadata: dict[str, str]) -> int | None:
    for key in ("ticker_limit", "limit"):
        if metadata.get(key):
            try:
                return int(metadata[key])
            except ValueError:
                pass

    patterns = [
        r"(?:^|_)limit_(\d+)(?:_|$)",
        r"(?:^|_)ticker_limit_(\d+)(?:_|$)",
        r"(?:^|/)ticker_limit_(\d+)(?:_|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, run_id)
        if match:
            return int(match.group(1))
    return None


def infer_model(run_id: str, metadata: dict[str, str]) -> str | None:
    if metadata.get("model"):
        return metadata["model"]
    for model in ("logistic_regression", "random_forest", "baseline"):
        if model in run_id:
            return model
    return None


def result_path(run_dir: Path, filename: str) -> Path | None:
    candidates = [
        run_dir / "results" / filename,
        run_dir / "data" / "results" / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    matches = sorted(run_dir.rglob(filename))
    return matches[0] if matches else None


def discover_runs(experiments_dir: Path) -> list[Path]:
    if not experiments_dir.exists():
        raise FileNotFoundError(f"Experiments directory does not exist: {experiments_dir}")

    run_dirs: list[Path] = []
    for child in sorted(experiments_dir.iterdir()):
        if not child.is_dir() or child.name == PLOTS_DIR_NAME:
            continue
        has_result = any(result_path(child, filename) for filename in RESULT_FILES.values())
        if has_result or (child / "metadata.txt").exists():
            run_dirs.append(child)
    return run_dirs


def load_result_frame(
    run_dir: Path,
    experiments_dir: Path,
    result_kind: str,
    filename: str,
) -> pd.DataFrame | None:
    metadata = parse_metadata(run_dir / "metadata.txt")
    relative_run_id = run_dir.relative_to(experiments_dir).as_posix()
    path = result_path(run_dir, filename)
    if not path:
        LOGGER.warning("Missing %s for run=%s", filename, relative_run_id)
        return None

    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        LOGGER.warning("Could not read %s for run=%s: %s", filename, relative_run_id, exc)
        return None

    frame.insert(0, "result_kind", result_kind)
    frame.insert(0, "source_file", path.relative_to(experiments_dir).as_posix())
    frame.insert(0, "run_id", relative_run_id)
    frame.insert(1, "ticker_limit", infer_ticker_limit(relative_run_id, metadata))
    frame.insert(2, "experiment_model", infer_model(relative_run_id, metadata))
    frame.insert(3, "experiment_timestamp", metadata.get("timestamp"))
    frame.insert(4, "hostname", metadata.get("hostname"))
    frame.insert(5, "git_commit", metadata.get("git_commit"))
    return frame


def collect_results(experiments_dir: Path) -> dict[str, pd.DataFrame]:
    runs = discover_runs(experiments_dir)
    LOGGER.info("Found %d experiment run folders", len(runs))

    collected: dict[str, list[pd.DataFrame]] = {
        "model": [],
        "backtest": [],
        "benchmark": [],
    }
    for run_dir in runs:
        for result_kind, filename in RESULT_FILES.items():
            frame = load_result_frame(run_dir, experiments_dir, result_kind, filename)
            if frame is not None:
                collected[result_kind].append(frame)

    return {
        kind: pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        for kind, frames in collected.items()
    }


def write_summary_csvs(experiments_dir: Path, results: dict[str, pd.DataFrame]) -> None:
    outputs = {
        "model": experiments_dir / "summary_model_metrics.csv",
        "backtest": experiments_dir / "summary_backtest_metrics.csv",
        "benchmark": experiments_dir / "summary_benchmark.csv",
    }
    for kind, output in outputs.items():
        results[kind].to_csv(output, index=False)
        LOGGER.info("Wrote %d %s rows to %s", len(results[kind]), kind, output)


def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 30) -> str:
    existing = [column for column in columns if column in frame.columns]
    if frame.empty or not existing:
        return "_No rows available._"
    view = frame[existing].copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")

    view = view.head(max_rows).fillna("")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = [
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in view.itertuples(index=False, name=None)
    ]
    return "\n".join([header, separator, *rows])


def write_summary_markdown(experiments_dir: Path, results: dict[str, pd.DataFrame]) -> None:
    model_columns = [
        "run_id",
        "ticker_limit",
        "model",
        "accuracy",
        "f1",
        "area_under_roc",
        "test_rows",
    ]
    backtest_columns = [
        "run_id",
        "ticker_limit",
        "experiment_model",
        "strategy",
        "cumulative_return",
        "annualized_return",
        "sharpe_ratio",
        "max_drawdown",
        "win_rate",
    ]
    benchmark_columns = [
        "run_id",
        "ticker_limit",
        "engine",
        "ticker_count",
        "partitions",
        "runtime_seconds",
        "estimated_t3_large_cost_usd",
    ]

    content = "\n\n".join(
        [
            "# Experiment Summary",
            "Generated from experiment folders under `experiments/`.",
            "## Model Metrics",
            markdown_table(results["model"], model_columns),
            "## Backtest Metrics",
            markdown_table(results["backtest"], backtest_columns),
            "## Benchmark Metrics",
            markdown_table(results["benchmark"], benchmark_columns),
            "## Generated Plots",
            "\n".join(
                [
                    f"- `{PLOTS_DIR_NAME}/runtime_vs_ticker_limit.png`",
                    f"- `{PLOTS_DIR_NAME}/accuracy_vs_ticker_limit.png`",
                    f"- `{PLOTS_DIR_NAME}/f1_vs_ticker_limit.png`",
                    f"- `{PLOTS_DIR_NAME}/cumulative_return_vs_ticker_limit.png`",
                    f"- `{PLOTS_DIR_NAME}/sharpe_ratio_vs_ticker_limit.png`",
                    f"- `{PLOTS_DIR_NAME}/max_drawdown_vs_ticker_limit.png`",
                ]
            ),
            "",
        ]
    )
    output = experiments_dir / "summary.md"
    output.write_text(content, encoding="utf-8")
    LOGGER.info("Wrote Markdown summary to %s", output)


def usable_numeric(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    if "ticker_limit" in result.columns:
        result["ticker_limit"] = pd.to_numeric(result["ticker_limit"], errors="coerce")
    return result.dropna(subset=["ticker_limit"])


def save_line_plot(
    frame: pd.DataFrame,
    x_col: str,
    y_col: str,
    group_col: str | None,
    title: str,
    ylabel: str,
    output: Path,
) -> None:
    import matplotlib.pyplot as plt

    output.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(9, 5))
    ax = fig.add_subplot(111)

    if frame.empty or x_col not in frame.columns or y_col not in frame.columns:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center")
    elif group_col and group_col in frame.columns:
        for group_value, group in frame.groupby(group_col, dropna=False):
            grouped = group.groupby(x_col, as_index=False)[y_col].mean().sort_values(x_col)
            ax.plot(grouped[x_col], grouped[y_col], marker="o", label=str(group_value))
        ax.legend()
    else:
        grouped = frame.groupby(x_col, as_index=False)[y_col].mean().sort_values(x_col)
        ax.plot(grouped[x_col], grouped[y_col], marker="o")

    ax.set_title(title)
    ax.set_xlabel("Ticker limit")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    LOGGER.info("Wrote plot to %s", output)


def benchmark_runtime_frame(benchmark: pd.DataFrame) -> pd.DataFrame:
    if benchmark.empty:
        return benchmark

    frame = usable_numeric(benchmark, ["ticker_limit", "ticker_count", "runtime_seconds"])
    if frame.empty or "ticker_count" not in frame.columns:
        return frame

    matched = frame[frame["ticker_count"] == frame["ticker_limit"]]
    if not matched.empty:
        return matched

    max_by_run = frame.groupby("run_id")["ticker_count"].transform("max")
    return frame[frame["ticker_count"] == max_by_run]


def generate_plots(experiments_dir: Path, results: dict[str, pd.DataFrame]) -> None:
    plots_dir = experiments_dir / PLOTS_DIR_NAME

    runtime = benchmark_runtime_frame(results["benchmark"])
    save_line_plot(
        runtime,
        x_col="ticker_limit",
        y_col="runtime_seconds",
        group_col="engine",
        title="Runtime vs Ticker Limit",
        ylabel="Runtime seconds",
        output=plots_dir / "runtime_vs_ticker_limit.png",
    )

    model = usable_numeric(results["model"], ["ticker_limit", "accuracy", "f1"])
    save_line_plot(
        model,
        x_col="ticker_limit",
        y_col="accuracy",
        group_col="model",
        title="Accuracy vs Ticker Limit",
        ylabel="Accuracy",
        output=plots_dir / "accuracy_vs_ticker_limit.png",
    )
    save_line_plot(
        model,
        x_col="ticker_limit",
        y_col="f1",
        group_col="model",
        title="F1 Score vs Ticker Limit",
        ylabel="F1 score",
        output=plots_dir / "f1_vs_ticker_limit.png",
    )

    backtest = usable_numeric(
        results["backtest"],
        ["ticker_limit", "cumulative_return", "sharpe_ratio", "max_drawdown"],
    )
    save_line_plot(
        backtest,
        x_col="ticker_limit",
        y_col="cumulative_return",
        group_col="strategy",
        title="Cumulative Return vs Ticker Limit",
        ylabel="Cumulative return",
        output=plots_dir / "cumulative_return_vs_ticker_limit.png",
    )
    save_line_plot(
        backtest,
        x_col="ticker_limit",
        y_col="sharpe_ratio",
        group_col="strategy",
        title="Sharpe Ratio vs Ticker Limit",
        ylabel="Sharpe ratio",
        output=plots_dir / "sharpe_ratio_vs_ticker_limit.png",
    )
    save_line_plot(
        backtest,
        x_col="ticker_limit",
        y_col="max_drawdown",
        group_col="strategy",
        title="Max Drawdown vs Ticker Limit",
        ylabel="Max drawdown",
        output=plots_dir / "max_drawdown_vs_ticker_limit.png",
    )


def summarize_experiments(experiments_dir: Path) -> dict[str, pd.DataFrame]:
    results = collect_results(experiments_dir)
    experiments_dir.mkdir(parents=True, exist_ok=True)
    write_summary_csvs(experiments_dir, results)
    write_summary_markdown(experiments_dir, results)
    generate_plots(experiments_dir, results)
    return results


def main() -> None:
    args = parse_args()
    summarize_experiments(Path(args.experiments_dir))


if __name__ == "__main__":
    main()
