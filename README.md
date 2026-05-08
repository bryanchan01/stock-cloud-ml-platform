# Cloud-Native Distributed Stock Market Forecasting and Backtesting Platform

This project is a course-sized cloud ML systems platform for historical stock trend classification and backtesting. It uses PySpark for distributed ETL and feature engineering, Spark MLlib for classification, pandas for small local comparisons, Docker for reproducibility, and AWS EC2 guidance for cloud deployment.

It is not financial advice and it is not a production trading system. The goal is to demonstrate distributed data processing, ML pipeline automation, cloud deployment, backtesting, and cost/performance evaluation.

## Core Scope

- Historical batch ingestion from `yfinance` into CSV and Parquet.
- Spark DataFrame ETL with no look-ahead feature engineering.
- Logistic Regression and Random Forest models using Spark MLlib.
- Moving-average baseline.
- Long/cash backtest with transaction costs.
- pandas versus Spark benchmark outputs and plots.
- Docker and AWS EC2 setup documentation.

Optional streaming, FastAPI, and LSTM components are intentionally omitted until the core project works.

## Repository Layout

```text
config/                 YAML configuration
data/                   Generated raw, processed, prediction, and result files
docs/                   Architecture, AWS setup, experiments, final report draft
scripts/                Local, Docker, and EC2 helper scripts
src/data_ingestion/     yfinance downloader
src/spark_pipeline/     Spark feature engineering
src/models/             Spark ML training
src/backtesting/        Strategy simulation and metrics
src/experiments/        Benchmarks and cost estimator
tests/                  Synthetic smoke validation
```

## Local Setup

```powershell
cd C:\Users\Bryan\Desktop\project\stock-cloud-ml-platform
python -m venv .venv
```

Then use whichever venv layout your Python creates:

```powershell
# Standard Windows CPython
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt

# MSYS/UCRT Python layout, if Scripts does not exist
.\.venv\bin\python.exe -m pip install --upgrade pip
.\.venv\bin\python.exe -m pip install -r requirements.txt
```

For this project, standard CPython, WSL Ubuntu, Docker, or EC2 Ubuntu is recommended. MSYS Python may try to compile scientific packages from source instead of using normal Windows wheels.

On Linux or EC2:

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
```

## Run The Core Pipeline

Use the synthetic smoke test first. It does not call external data APIs.

```bash
make smoke
```

Then run with downloaded market data:

```bash
make download TICKER_LIMIT=10
make features
make train MODEL=logistic_regression
make backtest
make benchmark
```

Equivalent direct Python commands:

```bash
python -m src.data_ingestion.download_data --config config/config.yaml --limit 10
python -m src.spark_pipeline.feature_engineering --config config/config.yaml
python -m src.models.train_spark_ml --config config/config.yaml --model logistic_regression
python -m src.backtesting.backtest --config config/config.yaml
python -m src.experiments.benchmark_spark --config config/config.yaml
```

## Outputs

- Raw data: `data/raw/prices.csv`, `data/raw/prices.parquet`
- Features: `data/processed/features.parquet`
- Predictions: `data/predictions/*_predictions.parquet`
- Model metrics: `data/results/model_metrics.csv`
- Backtest metrics: `data/results/backtest_metrics.csv`
- Equity curve: `data/results/equity_curve.csv`
- Benchmark results: `data/results/benchmark_results.csv`
- Plots: `data/results/plots/`

## Docker

```bash
make docker-build
make docker-run
```

The Docker image runs the synthetic smoke pipeline by default and mounts `data/`, `config/`, and `models/` through Compose.

## AWS EC2 Summary

Recommended student-budget path:

1. Launch Ubuntu 24.04 LTS on EC2.
2. Start with `t3.medium` for smoke tests; use `t3.large` for larger Spark runs.
3. Restrict SSH to your IP address.
4. Stop or terminate instances when finished.
5. Do not put AWS credentials in this repository.

See [docs/aws_setup.md](docs/aws_setup.md) for exact setup commands and cost controls.

## Financial ML Rules Used

- Time-based train/test split only.
- Rolling features use current and past rows only.
- Labels use future return through `lead(close, horizon)`.
- The model never receives `future_return`, `future_close`, or future labels as features.
- Backtest includes transaction costs.
- Buy-and-hold is reported as a baseline.

## References

- [yfinance documentation](https://ranaroussi.github.io/yfinance/)
- [PySpark installation](https://spark.apache.org/docs/latest/api/python/getting_started/install.html)
- [Apache Spark overview](https://downloads.apache.org/spark/docs/4.0.1/)
- [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Ubuntu EC2 launch guide](https://documentation.ubuntu.com/aws/aws-how-to/instances/launch-ubuntu-ec2-instance/)
- [AWS T3 instance information](https://aws.amazon.com/es/ec2/instance-types/t3/)
- [scikit-learn TimeSeriesSplit notes](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
- [QuantStart Sharpe ratio article](https://www.quantstart.com/articles/Sharpe-Ratio-for-Algorithmic-Trading-Performance-Measurement/)
