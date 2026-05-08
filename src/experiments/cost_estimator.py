from __future__ import annotations

import argparse

from src.utils.config_loader import load_config


def estimate_cost(hours: float, hourly_rate: float, instances: int = 1) -> float:
    return float(hours) * float(hourly_rate) * int(instances)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate simple EC2 experiment cost.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--instance", default="t3_large", choices=["t3_medium", "t3_large"])
    parser.add_argument("--hours", type=float, required=True)
    parser.add_argument("--instances", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    aws_cost = config["benchmark"]["aws_cost"]
    key = f"{args.instance}_hourly_usd"
    hourly = float(aws_cost[key])
    total = estimate_cost(args.hours, hourly, args.instances)
    print(
        f"region={aws_cost['region']} instance={args.instance} "
        f"instances={args.instances} hours={args.hours:.2f} "
        f"estimated_cost_usd={total:.4f}"
    )


if __name__ == "__main__":
    main()

