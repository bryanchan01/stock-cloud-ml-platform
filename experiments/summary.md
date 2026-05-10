# Experiment Summary

Generated from experiment folders under `experiments/`.

## Model Metrics

| run_id | ticker_limit | model | accuracy | f1 | area_under_roc | test_rows |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-05-10_223848_limit_10_logistic_regression | 10 | logistic_regression | 0.5203 | 0.4888 | 0.5063 | 5614 |
| ticker_limit_10 | 10 | logistic_regression | 0.5203 | 0.4888 | 0.5063 | 5614 |
| ticker_limit_10 | 10 | random_forest | 0.5093 | 0.4845 | 0.4971 | 5614 |
| ticker_limit_100 | 100 | logistic_regression | 0.5246 | 0.4516 | 0.5086 | 57762 |
| ticker_limit_100 | 100 | random_forest | 0.5250 | 0.4536 | 0.5054 | 57762 |
| ticker_limit_50 | 50 | logistic_regression | 0.5279 | 0.4631 | 0.5106 | 28898 |
| ticker_limit_50 | 50 | random_forest | 0.5271 | 0.4793 | 0.5076 | 28898 |

## Backtest Metrics

| run_id | ticker_limit | experiment_model | strategy | cumulative_return | annualized_return | sharpe_ratio | max_drawdown | win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05-10_223848_limit_10_logistic_regression | 10 | logistic_regression | model_long_cash | 0.7908 | 0.2831 | 1.1650 | -0.2710 | 0.5416 |
| 2026-05-10_223848_limit_10_logistic_regression | 10 | logistic_regression | equal_weight_buy_hold | 2.8785 | 0.7859 | 2.0432 | -0.2885 | 0.5552 |
| ticker_limit_10 | 10 |  | model_long_cash | 0.7908 | 0.2831 | 1.1650 | -0.2710 | 0.5416 |
| ticker_limit_10 | 10 |  | equal_weight_buy_hold | 2.8785 | 0.7859 | 2.0432 | -0.2885 | 0.5552 |
| ticker_limit_100 | 100 |  | model_long_cash | 1.1859 | 0.3974 | 1.6437 | -0.2383 | 0.5688 |
| ticker_limit_100 | 100 |  | equal_weight_buy_hold | 2.3059 | 0.6679 | 2.0704 | -0.2797 | 0.5756 |
| ticker_limit_50 | 50 |  | model_long_cash | 1.5480 | 0.4921 | 1.7390 | -0.2617 | 0.5823 |
| ticker_limit_50 | 50 |  | equal_weight_buy_hold | 3.2249 | 0.8525 | 2.2047 | -0.3017 | 0.5976 |

## Benchmark Metrics

| run_id | ticker_limit | engine | ticker_count | partitions | runtime_seconds | estimated_t3_large_cost_usd |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-05-10_223848_limit_10_logistic_regression | 10 | pandas | 3 | 1 | 0.0272 | 0.0000 |
| 2026-05-10_223848_limit_10_logistic_regression | 10 | pandas | 10 | 1 | 0.0476 | 0.0000 |
| 2026-05-10_223848_limit_10_logistic_regression | 10 | spark_local | 3 | 1 | 5.1225 | 0.0001 |
| 2026-05-10_223848_limit_10_logistic_regression | 10 | spark_local | 3 | 2 | 2.5748 | 0.0001 |
| 2026-05-10_223848_limit_10_logistic_regression | 10 | spark_local | 3 | 4 | 2.2137 | 0.0001 |
| 2026-05-10_223848_limit_10_logistic_regression | 10 | spark_local | 10 | 1 | 2.5742 | 0.0001 |
| 2026-05-10_223848_limit_10_logistic_regression | 10 | spark_local | 10 | 2 | 2.2925 | 0.0001 |
| 2026-05-10_223848_limit_10_logistic_regression | 10 | spark_local | 10 | 4 | 2.2788 | 0.0001 |
| ticker_limit_10 | 10 | pandas | 3 | 1 | 0.0273 | 0.0000 |
| ticker_limit_10 | 10 | pandas | 10 | 1 | 0.0486 | 0.0000 |
| ticker_limit_10 | 10 | spark_local | 3 | 1 | 5.1468 | 0.0001 |
| ticker_limit_10 | 10 | spark_local | 3 | 2 | 2.5907 | 0.0001 |
| ticker_limit_10 | 10 | spark_local | 3 | 4 | 2.3043 | 0.0001 |
| ticker_limit_10 | 10 | spark_local | 10 | 1 | 2.5451 | 0.0001 |
| ticker_limit_10 | 10 | spark_local | 10 | 2 | 2.3227 | 0.0001 |
| ticker_limit_10 | 10 | spark_local | 10 | 4 | 2.3817 | 0.0001 |
| ticker_limit_100 | 100 | pandas | 3 | 1 | 0.0392 | 0.0000 |
| ticker_limit_100 | 100 | pandas | 10 | 1 | 0.0584 | 0.0000 |
| ticker_limit_100 | 100 | spark_local | 3 | 1 | 5.4083 | 0.0001 |
| ticker_limit_100 | 100 | spark_local | 3 | 2 | 2.7051 | 0.0001 |
| ticker_limit_100 | 100 | spark_local | 3 | 4 | 2.3907 | 0.0001 |
| ticker_limit_100 | 100 | spark_local | 10 | 1 | 2.6189 | 0.0001 |
| ticker_limit_100 | 100 | spark_local | 10 | 2 | 2.4608 | 0.0001 |
| ticker_limit_100 | 100 | spark_local | 10 | 4 | 2.4540 | 0.0001 |
| ticker_limit_50 | 50 | pandas | 3 | 1 | 0.0366 | 0.0000 |
| ticker_limit_50 | 50 | pandas | 10 | 1 | 0.0528 | 0.0000 |
| ticker_limit_50 | 50 | spark_local | 3 | 1 | 5.2805 | 0.0001 |
| ticker_limit_50 | 50 | spark_local | 3 | 2 | 2.6892 | 0.0001 |
| ticker_limit_50 | 50 | spark_local | 3 | 4 | 2.2328 | 0.0001 |
| ticker_limit_50 | 50 | spark_local | 10 | 1 | 2.6379 | 0.0001 |

## Generated Plots

- `summary_plots/runtime_vs_ticker_limit.png`
- `summary_plots/accuracy_vs_ticker_limit.png`
- `summary_plots/f1_vs_ticker_limit.png`
- `summary_plots/cumulative_return_vs_ticker_limit.png`
- `summary_plots/sharpe_ratio_vs_ticker_limit.png`
- `summary_plots/max_drawdown_vs_ticker_limit.png`

