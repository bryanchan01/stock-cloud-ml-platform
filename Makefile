PYTHON ?= python
CONFIG ?= config/config.yaml
MODEL ?= logistic_regression
TICKER_LIMIT ?=

.PHONY: help install download features train train-all backtest benchmark cost smoke clean docker-build docker-run

help:
	@echo "Available targets:"
	@echo "  make install       Install Python dependencies"
	@echo "  make download      Download yfinance historical prices"
	@echo "  make features      Build Spark feature Parquet"
	@echo "  make train         Train MODEL=logistic_regression|random_forest|baseline"
	@echo "  make train-all     Train baseline, logistic regression, and random forest"
	@echo "  make backtest      Backtest configured predictions"
	@echo "  make benchmark     Run pandas vs Spark benchmark"
	@echo "  make smoke         Run synthetic end-to-end smoke test"
	@echo "  make docker-build  Build Docker image"
	@echo "  make docker-run    Run the pipeline in Docker"

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

download:
	$(PYTHON) -m src.data_ingestion.download_data --config $(CONFIG) $(if $(TICKER_LIMIT),--limit $(TICKER_LIMIT),)

features:
	$(PYTHON) -m src.spark_pipeline.feature_engineering --config $(CONFIG)

train:
	$(PYTHON) -m src.models.train_spark_ml --config $(CONFIG) --model $(MODEL)

train-all:
	$(PYTHON) -m src.models.train_spark_ml --config $(CONFIG) --model all

backtest:
	$(PYTHON) -m src.backtesting.backtest --config $(CONFIG)

benchmark:
	$(PYTHON) -m src.experiments.benchmark_spark --config $(CONFIG)

cost:
	$(PYTHON) -m src.experiments.cost_estimator --config $(CONFIG) --hours 2 --instance t3_large

smoke:
	$(PYTHON) -m tests.smoke_synthetic

clean:
	$(PYTHON) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['data/raw','data/processed','data/predictions','data/results','models']]; [pathlib.Path(p).mkdir(parents=True, exist_ok=True) for p in ['data/raw','data/processed','data/predictions','data/results/plots']]"

docker-build:
	docker build -t stock-cloud-ml-platform:latest .

docker-run:
	docker compose run --rm stock-ml make smoke

